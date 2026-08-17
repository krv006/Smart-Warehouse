from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsManagement
from apps.expenses.models import Expense
from apps.invoices.models import ElectronicInvoice
from apps.invoices.serializers import ElectronicInvoiceSerializer


def _can_manage_prices(user):
    return getattr(user, 'is_management', False) or user.is_superuser


def _can_view_prices(user):
    return (_can_manage_prices(user)
            or getattr(user, 'is_accountant', False))


class CanManageEInvoice(BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return (_can_manage_prices(request.user)
                or getattr(request.user, 'is_operator', False))


@extend_schema_view(
    list=extend_schema(summary='Elektron fakturalar roʻyxati', tags=['E-faktura']),
    retrieve=extend_schema(summary='Elektron faktura', tags=['E-faktura']),
    create=extend_schema(summary='Yangi elektron faktura', tags=['E-faktura']),
    update=extend_schema(summary='Elektron faktura yangilash', tags=['E-faktura']),
    partial_update=extend_schema(summary='Elektron faktura qisman yangilash', tags=['E-faktura']),
    destroy=extend_schema(summary='Elektron faktura oʻchirish', tags=['E-faktura']),
)
class ElectronicInvoiceViewSet(ModelViewSet):
    queryset = ElectronicInvoice.objects.select_related('client', 'created_by').prefetch_related('lines__product')
    serializer_class = ElectronicInvoiceSerializer
    permission_classes = (CanManageEInvoice,)
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = ('document_type', 'client')
    search_fields = ('contract_number', 'name', 'client__company_name')
    ordering_fields = ('created_at', 'contract_date', 'contract_number')
    ordering = ('-created_at',)

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsManagement()]
        return super().get_permissions()

    def perform_destroy(self, instance):
        # Fakturaga bog'liq kassa chiqimi ham o'chirilsin — aks holda
        # egasiz Expense yozuvi kassada qolib ketadi.
        Expense.objects.filter(invoice=instance).delete()
        instance.delete()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['can_view_prices'] = _can_view_prices(self.request.user)
        return ctx

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if not _can_view_prices(self.request.user):
            for field in (
                    'unit_price', 'delivery_amount', 'vat_amount', 'total_amount',
                    'total_delivery', 'total_vat', 'grand_total',
            ):
                if field in serializer.fields:
                    serializer.fields.pop(field)
        return serializer
