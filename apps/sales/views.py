from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsOperatorOrReadOnly
from apps.sales.models import Sale
from apps.sales.serializers import (SaleSerializer, SaleOperatorSerializer,
                                    SaleBulkCreateSerializer)


@extend_schema_view(
    list=extend_schema(
        summary="Sotuvlar ro'yxati (Chiqim)",
        description="Filtr: `?product=1`, `?sold_date=2024-06-01`",
        tags=["Sales"],
    ),
    retrieve=extend_schema(summary="Sotuv", tags=["Sales"]),
    create=extend_schema(
        summary="Yangi sotuv — FIFO (Operator)",
        description="Ombor qoldig'i FIFO tartibida avtomatik kamayadi.",
        tags=["Sales"],
    ),
    update=extend_schema(summary="Sotuv yangilash", tags=["Sales"]),
    partial_update=extend_schema(summary="Sotuv qisman yangilash", tags=["Sales"]),
    destroy=extend_schema(summary="Sotuv o'chirish", tags=["Sales"]),
)
class SaleViewSet(ModelViewSet):
    queryset           = Sale.objects.select_related('product', 'product__category', 'client')
    serializer_class   = SaleSerializer
    permission_classes = (IsOperatorOrReadOnly,)
    filterset_fields   = ('product', 'sold_date', 'client')
    search_fields      = ('product__name', 'sold_to', 'destination', 'client__company_name')
    ordering_fields    = ('sold_date', 'sold_price', 'quantity')

    def get_serializer_class(self):
        # Operator (management/accountant emas) sotuv narxi/foydasini ko'rmaydi
        user = self.request.user
        if user.is_authenticated and (
                getattr(user, 'is_management', False)
                or getattr(user, 'is_accountant', False)):
            return SaleSerializer
        return SaleOperatorSerializer

    @extend_schema(
        summary="Bir vaqtda bir nechta mahsulot savdosi (bulk)",
        description=(
            "Bitta client/sana/manzil ostida bir nechta mahsulot sotiladi. "
            "Har biri alohida Sale yozuvi bo'ladi, ombordan FIFO tartibida ayiriladi.\n\n"
            "```json\n"
            "{\n"
            '  "client": "<uuid>",\n'
            '  "sold_to": "Aliyev Vohid",\n'
            '  "destination": "Toshkent",\n'
            '  "sold_date": "2026-07-02",\n'
            '  "items": [\n'
            '    { "product": 12, "quantity": 4, "sold_price": "3900000" },\n'
            '    { "product": 7,  "quantity": 2, "sold_price": "1200000" }\n'
            "  ]\n"
            "}\n"
            "```"
        ),
        request=SaleBulkCreateSerializer,
        tags=["Sales"],
    )
    @action(detail=False, methods=['post'])
    def bulk(self, request):
        serializer = SaleBulkCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        sales = serializer.save()
        return Response(
            SaleBulkCreateSerializer().to_representation(sales),
            status=201,
        )
