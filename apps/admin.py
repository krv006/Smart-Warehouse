from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.models import User, Product, Stock, Sale


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'role', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('Rol', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol', {'fields': ('role',)}),
    )


class StockInline(admin.TabularInline):
    model = Stock
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'model', 'serial_number',
                    'purchase_price', 'quantity_in_stock', 'created_at')
    search_fields = ('name', 'model', 'serial_number')
    inlines = (StockInline,)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'warehouse_location', 'quantity')
    list_filter = ('warehouse_location',)
    search_fields = ('product__name', 'product__serial_number')
    autocomplete_fields = ('product',)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'quantity', 'sold_price',
                    'total_amount', 'profit', 'sold_to', 'sold_date')
    list_filter = ('sold_date',)
    search_fields = ('product__name', 'sold_to')
    autocomplete_fields = ('product',)
