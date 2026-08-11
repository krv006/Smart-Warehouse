from django.contrib import admin

from apps.invoices.models import ElectronicInvoice, InvoiceLineItem


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0


@admin.register(ElectronicInvoice)
class ElectronicInvoiceAdmin(admin.ModelAdmin):
    list_display = ('contract_number', 'document_type', 'client', 'contract_date', 'created_at')
    search_fields = ('contract_number', 'name')
    inlines = (InvoiceLineItemInline,)
