from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsOperatorOrReadOnly
from apps.sales.models import Sale
from apps.sales.serializers import SaleSerializer


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
