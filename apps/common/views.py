from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from apps.common.approval import PendingChange
from apps.common.company import CompanyProfile
from apps.common.permissions import IsManagement
from apps.common.serializers import CompanyProfileSerializer, PendingChangeSerializer


class CompanyProfileView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == 'PATCH':
            return [IsManagement()]
        return super().get_permissions()

    def get(self, request):
        profile = CompanyProfile.get_profile()
        return Response(CompanyProfileSerializer(profile).data)

    def patch(self, request):
        profile = CompanyProfile.get_profile()
        serializer = CompanyProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="Tasdiqlash kutilayotgan o'zgarishlar (Buxgalter)",
        description=(
            "Management/superuser — hammasini ko'radi. Buxgalter — faqat "
            "o'zi so'ragan o'zgarishlarni. Filtr: `?status=pending|approved|rejected`"
        ),
        tags=["Tasdiqlash (Buxgalter)"],
    ),
    retrieve=extend_schema(summary="Bitta o'zgarish", tags=["Tasdiqlash (Buxgalter)"]),
)
class PendingChangeViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    """Buxgalter kiritgan/tahrirlagan yozuvlar — Admin tasdig'ini kutadi."""
    queryset           = PendingChange.objects.select_related('requested_by', 'reviewed_by')
    serializer_class   = PendingChangeSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields   = ('status', 'kind')
    ordering_fields    = ('created_at',)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'is_management', False):
            return qs
        return qs.filter(requested_by=user)

    @extend_schema(summary="Tasdiqlash (Management)", tags=["Tasdiqlash (Buxgalter)"])
    @action(detail=True, methods=['post'], permission_classes=[IsManagement])
    def approve(self, request, pk=None):
        pending = self.get_object()
        if pending.status != PendingChange.PENDING:
            raise ValidationError({'detail': "Bu o'zgarish allaqachon ko'rib chiqilgan."})
        try:
            pending.approve(request.user)
        except Exception as exc:
            pending.error = str(exc)
            pending.save(update_fields=['error'])
            raise ValidationError({'detail': f"Tasdiqlashda xatolik: {exc}"})
        return Response(PendingChangeSerializer(pending).data)

    @extend_schema(summary="Rad etish (Management)", tags=["Tasdiqlash (Buxgalter)"])
    @action(detail=True, methods=['post'], permission_classes=[IsManagement])
    def reject(self, request, pk=None):
        pending = self.get_object()
        if pending.status != PendingChange.PENDING:
            raise ValidationError({'detail': "Bu o'zgarish allaqachon ko'rib chiqilgan."})
        note = (request.data.get('review_note') or '').strip()
        if not note:
            raise ValidationError({'review_note': 'Rad etish sababi (izoh) kiritilishi shart.'})
        pending.reject(request.user, note=note)
        return Response(PendingChangeSerializer(pending).data)
