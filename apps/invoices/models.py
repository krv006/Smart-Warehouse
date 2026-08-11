import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import (UUIDField, CharField, TextField, ForeignKey,
                              CASCADE, SET_NULL, DateField, BooleanField,
                              PositiveIntegerField, DecimalField)

from apps.common.models import TimeStampedModel
from apps.warehouse.models import ProductUnit


class VatPercent(models.TextChoices):
    NONE = 'none', 'QQS siz'
    ZERO = '0', '0%'
    SIX = '6', '6%'
    TWELVE = '12', '12%'
    FIFTEEN = '15', '15%'

    @classmethod
    def rate(cls, value):
        if value in (cls.NONE, '', None):
            return Decimal('0')
        try:
            return Decimal(value)
        except Exception:
            return Decimal('0')


class DocumentType(models.TextChoices):
    CONTRACT_SK = 'contract_sk', 'Shartnoma (SK)'
    INVOICE = 'invoice', 'Hisob-faktura'
    ACT = 'act', 'Dalolatnoma'


class ElectronicInvoice(TimeStampedModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_type = CharField(max_length=32, choices=DocumentType.choices,
                              default=DocumentType.CONTRACT_SK)
    name = CharField(max_length=512, blank=True, default='',
                     verbose_name='Hujjat nomi')
    contract_number = CharField(max_length=100, blank=True, default='',
                                verbose_name='Shartnoma raqami')
    place_signed = CharField(max_length=255, blank=True, default='',
                             verbose_name='Tuzilgan joyi')
    contract_date = DateField(null=True, blank=True, verbose_name='Tuzilgan sana')
    valid_until = DateField(null=True, blank=True,
                            verbose_name='Amal qilish muddati')
    client = ForeignKey('clients.Client', on_delete=SET_NULL,
                        null=True, blank=True, related_name='invoices')
    reverse_calculation = BooleanField(default=False,
                                       verbose_name='Teskari hisob')
    content_title = CharField(max_length=512, blank=True, default='',
                              verbose_name='Mazmun sarlavhasi')
    content_body = TextField(blank=True, default='',
                             verbose_name='Mazmun matni')
    comment = TextField(blank=True, null=True)
    created_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                            null=True, blank=True, related_name='invoices')

    class Meta:
        db_table = 'invoices_electronic_invoice'
        ordering = ('-created_at',)
        verbose_name = 'Elektron faktura'
        verbose_name_plural = 'Elektron fakturalar'

    def __str__(self):
        return self.contract_number or self.name or str(self.id)

    @property
    def total_delivery(self):
        return sum((line.delivery_amount or 0) for line in self.lines.all())

    @property
    def total_vat(self):
        return sum((line.vat_amount or 0) for line in self.lines.all())

    @property
    def grand_total(self):
        return sum((line.total_amount or 0) for line in self.lines.all())


class InvoiceLineItem(TimeStampedModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = ForeignKey(ElectronicInvoice, on_delete=CASCADE,
                           related_name='lines')
    line_number = PositiveIntegerField(default=1)
    product = ForeignKey('warehouse.Product', on_delete=SET_NULL,
                         null=True, blank=True, related_name='invoice_lines')
    product_name = CharField(max_length=255, blank=True, default='')
    identification_code = CharField(max_length=255, blank=True, default='',
                                    verbose_name='Identifikatsiya kodi')
    barcode = CharField(max_length=128, blank=True, default='',
                        verbose_name='Shtrix kod')
    unit = CharField(max_length=20, choices=ProductUnit.choices,
                     default=ProductUnit.PIECE)
    quantity = PositiveIntegerField(default=1)
    unit_price = DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    delivery_amount = DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                   verbose_name='Yetkazish narxi')
    vat_percent = CharField(max_length=8, choices=VatPercent.choices,
                              default=VatPercent.NONE)
    vat_amount = DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_amount = DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    class Meta:
        db_table = 'invoices_line_item'
        ordering = ('line_number', 'id')
        verbose_name = 'Faktura qatori'
        verbose_name_plural = 'Faktura qatorlari'

    def __str__(self):
        return f'{self.line_number}. {self.product_name or self.product}'

    @staticmethod
    def compute_line(quantity, unit_price, vat_percent_value, *,
                     delivery_amount=None, vat_amount=None, total_amount=None,
                     reverse=False):
        qty = Decimal(quantity or 0)
        price = Decimal(unit_price or 0)
        vat_rate = VatPercent.rate(vat_percent_value)

        if reverse:
            delivery = Decimal(delivery_amount or 0)
            vat = Decimal(vat_amount or 0)
            total = Decimal(total_amount or 0)
            if not total and delivery:
                total = delivery + vat
            return delivery, vat, total

        delivery = (qty * price).quantize(Decimal('0.01'))
        vat = (delivery * vat_rate / Decimal('100')).quantize(Decimal('0.01'))
        total = (delivery + vat).quantize(Decimal('0.01'))
        return delivery, vat, total
