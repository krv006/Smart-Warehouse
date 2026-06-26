from django.contrib import admin
from django.utils.html import format_html

from apps.notifications.models import TelegramSettings


@admin.register(TelegramSettings)
class TelegramSettingsAdmin(admin.ModelAdmin):
    list_display    = ('chat_id', 'is_active', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('bot_token', 'chat_id', 'is_active', 'extra_note'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        return not TelegramSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
