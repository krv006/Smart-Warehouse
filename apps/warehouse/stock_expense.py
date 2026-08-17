"""Omborga kirim qilingan mahsulot narxini kassadan chiqim sifatida yozish."""
from decimal import Decimal

from django.utils import timezone

from apps.expenses.models import Expense, ExpenseSubType, ExpenseType


def record_stock_in_expense(product, quantity, *, user=None, asos=None,
                            contract_number=None, faktura=None):
    """
    Kelish narxi (`purchase_price`) belgilangan mahsulot omborga kirim
    qilinganda — kirim summasi (narx × miqdor) kassadan CHIQIM sifatida
    alohida hujjatli `Expense` yozuvi bo'lib yoziladi (Zakaz/import
    oqimidagi `sync_zakaz_expense` bilan bir xil g'oyada). Kelish narxi
    kiritilmagan bo'lsa (operator ko'rmaydi/kiritmaydi) — hisoblab
    bo'lmagani uchun chiqim yozilmaydi.
    """
    price = product.purchase_price
    if price is None or price <= 0 or quantity <= 0:
        return None

    amount = (Decimal(price) * Decimal(quantity)).quantize(Decimal('0.01'))

    expense_type, _ = ExpenseType.objects.get_or_create(
        code=ExpenseType.IMPORT,
        defaults={'name': 'Import rasxod'},
    )
    sub_type, _ = ExpenseSubType.objects.get_or_create(
        expense_type=expense_type,
        name='Ombor kirim',
    )

    comment = f'Kirim — {product.name} ({quantity} dona)'
    if asos:
        comment += f' — {asos}'
    if contract_number:
        comment += f' — shartnoma №{contract_number}'
    if faktura:
        comment += f' — faktura {faktura}'

    return Expense.objects.create(
        expense_type=expense_type,
        sub_type=sub_type,
        amount=amount,
        currency=Expense.UZS,
        date=timezone.localdate(),
        responsible=user if getattr(user, 'is_authenticated', False) else None,
        comment=comment,
    )
