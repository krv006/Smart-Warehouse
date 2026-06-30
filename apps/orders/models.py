from django.db import transaction
from django.db.models import (
    CharField, ForeignKey, PROTECT, SET_NULL,
    PositiveIntegerField, DateField, TextField,
)
from django.db.models import F

from apps.common.models import TimeStampedModel


class Order(TimeStampedModel):
    """
    Buyurtma / Bron tizimi.

    Holat logikasi:
      pending   — omborda yetarli qoldiq yo'q, zakaz kutilmoqda
      partial   — qisman bron (bir qismi omborda bron, qolgani zakaz)
      reserved  — to'liq bron (hammasi omborda ajratilgan)
      fulfilled — yetkazildi (sotuv amalga oshdi)
      cancelled — bekor qilindi
    """
    PENDING   = 'pending'
    PARTIAL   = 'partial'
    RESERVED  = 'reserved'
    FULFILLED = 'fulfilled'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = (
        (PENDING,   'Zakaz (kutilmoqda)'),
        (PARTIAL,   'Qisman bron'),
        (RESERVED,  'Bron qilingan'),
        (FULFILLED, 'Yetkazildi'),
        (CANCELLED, 'Bekor qilindi'),
    )

    client       = ForeignKey('clients.Client', on_delete=SET_NULL,
                              null=True, blank=True, related_name='orders')
    product      = ForeignKey('warehouse.Product', on_delete=PROTECT,
                              related_name='orders')
    quantity     = PositiveIntegerField(help_text='Buyurtma qilingan miqdor')
    reserved_qty = PositiveIntegerField(default=0,
                                        help_text='Hozirda bron qilingan miqdor')
    due_date     = DateField(null=True, blank=True,
                             help_text='Yetkazish muddati (deadline)')
    status       = CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    comment      = TextField(blank=True, null=True)

    class Meta:
        db_table        = 'orders_order'
        ordering        = ('due_date', '-created_at')
        verbose_name    = 'Buyurtma'
        verbose_name_plural = 'Buyurtmalar'

    def __str__(self):
        client = str(self.client) if self.client else '—'
        return f'#{self.pk} {self.product.name} x{self.quantity} [{self.status}] → {client}'

    @property
    def backorder_qty(self):
        """Hali bronlanmagan, kelishi kutilayotgan miqdor."""
        return self.quantity - self.reserved_qty

    @transaction.atomic
    def reserve(self):
        """
        Ombordagi mavjud (bron qilinmagan) miqdordan buyurtmaga bron ajratadi.
        FIFO tartibida stock yozuvlaridan ajratadi.
        """
        from apps.warehouse.models import Stock
        still_needed = self.quantity - self.reserved_qty
        if still_needed <= 0:
            return

        stocks = (
            Stock.objects
            .select_for_update()
            .filter(product=self.product, quantity__gt=0)
            .order_by('id')
        )
        for stock in stocks:
            available = stock.quantity - stock.reserved_quantity
            if available <= 0:
                continue
            take = min(available, still_needed)
            stock.reserved_quantity = F('reserved_quantity') + take
            stock.save(update_fields=['reserved_quantity'])
            still_needed -= take
            if still_needed <= 0:
                break

        self.reserved_qty = self.quantity - still_needed
        self._update_status()
        self.save(update_fields=['reserved_qty', 'status'])

    @transaction.atomic
    def release(self):
        """Bronni bo'shatadi (bekor qilish yoki fulfil qilinganda chaqiriladi)."""
        from apps.warehouse.models import Stock
        to_release = self.reserved_qty
        if to_release <= 0:
            return

        stocks = (
            Stock.objects
            .select_for_update()
            .filter(product=self.product, reserved_quantity__gt=0)
            .order_by('id')
        )
        for stock in stocks:
            take = min(stock.reserved_quantity, to_release)
            stock.reserved_quantity = F('reserved_quantity') - take
            stock.save(update_fields=['reserved_quantity'])
            to_release -= take
            if to_release <= 0:
                break

        self.reserved_qty = 0

    @transaction.atomic
    def fulfill(self):
        """
        Buyurtmani yetkazildi deb belgilaydi:
        - Bron qilingan miqdorni ombor qoldiq va reserved_quantity dan ayiradi
        - Statusi FULFILLED ga o'tkazadi
        """
        from apps.warehouse.models import Stock
        from django.db import transaction as tx
        remaining = self.reserved_qty
        if remaining <= 0:
            return

        stocks = (
            Stock.objects
            .select_for_update()
            .filter(product=self.product, reserved_quantity__gt=0)
            .order_by('id')
        )
        for stock in stocks:
            take = min(min(stock.reserved_quantity, stock.quantity), remaining)
            stock.quantity           = F('quantity') - take
            stock.reserved_quantity  = F('reserved_quantity') - take
            stock.save(update_fields=['quantity', 'reserved_quantity'])
            remaining -= take
            if remaining <= 0:
                break

        self.reserved_qty = 0
        self.status = self.FULFILLED
        self.save(update_fields=['reserved_qty', 'status'])

        # Yangi qoldiq bo'lishi mumkin emas, lekin boshqa pending orderlarga allocate
        allocate_pending_orders(self.product)

    def _update_status(self):
        if self.reserved_qty >= self.quantity:
            self.status = self.RESERVED
        elif self.reserved_qty > 0:
            self.status = self.PARTIAL
        else:
            self.status = self.PENDING


def allocate_pending_orders(product):
    """
    Mahsulot qoldig'i o'zgarganda (yangi kirim yoki fulfil)
    pending/partial orderlarni due_date bo'yicha tartiblab bron ajratadi.
    """
    pending_orders = (
        Order.objects
        .filter(product=product, status__in=(Order.PENDING, Order.PARTIAL))
        .order_by('due_date', 'created_at')
        .select_for_update()
    )
    for order in pending_orders:
        order.reserve()
