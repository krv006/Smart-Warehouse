from django.conf import settings
from django.db import models, transaction
from django.db.models import (
    CharField, ForeignKey, CASCADE, PROTECT, SET_NULL,
    PositiveIntegerField, DecimalField, DateField, DateTimeField, TextField,
)
from django.db.models import F
from django.utils import timezone

from apps.common.models import TimeStampedModel


# ── Order (Mijoz buyurtmasi / bron) ──────────────────────────────────────────

class Order(TimeStampedModel):
    """
    Mijoz buyurtmasi va bron tizimi.

    1-etap: buyurtma olinadi (shartnoma raqami majburiy, oldindan to'lov saqlanadi).
    Yaratilganda mavjud (bron bo'lmagan) qoldiqdan bron ajratiladi. Yetishmagan
    (backorder) qism uchun **avtomatik Zakaz** ochiladi — o'sha shartnoma raqami asosida.

    Buyurtmani bir necha bor tahrirlash mumkin — har bir tahrir shartnoma raqami,
    asos va aniq sana/vaqt bilan tarixga (OrderHistory) yoziladi.

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

    client          = ForeignKey('clients.Client', on_delete=SET_NULL,
                                 null=True, blank=True, related_name='orders')
    product         = ForeignKey('warehouse.Product', on_delete=PROTECT,
                                 related_name='orders')
    quantity        = PositiveIntegerField(help_text='Buyurtma qilingan miqdor')
    unit_price      = DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                   help_text='Birlik narxi (sotuv narxi)')
    prepaid_amount  = DecimalField(max_digits=14, decimal_places=2, default=0,
                                   help_text='Oldindan to\'langan summa (qisman to\'lov)')
    contract_number = CharField(max_length=100, default='',
                                help_text='Shartnoma (dogovor) raqami — majburiy')
    contract_date   = DateField(default=timezone.localdate,
                                help_text='Shartnoma sanasi (Tashkent)')
    reserved_qty    = PositiveIntegerField(default=0,
                                           help_text='Hozirda bron qilingan miqdor')
    due_date        = DateField(null=True, blank=True,
                                help_text='Yetkazish muddati (deadline)')
    status          = CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    comment         = TextField(blank=True, null=True)

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

    @property
    def total(self):
        """Jami summa (unit_price * quantity)."""
        if self.unit_price is None:
            return None
        return self.unit_price * self.quantity

    @property
    def balance_due(self):
        """Qolgan to'lov (total − prepaid_amount)."""
        if self.total is None:
            return None
        return self.total - (self.prepaid_amount or 0)

    @property
    def has_active_zakaz(self):
        """
        Shu mahsulot uchun faol (yakunlanmagan) zakaz bormi?
        True bo'lsa — frontend "Zakaz berish" tugmasini yashiradi.
        """
        return self.product.zakazlar.filter(
            status__in=(Zakaz.NEW, Zakaz.CONFIRMED, Zakaz.ORDERED)
        ).exists()

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
    def resync_reservation(self):
        """
        Miqdor tahrirlanganda bronni qayta moslaydi:
        ortsa — qo'shimcha bron oladi, kamaysa — ortiqchasini bo'shatadi.
        """
        if self.status in (self.FULFILLED, self.CANCELLED):
            return
        if self.reserved_qty > self.quantity:
            self.release()
            self.save(update_fields=['reserved_qty'])
        self.reserve()
        allocate_pending_orders(self.product)

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

    @transaction.atomic
    def create_backorder_zakaz(self, user=None):
        """
        2-etap: buyurtmadagi yetishmagan (backorder) miqdor uchun avtomatik
        Zakaz ochadi. Zakaz o'sha buyurtma va SHARTNOMA RAQAMI asosida bog'lanadi
        — shunda yetishmagan mahsulot qaysi shartnoma asosida zakaz qilingani aniq.
        Shu mahsulot uchun faol zakaz bo'lsa — takror ochilmaydi.
        """
        if self.backorder_qty <= 0 or self.has_active_zakaz:
            return None
        zakaz = Zakaz.objects.create(
            order=self,
            product=self.product,
            quantity=self.backorder_qty,
            contract_number=self.contract_number,
            contract_date=self.contract_date,
            supplier=self.product.source,
            expected_date=self.due_date,
            status=Zakaz.NEW,
            created_by=user,
        )
        ZakazHistory.objects.create(
            zakaz=zakaz, changed_by=user, action=ZakazHistory.CREATED,
            new_status=Zakaz.NEW, contract_number=self.contract_number,
            asos=(f'Buyurtma #{self.pk} dan avtomatik zakaz — '
                  f'yetishmagan {self.backorder_qty} dona.'),
        )
        return zakaz

    def sync_payment(self, user=None):
        """
        Buyurtma summasini KASSAGA yozadi/yangilaydi (Payment).

        Buyurtma berilganda bitta amalda kassada ham yozuv paydo bo'ladi:
        total (jami summa), paid_amount (oldindan to'lov) va status
        (pending/partial/paid) avtomatik.

        Har bir pul harakati alohida tranzaksiya (PaymentTransaction) bo'lib
        yoziladi: birinchi oldindan to'lov, keyin buyurtma tahririda oshgan
        to'lovlar — bo'lib-bo'lib to'lash tarixi kassada to'liq ko'rinadi.
        """
        from apps.cash.models import Payment
        if self.total is None:
            return None
        prepaid = self.prepaid_amount or 0
        payment = self.payments.order_by('id').first()

        if payment is None:
            payment = Payment.objects.create(
                order=self,
                client=self.client,
                total_amount=self.total,
                paid_amount=0,
                currency=Payment.UZS,
                due_date=self.due_date,
                comment=f'Buyurtma #{self.pk} — shartnoma №{self.contract_number}',
            )
            if prepaid > 0:
                payment.add_payment(
                    prepaid, user=user,
                    comment='Oldindan to\'lov (buyurtma bilan birga)')
            return payment

        payment.client   = self.client
        payment.due_date = self.due_date
        payment.save()  # total buyurtmadan qayta hisoblanadi

        # Oldindan to'lov o'zgargan bo'lsa — farq alohida tranzaksiya
        diff = prepaid - payment.paid_amount
        if diff > 0:
            payment.add_payment(
                diff, user=user,
                comment='Qo\'shimcha to\'lov (buyurtma orqali)')
        elif diff < 0:
            payment.transactions.create(
                amount=diff, received_by=user,
                comment='To\'lov korrektsiyasi (buyurtma tahriri)')
            payment.paid_amount = prepaid
            payment.save()
        return payment

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

    Yaratish: operator yoki manager (status avtomatik 'new'), yoki buyurtmadagi
    yetishmagan miqdor uchun avtomatik.
    Status o'zgartirish: FAQAT manager.

    Muhim qoidalar:
        - Tasdiqlash (confirmed): shartnoma (dogovor) raqami kiritilmaguncha
          tasdiqlab bo'lmaydi. Tasdiqlashda shartnoma sanasi avtomatik bugungi
          (Asia/Tashkent) qilib qo'yiladi.
        - Qabul qilish (received): asos va faktura majburiy.

    Holat oqimi:
        new → confirmed → ordered → received → (avtomatik ombor to'ldiriladi)
        har qanday → cancelled
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

    order              = ForeignKey('orders.Order', on_delete=SET_NULL,
                                    null=True, blank=True, related_name='zakazlar',
                                    verbose_name='Manba buyurtma')
    product            = ForeignKey('warehouse.Product', on_delete=PROTECT,
                                    related_name='zakazlar')
    quantity           = PositiveIntegerField(help_text='Zakaz qilingan miqdor')
    received_qty       = PositiveIntegerField(
                             default=0,
                             help_text='Qabul qilingan miqdor (status=received da kiritiladi)')
    supplier           = CharField(max_length=255, blank=True, null=True,
                                   help_text='Etkazuvchi nomi / manzili')
    status             = CharField(max_length=12, choices=STATUS_CHOICES, default=NEW)

    # Shartnoma (dogovor) — tasdiqlash uchun asos
    contract_number    = CharField(max_length=100, blank=True, null=True,
                                   help_text='Shartnoma (dogovor) raqami — tasdiqlash uchun majburiy')
    contract_date      = DateField(null=True, blank=True,
                                   help_text='Shartnoma sanasi (tasdiqlashda avtomatik bugungi kun)')
    confirmed_at       = DateTimeField(null=True, blank=True,
                                       help_text='Tasdiqlangan aniq sana/vaqt (Tashkent)')

    # Qabul qilish — asos + faktura
    asos               = TextField(blank=True, null=True,
                                   help_text='Qabul qilish uchun asos (majburiy)')
    faktura            = CharField(max_length=100, blank=True, null=True,
                                   help_text='Faktura raqami (qabul qilish uchun majburiy)')

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


# ── Audit tarixi ──────────────────────────────────────────────────────────────

class OrderHistory(models.Model):
    """
    Buyurtmaning har bir yaratilishi/tahriri tarixi.
    Shartnoma raqami + asos + aniq sana/vaqt bilan (audit uchun).
    """
    CREATED   = 'created'
    EDITED    = 'edited'
    FULFILLED = 'fulfilled'
    CANCELLED = 'cancelled'

    ACTION_CHOICES = (
        (CREATED,   'Yaratildi'),
        (EDITED,    'Tahrirlandi'),
        (FULFILLED, 'Yetkazildi'),
        (CANCELLED, 'Bekor qilindi'),
    )

    order           = ForeignKey(Order, on_delete=CASCADE, related_name='history')
    changed_by      = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                                 null=True, blank=True, related_name='order_changes')
    action          = CharField(max_length=12, choices=ACTION_CHOICES)
    contract_number = CharField(max_length=100, blank=True, null=True)
    asos            = TextField(blank=True, null=True, help_text='Tahrir/amal asosi')
    changes         = TextField(blank=True, null=True, help_text='O\'zgargan maydonlar (JSON)')
    created_at      = DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'orders_order_history'
        ordering            = ('-created_at',)
        verbose_name        = 'Buyurtma tarixi'
        verbose_name_plural = 'Buyurtma tarixi'

    def __str__(self):
        return f'Order #{self.order_id} — {self.get_action_display()} @ {self.created_at:%Y-%m-%d %H:%M}'


class ZakazHistory(models.Model):
    """
    Zakazning har bir yaratilishi/status o'zgarishi/tahriri tarixi.
    Shartnoma raqami, asos, faktura + aniq sana/vaqt bilan (audit uchun).
    """
    CREATED        = 'created'
    STATUS_CHANGED = 'status_changed'
    EDITED         = 'edited'
    RECEIVED       = 'received'

    ACTION_CHOICES = (
        (CREATED,        'Yaratildi'),
        (STATUS_CHANGED, 'Status o\'zgardi'),
        (EDITED,         'Tahrirlandi'),
        (RECEIVED,       'Qabul qilindi'),
    )

    zakaz           = ForeignKey(Zakaz, on_delete=CASCADE, related_name='history')
    changed_by      = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                                 null=True, blank=True, related_name='zakaz_changes')
    action          = CharField(max_length=14, choices=ACTION_CHOICES)
    old_status      = CharField(max_length=12, blank=True, null=True)
    new_status      = CharField(max_length=12, blank=True, null=True)
    contract_number = CharField(max_length=100, blank=True, null=True)
    contract_date   = DateField(null=True, blank=True)
    asos            = TextField(blank=True, null=True)
    faktura         = CharField(max_length=100, blank=True, null=True)
    changes         = TextField(blank=True, null=True, help_text='O\'zgargan maydonlar (JSON)')
    created_at      = DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'orders_zakaz_history'
        ordering            = ('-created_at',)
        verbose_name        = 'Zakaz tarixi'
        verbose_name_plural = 'Zakaz tarixi'

    def __str__(self):
        return f'Zakaz #{self.zakaz_id} — {self.get_action_display()} @ {self.created_at:%Y-%m-%d %H:%M}'


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
