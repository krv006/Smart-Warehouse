from django.urls import path
from apps.reports.views import (SalesExportView, StockExportView,
                                 ExpensesExportView, PaymentsExportView,
                                 FinancialSummaryView, WarehouseReportView,
                                 CashReportView, ExpensesReportView,
                                 TopProductsView)

urlpatterns = [
    path('excel/sales/',    SalesExportView.as_view(),    name='report-sales-excel'),
    path('excel/stock/',    StockExportView.as_view(),    name='report-stock-excel'),
    path('excel/expenses/', ExpensesExportView.as_view(), name='report-expenses-excel'),
    path('excel/payments/', PaymentsExportView.as_view(), name='report-payments-excel'),
    path('summary/',        FinancialSummaryView.as_view(),  name='report-summary'),
    path('warehouse/',      WarehouseReportView.as_view(),   name='report-warehouse'),
    path('cash/',           CashReportView.as_view(),        name='report-cash'),
    path('expenses/',       ExpensesReportView.as_view(),    name='report-expenses'),
    path('top-products/',   TopProductsView.as_view(),       name='report-top-products'),
]
