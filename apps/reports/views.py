from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count
from django.utils import timezone

from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cash.models import Payment
from apps.common.permissions import IsAccountantOrManagement
from apps.expenses.models import Expense
from apps.reports.excel import (export_sales, export_stock,
                                 export_expenses, export_payments)
from apps.sales.models import Sale
from apps.warehouse.models import Stock, Product


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
        return export_sales(qs)


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
        return export_expenses(qs)


class PaymentsExportView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(summary="Kassa — Excel yuklash", tags=["Reports / Excel"])
    def get(self, request):
        qs = Payment.objects.select_related('sale__product', 'client').order_by('-created_at')
        return export_payments(qs)


class FinancialSummaryView(APIView):
    permission_classes = (IsAccountantOrManagement,)

    @extend_schema(
        summary="Moliyaviy xulosa (Management / Accountant)",
        tags=["Reports / Summary"],
    )
    def get(self, request):
        today = timezone.now().date()

        sales_total = Sale.objects.aggregate(
            total=Sum(ExpressionWrapper(
                F('sold_price') * F('quantity'),
                output_field=DecimalField()
            ))
        )['total'] or 0

        expenses_total_uzs = Expense.objects.filter(currency='UZS').aggregate(
            total=Sum('amount')
        )['total'] or 0

        expenses_total_usd = Expense.objects.filter(currency='USD').aggregate(
            total=Sum('amount')
        )['total'] or 0

        paid_uzs = Payment.objects.filter(
            status=Payment.PAID, currency=Payment.UZS
        ).aggregate(total=Sum('paid_amount'))['total'] or 0

        overdue_count = Payment.objects.filter(
            status__in=(Payment.PENDING, Payment.PARTIAL),
            due_date__lt=today,
        ).count()

        commission_total = Payment.objects.filter(
            status=Payment.PAID
        ).aggregate(total=Sum('commission'))['total'] or 0

        return Response({
            'sales_revenue_total':   sales_total,
            'expenses_uzs':          expenses_total_uzs,
            'expenses_usd':          expenses_total_usd,
            'kassa_collected_uzs':   paid_uzs,
            'commission_earned':     commission_total,
            'overdue_payments_count': overdue_count,
            'report_date':           today,
        })


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
        ],
        tags=["Reports / Summary"],
    )
    def get(self, request):
        today     = timezone.now().date()
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')

        qs = Payment.objects.all()
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        overdue_count = qs.filter(
            status__in=(Payment.PENDING, Payment.PARTIAL, Payment.OVERDUE),
            due_date__lt=today,
        ).count()

        return Response({
            'total_pending':    qs.filter(status=Payment.PENDING).count(),
            'total_partial':    qs.filter(status=Payment.PARTIAL).count(),
            'total_paid':       qs.filter(status=Payment.PAID).count(),
            'total_overdue':    overdue_count,
            'sum_paid_uzs':     qs.filter(status=Payment.PAID, currency=Payment.UZS)
                                  .aggregate(s=Sum('paid_amount'))['s'] or 0,
            'sum_paid_usd':     qs.filter(status=Payment.PAID, currency=Payment.USD)
                                  .aggregate(s=Sum('paid_amount'))['s'] or 0,
            'commission_total': qs.filter(status=Payment.PAID)
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
        ],
        tags=["Reports / Summary"],
    )
    def get(self, request):
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')
        limit     = int(request.query_params.get('limit', 10))

        sales_qs = Sale.objects.all()
        if date_from:
            sales_qs = sales_qs.filter(sold_date__gte=date_from)
        if date_to:
            sales_qs = sales_qs.filter(sold_date__lte=date_to)

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
