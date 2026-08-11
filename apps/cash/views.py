from django.db.models import F, Sum
from django.utils import timezone

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.cash.models import ExchangeRate, ExchangeRateSettings, Payment
from apps.cash.serializers import (ExchangeRateSerializer, ExchangeRateSettingsSerializer,
                                   PaymentSerializer, PaymentOperatorSerializer,
                                   PaymentUpdateSerializer,
                                   PaymentPaySerializer)
from apps.cash.services import ExchangeRateFetchError, sync_today_usd_rate
from apps.common.permissions import (IsAccountantOrManagement,
                                     IsAccountantWithManagementRead,
                                     IsManagement)


@extend_schema_view(
    list=extend_schema(summary="Valyuta kurslari", tags=["Cash / Kassa"]),
    retrieve=extend_schema(summary="Valyuta kursi", tags=["Cash / Kassa"]),
    create=extend_schema(summary="Valyuta kursini saqlash", tags=["Cash / Kassa"]),
)
class ExchangeRateViewSet(ModelViewSet):
    queryset = ExchangeRate.objects.all()
    serializer_class = ExchangeRateSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('currency', 'manual_override', 'rate_date')
    ordering_fields = ('rate_date', 'created_at', 'mb_rate')
    http_method_names = ('get', 'post', 'patch', 'head', 'options')

    def get_queryset(self):
        return ExchangeRate.objects.order_by('-rate_date', '-created_at')

    def get_permissions(self):
        if self.action == 'rate_settings' and self.request.method == 'PATCH':
            return [IsManagement()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(
            currency=ExchangeRate.USD,
            buy_rate=serializer.validated_data.get('buy_rate') or serializer.validated_data['mb_rate'],
            sell_rate=serializer.validated_data.get('sell_rate') or serializer.validated_data['mb_rate'],
            rate_date=timezone.localdate(),
            source='manual',
            manual_override=True,
        )

    @action(detail=False, methods=['get'], url_path='latest')
    def latest(self, request):
        refresh = request.query_params.get('refresh', '').lower() in {'1', 'true', 'yes'}
        today = timezone.localdate()
        rate = (
            ExchangeRate.objects
            .filter(currency=ExchangeRate.USD, rate_date=today)
            .order_by('-manual_override', '-created_at')
            .first()
        )
        if refresh or rate is None:
            try:
                rate, _ = sync_today_usd_rate(force=refresh)
            except ExchangeRateFetchError as exc:
                fallback = ExchangeRate.get_latest(ExchangeRate.USD)
                if fallback:
                    serializer = ExchangeRateSerializer(fallback)
                    return Response(serializer.data)
                return Response({'detail': str(exc)}, status=503)
        serializer = ExchangeRateSerializer(rate)
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'patch'], url_path='settings')
    def rate_settings(self, request):
        obj = ExchangeRateSettings.get_settings()
        if request.method == 'PATCH':
            serializer = ExchangeRateSettingsSerializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(ExchangeRateSettingsSerializer(obj).data)


@extend_schema_view(
    list=extend_schema(
        summary="Toʻlovlar roʻyxati",
        description=(
            "Standart roʻyxat faqat faol to‘lovlarni qaytaradi "
            "(kutilmoqda, qisman, kechikkan). To‘liq to‘langanlar "
            "ko‘rinmaydi. Filtr: `?status=paid`, `?include_paid=true`, "
            "`?status=overdue`, `?client=1`, `?currency=UZS`"
        ),
        tags=["Cash / Kassa"],
    ),
    retrieve=extend_schema(summary="Toʻlov", tags=["Cash / Kassa"]),
    create=extend_schema(summary="Yangi toʻlov (Accountant)", tags=["Cash / Kassa"]),
    update=extend_schema(summary="Toʻlov yangilash", tags=["Cash / Kassa"]),
    partial_update=extend_schema(summary="Qisman yangilash", tags=["Cash / Kassa"]),
    destroy=extend_schema(summary="Toʻlov oʻchirish (Management)", tags=["Cash / Kassa"]),
)
class PaymentViewSet(ModelViewSet):
    queryset = Payment.objects.all()
    # Operator kirolmaydi — to'lovlarda narx/summa/komissiya bor
    permission_classes  = (IsAccountantWithManagementRead,)
    filterset_fields    = ('status', 'client', 'currency', 'due_date',
                           'order', 'sale')
    search_fields       = ('sale__product__name', 'order__items__product__name',
                           'order__contract_number', 'client__company_name',
                           'comment')
    ordering_fields     = ('due_date', 'created_at', 'total_amount')

    def get_queryset(self):
        qs = Payment.objects.select_related(
            'sale__product', 'order', 'client',
        ).prefetch_related(
            'transactions__received_by',
            'order__items__product',
        )
        if self.action == 'list':
            include_paid = self.request.query_params.get(
                'include_paid', '',
            ).lower() in {'1', 'true', 'yes'}
            status = self.request.query_params.get('status')
            if not include_paid and not status:
                qs = qs.exclude(status=Payment.PAID)
        return qs

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return PaymentUpdateSerializer
        user = self.request.user
        if user.is_authenticated and getattr(user, 'is_operator', False) and not (
                getattr(user, 'is_management', False)
                or getattr(user, 'is_accountant', False)):
            return PaymentOperatorSerializer
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
        try:
            # add_payment qatorni qulflab qoldiqni qayta tekshiradi —
            # parallel to'lovlar total'dan oshira olmaydi
            payment.add_payment(
                amount,
                user=request.user,
                comment=serializer.validated_data.get('comment') or 'Qo\'shimcha to\'lov',
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        ser_class = self.get_serializer_class()
        return Response(ser_class(payment, context={'request': request}).data)

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
            # paid_amount — real olingan pul; PARTIAL to'lovlarning
            # qismi ham kassaga kirgan, shuning uchun status filtrsiz
            'sum_paid_uzs':        qs.filter(currency=Payment.UZS).aggregate(
                                       s=Sum('paid_amount'))['s'] or 0,
            'sum_paid_usd':        qs.filter(currency=Payment.USD).aggregate(
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
