from django.db.models import (CharField, ForeignKey, CASCADE, SET_NULL,
                              PositiveIntegerField, DecimalField, DateTimeField, Sum)
from mptt.models import MPTTModel, TreeForeignKey

from apps.common.models import TimeStampedModel

STATUS_IN_STOCK  = 'in_stock'
STATUS_LOW_STOCK = 'low_stock'
STATUS_OUT       = 'out_of_stock'


class Category(MPTTModel):
    name   = CharField(max_length=255)
    parent = TreeForeignKey('self', on_delete=CASCADE,
                            null=True, blank=True, related_name='children')

    class MPTTMeta:
        order_insertion_by = ('name',)

    class Meta:
        db_table = 'warehouse_category'
        verbose_name = 'Kategoriya'
        verbose_name_plural = 'Kategoriyalar'

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    category      = TreeForeignKey(Category, on_delete=SET_NULL,
                                   null=True, blank=True, related_name='products')
    name          = CharField(max_length=255)
    model         = CharField(max_length=255, blank=True, null=True)
    serial_number = CharField(max_length=255, unique=True)
    purchase_price = DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                  help_text='Operator tomonidan kiritilmaydi — Management belgilaydi')
    selling_price  = DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                  help_text='Sotuv/ketish narxi — Management belgilaydi')
    source         = CharField(max_length=255, blank=True, null=True,
                               help_text='Qayerdan keldi (yetkazuvchi/manzil)')
    min_quantity   = PositiveIntegerField(default=5,
                                          help_text='Minimal qoldiq chegarasi (notification uchun)')

    class Meta:
        db_table = 'warehouse_product'
        ordering = ('-created_at',)
        verbose_name = 'Mahsulot'
        verbose_name_plural = 'Mahsulotlar'

    def __str__(self):
        return f'{self.name} ({self.serial_number})'

    @property
    def quantity_in_stock(self):
        return self.stocks.aggregate(total=Sum('quantity'))['total'] or 0

    @property
    def reserved_quantity(self):
        return self.stocks.aggregate(total=Sum('reserved_quantity'))['total'] or 0

    @property
    def available_quantity(self):
        return self.quantity_in_stock - self.reserved_quantity

    @property
    def stock_status(self):
        avail = self.available_quantity
        if avail <= 0:
            return STATUS_OUT
        if avail <= self.min_quantity:
            return STATUS_LOW_STOCK
        return STATUS_IN_STOCK


class Stock(TimeStampedModel):
    product            = ForeignKey(Product, on_delete=CASCADE, related_name='stocks')
    quantity           = PositiveIntegerField(default=0)
    reserved_quantity  = PositiveIntegerField(default=0,
                                              help_text='Bron qilingan miqdor')
    warehouse_location = CharField(max_length=255)

    class Meta:
        db_table = 'warehouse_stock'
        ordering = ('product', 'warehouse_location')
        verbose_name = 'Qoldiq'
        verbose_name_plural = 'Qoldiqlar'
        unique_together = ('product', 'warehouse_location')

    def __str__(self):
        return f'{self.product.name} @ {self.warehouse_location}: {self.quantity}'
