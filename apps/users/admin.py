from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from apps.users.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display  = ('id', 'username', 'full_name', 'role_badge',
                     'can_view_clients', 'is_active', 'date_joined')
    list_filter   = ('role', 'is_active', 'can_view_clients')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering      = ('-date_joined',)
    list_per_page = 25

    fieldsets = UserAdmin.fieldsets + (
        ('Rol va qo\'shimcha', {
            'fields': ('role', 'phone', 'telegram_id', 'can_view_clients'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol', {'fields': ('role', 'phone', 'telegram_id', 'can_view_clients')}),
    )

    @admin.display(description='Ismi')
    def full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip() or '—'

    @admin.display(description='Rol')
    def role_badge(self, obj):
        colors = {
            User.MANAGEMENT:  ('#28a745', '👑 Management'),
            User.ACCOUNTANT:  ('#fd7e14', '💼 Accountant'),
            User.OPERATOR:    ('#007bff', '🔧 Operator'),
        }
        color, label = colors.get(obj.role, ('#6c757d', obj.role))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600">{}</span>',
            color, label
        )
