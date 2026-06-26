from django.contrib import admin
from django.utils.html import format_html

from apps.sales.models import Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display    = ('id', 'product', 'quantity', 'sold_price_fmt',
                       'total_fmt', 'profit_fmt', 'sold_to', 'destination', 'sold_date')
    list_filter     = ('sold_date', 'product')
    search_fields   = ('product__name', 'sold_to', 'destination')
    autocomplete_fields = ('product',)
    list_select_related = ('product',)
    date_hierarchy  = 'sold_date'
    ordering        = ('-sold_date', '-created_at')
    list_per_page   = 25
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Sotuv', {'fields': ('product', 'quantity', 'sold_price',
                              'sold_to', 'destination', 'sold_date')}),
        ('Qo\'shimcha', {'fields': ('comment', 'created_at', 'updated_at'),
                         'classes': ('collapse',)}),
    )

    @admin.display(description='Sotuv narxi', ordering='sold_price')
    def sold_price_fmt(self, obj):
        return format_html('{:,.0f} so\'m', obj.sold_price)

    @admin.display(description='Jami')
    def total_fmt(self, obj):
        return format_html('<b style="color:#004085">{:,.0f} so\'m</b>', obj.total_amount)

    @admin.display(description='Foyda')
    def profit_fmt(self, obj):
        p     = obj.profit
        color = '#28a745' if p >= 0 else '#dc3545'
        sign  = '+' if p >= 0 else ''
        return format_html('<b style="color:{}">{}{:,.0f} so\'m</b>', color, sign, p)
