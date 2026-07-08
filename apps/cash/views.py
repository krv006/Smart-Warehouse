from django.db.models import F, Sum
from django.utils import timezone

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.cash.models import Payment
from apps.cash.serializers import (PaymentSerializer, PaymentUpdateSerializer,
                                   PaymentPaySerializer)
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
        'sale__product', 'order', 'client'
    ).prefetch_related('transactions__received_by',
                       'order__items__product')
    permission_classes  = (IsAccountantOrReadOnly,)
    filterset_fields    = ('status', 'client', 'currency', 'due_date',
                           'order', 'sale')
    search_fields       = ('sale__product__name', 'order__items__product__name',
                           'order__contract_number', 'client__company_name',
                           'comment')
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
        summary="Qo'shimcha to'lov qabul qilish (bo'lib to'lash)",
        description=(
            "Qisman to'lov qilgan mijoz keyinroq yana to'lasa — shu endpoint "
            "orqali qo'shimcha to'lov qabul qilinadi. Har bir to'lov alohida "
            "tranzaksiya bo'lib yoziladi (kim, qachon, qancha), `paid_amount` "
            "yig'ilib boradi, status avtomatik (`pending → partial → paid`).\n\n"
            "Buyurtma to'lovi bo'lsa buyurtmadagi `prepaid_amount` ham "
            "avtomatik yangilanadi.\n\n"
            "```json\n"
            "{ \"amount\": \"5000000\", \"comment\": \"Ikkinchi bo'lib to'lash\" }\n"
            "```"
        ),
        request=PaymentPaySerializer,
        tags=["Cash / Kassa"],
    )
    @action(detail=True, methods=['post'],
            permission_classes=[IsAccountantOrManagement])
    def pay(self, request, pk=None):
        payment = self.get_object()
        serializer = PaymentPaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        if payment.remaining_amount <= 0:
            return Response(
                {'detail': 'Bu to\'lov allaqachon to\'liq to\'langan.'},
                status=400,
            )
        if amount > payment.remaining_amount:
            return Response(
                {'detail': f'To\'lov qoldiqdan ({payment.remaining_amount}) '
                           f'oshib ketdi.'},
                status=400,
            )
        payment.add_payment(
            amount,
            user=request.user,
            comment=serializer.validated_data.get('comment') or 'Qo\'shimcha to\'lov',
        )
        return Response(PaymentSerializer(payment).data)

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

            # Buyurtma to'lovlari (oldindan to'lovlar) — alohida ko'rinadi
            'order_payments_count':   qs.filter(order__isnull=False).count(),
            'sum_order_total_uzs':    qs.filter(order__isnull=False,
                                                currency=Payment.UZS).aggregate(
                                          s=Sum('total_amount'))['s'] or 0,
            'sum_order_prepaid_uzs':  qs.filter(order__isnull=False,
                                                currency=Payment.UZS).aggregate(
                                          s=Sum('paid_amount'))['s'] or 0,
            'sum_order_due_uzs':      qs.filter(order__isnull=False,
                                                currency=Payment.UZS).aggregate(
                                          s=Sum(F('total_amount') - F('paid_amount')))['s'] or 0,
        }
        return Response(data)
