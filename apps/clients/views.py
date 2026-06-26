from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.viewsets import ModelViewSet

from apps.clients.models import Client
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
    search_fields      = ('company_name', 'email')
    filterset_fields   = ('is_active',)
    ordering_fields    = ('company_name', 'created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return ClientListSerializer
        return ClientSerializer
