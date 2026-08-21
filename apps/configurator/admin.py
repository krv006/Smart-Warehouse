from django.contrib import admin

from apps.configurator.models import ServerConfiguration, ConfigurationItem


class ConfigurationItemInline(admin.TabularInline):
    model = ConfigurationItem
    extra = 0


@admin.register(ServerConfiguration)
class ServerConfigurationAdmin(admin.ModelAdmin):
    list_display  = ('id', 'name', 'client', 'created_by', 'created_at')
    search_fields = ('name',)
    inlines       = (ConfigurationItemInline,)
