from decimal import Decimal
from calendar import monthrange
from datetime import date

from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count, Q
from django.utils import timezone

from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cash.ledger import build_ledger_entries
from apps.cash.models import Payment, ExchangeRate, PaymentTransaction
from apps.cash.services import get_active_mb_rate
from apps.common.permissions import IsAccountantOrManagement
from apps.expenses.models import Expense
from apps.orders.models import Zakaz
from apps.reports.excel import (export_sales, export_stock,
                                 export_expenses, export_payments,
                                 export_kassa_ledger, export_imports)
from apps.sales.models import Sale
from apps.warehouse.models import Stock, Product

UZ_MONTHS = (
    '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
    'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
)


def _usd_to_uzs(amount, mb_rate):
    if not amount:
        return Decimal('0')
    if not mb_rate:
        return Decimal('0')
    return Decimal(amount) * Decimal(mb_rate)


def _parse_period(request):
    date_from = request.query_params.get('date_from') or None
    date_to = request.query_params.get('date_to') or None
    return date_from, date_to


def _parse_currency(request):
    currency = (request.query_params.get('currency') or '').upper()
    if currency in ('UZS', 'USD'):
        return currency
    return None


def _parse_int_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_dashboard_filters(request):
    category_id = _parse_int_param(request, 'category')
    client_id = _parse_int_param(request, 'client')
    product_id = _parse_int_param(request, 'product')
    supplier = (request.query_params.get('supplier') or '').strip() or None
    payment_status = (request.query_params.get('payment_status') or '').lower()
    if payment_status not in (Payment.PENDING, Payment.PARTIAL, Payment.PAID, Payment.OVERDUE):
        payment_status = None
    return category_id, client_id, product_id, supplier, payment_status


def _filter_payments(qs, client_id=None, payment_status=None):
    if client_id:
        qs = qs.filter(client_id=client_id)
    if payment_status:
        today = timezone.now().date()
        if payment_status == Payment.OVERDUE:
            qs = qs.filter(
                status__in=(Payment.PENDING, Payment.PARTIAL, Payment.OVERDUE),
                due_date__lt=today,
            )
        else:
            qs = qs.filter(status=payment_status)
    return qs


def _sales_revenue(date_from=None, date_to=None, category_id=None,
                   product_id=None, client_id=None, **_):
    qs = Sale.objects.all()
    if date_from:
        qs = qs.filter(sold_date__gte=date_from)
    if date_to:
        qs = qs.filter(sold_date__lte=date_to)
    if category_id:
        qs = qs.filter(product__category_id=category_id)
    if product_id:
        qs = qs.filter(product_id=product_id)
    if client_id:
        qs = qs.filter(client_id=client_id)
    return qs.aggregate(
        total=Sum(ExpressionWrapper(
            F('sold_price') * F('quantity'),
            output_field=DecimalField(),
        ))
    )['total'] or Decimal('0')


def _kassa_collected(date_from=None, date_to=None, currency=None,
                     client_id=None, payment_status=None, **_):
    qs = PaymentTransaction.objects.filter(payment__zakaz__isnull=True)
    if currency:
        qs = qs.filter(payment__currency=currency)
    if client_id:
        qs = qs.filter(payment__client_id=client_id)
    if payment_status:
        today = timezone.now().date()
        if payment_status == Payment.OVERDUE:
            qs = qs.filter(
                payment__status__in=(Payment.PENDING, Payment.PARTIAL, Payment.OVERDUE),
                payment__due_date__lt=today,
            )
        else:
            qs = qs.filter(payment__status=payment_status)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')


def _ledger_in_uzs(date_from=None, date_to=None):
    """Kassa jurnalidagi tushumlar — import PaymentTransaction emas."""
    entries = build_ledger_entries(date_from=date_from, date_to=date_to, kind='in')
    return sum(
        (Decimal(e['amount']) for e in entries if e.get('currency') == Payment.UZS),
        Decimal('0'),
    )


def _ledger_out_uzs(date_from=None, date_to=None):
    """Kassa jurnalidagi import chiqimlari (Expense)."""
    entries = build_ledger_entries(date_from=date_from, date_to=date_to, kind='out')
    return sum(
        (Decimal(e['amount']) for e in entries if e.get('currency') == Payment.UZS),
        Decimal('0'),
    )


def _import_paid_totals(date_from=None, date_to=None, currency=None,
                        category_id=None, product_id=None, supplier=None, **_):
    """Import bo'yicha kassadan chiqqan summalar (Expense, zakaz bog'langan)."""
    rate = get_active_mb_rate()

    qs = Expense.objects.filter(zakaz__isnull=False).select_related('zakaz__product')
    if category_id:
        qs = qs.filter(zakaz__product__category_id=category_id)
    if product_id:
        qs = qs.filter(zakaz__product_id=product_id)
    if supplier:
        qs = qs.filter(zakaz__supplier__icontains=supplier)
    if currency:
        qs = qs.filter(currency=currency)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    total_uzs = Decimal('0')
    total_usd = Decimal('0')
    for expense in qs:
        if expense.currency == Zakaz.USD:
            total_usd += expense.amount
            if currency != Zakaz.USD:
                total_uzs += _usd_to_uzs(expense.amount, rate)
        else:
            total_uzs += expense.amount

    return total_uzs, total_usd, rate


def _shift_month(year, month, delta):
    idx = (year * 12 + (month - 1)) + delta
    return idx // 12, (idx % 12) + 1


def _month_bounds(year, month):
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _month_label(year, month):
    return f'{UZ_MONTHS[month]} {year}'


class SalesExportView(APIView):
    # Sotuv narxi/summasi bor — operator ko'rmasligi kerak
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Sotuvlar — Excel yuklash",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to',   str, description='YYYY-MM-DD'),
        ],
        tags=["Reports / Excel"],
    )
    def get(self, request):
        qs = Sale.objects.select_related('product__category').order_by('-sold_date')
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(sold_date__gte=date_from)
        if date_to:
            qs = qs.filter(sold_date__lte=date_to)
        return export_sales(qs, date_from=date_from, date_to=date_to)


class StockExportView(APIView):
    # Kelish narxi (purchase_price) bor — operator ko'rmasligi kerak
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(summary="Ombor holati — Excel yuklash", tags=["Reports / Excel"])
    def get(self, request):
        qs = Stock.objects.select_related('product__category').filter(quantity__gt=0)
        return export_stock(qs)


class ExpensesExportView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Rasxodlar — Excel yuklash",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to',   str, description='YYYY-MM-DD'),
        ],
        tags=["Reports / Excel"],
    )
    def get(self, request):
        qs = Expense.objects.select_related(
            'expense_type', 'sub_type', 'responsible'
        ).order_by('-date')
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return export_expenses(qs, date_from=date_from, date_to=date_to)


class PaymentsExportView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Kassa — Excel yuklash (tushum + import chiqim)",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to',   str, description='YYYY-MM-DD'),
        ],
        tags=["Reports / Excel"],
    )
    def get(self, request):
        date_from, date_to = _parse_period(request)
        return export_kassa_ledger(date_from=date_from, date_to=date_to)


class ImportsExportView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Import (zakaz) — Excel yuklash",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to',   str, description='YYYY-MM-DD'),
        ],
        tags=["Reports / Excel"],
    )
    def get(self, request):
        from apps.orders.models import Zakaz
        qs = Zakaz.objects.filter(zakaz_type=Zakaz.MANUAL).select_related(
            'product',
        ).order_by('-created_at')
        date_from, date_to = _parse_period(request)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return export_imports(qs, date_from=date_from, date_to=date_to)


class FinancialSummaryView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Moliyaviy xulosa (Management / Accountant)",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD (ixtiyoriy)'),
            OpenApiParameter('date_to', str, description='YYYY-MM-DD (ixtiyoriy)'),
            OpenApiParameter('currency', str, description='UZS yoki USD (ixtiyoriy)'),
            OpenApiParameter('category', int, description='Kategoriya ID (ixtiyoriy)'),
            OpenApiParameter('client', int, description='Mijoz ID (ixtiyoriy)'),
            OpenApiParameter('supplier', str, description='Yetkazuvchi (qisman mos)'),
            OpenApiParameter('product', int, description='Mahsulot ID (ixtiyoriy)'),
            OpenApiParameter('payment_status', str,
                             description='pending|partial|paid|overdue (ixtiyoriy)'),
        ],
        tags=["Reports / Summary"],
    )
    def get(self, request):
        today = timezone.now().date()
        date_from, date_to = _parse_period(request)
        currency = _parse_currency(request)
        category_id, client_id, product_id, supplier, payment_status = (
            _parse_dashboard_filters(request)
        )
        filtered = bool(
            date_from or date_to or currency or category_id or client_id
            or product_id or supplier or payment_status
        )
        dash_kw = dict(
            category_id=category_id,
            product_id=product_id,
            client_id=client_id,
            supplier=supplier,
        )
        kassa_kw = dict(client_id=client_id, payment_status=payment_status)

        mb_rate = get_active_mb_rate()

        sales_all = _sales_revenue(**dash_kw)
        kassa_all_uzs = _kassa_collected(currency=Payment.UZS, **kassa_kw)
        kassa_all_usd = _kassa_collected(currency=Payment.USD, **kassa_kw)
        kassa_today_uzs = _kassa_collected(today, today, Payment.UZS, **kassa_kw)
        kassa_today_usd = _kassa_collected(today, today, Payment.USD, **kassa_kw)
        import_today_uzs, import_today_usd, _ = _import_paid_totals(
            today, today, **dash_kw,
        )

        ledger_from = date_from if filtered else None
        ledger_to = date_to if filtered else None
        ledger_out_uzs = _ledger_out_uzs(ledger_from, ledger_to)

        if filtered:
            sales_period = _sales_revenue(date_from, date_to, **dash_kw)
            if currency == Payment.USD:
                kassa_period_uzs = Decimal('0')
                kassa_period_usd = _kassa_collected(
                    date_from, date_to, Payment.USD, **kassa_kw,
                )
            elif currency == Payment.UZS:
                kassa_period_uzs = _kassa_collected(
                    date_from, date_to, Payment.UZS, **kassa_kw,
                )
                kassa_period_usd = Decimal('0')
            else:
                kassa_period_uzs = _kassa_collected(
                    date_from, date_to, Payment.UZS, **kassa_kw,
                )
                kassa_period_usd = _kassa_collected(
                    date_from, date_to, Payment.USD, **kassa_kw,
                )
            import_period_uzs, import_period_usd, _ = _import_paid_totals(
                date_from, date_to, currency, **dash_kw,
            )
        else:
            sales_period = sales_all
            kassa_period_uzs = kassa_all_uzs
            kassa_period_usd = kassa_all_usd
            import_period_uzs, import_period_usd, _ = _import_paid_totals()

        # Kassa jurnali bilan bir xil: tushum faqat sotuv/buyurtma, import — chiqim
        if not client_id and not payment_status:
            if currency in (None, '', Payment.UZS):
                kassa_period_uzs = _ledger_in_uzs(ledger_from, ledger_to)
                import_period_uzs = ledger_out_uzs
            if currency == Payment.USD:
                kassa_period_usd = _kassa_collected(
                    ledger_from, ledger_to, Payment.USD, **kassa_kw,
                )

        net_balance_uzs = kassa_period_uzs - (
            import_period_uzs if currency != Payment.USD else Decimal('0')
        )
        net_balance_usd = kassa_period_usd - (import_period_usd or Decimal('0'))

        overdue_qs = _filter_payments(
            Payment.objects.filter(
                status__in=(Payment.PENDING, Payment.PARTIAL, Payment.OVERDUE),
                due_date__lt=today,
            ),
            client_id,
            payment_status,
        )
        overdue_count = overdue_qs.count()

        commission_qs = Payment.objects.filter(status=Payment.PAID, currency=Payment.UZS)
        commission_qs = _filter_payments(commission_qs, client_id, payment_status)
        if date_from or date_to:
            txn_qs = PaymentTransaction.objects.all()
            if date_from:
                txn_qs = txn_qs.filter(created_at__date__gte=date_from)
            if date_to:
                txn_qs = txn_qs.filter(created_at__date__lte=date_to)
            if client_id:
                txn_qs = txn_qs.filter(payment__client_id=client_id)
            if payment_status:
                today = timezone.now().date()
                if payment_status == Payment.OVERDUE:
                    txn_qs = txn_qs.filter(
                        payment__status__in=(
                            Payment.PENDING, Payment.PARTIAL, Payment.OVERDUE,
                        ),
                        payment__due_date__lt=today,
                    )
                else:
                    txn_qs = txn_qs.filter(payment__status=payment_status)
            payment_ids = txn_qs.values_list('payment_id', flat=True).distinct()
            commission_qs = commission_qs.filter(pk__in=payment_ids)
        commission_total = commission_qs.aggregate(
            total=Sum('commission'),
        )['total'] or Decimal('0')

        expenses_uzs = Expense.objects.filter(currency='UZS')
        expenses_usd = Expense.objects.filter(currency='USD')
        if date_from:
            expenses_uzs = expenses_uzs.filter(date__gte=date_from)
            expenses_usd = expenses_usd.filter(date__gte=date_from)
        if date_to:
            expenses_uzs = expenses_uzs.filter(date__lte=date_to)
            expenses_usd = expenses_usd.filter(date__lte=date_to)
        if currency == 'UZS':
            expenses_usd = Expense.objects.none()
        elif currency == 'USD':
            expenses_uzs = Expense.objects.none()

        return Response({
            'date_from':                date_from,
            'date_to':                  date_to,
            'currency':                 currency,
            'category':                 category_id,
            'client':                   client_id,
            'supplier':                 supplier,
            'product':                  product_id,
            'payment_status':           payment_status,
            'filtered':                 filtered,
            'sales_revenue_total':      sales_period,
            'sales_revenue_uzs':        sales_period,
            'kassa_collected_uzs':      kassa_period_uzs,
            'kassa_collected_usd':      kassa_period_usd,
            'kassa_collected_today_uzs': kassa_today_uzs,
            'kassa_collected_today_usd': kassa_today_usd,
            'import_paid_uzs':          import_period_uzs,
            'import_paid_usd':          import_period_usd,
            'import_paid_today_uzs':    import_today_uzs,
            'import_paid_today_usd':    import_today_usd,
            'import_out_uzs':           ledger_out_uzs,
            'net_balance_uzs':          net_balance_uzs,
            'net_balance_usd':          net_balance_usd,
            'mb_rate_today':            mb_rate,
            'expenses_uzs':             expenses_uzs.aggregate(t=Sum('amount'))['t'] or 0,
            'expenses_usd':             expenses_usd.aggregate(t=Sum('amount'))['t'] or 0,
            'commission_earned':        commission_total,
            'overdue_payments_count':   overdue_count,
            'report_date':              today,
        })


class MonthlyTrendView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Oylik moliyaviy trend",
        parameters=[
            OpenApiParameter('months', int, description='Nechta oy (default 6, max 24)'),
            OpenApiParameter('currency', str, description='UZS yoki USD (ixtiyoriy)'),
            OpenApiParameter('category', int, description='Kategoriya ID (ixtiyoriy)'),
            OpenApiParameter('client', int, description='Mijoz ID (ixtiyoriy)'),
            OpenApiParameter('supplier', str, description='Yetkazuvchi (qisman mos)'),
            OpenApiParameter('product', int, description='Mahsulot ID (ixtiyoriy)'),
            OpenApiParameter('payment_status', str,
                             description='pending|partial|paid|overdue (ixtiyoriy)'),
        ],
        tags=["Reports / Summary"],
    )
    def get(self, request):
        try:
            count = int(request.query_params.get('months', 6))
        except (TypeError, ValueError):
            count = 6
        count = max(1, min(count, 24))
        currency = _parse_currency(request)
        category_id, client_id, product_id, supplier, payment_status = (
            _parse_dashboard_filters(request)
        )
        dash_kw = dict(
            category_id=category_id,
            product_id=product_id,
            client_id=client_id,
            supplier=supplier,
        )
        kassa_kw = dict(client_id=client_id, payment_status=payment_status)

        today = timezone.now().date()
        y, m = today.year, today.month
        rows = []

        for offset in range(count):
            year, month = _shift_month(y, m, -offset)
            start, end = _month_bounds(year, month)
            if offset == 0:
                end = min(end, today)
            if currency == Payment.USD:
                kassa = _kassa_collected(start, end, Payment.USD, **kassa_kw)
            else:
                kassa = _ledger_in_uzs(start, end)
            import_uzs, import_usd, _ = _import_paid_totals(
                start, end, currency, **dash_kw,
            )
            if currency != Payment.USD and not client_id and not payment_status:
                import_uzs = _ledger_out_uzs(start, end)
            sales = _sales_revenue(start, end, **dash_kw)
            rows.append({
                'year':          year,
                'month':         month,
                'label':         _month_label(year, month),
                'date_from':     start.isoformat(),
                'date_to':       end.isoformat(),
                'kassa_uzs':     kassa,
                'import_uzs':    import_uzs,
                'import_usd':    import_usd,
                'sales_uzs':     sales,
            })

        return Response(rows)


class WarehouseReportView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Ombor hisoboti",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to',   str, description='YYYY-MM-DD'),
        ],
        tags=["Reports / Summary"],
    )
    def get(self, request):
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')

        stocks_qs = Stock.objects.select_related('product__category')
        if date_from:
            stocks_qs = stocks_qs.filter(created_at__date__gte=date_from)
        if date_to:
            stocks_qs = stocks_qs.filter(created_at__date__lte=date_to)

        total_products = Product.objects.count()
        total_qty      = stocks_qs.aggregate(t=Sum('quantity'))['t'] or 0

        from django.db.models import F as _F
        low_stock = list(
            Stock.objects.select_related('product')
            .filter(quantity__gt=0, quantity__lte=_F('product__min_quantity'))
            .values('product__id', 'product__name', 'product__serial_number',
                    'quantity', 'product__min_quantity')
        )
        out_of_stock = list(
            Stock.objects.select_related('product')
            .filter(quantity=0)
            .values('product__id', 'product__name', 'product__serial_number')
        )

        by_category = list(
            stocks_qs.values('product__category__name')
            .annotate(total_qty=Sum('quantity'))
            .order_by('-total_qty')
        )

        return Response({
            'total_product_types': total_products,
            'total_quantity':      total_qty,
            'by_category':         by_category,
            'low_stock':           low_stock,
            'out_of_stock':        out_of_stock,
        })


class CashReportView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Kassa hisoboti",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to',   str, description='YYYY-MM-DD'),
            OpenApiParameter('client', int, description='Mijoz ID (ixtiyoriy)'),
            OpenApiParameter('payment_status', str,
                             description='pending|partial|paid|overdue (ixtiyoriy)'),
        ],
        tags=["Reports / Summary"],
    )
    def get(self, request):
        today     = timezone.now().date()
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')
        _, client_id, _, _, payment_status = _parse_dashboard_filters(request)

        qs = Payment.objects.all()
        qs = _filter_payments(qs, client_id, payment_status)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        overdue_count = qs.filter(
            status__in=(Payment.PENDING, Payment.PARTIAL, Payment.OVERDUE),
            due_date__lt=today,
        ).count()

        if date_from or date_to:
            txn_qs = PaymentTransaction.objects.filter(payment__currency=Payment.UZS)
            if client_id:
                txn_qs = txn_qs.filter(payment__client_id=client_id)
            if payment_status:
                if payment_status == Payment.OVERDUE:
                    txn_qs = txn_qs.filter(
                        payment__status__in=(
                            Payment.PENDING, Payment.PARTIAL, Payment.OVERDUE,
                        ),
                        payment__due_date__lt=today,
                    )
                else:
                    txn_qs = txn_qs.filter(payment__status=payment_status)
            if date_from:
                txn_qs = txn_qs.filter(created_at__date__gte=date_from)
            if date_to:
                txn_qs = txn_qs.filter(created_at__date__lte=date_to)
            sum_paid_uzs = txn_qs.aggregate(s=Sum('amount'))['s'] or 0
        else:
            sum_paid_uzs = qs.filter(currency=Payment.UZS).aggregate(
                s=Sum('paid_amount'),
            )['s'] or 0

        return Response({
            'total_pending':    qs.filter(status=Payment.PENDING).count(),
            'total_partial':    qs.filter(status=Payment.PARTIAL).count(),
            'total_paid':       qs.filter(status=Payment.PAID).count(),
            'total_overdue':    overdue_count,
            'sum_paid_uzs':     sum_paid_uzs,
            'sum_paid_usd':     qs.filter(currency=Payment.USD)
                                  .aggregate(s=Sum('paid_amount'))['s'] or 0,
            # Komissiya faqat UZS bo'yicha (valyuta aralashmasin)
            'commission_total': qs.filter(status=Payment.PAID,
                                          currency=Payment.UZS)
                                  .aggregate(s=Sum('commission'))['s'] or 0,
        })


class ExpensesReportView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Rasxod hisoboti",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to',   str, description='YYYY-MM-DD'),
        ],
        tags=["Reports / Summary"],
    )
    def get(self, request):
        from apps.expenses.models import ExpenseType as ET
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')

        qs = Expense.objects.select_related('expense_type')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        total_uzs = qs.filter(currency='UZS').aggregate(t=Sum('amount'))['t'] or 0
        total_usd = qs.filter(currency='USD').aggregate(t=Sum('amount'))['t'] or 0

        by_type = list(
            qs.values('expense_type__id', 'expense_type__name', 'currency')
            .annotate(total=Sum('amount'))
            .order_by('expense_type__name')
        )

        return Response({
            'total_uzs': total_uzs,
            'total_usd': total_usd,
            'by_type':   by_type,
            'count':     qs.count(),
        })


class TopProductsView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Eng ko'p sotilgan mahsulotlar (B8)",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to',   str, description='YYYY-MM-DD'),
            OpenApiParameter('limit',     int, description='Nechta (default 10)'),
            OpenApiParameter('category', int, description='Kategoriya ID (ixtiyoriy)'),
            OpenApiParameter('client', int, description='Mijoz ID (ixtiyoriy)'),
            OpenApiParameter('product', int, description='Mahsulot ID (ixtiyoriy)'),
        ],
        tags=["Reports / Summary"],
    )
    def get(self, request):
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')
        category_id, client_id, product_id, _, _ = _parse_dashboard_filters(request)
        try:
            limit = int(request.query_params.get('limit', 10))
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 100))

        sales_qs = Sale.objects.all()
        if date_from:
            sales_qs = sales_qs.filter(sold_date__gte=date_from)
        if date_to:
            sales_qs = sales_qs.filter(sold_date__lte=date_to)
        if category_id:
            sales_qs = sales_qs.filter(product__category_id=category_id)
        if client_id:
            sales_qs = sales_qs.filter(client_id=client_id)
        if product_id:
            sales_qs = sales_qs.filter(product_id=product_id)

        top = (
            sales_qs
            .values('product__id', 'product__name', 'product__serial_number',
                    'product__min_quantity')
            .annotate(sold_qty=Sum('quantity'))
            .order_by('-sold_qty')[:limit]
        )

        result = []
        for row in top:
            pid = row['product__id']
            current_stock = (
                Stock.objects.filter(product_id=pid)
                .aggregate(t=Sum('quantity'))['t'] or 0
            )
            is_low = current_stock <= row['product__min_quantity']
            result.append({
                'product':       pid,
                'name':          row['product__name'],
                'serial_number': row['product__serial_number'],
                'sold_qty':      row['sold_qty'],
                'current_stock': current_stock,
                'min_quantity':  row['product__min_quantity'],
                'is_low':        is_low,
            })

        return Response(result)
