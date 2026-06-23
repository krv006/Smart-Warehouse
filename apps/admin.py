from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from mptt.admin import DraggableMPTTAdmin

from apps.models import User, Product, Stock, Sale, Category


# ─────────────────────────────────────────────
#  FOYDALANUVCHILAR
# ─────────────────────────────────────────────
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display  = ('id', 'username', 'full_name', 'role_badge',
                     'is_active', 'is_staff', 'date_joined')
    list_filter   = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering      = ('-date_joined',)
    list_per_page = 20

    fieldsets = UserAdmin.fieldsets + (
        ('Rol va huquqlar', {
            'fields': ('role',),
            'classes': ('collapse',),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol', {'fields': ('role',)}),
    )

    @admin.display(description='Ismi')
    def full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip() or '—'

    @admin.display(description='Rol')
    def role_badge(self, obj):
        colors = {
            User.MANAGEMENT: ('#28a745', '👑 Management'),
            User.OPERATOR:   ('#007bff', '🔧 Operator'),
        }
        color, label = colors.get(obj.role, ('#6c757d', obj.role))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600">{}</span>',
            color, label
        )


# ─────────────────────────────────────────────
#  KATEGORIYALAR
# ─────────────────────────────────────────────
@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    list_display = ('tree_actions', 'indented_title')
    list_display_links = ('indented_title',)
    search_fields = ('name',)
    mptt_level_indent = 20


# ─────────────────────────────────────────────
#  MAHSULOTLAR
# ─────────────────────────────────────────────
class StockInline(admin.TabularInline):
    model       = Stock
    extra       = 1
    fields      = ('warehouse_location', 'quantity')
    show_change_link = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ('id', 'name', 'model', 'serial_number', 'category',
                     'purchase_price_formatted', 'stock_badge', 'created_at')
    search_fields = ('name', 'model', 'serial_number')
    list_filter   = ('created_at', 'category')
    ordering      = ('-created_at',)
    list_per_page = 25
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    inlines       = (StockInline,)

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('name', 'model', 'serial_number'),
        }),
        ('Narx va sana', {
            'fields': ('purchase_price', 'created_at'),
        }),
    )

    @admin.display(description='Olish narxi', ordering='purchase_price')
    def purchase_price_formatted(self, obj):
        return format_html(
            '<b style="color:#155724">{:,.0f} so\'m</b>',
            obj.purchase_price
        )

    @admin.display(description='Ombor qoldig\'i')
    def stock_badge(self, obj):
        qty = obj.quantity_in_stock
        if qty == 0:
            color, icon = '#dc3545', '❌'
        elif qty < 5:
            color, icon = '#ffc107', '⚠️'
        else:
            color, icon = '#28a745', '✅'
        return format_html(
            '<span style="color:{};font-weight:600">{} {} dona</span>',
            color, icon, qty
        )


# ─────────────────────────────────────────────
#  OMBOR QOLDIQLARI
# ─────────────────────────────────────────────
@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display  = ('id', 'product_link', 'warehouse_location',
                     'quantity_colored')
    list_filter   = ('warehouse_location',)
    search_fields = ('product__name', 'product__serial_number', 'warehouse_location')
    autocomplete_fields = ('product',)
    list_per_page = 25
    list_select_related = ('product',)

    @admin.display(description='Mahsulot', ordering='product__name')
    def product_link(self, obj):
        return format_html(
            '<a href="/admin/apps/product/{}/change/">{}</a>',
            obj.product.id, obj.product.name
        )

    @admin.display(description='Miqdor', ordering='quantity')
    def quantity_colored(self, obj):
        if obj.quantity == 0:
            color = '#dc3545'
        elif obj.quantity < 5:
            color = '#fd7e14'
        else:
            color = '#28a745'
        return format_html(
            '<span style="color:{};font-weight:700;font-size:14px">{} dona</span>',
            color, obj.quantity
        )


# ─────────────────────────────────────────────
#  SOTUVLAR
# ─────────────────────────────────────────────
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display  = ('id', 'product_name', 'quantity', 'sold_price_fmt',
                     'total_amount_fmt', 'profit_fmt', 'sold_to', 'sold_date')
    list_filter   = ('sold_date', 'product')
    search_fields = ('product__name', 'product__serial_number', 'sold_to')
    autocomplete_fields = ('product',)
    list_select_related = ('product',)
    date_hierarchy = 'sold_date'
    ordering      = ('-sold_date', '-created_at')
    list_per_page = 25
    readonly_fields = ('created_at', 'total_amount_display', 'profit_display')

    fieldsets = (
        ('Sotuv ma\'lumotlari', {
            'fields': ('product', 'quantity', 'sold_price', 'sold_to', 'sold_date'),
        }),
        ('Qo\'shimcha', {
            'fields': ('comment',),
            'classes': ('collapse',),
        }),
        ('Hisob-kitob (avtomatik)', {
            'fields': ('total_amount_display', 'profit_display', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Mahsulot', ordering='product__name')
    def product_name(self, obj):
        return obj.product.name

    @admin.display(description='Sotuv narxi', ordering='sold_price')
    def sold_price_fmt(self, obj):
        return format_html('{:,.0f} so\'m', obj.sold_price)

    @admin.display(description='Jami summa')
    def total_amount_fmt(self, obj):
        return format_html(
            '<b style="color:#004085">{:,.0f} so\'m</b>',
            obj.total_amount
        )

    @admin.display(description='Foyda')
    def profit_fmt(self, obj):
        profit = obj.profit
        color  = '#28a745' if profit >= 0 else '#dc3545'
        sign   = '+' if profit >= 0 else ''
        return format_html(
            '<b style="color:{}">{}{:,.0f} so\'m</b>',
            color, sign, profit
        )

    @admin.display(description='Jami summa')
    def total_amount_display(self, obj):
        return f"{obj.total_amount:,.0f} so'm"

    @admin.display(description='Foyda')
    def profit_display(self, obj):
        return f"{obj.profit:,.0f} so'm"
