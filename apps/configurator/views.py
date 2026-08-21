from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.mixins import (CreateModelMixin, ListModelMixin,
                                   RetrieveModelMixin, UpdateModelMixin,
                                   DestroyModelMixin)
from rest_framework.viewsets import GenericViewSet

from apps.common.permissions import IsFullAccessOrSales
from apps.configurator.models import ServerConfiguration
from apps.configurator.serializers import (ServerConfigurationSerializer,
                                           ServerConfigurationCreateSerializer)


@extend_schema_view(
    list=extend_schema(
        summary="Konfiguratsiyalar ro'yxati",
        description=("Sales — faqat o'zi yaratganlarini ko'radi. Admin/Operator/"
                     "Accountant — hammasini."),
        tags=["Configurator"],
    ),
    retrieve=extend_schema(summary="Konfiguratsiya (qatorlari bilan)", tags=["Configurator"]),
    create=extend_schema(
        summary="Yangi konfiguratsiya",
        description=(
            "Bazada mavjud tovarlardan server/to'plam yig'ish — umumiy narx "
            "avtomatik hisoblanadi (`total`).\n\n"
            "```json\n"
            "{\n"
            '  "name": "Mijoz X uchun server",\n'
            '  "items": [\n'
            '    { "product": 4, "quantity": 1 },\n'
            '    { "product": 9, "quantity": 2, "unit_price": "450000" }\n'
            "  ]\n"
            "}\n"
            "```"
        ),
        tags=["Configurator"],
    ),
    partial_update=extend_schema(summary="Konfiguratsiyani tahrirlash", tags=["Configurator"]),
    destroy=extend_schema(summary="Konfiguratsiyani o'chirish", tags=["Configurator"]),
)
class ServerConfigurationViewSet(CreateModelMixin, ListModelMixin, RetrieveModelMixin,
                                 UpdateModelMixin, DestroyModelMixin, GenericViewSet):
    queryset           = (ServerConfiguration.objects
                          .select_related('client', 'created_by')
                          .prefetch_related('items__product'))
    permission_classes = (IsFullAccessOrSales,)
    filterset_fields   = ('client',)
    search_fields      = ('name', 'comment')
    ordering_fields     = ('created_at', 'name')
    http_method_names  = ('get', 'post', 'patch', 'delete', 'head', 'options')

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'is_sales', False) and not (
                getattr(user, 'is_management', False)
                or getattr(user, 'is_operator', False)
                or getattr(user, 'is_accountant', False)):
            return qs.filter(created_by=user)
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return ServerConfigurationCreateSerializer
        return ServerConfigurationSerializer

    def perform_destroy(self, instance):
        user = self.request.user
        if (getattr(user, 'is_sales', False)
                and not (getattr(user, 'is_management', False) or user.is_superuser)
                and instance.created_by_id != user.id):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Faqat o'zingiz yaratgan konfiguratsiyani o'chira olasiz.")
        instance.delete()
