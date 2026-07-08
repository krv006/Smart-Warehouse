from django.contrib import admin
from django.utils.html import format_html

from apps.cash.models import Payment, PaymentTransaction


class PaymentTransactionInline(admin.TabularInline):
    model           = PaymentTransaction
    extra           = 0
    can_delete      = False
    readonly_fields = ('amount', 'received_by', 'comment', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    inlines = (PaymentTransactionInline,)
    list_display    = ('id', 'source_col', 'sale', 'order', 'client', 'total_amount',
                       'commission', 'paid_amount_fmt', 'currency',
                       'status_badge', 'due_date')
    list_filter     = ('status', 'currency', 'due_date')
    search_fields   = ('sale__product__name', 'order__items__product__name',
                       'order__contract_number', 'client__company_name', 'comment')
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

    @admin.display(description='Manba')
    def source_col(self, obj):
        if obj.order_id:
            return format_html('<span style="color:#0d6efd;font-weight:600">Buyurtma</span>')
        return format_html('<span style="color:#198754;font-weight:600">Sotuv</span>')

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
