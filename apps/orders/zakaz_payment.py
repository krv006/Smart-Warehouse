from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.cash.models import Payment
from apps.expenses.models import Expense, ExpenseSubType, ExpenseType
from apps.orders.models import Zakaz


def _target_expense_amount(zakaz):
    """Etkazuvchiga HAQIQATDA to'langan / kassadan chiqqan summa.

    MUHIM: `UNPAID` holatida hali kassadan bir tiyin ham chiqmagan — shuning
    uchun None qaytariladi (Expense yozilmaydi). Avval bu holatda ham to'liq
    summa chiqim sifatida yozilardi — bu kassa balansini haqiqiy pul
    chiqmasdan turib minusga tushirib yuborardi (kutayotgan/to'lanmagan
    importlar ko'payishi bilan balans sun'iy ravishda pasayardi)."""
    total = zakaz.total
    if total is None or total <= 0:
        return None
    if zakaz.payment_status == Zakaz.PAID:
        return total
    if zakaz.payment_status == Zakaz.PREPAID:
        paid = Decimal(str(zakaz.paid_amount or 0))
        return paid if paid > 0 else None
    # To'lanmagan — hali kassadan pul chiqmagan, chiqim yozilmaydi
    return None


def sync_zakaz_expense(zakaz, user=None):
    """
    Import (manual zakaz) etkazuvchi to'lovini kassadan CHIQIM sifatida yozadi.
    payment_status + paid_amount bo'yicha Expense yaratadi/yangilaydi.
    """
    if zakaz.zakaz_type != Zakaz.MANUAL:
        return None

    target = _target_expense_amount(zakaz)
    supplier = (zakaz.supplier or '').strip()
    product_name = str(zakaz.product) if zakaz.product_id else 'Mahsulot'
    comment = f'Import #{zakaz.pk} — {product_name}'
    if supplier:
        comment = f'{comment} ({supplier})'

    with transaction.atomic():
        # Eski xato: import Payment (kirim) bo'lmasligi kerak
        Payment.objects.filter(zakaz=zakaz).delete()

        if target is None:
            Expense.objects.filter(zakaz=zakaz).delete()
            return None

        expense_type, _ = ExpenseType.objects.get_or_create(
            code=ExpenseType.IMPORT,
            defaults={'name': 'Import rasxod'},
        )
        sub_type, _ = ExpenseSubType.objects.get_or_create(
            expense_type=expense_type,
            name='Import',
        )

        expense, _created = Expense.objects.get_or_create(
            zakaz=zakaz,
            defaults={
                'expense_type': expense_type,
                'sub_type': sub_type,
                'amount': target,
                'currency': zakaz.currency,
                'date': timezone.localdate(),
                'responsible': user if getattr(user, 'is_authenticated', False) else None,
                'comment': comment,
            },
        )
        updates = []
        if expense.amount != target:
            expense.amount = target
            updates.append('amount')
        if expense.currency != zakaz.currency:
            expense.currency = zakaz.currency
            updates.append('currency')
        if expense.comment != comment:
            expense.comment = comment
            updates.append('comment')
        if expense.responsible_id is None and getattr(user, 'is_authenticated', False):
            expense.responsible = user
            updates.append('responsible')
        if updates:
            expense.save(update_fields=updates)

    return expense


# Orqaga moslik — eski import nomi
sync_zakaz_payment = sync_zakaz_expense
