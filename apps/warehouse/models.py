from decimal import Decimal

from django.db import models
from django.db.models import (CharField, ForeignKey, CASCADE, SET_NULL,
                              PositiveIntegerField, DecimalField, DateTimeField, Sum)
from mptt.models import MPTTModel, TreeForeignKey

from apps.common.models import TimeStampedModel

STATUS_IN_STOCK   = 'in_stock'
STATUS_LOW_STOCK  = 'low_stock'
STATUS_OUT        = 'out_of_stock'
# Qoldiq 0, lekin faol (hali qabul qilinmagan) Zakaz/Kirim bor — "Yo'lda"
STATUS_ON_THE_WAY = 'on_the_way'


class VatPercent(models.TextChoices):
    NONE = 'none', 'QQS siz'
    ZERO = '0', '0%'
    SIX = '6', '6%'
    TWELVE = '12', '12%'
    FIFTEEN = '15', '15%'


class ProductUnit(models.TextChoices):
    PIECE = 'piece', 'dona'
    KG = 'kg', 'kg'
    GRAM = 'gram', 'gram'
    TON = 'ton', 'tonna'
    METER = 'meter', 'm'
    CM = 'cm', 'sm'
    MM = 'mm', 'mm'
    LITER = 'liter', 'l'
    ML = 'ml', 'ml'
    SQM = 'sqm', 'm²'
    CBM = 'cbm', 'm³'
    BARREL = 'barrel', 'bochka'
    BOX = 'box', 'quti'
    PACK = 'pack', 'pachka'
    SET = 'set', 'komplekt'
    PAIR = 'pair', 'juft'
    ROLL = 'roll', 'rulon'
    BAG = 'bag', 'qop'
    SHEET = 'sheet', 'list'


class ProductOrigin(models.TextChoices):
    WAREHOUSE = 'warehouse', 'Ombor'
    IMPORT = 'import', 'Import'


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
    serial_number = CharField(max_length=255, unique=True, blank=True, null=True,
                              help_text='Seriya raqami — qo‘lda kiritiladi, '
                                        'avtomatik yaratilmaydi')
    barcode       = CharField(max_length=128, blank=True, null=True,
                              help_text='Shtrix kod')
    purchase_price = DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                  help_text='Operator tomonidan kiritilmaydi — Management belgilaydi')
    selling_price  = DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                  help_text='Sotuv/ketish narxi — Management belgilaydi')
    delivery_price = DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                  help_text='Yetkazish narxi (birlik)')
    vat_percent    = CharField(max_length=8, choices=VatPercent.choices,
                               default=VatPercent.NONE,
                               help_text='QQS foizi')
    source         = CharField(max_length=255, blank=True, null=True,
                               help_text='Qayerdan keldi (yetkazuvchi/manzil)')
    unit           = CharField(max_length=20, choices=ProductUnit.choices,
                               default=ProductUnit.PIECE,
                               help_text='O‘lchov birligi')
    min_quantity   = PositiveIntegerField(default=5,
                                          help_text='Minimal qoldiq chegarasi (notification uchun)')
    origin         = CharField(max_length=20, choices=ProductOrigin.choices,
                               default=ProductOrigin.WAREHOUSE,
                               help_text='Mahsulot qayerdan yaratilgan: '
                                         'ombor yoki import (buyurtma/import '
                                         'qatoridan avtomatik)')

    class Meta:
        db_table = 'warehouse_product'
        ordering = ('-created_at',)
        verbose_name = 'Mahsulot'
        verbose_name_plural = 'Mahsulotlar'

    def __str__(self):
        if self.serial_number:
            return f'{self.name} ({self.serial_number})'
        return self.name

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
    def pending_import_quantity(self):
        """Yo'ldagi (hali qabul qilinmagan) import miqdori.

        Buyurtma yoki import ochilgan, lekin tovar omborga hali kelmagan —
        qoldiq 0 bo'lsa ham nechta dona kutilayotgani ko'rinib tursin.
        """
        from apps.orders.models import Zakaz
        # prefetch_related('zakazlar') bo'lsa qo'shimcha so'rov ketmasin
        return sum(
            max(zakaz.quantity - (zakaz.received_qty or 0), 0)
            for zakaz in self.zakazlar.all()
            if zakaz.status in Zakaz.ACTIVE_STATUSES
        )

    @property
    def stock_status(self):
        avail = self.available_quantity
        if avail <= 0:
            # Qoldiq yo'q, lekin yo'lda (faol Zakaz/Kirim) miqdor bor —
            # "tugagan" emas, "Yo'lda" deb ko'rsatiladi
            if self.pending_import_quantity > 0:
                return STATUS_ON_THE_WAY
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
