from django.db.models import F, Sum
from django.utils import timezone

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.cash.ledger import build_ledger_entries, ledger_totals
from apps.cash.models import ExchangeRate, ExchangeRateSettings, Payment
from apps.cash.serializers import (CashBalanceAdjustmentCreateSerializer,
                                   CashBalanceAdjustmentSerializer,
                                   CashConversionCreateSerializer, CashConversionSerializer,
                                   ExchangeRateSerializer, ExchangeRateSettingsSerializer,
                                   PaymentSerializer, PaymentOperatorSerializer,
                                   PaymentUpdateSerializer,
                                   PaymentPaySerializer)
from apps.cash.services import (ExchangeRateFetchError, get_active_rate_info,
                                get_cached_market_usd_rates, get_market_usd_rates,
                                get_today_rate, sync_today_usd_rate)
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
        if self.action in ('create',) or (
                self.action == 'rate_settings' and self.request.method == 'PATCH'):
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
        settings = ExchangeRateSettings.get_settings()
        if refresh:
            try:
                sync_today_usd_rate(force=True)
            except ExchangeRateFetchError as exc:
                fallback = ExchangeRate.get_latest(ExchangeRate.USD)
                if not fallback:
                    return Response({'detail': str(exc)}, status=503)
        else:
            auto = get_today_rate(manual=False)
            if auto is None:
                try:
                    sync_today_usd_rate()
                except ExchangeRateFetchError:
                    pass

        infinbank = get_today_rate(manual=False)
        manual = get_today_rate(manual=True)
        active_info = get_active_rate_info()
        payload = {
            'infinbank': ExchangeRateSerializer(infinbank).data if infinbank else None,
            'manual': ExchangeRateSerializer(manual).data if manual else None,
            'active_source': active_info['active_source'],
            'preferred_rate_source': settings.preferred_rate_source,
            'preferred_bank_code': settings.preferred_bank_code,
            'preferred_bank_side': settings.preferred_bank_side,
            'currency': 'USD',
            'mb_rate': str(active_info['mb_rate']),
            'source': active_info['source'],
            'rate_date': str(timezone.localdate()),
        }
        if active_info.get('active_bank_code'):
            payload['active_bank_code'] = active_info['active_bank_code']
            payload['active_bank_name'] = active_info['active_bank_name']
            payload['active_bank_side'] = active_info['active_bank_side']
        record = active_info.get('record')
        if record:
            payload.update(ExchangeRateSerializer(record).data)

        try:
            payload['market_rates'] = get_market_usd_rates(force=refresh)
        except ExchangeRateFetchError:
            payload['market_rates'] = get_cached_market_usd_rates()

        return Response(payload)

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
    # Operator faqat ko'radi (summasiz — PaymentOperatorSerializer);
    # yozish faqat Accountant/Management
    permission_classes  = (IsAccountantWithManagementRead,)
    filterset_fields    = ('status', 'client', 'currency', 'due_date',
                           'order', 'sale')
    search_fields       = ('sale__product__name', 'order__items__product__name',
                           'order__contract_number', 'zakaz__product__name',
                           'zakaz__supplier', 'client__company_name',
                           'comment')
    ordering_fields     = ('due_date', 'created_at', 'total_amount')

    def get_queryset(self):
        qs = Payment.objects.select_related(
            'sale__product', 'order', 'zakaz__product', 'client',
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
            # paid_amount — faqat tushumlar (import Payment emas)
            'sum_paid_uzs':        qs.filter(currency=Payment.UZS, zakaz__isnull=True).aggregate(
                                       s=Sum('paid_amount'))['s'] or 0,
            'sum_paid_usd':        qs.filter(currency=Payment.USD, zakaz__isnull=True).aggregate(
                                       s=Sum('paid_amount'))['s'] or 0,
            'total_commission_uzs': qs.filter(currency=Payment.UZS, zakaz__isnull=True).aggregate(
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
        data.update(ledger_totals())
        return Response(data)

    @extend_schema(
        summary="Valyuta konvertatsiyasi (UZS ↔ USD, kassa balansi)",
        description=(
            "Kassa balansi orasida UZS↔USD ko'chiradi va DBda saqlaydi. "
            "`direction`: `uzs_to_usd` yoki `usd_to_uzs`. `amount` — manba "
            "valyutadagi summa (ayiriladi), `rate` — 1 USD necha UZS "
            "ekanligi (natija shunga qarab hisoblanadi). Balans yetarli "
            "bo'lmasa 400 qaytadi.\n\n"
            "```json\n"
            "{ \"direction\": \"uzs_to_usd\", \"amount\": \"15000000\", "
            "\"rate\": \"11857.35\" }\n"
            "```"
        ),
        request=CashConversionCreateSerializer,
        tags=["Cash / Kassa"],
    )
    @action(detail=False, methods=['post'], url_path='convert',
            permission_classes=[IsAccountantOrManagement])
    def convert(self, request):
        serializer = CashConversionCreateSerializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        conversion = serializer.save()
        return Response(CashConversionSerializer(conversion).data, status=201)

    @extend_schema(
        summary="Kassa balansini qo'lda tuzatish (Management)",
        description=(
            "Kassa balansi (UZS yoki USD) qo'lda kerakli qiymatga o'zgartiriladi "
            "— joriy balansdan farqi avtomatik hisoblanadi va DBga (`CashBalanceAdjustment`) "
            "yoziladi (kim, qachon, qancha, nima uchun). `asos` MAJBURIY.\n\n"
            "```json\n"
            "{ \"currency\": \"UZS\", \"target_balance\": \"4800000000\", "
            "\"asos\": \"Inventarizatsiya natijasida farq aniqlandi\" }\n"
            "```"
        ),
        request=CashBalanceAdjustmentCreateSerializer,
        tags=["Cash / Kassa"],
    )
    @action(detail=False, methods=['post'], url_path='adjust-balance',
            permission_classes=[IsManagement])
    def adjust_balance(self, request):
        serializer = CashBalanceAdjustmentCreateSerializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        adjustment = serializer.save()
        return Response(CashBalanceAdjustmentSerializer(adjustment).data, status=201)

    @extend_schema(
        summary="Kassa harakatlari (tushum + import chiqim)",
        description=(
            'Birlashgan kassa jurnali: sotuv/buyurtma tushumlari (`in`) va '
            'import chiqimlari (`out`).'
        ),
        tags=["Cash / Kassa"],
    )
    @action(detail=False, methods=['get'], url_path='ledger',
            permission_classes=[IsAccountantWithManagementRead])
    def ledger(self, request):
        search = (request.query_params.get('search') or '').strip() or None
        source = (request.query_params.get('source') or '').strip() or None
        kind = (request.query_params.get('kind') or '').strip() or None
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(100, max(1, int(request.query_params.get('page_size', 25))))
        except (TypeError, ValueError):
            page_size = 25

        entries = build_ledger_entries(search=search, source=source, kind=kind)
        total = len(entries)
        start = (page - 1) * page_size
        return Response({
            'count': total,
            'results': entries[start:start + page_size],
        })
