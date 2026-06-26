from django.db.models import Sum, F, ExpressionWrapper, DecimalField
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
from apps.warehouse.models import Stock


class SalesExportView(APIView):
    permission_classes = (IsAuthenticated,)

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
    permission_classes = (IsAuthenticated,)

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
