from decimal import Decimal

from django.conf import settings
from django.db.models import (CharField, ForeignKey, CASCADE, PROTECT, SET_NULL,
                              PositiveIntegerField, DecimalField, TextField)

from apps.common.models import TimeStampedModel


class ServerConfiguration(TimeStampedModel):
    """
    Konfigurator — bazadagi mavjud tovarlardan (Product) server/to'plam
    yig'ish va umumiy narxini hisoblash. Admin va Sales foydalanadi;
    Sales faqat o'zi yaratgan konfiguratsiyalarni ko'radi.
    """
    name        = CharField(max_length=255, blank=True, default='',
                            help_text="Konfiguratsiya nomi (masalan: \"Mijoz X uchun server\")")
    client      = ForeignKey('clients.Client', on_delete=SET_NULL,
                             null=True, blank=True, related_name='configurations')
    created_by  = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                             null=True, blank=True, related_name='configurations')
    comment     = TextField(blank=True, null=True)

    class Meta:
        db_table            = 'configurator_configuration'
        ordering            = ('-created_at',)
        verbose_name        = 'Konfiguratsiya'
        verbose_name_plural = 'Konfiguratsiyalar'

    def __str__(self):
        return self.name or f'Konfiguratsiya #{self.pk}'

    @property
    def total(self):
        return sum((i.subtotal for i in self.items.all()), Decimal('0'))


class ConfigurationItem(TimeStampedModel):
    configuration = ForeignKey(ServerConfiguration, on_delete=CASCADE, related_name='items')
    product       = ForeignKey('warehouse.Product', on_delete=PROTECT,
                               related_name='configuration_items')
    quantity      = PositiveIntegerField(default=1)
    unit_price    = DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                 help_text="Qo'shilgan paytdagi sotuv narxi (snapshot); "
                                           "bo'sh bo'lsa mahsulotning joriy narxidan olinadi")

    class Meta:
        db_table            = 'configurator_configuration_item'
        ordering            = ('id',)
        verbose_name        = 'Konfiguratsiya qatori'
        verbose_name_plural = 'Konfiguratsiya qatorlari'

    def __str__(self):
        return f'{self.product.name} x{self.quantity}'

    def save(self, *args, **kwargs):
        if self.unit_price is None and self.product_id:
            self.unit_price = self.product.selling_price
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        if self.unit_price is None:
            return Decimal('0')
        return self.unit_price * self.quantity
