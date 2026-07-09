"""
Kassa ↔ Buyurtma avtomatik sinxronlash (background himoya).

Buyurtma qatori QANDAY YO'L bilan o'zgarmasin yoki o'chirilmasin
(API, admin panel, boshqa kod) — kassadagi to'lov yozuvining jami
summasi va statusi darhol qayta hisoblanadi. Kassa hech qachon
eski summada qolib ketmaydi.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.orders.models import Order, OrderItem


@receiver(post_save, sender=OrderItem)
@receiver(post_delete, sender=OrderItem)
def sync_payment_on_item_change(sender, instance, **kwargs):
    """Qator o'zgardi/o'chirildi → kassadagi jami summa moslashadi."""
    order_id = instance.order_id
    if not order_id:
        return
    # Buyurtma o'chirilayotgan (cascade) paytda hech narsa qilmaymiz
    if not Order.objects.filter(pk=order_id).exists():
        return
    from apps.cash.models import Payment
    payment = (Payment.objects
               .filter(order_id=order_id)
               .order_by('id')
               .first())
    if payment is None:
        return
    # total buyurtmadan qayta hisoblanadi, status avtomatik sinxronlanadi
    payment.save()
