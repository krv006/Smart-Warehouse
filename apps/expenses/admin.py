from django.contrib import admin
from django.utils.html import format_html

from apps.expenses.models import ExpenseType, ExpenseSubType, Expense


class ExpenseSubTypeInline(admin.TabularInline):
    model  = ExpenseSubType
    extra  = 2
    fields = ('name',)


@admin.register(ExpenseType)
class ExpenseTypeAdmin(admin.ModelAdmin):
    list_display  = ('id', 'code', 'name')
    search_fields = ('name', 'code')
    inlines       = (ExpenseSubTypeInline,)


@admin.register(ExpenseSubType)
class ExpenseSubTypeAdmin(admin.ModelAdmin):
    list_display  = ('id', 'expense_type', 'name')
    list_filter   = ('expense_type',)
    search_fields = ('name',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display    = ('id', 'expense_type', 'sub_type', 'amount_fmt',
                       'currency', 'responsible', 'date')
    list_filter     = ('expense_type', 'currency', 'date')
    search_fields   = ('expense_type__name', 'sub_type__name', 'comment')
    date_hierarchy  = 'date'
    ordering        = ('-date', '-created_at')
    list_per_page   = 25
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Summa', ordering='amount')
    def amount_fmt(self, obj):
        return format_html('<b>{:,.0f} {}</b>', obj.amount, obj.currency)
