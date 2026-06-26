from django.contrib import admin
from django.utils.html import format_html
from mptt.admin import DraggableMPTTAdmin

from apps.warehouse.models import Category, Product, Stock


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    list_display       = ('tree_actions', 'indented_title')
    list_display_links = ('indented_title',)
    search_fields      = ('name',)
    mptt_level_indent  = 20


class StockInline(admin.TabularInline):
    model            = Stock
    extra            = 1
    fields           = ('warehouse_location', 'quantity')
    show_change_link = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display    = ('id', 'name', 'model', 'serial_number', 'category',
                       'source', 'purchase_price_fmt', 'stock_badge', 'created_at')
    search_fields   = ('name', 'model', 'serial_number', 'source')
    list_filter     = ('created_at', 'category')
    ordering        = ('-created_at',)
    list_per_page   = 25
    date_hierarchy  = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    inlines         = (StockInline,)

    fieldsets = (
        ('Asosiy', {'fields': ('category', 'name', 'model', 'serial_number', 'source')}),
        ('Narx',   {'fields': ('purchase_price',)}),
        ('Vaqt',   {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Narxi', ordering='purchase_price')
    def purchase_price_fmt(self, obj):
        return format_html('<b style="color:#155724">{:,.0f} so\'m</b>', obj.purchase_price)

    @admin.display(description='Qoldiq')
    def stock_badge(self, obj):
        qty = obj.quantity_in_stock
        color = '#dc3545' if qty == 0 else ('#ffc107' if qty < 5 else '#28a745')
        icon  = '❌' if qty == 0 else ('⚠️' if qty < 5 else '✅')
        return format_html('<span style="color:{};font-weight:600">{} {} dona</span>',
                           color, icon, qty)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display        = ('id', 'product', 'warehouse_location', 'quantity_colored')
    list_filter         = ('warehouse_location',)
    search_fields       = ('product__name', 'product__serial_number', 'warehouse_location')
    autocomplete_fields = ('product',)
    list_per_page       = 25
    list_select_related = ('product',)

    @admin.display(description='Miqdor', ordering='quantity')
    def quantity_colored(self, obj):
        color = '#dc3545' if obj.quantity == 0 else ('#fd7e14' if obj.quantity < 5 else '#28a745')
        return format_html('<span style="color:{};font-weight:700">{} dona</span>',
                           color, obj.quantity)
