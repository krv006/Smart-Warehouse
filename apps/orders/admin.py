from django.contrib import admin
from django.utils.html import format_html

from apps.orders.models import (Order, OrderItem, OrderHistory,
                                Zakaz, ZakazHistory, ProductContract)


# ── Mahsulot shartnomalari reestri ───────────────────────────────────────────

@admin.register(ProductContract)
class ProductContractAdmin(admin.ModelAdmin):
    list_display    = ('id', 'product', 'contract_number', 'contract_date',
                       'source_type', 'faktura', 'order', 'zakaz',
                       'created_by', 'created_at')
    list_filter     = ('source_type', 'contract_date')
    search_fields   = ('contract_number', 'faktura', 'asos',
                       'product__name', 'product__serial_number')
    ordering        = ('-created_at',)
    list_per_page   = 30
    readonly_fields = ('product', 'contract_number', 'contract_date', 'asos',
                       'faktura', 'source_type', 'order', 'zakaz',
                       'created_by', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False  # faqat tizim avtomatik yozadi

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # audit butunligi


# ── Tarix inlinelar ───────────────────────────────────────────────────────────

class OrderHistoryInline(admin.TabularInline):
    model           = OrderHistory
    extra           = 0
    can_delete      = False
    readonly_fields = ('action', 'contract_number', 'asos', 'changes',
                       'changed_by', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


class ZakazHistoryInline(admin.TabularInline):
    model           = ZakazHistory
    extra           = 0
    can_delete      = False
    readonly_fields = ('action', 'old_status', 'new_status', 'contract_number',
                       'contract_date', 'asos', 'faktura', 'changes',
                       'changed_by', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


# ── Order (Bron) ──────────────────────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model               = OrderItem
    extra               = 0
    autocomplete_fields = ('product',)
    readonly_fields     = ('reserved_qty',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ('id', 'contract_number', 'items_col', 'client', 'quantity_col',
                       'reserved_col', 'backorder_col', 'prepaid_col', 'status_badge',
                       'due_date', 'created_at')
    list_filter     = ('status', 'due_date', 'contract_date')
    search_fields   = ('contract_number', 'items__product__name',
                       'items__product__serial_number',
                       'client__company_name', 'comment')
    ordering        = ('due_date', '-created_at')
    list_per_page   = 25
    readonly_fields = ('status', 'created_at', 'updated_at')
    inlines         = (OrderItemInline, OrderHistoryInline)

    _STATUS_COLORS = {
        Order.PENDING:   ('#fd7e14', 'Zakaz'),
        Order.PARTIAL:   ('#ffc107', 'Qisman bron'),
        Order.RESERVED:  ('#198754', 'To\'liq bron'),
        Order.FULFILLED: ('#0d6efd', 'Yetkazildi'),
        Order.CANCELLED: ('#6c757d', 'Bekor'),
    }

    @admin.display(description='Mahsulotlar')
    def items_col(self, obj):
        names = [i.product.name for i in obj.items.all()[:3]]
        extra = obj.items.count() - len(names)
        text  = ', '.join(names) + (f' +{extra}' if extra > 0 else '')
        return text or '—'

    @admin.display(description='Buyurtma')
    def quantity_col(self, obj):
        return format_html('<b>{} dona</b>', obj.total_quantity)

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

    @admin.display(description='Oldindan to\'lov')
    def prepaid_col(self, obj):
        if not obj.prepaid_amount:
            return format_html('<span style="color:#6c757d">—</span>')
        return format_html('<span style="color:#198754">{}</span>', obj.prepaid_amount)

    @admin.display(description='Holat')
    def status_badge(self, obj):
        color, label = self._STATUS_COLORS.get(obj.status, ('#333', obj.status))
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>', color, label
        )


# ── Zakaz (Procurement) ───────────────────────────────────────────────────────

@admin.register(Zakaz)
class ZakazAdmin(admin.ModelAdmin):
    list_display    = ('id', 'zakaz_type', 'contract_number', 'product', 'quantity',
                       'unit_price', 'total_col', 'received_qty_col',
                       'supplier', 'faktura', 'status_badge', 'payment_status',
                       'expected_date', 'order', 'created_by', 'created_at')
    list_filter     = ('status', 'zakaz_type', 'payment_status',
                       'expected_date', 'contract_date')
    search_fields   = ('contract_number', 'faktura', 'product__name',
                       'product__serial_number', 'supplier', 'comment',
                       'created_by__username')
    ordering        = ('-created_at',)
    list_per_page   = 25
    readonly_fields = ('created_by', 'confirmed_at', 'created_at', 'updated_at')
    autocomplete_fields = ('product',)
    inlines         = (ZakazHistoryInline,)

    _STATUS_COLORS = {
        Zakaz.NEW:       ('#0d6efd', 'Yangi'),
        Zakaz.CONFIRMED: ('#6610f2', 'Tasdiqlandi'),
        Zakaz.RECEIVED:  ('#198754', 'Qabul qilindi'),
        Zakaz.CANCELLED: ('#6c757d', 'Bekor'),
    }

    @admin.display(description='Summa')
    def total_col(self, obj):
        if obj.total is None:
            return format_html('<span style="color:#6c757d">—</span>')
        return format_html('<b>{} {}</b>', obj.total, obj.currency)

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
