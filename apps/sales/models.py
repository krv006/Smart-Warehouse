from django.db.models import (ForeignKey, PROTECT, DecimalField,
                              PositiveIntegerField, CharField, TextField, DateField)
from apps.common.models import TimeStampedModel
from apps.warehouse.models import Product


class Sale(TimeStampedModel):
    product     = ForeignKey(Product, on_delete=PROTECT, related_name='sales')
    quantity    = PositiveIntegerField()
    sold_price  = DecimalField(max_digits=14, decimal_places=2,
                               help_text='Birlik uchun sotuv narxi')
    sold_to     = CharField(max_length=255, blank=True, null=True)
    destination = CharField(max_length=255, blank=True, null=True,
                            help_text='Qayerga ketdi (shahar/manzil)')
    sold_date   = DateField()
    comment     = TextField(blank=True, null=True)

    class Meta:
        db_table = 'sales_sale'
        ordering = ('-sold_date', '-created_at')
        verbose_name = 'Sotuv'
        verbose_name_plural = 'Sotuvlar'

    def __str__(self):
        return f'{self.product.name} x{self.quantity} → {self.sold_to or "—"}'

    @property
    def total_amount(self):
        return self.sold_price * self.quantity

    @property
    def profit(self):
        return (self.sold_price - self.product.purchase_price) * self.quantity
