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
        cls.objects.filter(product=product, is_read=False,
                           title="Summasi kiritilmagan!").update(is_read=True)

    @classmethod
    def notify_low_stock(cls, product):
        """Mavjud qoldiq min_quantity dan pasayganda Management userlariga bildirishnoma."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        avail = product.available_quantity
        if avail <= 0:
            return
        title   = "Qoldiq kam!"
        unit = product.get_unit_display()
        message = (
            f'"{product.name}" ({product.serial_number}) mahsuloti qoldig\'i '
            f'minimal chegaradan ({product.min_quantity} {unit}) pastga tushdi. '
            f'Hozirgi mavjud qoldiq: {avail} {unit}.'
        )
        managers = User.objects.filter(role=User.MANAGEMENT, is_active=True)
        for manager in managers:
            exists = cls.objects.filter(
                recipient=manager, product=product, is_read=False, title=title
            ).exists()
            if not exists:
                cls.objects.create(recipient=manager, product=product,
                                   title=title, message=message)

    @classmethod
    def resolve_low_stock_notifications(cls, product):
        """Mahsulot qoldig'i min_quantity dan yuqoriga chiqsa, bildirishnomalarni yopadi."""
        cls.objects.filter(product=product, is_read=False,
                           title="Qoldiq kam!").update(is_read=True)

    @classmethod
    def check_product_stock_level(cls, product):
        """Bron/sotuv/kirimdan keyin mavjud qoldiqni tekshiradi."""
        avail = product.available_quantity
        if avail <= 0:
            return
        if avail <= product.min_quantity:
            cls.notify_low_stock(product)
        else:
            cls.resolve_low_stock_notifications(product)

    @classmethod
    def notify_delayed_import(cls, zakaz):
        """Etkazuvchidan kelishi kutilgan import kechikkan bo'lsa barcha faol foydalanuvchilarga bildirishnoma."""
        from django.contrib.auth import get_user_model
        if not zakaz.expected_date or zakaz.status in (zakaz.RECEIVED, zakaz.CANCELLED):
            return
        if zakaz.expected_date >= zakaz.created_at.date():
            return
        User = get_user_model()
        recipients = User.objects.filter(is_active=True)
        title = "Import kechikdi!"
        message = (
            f'"{zakaz.product.name}" mahsuloti uchun import kelishi kutilgan sana '
            f'{zakaz.expected_date} bo\'lib o\'tgan, lekin hali qabul qilinmagan. '
            f'Qolgan miqdor: {zakaz.quantity - zakaz.received_qty} dona.'
        )
        for recipient in recipients:
            exists = cls.objects.filter(
                recipient=recipient, product=zakaz.product, is_read=False, title=title
            ).exists()
            if not exists:
                cls.objects.create(recipient=recipient, product=zakaz.product,
                                   title=title, message=message)

    @classmethod
    def resolve_delayed_import_notifications(cls, zakaz):
        cls.objects.filter(product=zakaz.product, is_read=False,
                           title="Import kechikdi!").update(is_read=True)


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
