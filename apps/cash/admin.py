from django.contrib import admin
from django.utils.html import format_html

from apps.cash.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display    = ('id', 'sale', 'client', 'total_amount',
                       'commission', 'paid_amount_fmt', 'currency',
                       'status_badge', 'due_date')
    list_filter     = ('status', 'currency', 'due_date')
    search_fields   = ('sale__product__name', 'client__company_name', 'comment')
    readonly_fields = ('total_amount', 'commission', 'status', 'created_at', 'updated_at')
    date_hierarchy  = 'created_at'
    ordering        = ('-created_at',)
    list_per_page   = 25

    STATUS_COLORS = {
        Payment.PENDING:  '#f0ad4e',
        Payment.PARTIAL:  '#5bc0de',
        Payment.PAID:     '#5cb85c',
        Payment.OVERDUE:  '#d9534f',
    }

    @admin.display(description='Toʻlangan', ordering='paid_amount')
    def paid_amount_fmt(self, obj):
        return format_html('<b>{}</b>', f'{obj.paid_amount:,.0f}')

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        color = self.STATUS_COLORS.get(obj.status, '#aaa')
        label = obj.get_status_display()
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:3px">{}</span>',
            color, label
        )
