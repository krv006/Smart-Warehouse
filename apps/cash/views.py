from django.db.models import Sum
from django.utils import timezone

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.cash.models import Payment
from apps.cash.serializers import PaymentSerializer, PaymentUpdateSerializer
from apps.common.permissions import IsAccountantOrManagement, IsAccountantOrReadOnly


@extend_schema_view(
    list=extend_schema(
        summary="Toʻlovlar roʻyxati",
        description="Filtr: `?status=pending`, `?status=overdue`, `?client=1`, `?currency=UZS`",
        tags=["Cash / Kassa"],
    ),
    retrieve=extend_schema(summary="Toʻlov", tags=["Cash / Kassa"]),
    create=extend_schema(summary="Yangi toʻlov (Accountant)", tags=["Cash / Kassa"]),
    update=extend_schema(summary="Toʻlov yangilash", tags=["Cash / Kassa"]),
    partial_update=extend_schema(summary="Qisman yangilash", tags=["Cash / Kassa"]),
    destroy=extend_schema(summary="Toʻlov oʻchirish (Management)", tags=["Cash / Kassa"]),
)
class PaymentViewSet(ModelViewSet):
    queryset = Payment.objects.select_related(
        'sale__product', 'client'
    )
    permission_classes  = (IsAccountantOrReadOnly,)
    filterset_fields    = ('status', 'client', 'currency', 'due_date')
    search_fields       = ('sale__product__name', 'client__company_name', 'comment')
    ordering_fields     = ('due_date', 'created_at', 'total_amount')

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return PaymentUpdateSerializer
        return PaymentSerializer

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAccountantOrManagement()]
        return super().get_permissions()

    @extend_schema(
        summary="Kassa xulosasi (Management)",
        tags=["Cash / Kassa"],
    )
    @action(detail=False, methods=['get'], url_path='summary',
            permission_classes=[IsAccountantOrManagement])
    def summary(self, request):
        qs     = self.get_queryset()
        today  = timezone.now().date()

        overdue_qs = qs.filter(
            status__in=(Payment.PENDING, Payment.PARTIAL, Payment.OVERDUE),
            due_date__lt=today,
        )

        data = {
            'total_pending':       qs.filter(status=Payment.PENDING).count(),
            'total_partial':       qs.filter(status=Payment.PARTIAL).count(),
            'total_paid':          qs.filter(status=Payment.PAID).count(),
            'total_overdue':       overdue_qs.count(),
            'sum_paid_uzs':        qs.filter(status=Payment.PAID,
                                              currency=Payment.UZS).aggregate(
                                       s=Sum('paid_amount'))['s'] or 0,
            'sum_paid_usd':        qs.filter(status=Payment.PAID,
                                              currency=Payment.USD).aggregate(
                                       s=Sum('paid_amount'))['s'] or 0,
            'total_commission_uzs': qs.filter(currency=Payment.UZS).aggregate(
                                        s=Sum('commission'))['s'] or 0,
        }
        return Response(data)
