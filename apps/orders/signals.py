"""
Kassa ↔ Buyurtma avtomatik sinxronlash (background himoya).

Buyurtma yoki uning qatori QANDAY YO'L bilan o'zgarmasin yoki
o'chirilmasin (API, admin panel, boshqa kod) — kassadagi to'lov
yozuvining jami summasi, muddati, mijozi va statusi darhol qayta
hisoblanadi. Kassa hech qachon eski ma'lumotda qolib ketmaydi.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.orders.models import Order, OrderItem


def _resync_payment(order):
    """Buyurtmaga bog'liq kassa yozuvini buyurtmadan qayta to'ldiradi."""
    from apps.cash.models import Payment
    payment = (Payment.objects
               .filter(order_id=order.pk)
               .order_by('id')
               .first())
    if payment is None:
        return
    payment.client   = order.client
    payment.due_date = order.due_date
    # total buyurtmadan qayta hisoblanadi, status avtomatik sinxronlanadi
    payment.save()


@receiver(post_save, sender=OrderItem)
@receiver(post_delete, sender=OrderItem)
def sync_payment_on_item_change(sender, instance, **kwargs):
    """Qator o'zgardi/o'chirildi → kassadagi jami summa moslashadi."""
    order_id = instance.order_id
    if not order_id:
        return
    # Buyurtma o'chirilayotgan (cascade) paytda hech narsa qilmaymiz
    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return
    _resync_payment(order)


@receiver(post_save, sender=Order)
def sync_payment_on_order_change(sender, instance, **kwargs):
    """
    Buyurtma sarlavhasi o'zgardi (muddat, mijoz, holat) → kassadagi
    to'lov yozuvi ham moslashadi. Payment.save() buyurtmani qayta
    saqlamaydi, shuning uchun rekursiya bo'lmaydi.
    """
    _resync_payment(instance)
