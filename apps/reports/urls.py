from django.urls import path
from apps.reports.views import (SalesExportView, StockExportView,
                                 ExpensesExportView, PaymentsExportView,
                                 FinancialSummaryView)

urlpatterns = [
    path('excel/sales/',    SalesExportView.as_view(),    name='report-sales-excel'),
    path('excel/stock/',    StockExportView.as_view(),    name='report-stock-excel'),
    path('excel/expenses/', ExpensesExportView.as_view(), name='report-expenses-excel'),
    path('excel/payments/', PaymentsExportView.as_view(), name='report-payments-excel'),
    path('summary/',        FinancialSummaryView.as_view(), name='report-summary'),
]
