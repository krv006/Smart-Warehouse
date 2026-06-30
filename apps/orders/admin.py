from django.contrib import admin
from django.utils.html import format_html

from apps.orders.models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ('id', 'product', 'client', 'quantity', 'reserved_qty',
                       'backorder_qty_col', 'status_badge', 'due_date', 'created_at')
    list_filter     = ('status', 'due_date')
    search_fields   = ('product__name', 'product__serial_number',
                       'client__company_name', 'comment')
    ordering        = ('due_date', '-created_at')
    list_per_page   = 25
    readonly_fields = ('reserved_qty', 'status', 'created_at', 'updated_at')
    autocomplete_fields = ('product',)

    STATUS_COLORS = {
        Order.PENDING:   ('#fd7e14', 'Zakaz'),
        Order.PARTIAL:   ('#ffc107', 'Qisman bron'),
        Order.RESERVED:  ('#198754', 'Bron'),
        Order.FULFILLED: ('#0d6efd', 'Yetkazildi'),
        Order.CANCELLED: ('#6c757d', 'Bekor'),
    }

    @admin.display(description='Holat')
    def status_badge(self, obj):
        color, label = self.STATUS_COLORS.get(obj.status, ('#333', obj.status))
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>', color, label
        )

    @admin.display(description='Zakaz (yetishmaydi)')
    def backorder_qty_col(self, obj):
        bq = obj.backorder_qty
        if bq <= 0:
            return format_html('<span style="color:#198754">0</span>')
        return format_html('<span style="color:#dc3545;font-weight:700">{} dona</span>', bq)
