from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from django.utils.html import format_html

from apps.users.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display  = ('id', 'username', 'full_name', 'role_badge',
                     'access_summary', 'is_active', 'date_joined')
    list_filter   = ('role', 'is_active', 'can_view_clients', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering      = ('-date_joined',)
    list_per_page = 25
    actions       = ('make_operator', 'make_accountant', 'make_management',
                     'allow_clients', 'deny_clients')

    fieldsets = UserAdmin.fieldsets + (
        ('Smart Warehouse ruxsatlari', {
            'fields': ('role', 'phone', 'telegram_id', 'can_view_clients'),
            'description': (
                'Role asosiy modullarni boshqaradi: Operator — ombor/buyurtma/sotuv, '
                'Accountant — kassa/xarajat, Management — hisobot va nazorat. '
                '"Mijozlarni ko\'rish" alohida yoqiladi.'
            ),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Smart Warehouse ruxsatlari', {
            'fields': ('role', 'phone', 'telegram_id', 'can_view_clients'),
        }),
    )

    @admin.display(description='Ismi')
    def full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip() or '—'

    @admin.display(description='Rol')
    def role_badge(self, obj):
        colors = {
            User.MANAGEMENT:  ('#28a745', 'Management'),
            User.ACCOUNTANT:  ('#fd7e14', 'Accountant'),
            User.OPERATOR:    ('#007bff', 'Operator'),
        }
        color, label = colors.get(obj.role, ('#6c757d', obj.role))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600">{}</span>',
            color, label
        )

    @admin.display(description='Ruxsatlar')
    def access_summary(self, obj):
        labels = []
        if obj.is_operator:
            labels.extend(['Buyurtma', 'Ombor', 'Sotuv'])
        if obj.is_accountant:
            labels.extend(['Kassa', 'Xarajat'])
        if obj.is_management:
            labels.extend(['Hisobot'])
        if obj.can_view_clients:
            labels.append('Mijoz')
        if obj.is_superuser:
            labels.append('Superuser')
        return ', '.join(dict.fromkeys(labels)) or 'Faqat ko\'rish'

    def _update_selected(self, request, queryset, **changes):
        updated = queryset.update(**changes)
        self.message_user(request, f'{updated} ta foydalanuvchi yangilandi.', messages.SUCCESS)

    @admin.action(description='Tanlanganlarni Operator qilish')
    def make_operator(self, request, queryset):
        self._update_selected(request, queryset, role=User.OPERATOR)

    @admin.action(description='Tanlanganlarni Accountant qilish')
    def make_accountant(self, request, queryset):
        self._update_selected(request, queryset, role=User.ACCOUNTANT)

    @admin.action(description='Tanlanganlarni Management qilish')
    def make_management(self, request, queryset):
        self._update_selected(request, queryset, role=User.MANAGEMENT)

    @admin.action(description='Mijozlar bo\'limiga ruxsat berish')
    def allow_clients(self, request, queryset):
        self._update_selected(request, queryset, can_view_clients=True)

    @admin.action(description='Mijozlar bo\'limi ruxsatini olib tashlash')
    def deny_clients(self, request, queryset):
        self._update_selected(request, queryset, can_view_clients=False)
