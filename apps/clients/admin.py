from django.contrib import admin

from apps.clients.encryption import decrypt
from apps.clients.models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display    = ('id', 'company_name', 'decrypted_full_name',
                       'decrypted_phone', 'email', 'is_active', 'created_at')
    list_filter     = ('is_active',)
    search_fields   = ('company_name', 'email')
    readonly_fields = ('id', 'created_at', 'updated_at',
                       'decrypted_full_name', 'decrypted_inn', 'decrypted_phone')
    list_per_page   = 25

    @admin.display(description='Ism (plain)')
    def decrypted_full_name(self, obj):
        return decrypt(obj.full_name)

    @admin.display(description='INN (plain)')
    def decrypted_inn(self, obj):
        return decrypt(obj.inn)

    @admin.display(description='Tel (plain)')
    def decrypted_phone(self, obj):
        return decrypt(obj.phone)
