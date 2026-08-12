from drf_spectacular.utils import extend_schema, extend_schema_view
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.viewsets import ModelViewSet

from apps.clients.filters import ClientSearchFilter
from apps.clients.models import Client
from apps.common.querysets import apply_date_range
from apps.clients.serializers import ClientSerializer, ClientListSerializer
from apps.common.permissions import CanViewClients


@extend_schema_view(
    list=extend_schema(
        summary="Mijozlar roʻyxati (maxsus ruxsat)",
        tags=["Clients"],
    ),
    retrieve=extend_schema(summary="Mijoz", tags=["Clients"]),
    create=extend_schema(summary="Yangi mijoz", tags=["Clients"]),
    update=extend_schema(summary="Mijoz yangilash", tags=["Clients"]),
    partial_update=extend_schema(summary="Qisman yangilash", tags=["Clients"]),
    destroy=extend_schema(summary="Mijoz oʻchirish", tags=["Clients"]),
)
class ClientViewSet(ModelViewSet):
    queryset           = Client.objects.all()
    permission_classes = (CanViewClients,)
    filter_backends    = (DjangoFilterBackend, ClientSearchFilter, OrderingFilter)
    filterset_fields   = ('is_active',)
    ordering_fields    = ('company_name', 'created_at', 'is_active')

    def get_queryset(self):
        return apply_date_range(super().get_queryset(), self.request)

    def get_serializer_class(self):
        if self.action == 'list':
            return ClientListSerializer
        return ClientSerializer
