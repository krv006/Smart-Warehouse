from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.mixins import (CreateModelMixin, ListModelMixin,
                                   RetrieveModelMixin, UpdateModelMixin)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.common.permissions import IsOperatorOrReadOnly
from apps.orders.models import Order, Zakaz, allocate_pending_orders
from apps.orders.serializers import (OrderSerializer, ZakazSerializer,
                                     OrderBulkCreateSerializer,
                                     ZakazBulkCreateSerializer)


# ── Order (Bron) ──────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary="Buyurtmalar / Bron ro'yxati",
        description=(
            "Filtr: `?status=pending|partial|reserved|fulfilled|cancelled`, "
            "`?product=1`, `?client=<uuid>`"
        ),
        tags=["Orders / Bron"],
    ),
    retrieve=extend_schema(summary="Buyurtma", tags=["Orders / Bron"]),
    create=extend_schema(
        summary="Yangi buyurtma (Operator / Manager)",
        description=(
            "Mavjud bron bo'lmagan qoldiqdan bron ajratiladi.\n\n"
            "- `available_quantity > 0` → bron + backorder (partial/pending)\n"
            "- `available_quantity == 0` → **xato**: mahsulot tugagan, Zakaz bering.\n\n"
            "Yangi qoldiq kelganida pending/partial buyurtmalar **avtomatik** bronlanadi."
        ),
        tags=["Orders / Bron"],
    ),
    partial_update=extend_schema(
        summary="Buyurtma yangilash (due_date, comment)",
        tags=["Orders / Bron"],
    ),
)
class OrderViewSet(CreateModelMixin, ListModelMixin,
                   RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    """
    Buyurtma / Bron.
    O'chirish yo'q — buning o'rniga /cancel/ action ishlatiladi.
    Faqat PATCH (due_date, comment o'zgartirish uchun).
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
        summary="Bir vaqtda bir nechta mahsulot buyurtmasi (bulk)",
        description=(
            "Bitta client/due_date ostida bir nechta mahsulot buyurtma qilinadi. "
            "Har biri alohida Order yozuvi bo'ladi, har biriga bron ajratiladi.\n\n"
            "```json\n"
            "{\n"
            '  "client": "<uuid>",\n'
            '  "due_date": "2026-08-01",\n'
            '  "items": [\n'
            '    { "product": 12, "quantity": 4, "unit_price": "3900000" },\n'
            '    { "product": 7,  "quantity": 2, "unit_price": "1200000" }\n'
            "  ]\n"
            "}\n"
            "```"
        ),
        request=OrderBulkCreateSerializer,
        tags=["Orders / Bron"],
    )
    @action(detail=False, methods=['post'])
    def bulk(self, request):
        serializer = OrderBulkCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        orders = serializer.save()
        return Response(
            OrderBulkCreateSerializer().to_representation(orders),
            status=201,
        )

    @extend_schema(
        summary="Buyurtmani yetkazildi deb belgilash",
        description=(
            "Bron qilingan miqdor ombor qoldiqidan ayiriladi. "
            "Boshqa pending buyurtmalarga avtomatik bron qayta ajratiladi."
        ),
        tags=["Orders / Bron"],
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def fulfill(self, request, pk=None):
        order = self.get_object()
        if order.status == Order.FULFILLED:
            return Response(
                {'detail': 'Buyurtma allaqachon yetkazilgan.'},
                status=400,
            )
        if order.status == Order.CANCELLED:
            return Response(
                {'detail': 'Bekor qilingan buyurtmani yetkazib bo\'lmaydi.'},
                status=400,
            )
        if order.reserved_qty == 0:
            return Response(
                {'detail': 'Bron qilingan miqdor yo\'q. Avval omborda qoldiq bo\'lishi kerak.'},
                status=400,
            )
        order.fulfill()
        return Response(OrderSerializer(order).data)

    @extend_schema(
        summary="Buyurtmani bekor qilish (bron bo'shatiladi)",
        description="Bron bo'shatiladi va boshqa pending buyurtmalarga ajratiladi.",
        tags=["Orders / Bron"],
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status in (Order.FULFILLED, Order.CANCELLED):
            return Response(
                {'detail': f'"{order.get_status_display()}" holatidagi buyurtmani bekor qilib bo\'lmaydi.'},
                status=400,
            )
        order.release()
        order.status = Order.CANCELLED
        order.save(update_fields=['reserved_qty', 'status'])
        allocate_pending_orders(order.product)
        return Response(OrderSerializer(order).data)


# ── Zakaz (Etkazuvchidan buyurtma) ────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary="Zakazlar ro'yxati",
        description=(
            "Filtr: `?status=new|confirmed|ordered|received|cancelled`, `?product=1`\n\n"
            "Operator yaratadi. Status faqat Manager tomonidan o'zgartiriladi."
        ),
        tags=["Zakaz"],
    ),
    retrieve=extend_schema(summary="Zakaz", tags=["Zakaz"]),
    create=extend_schema(
        summary="Yangi zakaz (Operator / Manager)",
        description=(
            "Status avtomatik `new` qilib saqlanadi.\n\n"
            "Odatda mahsulot `available_quantity == 0` bo'lganda zakaz beriladi.\n\n"
            "`received_qty` va status o'zgartirish faqat Manager uchun (PATCH orqali)."
        ),
        tags=["Zakaz"],
    ),
    partial_update=extend_schema(
        summary="Zakaz yangilash — status, received_qty (faqat Manager)",
        description=(
            "**Operator:** faqat `supplier`, `expected_date`, `comment`, "
            "`warehouse_location` o'zgartira oladi.\n\n"
            "**Manager:** `status` va `received_qty` ham o'zgartira oladi.\n\n"
            "Status `received` ga o'tganda `received_qty` ombor qoldig'iga qo'shiladi "
            "va pending buyurtmalarga avtomatik bron ajratiladi."
        ),
        tags=["Zakaz"],
    ),
)
class ZakazViewSet(CreateModelMixin, ListModelMixin,
                   RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    """
    Zakaz (procurement order).
    Operator: yaratadi + supplier/comment/expected_date o'zgartiradi.
    Manager: status + received_qty o'zgartiradi.
    O'chirish: admin panel orqali.
    """
    queryset           = Zakaz.objects.select_related('product', 'created_by')
    serializer_class   = ZakazSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields   = {
        'status':  ['exact'],
        'product': ['exact'],
    }
    search_fields      = ('product__name', 'product__serial_number',
                          'supplier', 'comment')
    ordering_fields    = ('expected_date', 'created_at', 'status')
    http_method_names  = ('get', 'post', 'patch', 'head', 'options')

    @extend_schema(
        summary="Bir vaqtda bir nechta mahsulot uchun zakaz (bulk)",
        description=(
            "Bir nechta mahsulotni birdan zakaz qilish (masalan buyurtmada "
            "yetishmagan bir necha mahsulot uchun). Har biri alohida Zakaz "
            "(status=new). Faol zakazi bor mahsulot rad etiladi.\n\n"
            "```json\n"
            "{\n"
            '  "supplier": "Xitoy, Guangzhou",\n'
            '  "expected_date": "2026-08-15",\n'
            '  "items": [\n'
            '    { "product": 12, "quantity": 7 },\n'
            '    { "product": 7,  "quantity": 5 }\n'
            "  ]\n"
            "}\n"
            "```"
        ),
        request=ZakazBulkCreateSerializer,
        tags=["Zakaz"],
    )
    @action(detail=False, methods=['post'])
    def bulk(self, request):
        serializer = ZakazBulkCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        zakazlar = serializer.save()
        return Response(
            ZakazBulkCreateSerializer().to_representation(zakazlar),
            status=201,
        )
