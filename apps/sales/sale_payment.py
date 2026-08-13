from decimal import Decimal

from apps.cash.models import Payment


def sync_sale_payment(sale, user=None):
    """
    Sotuv tushumini kassaga yozadi (Payment + tranzaksiya).
    Sotuv yaratilganda to'liq summa kassaga kiradi.
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
        updates = []
        if payment.client_id != sale.client_id:
            payment.client = sale.client
            updates.append('client')
        if payment.comment != comment:
            payment.comment = comment
            updates.append('comment')
        if updates:
            payment.save(update_fields=updates)

    current = payment.paid_amount or Decimal('0')
    if total > current:
        payment.add_payment(
            total - current,
            user=user,
            comment='Sotuv tushumi',
        )
    return payment
