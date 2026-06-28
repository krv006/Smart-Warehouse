from django.conf import settings
from django.db.models import (CharField, TextField, BooleanField,
                              ForeignKey, CASCADE, SET_NULL)

from apps.common.models import TimeStampedModel


class Notification(TimeStampedModel):
    """Saytdagi (in-app) bildirishnoma — bevosita foydalanuvchiga biriktirilgan."""
    recipient = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE,
                           related_name='notifications')
    product   = ForeignKey('warehouse.Product', on_delete=SET_NULL,
                           null=True, blank=True, related_name='price_notifications')
    title     = CharField(max_length=255)
    message   = TextField()
    is_read   = BooleanField(default=False)

    class Meta:
        db_table = 'notifications_notification'
        ordering = ('-created_at',)
        verbose_name = 'Bildirishnoma'
        verbose_name_plural = 'Bildirishnomalar'

    def __str__(self):
        return f'{self.title} → {self.recipient}'

    @classmethod
    def notify_missing_price(cls, product):
        """Berilgan mahsulot narxsiz bo'lsa, har bir Management userga bitta
        o'qilmagan bildirishnoma bor ekanligini ta'minlaydi (takror yaratmaydi)."""
        from django.contrib.auth import get_user_model
        if product.purchase_price is not None:
            return
        User = get_user_model()
        title   = "Summasi kiritilmagan!"
        message = (
            f'"{product.name}" ({product.serial_number}) mahsuloti uchun '
            f'summasini (kelish narxini) kiritmagansiz! Iltimos, kiriting.'
        )
        managers = User.objects.filter(role=User.MANAGEMENT, is_active=True)
        for manager in managers:
            exists = cls.objects.filter(
                recipient=manager, product=product, is_read=False
            ).exists()
            if not exists:
                cls.objects.create(recipient=manager, product=product,
                                   title=title, message=message)

    @classmethod
    def sync_missing_price_for_user(cls, user):
        """Login paytida chaqiriladi — narxi hali kiritilmagan barcha mahsulotlar
        uchun ushbu Management userga bildirishnoma borligini ta'minlaydi."""
        from apps.warehouse.models import Product
        if not getattr(user, 'is_management', False):
            return
        unpriced = Product.objects.filter(purchase_price__isnull=True)
        already_notified = set(
            cls.objects.filter(recipient=user, product__in=unpriced, is_read=False)
            .values_list('product_id', flat=True)
        )
        to_create = [
            cls(
                recipient=user, product=product,
                title="Summasi kiritilmagan!",
                message=(f'"{product.name}" ({product.serial_number}) mahsuloti uchun '
                         f'summasini (kelish narxini) kiritmagansiz! Iltimos, kiriting.'),
            )
            for product in unpriced if product.id not in already_notified
        ]
        if to_create:
            cls.objects.bulk_create(to_create)

    @classmethod
    def resolve_price_notifications(cls, product):
        """Mahsulotga narx kiritilganda, unga oid o'qilmagan bildirishnomalarni yopadi."""
        cls.objects.filter(product=product, is_read=False).update(is_read=True)


class TelegramSettings(TimeStampedModel):
    """Singleton — faqat bitta yozuv bo'lishi kerak (pk=1)."""
    bot_token  = CharField(max_length=255)
    chat_id    = CharField(max_length=100)
    is_active  = BooleanField(default=True)
    extra_note = TextField(blank=True, null=True)

    class Meta:
        db_table         = 'notifications_telegramsettings'
        verbose_name     = 'Telegram sozlamalari'
        verbose_name_plural = 'Telegram sozlamalari'

    def __str__(self):
        return f'TelegramSettings (chat: {self.chat_id})'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'bot_token': '', 'chat_id': ''})
        return obj
