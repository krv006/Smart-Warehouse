from decimal import Decimal

from django.db import transaction

from apps.cash.models import Payment


@transaction.atomic
def sync_sale_payment(sale, user=None):
    """
    Sotuv tushumini kassaga yozadi/yangilaydi (Payment + tranzaksiya).

    Sotuv yaratilganda to'liq summa darhol kassaga kiradi (sotuv har doim
    to'liq to'langan hisoblanadi — buyurtmadagi kabi qisman to'lov yo'q).
    Sotuv keyinroq tahrirlansa (narx yoki miqdor o'zgarsa) — kassadagi
    summa ham shu bo'yicha qayta sinxronlanadi: oshgan farq qo'shimcha
    tranzaksiya, kamaygan farq esa manfiy korrektsiya tranzaksiyasi
    bo'lib yoziladi (buyurtma tahriridagi bilan bir xil qoida).
    """
    total = sale.total_amount
    if total is None or total <= 0:
        return None

    product_name = str(sale.product) if sale.product_id else 'Mahsulot'
    comment = f'Sotuv #{sale.pk} — {product_name}'

    payment = Payment.objects.filter(sale=sale).order_by('id').first()
    if payment is None:
        payment = Payment.objects.create(
            sale=sale,
            client=sale.client,
            total_amount=total,
            paid_amount=Decimal('0'),
            currency=Payment.UZS,
            comment=comment,
        )
    else:
        payment.client = sale.client
        payment.comment = comment
        payment.save()  # total_amount/commission sotuvdan qayta hisoblanadi

    # Qatorni qulflab QAYTA o'qiymiz — sotuv bir vaqtda ikki marta
    # tahrirlansa (yoki tahrir bilan qo'lda kassa tuzatishi to'qnashsa),
    # ikkalasi ham bir xil eski paid_amount'ni ko'rib, ikkalasi ham
    # noto'g'ri farq yozib qo'ymasin (add_payment() ijobiy holatda buni
    # allaqachon qiladi — manfiy tuzatish uchun ham xuddi shunday kerak).
    locked = Payment.objects.select_for_update().get(pk=payment.pk)
    current = locked.paid_amount or Decimal('0')
    diff = total - current
    if diff > 0:
        locked.add_payment(diff, user=user, comment='Sotuv tushumi')
    elif diff < 0:
        locked.transactions.create(
            amount=diff, received_by=user,
            comment='To\'lov korrektsiyasi (sotuv tahriri)')
        locked.paid_amount = total
        locked.save()
    return locked
