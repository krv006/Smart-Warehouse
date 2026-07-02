from django.conf import settings
from django.db import transaction
from django.db.models import (
    CharField, ForeignKey, PROTECT, SET_NULL,
    PositiveIntegerField, DateField, TextField,
)
from django.db.models import F

from apps.common.models import TimeStampedModel


# ── Order (Mijoz buyurtmasi / bron) ──────────────────────────────────────────

class Order(TimeStampedModel):
    """
    Mijoz buyurtmasi va bron tizimi.

    Yaratilganda mavjud (bron bo'lmagan) qoldiqdan bron ajratiladi.
    Agar available_quantity == 0 bo'lsa — Order yaratib bo'lmaydi,
    o'rniga Zakaz berish kerak.

    Holat oqimi:
        pending → (qoldiq kelganda) → partial / reserved → fulfilled
        har qanday → cancelled
    """
    PENDING   = 'pending'
    PARTIAL   = 'partial'
    RESERVED  = 'reserved'
    FULFILLED = 'fulfilled'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = (
        (PENDING,   'Zakaz (kutilmoqda)'),
        (PARTIAL,   'Qisman bron'),
        (RESERVED,  'To\'liq bron'),
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
        db_table            = 'orders_order'
        ordering            = ('due_date', '-created_at')
        verbose_name        = 'Buyurtma'
        verbose_name_plural = 'Buyurtmalar'

    def __str__(self):
        client = str(self.client) if self.client else '—'
        return f'#{self.pk} {self.product.name} x{self.quantity} [{self.get_status_display()}] → {client}'

    @property
    def backorder_qty(self):
        """Hali bronlanmagan, kelishi kutilayotgan miqdor."""
        return max(0, self.quantity - self.reserved_qty)

    @transaction.atomic
    def reserve(self):
        """Ombordagi mavjud qoldiqdan FIFO tartibida bron ajratadi."""
        from apps.warehouse.models import Stock
        still_needed = self.quantity - self.reserved_qty
        if still_needed <= 0:
            return

        for stock in (Stock.objects
                      .select_for_update()
                      .filter(product=self.product, quantity__gt=0)
                      .order_by('id')):
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
        self._sync_status()
        self.save(update_fields=['reserved_qty', 'status'])

    @transaction.atomic
    def release(self):
        """Bron bo'shatadi (bekor qilish yoki fulfill uchun)."""
        from apps.warehouse.models import Stock
        to_release = self.reserved_qty
        if to_release <= 0:
            return

        for stock in (Stock.objects
                      .select_for_update()
                      .filter(product=self.product, reserved_quantity__gt=0)
                      .order_by('id')):
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
        Yetkazildi: bron qilingan miqdorni ham quantity, ham reserved_quantity
        dan ayiradi. Boshqa pending orderlarga avtomatik bron qayta ajratiladi.
        """
        from apps.warehouse.models import Stock
        remaining = self.reserved_qty
        if remaining <= 0:
            return

        for stock in (Stock.objects
                      .select_for_update()
                      .filter(product=self.product, reserved_quantity__gt=0)
                      .order_by('id')):
            take = min(min(stock.reserved_quantity, stock.quantity), remaining)
            stock.quantity          = F('quantity') - take
            stock.reserved_quantity = F('reserved_quantity') - take
            stock.save(update_fields=['quantity', 'reserved_quantity'])
            remaining -= take
            if remaining <= 0:
                break

        self.reserved_qty = 0
        self.status = self.FULFILLED
        self.save(update_fields=['reserved_qty', 'status'])
        allocate_pending_orders(self.product)

    def _sync_status(self):
        if self.reserved_qty >= self.quantity:
            self.status = self.RESERVED
        elif self.reserved_qty > 0:
            self.status = self.PARTIAL
        else:
            self.status = self.PENDING


# ── Zakaz (Etkazuvchidan buyurtma) ───────────────────────────────────────────

class Zakaz(TimeStampedModel):
    """
    Etkazuvchidan mahsulot zakaz qilish (procurement order).

    Yaratish: operator yoki manager (status avtomatik 'new').
    Status o'zgartirish: FAQAT manager.

    Holat oqimi:
        new → confirmed → ordered → received → (avtomatik ombor to'ldiriladi)
        har qanday → cancelled

    status=received bo'lganda:
        - received_qty omborga qo'shiladi
        - pending/partial orderlarga avtomatik bron ajratiladi
    """
    NEW       = 'new'
    CONFIRMED = 'confirmed'
    ORDERED   = 'ordered'
    RECEIVED  = 'received'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = (
        (NEW,       'Yangi'),
        (CONFIRMED, 'Tasdiqlandi'),
        (ORDERED,   'Etkazuvchiga yuborildi'),
        (RECEIVED,  'Qabul qilindi'),
        (CANCELLED, 'Bekor qilindi'),
    )

    product            = ForeignKey('warehouse.Product', on_delete=PROTECT,
                                    related_name='zakazlar')
    quantity           = PositiveIntegerField(help_text='Zakaz qilingan miqdor')
    received_qty       = PositiveIntegerField(
                             default=0,
                             help_text='Qabul qilingan miqdor (status=received da kiritiladi)')
    supplier           = CharField(max_length=255, blank=True, null=True,
                                   help_text='Etkazuvchi nomi / manzili')
    status             = CharField(max_length=12, choices=STATUS_CHOICES, default=NEW)
    expected_date      = DateField(null=True, blank=True,
                                   help_text='Kutilayotgan kelish sanasi')
    warehouse_location = CharField(max_length=255, blank=True, null=True,
                                   help_text='Qabul qilinganda joylashtiriladi')
    created_by         = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                                    null=True, blank=True, related_name='zakazlar',
                                    verbose_name='Yaratuvchi')
    comment            = TextField(blank=True, null=True)

    class Meta:
        db_table            = 'orders_zakaz'
        ordering            = ('-created_at',)
        verbose_name        = 'Zakaz'
        verbose_name_plural = 'Zakazlar'

    def __str__(self):
        return (f'Zakaz #{self.pk} — {self.product.name} x{self.quantity} '
                f'[{self.get_status_display()}]')

    @transaction.atomic
    def receive(self):
        """
        Zakaz qabul qilindi:
        1. received_qty (yoki quantity) ni omborga qo'shadi.
        2. Pending/partial orderlarga avtomatik bron ajratadi.
        3. Low-stock bildirishnomalarini tekshiradi.
        """
        from apps.warehouse.models import Stock
        from apps.notifications.models import Notification

        qty = self.received_qty if self.received_qty > 0 else self.quantity
        loc = self.warehouse_location or 'Asosiy ombor'

        stock, _ = Stock.objects.select_for_update().get_or_create(
            product=self.product,
            warehouse_location=loc,
            defaults={'quantity': 0, 'reserved_quantity': 0},
        )
        stock.quantity = F('quantity') + qty
        stock.save(update_fields=['quantity'])

        # Pending orderlarga bron ajrat
        allocate_pending_orders(self.product)

        # Low-stock bildirishnomani yop (agar qoldiq etarli bo'lsa)
        self.product.refresh_from_db()
        if self.product.available_quantity > self.product.min_quantity:
            Notification.resolve_low_stock_notifications(self.product)


# ── Yordamchi funksiya ────────────────────────────────────────────────────────

def allocate_pending_orders(product):
    """
    Mahsulot qoldig'i o'zgarganda pending/partial buyurtmalarga
    due_date tartibida (eng yaqin deadline birinchi) bron ajratadi.
    """
    pending = (
        Order.objects
        .filter(product=product, status__in=(Order.PENDING, Order.PARTIAL))
        .order_by('due_date', 'created_at')
        .select_for_update()
    )
    for order in pending:
        order.reserve()
