from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.mixins import (CreateModelMixin, ListModelMixin,
                                   RetrieveModelMixin, UpdateModelMixin)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.common.permissions import IsOperatorOrReadOnly
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Buyurtmalar / Bron ro'yxati",
        description="Filtr: `?status=pending`, `?status=reserved`, `?product=1`, `?client=<uuid>`",
        tags=["Orders / Bron"],
    ),
    retrieve=extend_schema(summary="Buyurtma", tags=["Orders / Bron"]),
    create=extend_schema(
        summary="Yangi buyurtma (Operator/Management)",
        description=(
            "Mavjud qoldiqdan bron ajratiladi. Yetarli qoldiq bo'lmasa — "
            "`status=pending` yoki `partial` holida saqlanadi. "
            "Yangi kirim kelganda avtomatik bron qilinadi."
        ),
        tags=["Orders / Bron"],
    ),
    partial_update=extend_schema(
        summary="Buyurtma yangilash (faqat due_date, comment)",
        tags=["Orders / Bron"],
    ),
)
class OrderViewSet(CreateModelMixin, ListModelMixin,
                   RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    """
    Buyurtmalar. O'chirish yo'q — o'rniga /cancel/ action ishlatiladi.
    To'liq PUT ham yo'q — faqat PATCH (due_date, comment).
    """
    queryset           = Order.objects.select_related('product', 'client')
    serializer_class   = OrderSerializer
    permission_classes = (IsOperatorOrReadOnly,)
    filterset_fields   = ('status', 'product', 'client')
    search_fields      = ('product__name', 'product__serial_number',
                          'client__company_name', 'comment')
    ordering_fields    = ('due_date', 'created_at', 'status')
    http_method_names  = ('get', 'post', 'patch', 'head', 'options')

    @extend_schema(
        summary="Buyurtmani yetkazildi deb belgilash",
        description=(
            "Bron qilingan miqdor ombor qoldiqidan ayiriladi. "
            "Pending orderlar avtomatik qayta ajratiladi."
        ),
        tags=["Orders / Bron"],
    )
    @action(detail=True, methods=['post'],
            permission_classes=[IsAuthenticated])
    def fulfill(self, request, pk=None):
        order = self.get_object()
        if order.status == Order.FULFILLED:
            return Response({'detail': 'Buyurtma allaqachon yetkazilgan.'}, status=400)
        if order.status == Order.CANCELLED:
            return Response({'detail': 'Bekor qilingan buyurtmani yetkazib bo\'lmaydi.'}, status=400)
        order.fulfill()
        return Response(OrderSerializer(order).data)

    @extend_schema(
        summary="Buyurtmani bekor qilish (bron bo'shatiladi)",
        tags=["Orders / Bron"],
    )
    @action(detail=True, methods=['post'],
            permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status in (Order.FULFILLED, Order.CANCELLED):
            return Response({'detail': f'Status: {order.status} — o\'zgartirib bo\'lmaydi.'}, status=400)
        order.release()
        order.status = Order.CANCELLED
        order.save(update_fields=['reserved_qty', 'status'])

        # Boshqa pending orderlarga bo'shatilgan bron ajratilishi mumkin
        from apps.orders.models import allocate_pending_orders
        allocate_pending_orders(order.product)

        return Response(OrderSerializer(order).data)
