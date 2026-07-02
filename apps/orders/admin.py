from django.contrib import admin
from django.utils.html import format_html

from apps.orders.models import Order, Zakaz


# ── Order (Bron) ──────────────────────────────────────────────────────────────

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ('id', 'product', 'client', 'quantity_col',
                       'reserved_col', 'backorder_col', 'status_badge',
                       'due_date', 'created_at')
    list_filter     = ('status', 'due_date')
    search_fields   = ('product__name', 'product__serial_number',
                       'client__company_name', 'comment')
    ordering        = ('due_date', '-created_at')
    list_per_page   = 25
    readonly_fields = ('reserved_qty', 'status', 'created_at', 'updated_at')
    autocomplete_fields = ('product',)

    _STATUS_COLORS = {
        Order.PENDING:   ('#fd7e14', 'Zakaz'),
        Order.PARTIAL:   ('#ffc107', 'Qisman bron'),
        Order.RESERVED:  ('#198754', 'To\'liq bron'),
        Order.FULFILLED: ('#0d6efd', 'Yetkazildi'),
        Order.CANCELLED: ('#6c757d', 'Bekor'),
    }

    @admin.display(description='Buyurtma')
    def quantity_col(self, obj):
        return format_html('<b>{} dona</b>', obj.quantity)

    @admin.display(description='Bron')
    def reserved_col(self, obj):
        color = '#198754' if obj.reserved_qty > 0 else '#6c757d'
        return format_html('<span style="color:{}">{} dona</span>',
                           color, obj.reserved_qty)

    @admin.display(description='Zakaz (yetishmaydi)')
    def backorder_col(self, obj):
        bq = obj.backorder_qty
        if bq <= 0:
            return format_html('<span style="color:#198754">—</span>')
        return format_html('<span style="color:#dc3545;font-weight:700">{} dona</span>', bq)

    @admin.display(description='Holat')
    def status_badge(self, obj):
        color, label = self._STATUS_COLORS.get(obj.status, ('#333', obj.status))
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>', color, label
        )


# ── Zakaz (Procurement) ───────────────────────────────────────────────────────

@admin.register(Zakaz)
class ZakazAdmin(admin.ModelAdmin):
    list_display    = ('id', 'product', 'quantity', 'received_qty_col',
                       'supplier', 'status_badge', 'expected_date',
                       'created_by', 'created_at')
    list_filter     = ('status', 'expected_date')
    search_fields   = ('product__name', 'product__serial_number',
                       'supplier', 'comment', 'created_by__username')
    ordering        = ('-created_at',)
    list_per_page   = 25
    readonly_fields = ('created_by', 'created_at', 'updated_at')
    autocomplete_fields = ('product',)

    _STATUS_COLORS = {
        Zakaz.NEW:       ('#0d6efd', 'Yangi'),
        Zakaz.CONFIRMED: ('#6610f2', 'Tasdiqlandi'),
        Zakaz.ORDERED:   ('#fd7e14', 'Yuborildi'),
        Zakaz.RECEIVED:  ('#198754', 'Qabul qilindi'),
        Zakaz.CANCELLED: ('#6c757d', 'Bekor'),
    }

    @admin.display(description='Qabul qilingan')
    def received_qty_col(self, obj):
        if obj.status != Zakaz.RECEIVED:
            return format_html('<span style="color:#6c757d">—</span>')
        return format_html('<span style="color:#198754;font-weight:700">{} dona</span>',
                           obj.received_qty or obj.quantity)

    @admin.display(description='Holat')
    def status_badge(self, obj):
        color, label = self._STATUS_COLORS.get(obj.status, ('#333', obj.status))
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>', color, label
        )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
