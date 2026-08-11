from django.db.models import (ForeignKey, PROTECT, SET_NULL, DecimalField,
                              PositiveIntegerField, CharField, TextField, DateField)
from apps.common.models import TimeStampedModel
from apps.warehouse.models import Product


class Sale(TimeStampedModel):
    product     = ForeignKey(Product, on_delete=PROTECT, related_name='sales')
    client      = ForeignKey('clients.Client', on_delete=SET_NULL,
                             null=True, blank=True, related_name='sales')
    quantity    = PositiveIntegerField()
    sold_price  = DecimalField(max_digits=14, decimal_places=2,
                               help_text='Birlik uchun sotuv narxi')
    purchase_price = DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Sotuv paytidagi tannarx (snapshot) — keyin mahsulot '
                  'narxi o\'zgarsa ham tarixiy profit o\'zgarmaydi')
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

    def save(self, *args, **kwargs):
        # Tannarx sotuv paytida bir marta muhrlanadi
        if self.purchase_price is None and self.product_id:
            self.purchase_price = self.product.purchase_price
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                kwargs['update_fields'] = set(update_fields) | {'purchase_price'}
        super().save(*args, **kwargs)

    @property
    def total_amount(self):
        return self.sold_price * self.quantity

    @property
    def profit(self):
        # Eski (snapshot'siz) yozuvlar uchun mahsulotning joriy narxiga qaytamiz
        cost = (self.purchase_price if self.purchase_price is not None
                else self.product.purchase_price)
        if cost is None:
            return None
        return (self.sold_price - cost) * self.quantity
