"""Elektron faktura (shartnoma) summasini kassadan chiqim sifatida yozish."""
from decimal import Decimal

from django.utils import timezone

from apps.expenses.models import Expense, ExpenseSubType, ExpenseType
from apps.invoices.models import DocumentType, ElectronicInvoice


def _invoice_expense_amount(invoice: ElectronicInvoice):
    """
    Fakturadagi qatorlar jami (yetkazish + QQS). Import kelib chiqishli
    (`origin=import`) mahsulotlar hisobga olinmaydi — ularning narxi o'z
    Zakazi qabul qilinganda/to'langanda alohida chiqim bo'lib kassaga
    tushadi (`sync_zakaz_expense`), shu yerda ikki marta hisoblanmasin.
    Bu qoida barqaror: qator yangi ochilgan paytda ham, keyingi har qanday
    tahrirda ham bir xil ishlaydi (mahsulot turiga qarab aniqlanadi).
    """
    from apps.warehouse.models import ProductOrigin

    total = Decimal('0')
    for line in invoice.lines.select_related('product').all():
        if line.product_id and line.product.origin == ProductOrigin.IMPORT:
            continue
        total += line.total_amount or Decimal('0')
    return total


def sync_invoice_expense(invoice: ElectronicInvoice, *, user=None):
    """
    Shartnoma (SK) fakturasi — ombordagi (import bo'lmagan) mahsulotlar
    bo'yicha summani kassadan CHIQIM (Expense) sifatida yozadi/yangilaydi.
    Boshqa hujjat turlari (hisob-faktura, dalolatnoma) shartnoma summasini
    takrorlamasligi uchun kassaga yozilmaydi — ular shu shartnomaga
    qo'shimcha hujjat, xolos.
    """
    if invoice.document_type != DocumentType.CONTRACT_SK:
        Expense.objects.filter(invoice=invoice).delete()
        return None

    target = _invoice_expense_amount(invoice)
    if target <= 0:
        Expense.objects.filter(invoice=invoice).delete()
        return None

    client = str(invoice.client) if invoice.client else '—'
    comment = f'Shartnoma №{invoice.contract_number or "—"} — {client}'

    expense_type, _ = ExpenseType.objects.get_or_create(
        code=ExpenseType.IMPORT,
        defaults={'name': 'Import rasxod'},
    )
    sub_type, _ = ExpenseSubType.objects.get_or_create(
        expense_type=expense_type,
        name='Faktura',
    )

    expense, _created = Expense.objects.get_or_create(
        invoice=invoice,
        defaults={
            'expense_type': expense_type,
            'sub_type': sub_type,
            'amount': target,
            'currency': Expense.UZS,
            'date': invoice.contract_date or timezone.localdate(),
            'responsible': user if getattr(user, 'is_authenticated', False) else None,
            'comment': comment,
        },
    )
    updates = []
    if expense.amount != target:
        expense.amount = target
        updates.append('amount')
    if expense.comment != comment:
        expense.comment = comment
        updates.append('comment')
    if expense.responsible_id is None and getattr(user, 'is_authenticated', False):
        expense.responsible = user
        updates.append('responsible')
    if updates:
        expense.save(update_fields=updates)
    return expense
