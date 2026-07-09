from django.conf import settings
from django.db import models, transaction
from django.db.models import (
    CharField, ForeignKey, CASCADE, PROTECT, SET_NULL,
    PositiveIntegerField, DecimalField, DateField, DateTimeField, TextField,
)
from django.db.models import F
from django.utils import timezone

from apps.common.models import TimeStampedModel


# ── Order (Mijoz buyurtmasi / bron — HUJJAT) ─────────────────────────────────

class Order(TimeStampedModel):
    """
    Mijoz buyurtmasi — BITTA hujjat, ichida bir nechta mahsulot qatori
    (OrderItem). Nechta mahsulot bo'lishidan qat'i nazar buyurtma BITTA.

    1-etap: buyurtma olinadi (shartnoma raqami majburiy, oldindan to'lov
    saqlanadi, pul kassaga tushadi). Har bir qator uchun ombordagi mavjud
    qoldiqdan bron ajratiladi. Yetishmagan (backorder) qatorlar uchun
    avtomatik Zakaz ochiladi — o'sha shartnoma raqami asosida.

    Holat oqimi (qatorlardan hisoblanadi):
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
    prepaid_amount  = DecimalField(max_digits=14, decimal_places=2, default=0,
                                   help_text='Oldindan to\'langan summa (qisman to\'lov)')
    contract_number = CharField(max_length=100, default='',
                                help_text='Shartnoma (dogovor) raqami — majburiy')
    contract_date   = DateField(default=timezone.localdate,
                                help_text='Shartnoma sanasi (Tashkent)')
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
        return (f'#{self.pk} ({self.items.count()} mahsulot) '
                f'[{self.get_status_display()}] → {client}')

    # ── Yig'ma ko'rsatkichlar (qatorlardan) ──────────────────────────────────

    @property
    def total_quantity(self):
        """Barcha qatorlar bo'yicha jami buyurtma miqdori."""
        return sum(i.quantity for i in self.items.all())

    @property
    def reserved_qty(self):
        """Barcha qatorlar bo'yicha jami bron."""
        return sum(i.reserved_qty for i in self.items.all())

    @property
    def backorder_qty(self):
        """
        Barcha qatorlar bo'yicha jami yetishmagan (zakaz kutilayotgan) miqdor.
        Yetkazilgan yoki bekor qilingan buyurtmada kutiladigan narsa yo'q → 0.
        """
        if self.status in (self.FULFILLED, self.CANCELLED):
            return 0
        return sum(i.backorder_qty for i in self.items.all())

    @property
    def total(self):
        """Jami summa (barcha qatorlar). Hech bir qatorda narx bo'lmasa None."""
        totals = [i.total for i in self.items.all() if i.total is not None]
        if not totals:
            return None
        return sum(totals)

    @property
    def balance_due(self):
        """Qolgan to'lov (total − prepaid_amount)."""
        if self.total is None:
            return None
        return self.total - (self.prepaid_amount or 0)

    @property
    def has_active_zakaz(self):
        """Birorta qator mahsuloti uchun faol zakaz bormi?"""
        return any(i.has_active_zakaz for i in self.items.all())

    # ── Amallar ──────────────────────────────────────────────────────────────

    @transaction.atomic
    def reserve(self):
        """Barcha qatorlarga ombordagi mavjud qoldiqdan FIFO bron ajratadi."""
        for item in self.items.select_for_update():
            item.reserve()
        self.refresh_status()

    @transaction.atomic
    def release(self):
        """Barcha qatorlar bronini bo'shatadi."""
        for item in self.items.select_for_update():
            item.release()

    @transaction.atomic
    def fulfill(self):
        """
        Yetkazildi: har qator bo'yicha bron qilingan miqdor ombordan ayiriladi.
        Boshqa pending buyurtmalarga avtomatik bron qayta ajratiladi.
        """
        products = []
        for item in self.items.select_for_update():
            item.fulfill_reserved()
            products.append(item.product)
        self.status = self.FULFILLED
        self.save(update_fields=['status'])
        for product in products:
            allocate_pending_orders(product)

    def refresh_status(self):
        """Holatni qatorlardan qayta hisoblaydi (fulfilled/cancelled dan tashqari)."""
        if self.status in (self.FULFILLED, self.CANCELLED):
            return
        total_q  = self.total_quantity
        reserved = self.reserved_qty
        if total_q > 0 and reserved >= total_q:
            self.status = self.RESERVED
        elif reserved > 0:
            self.status = self.PARTIAL
        else:
            self.status = self.PENDING
        self.save(update_fields=['status'])

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

    @transaction.atomic
    def create_backorder_zakaz(self, user=None):
        """
        2-etap: buyurtmadagi yetishmagan (backorder) qatorlar uchun avtomatik
        Zakaz ochadi (har mahsulotga alohida zakaz). Zakaz buyurtma va
        SHARTNOMA RAQAMI asosida bog'lanadi. Faol zakazi bor mahsulotga
        takror ochilmaydi.
        """
        created = []
        for item in self.items.all():
            if item.backorder_qty <= 0 or item.has_active_zakaz:
                continue
            zakaz = Zakaz.objects.create(
                order=self,
                product=item.product,
                quantity=item.backorder_qty,
                contract_number=self.contract_number,
                contract_date=self.contract_date,
                supplier=item.product.source,
                expected_date=self.due_date,
                status=Zakaz.NEW,
                created_by=user,
            )
            asos = (f'Buyurtma #{self.pk} dan avtomatik zakaz — '
                    f'"{item.product.name}" yetishmagan {item.backorder_qty} dona.')
            ZakazHistory.objects.create(
                zakaz=zakaz, changed_by=user, action=ZakazHistory.CREATED,
                new_status=Zakaz.NEW, contract_number=self.contract_number,
                asos=asos,
            )
            register_contract(
                item.product, ProductContract.ZAKAZ_CREATED,
                contract_number=self.contract_number,
                contract_date=self.contract_date,
                asos=asos, order=self, zakaz=zakaz, user=user,
            )
            created.append(zakaz)
        return created

    @transaction.atomic
    def sync_backorder_zakaz(self, user=None):
        """
        Buyurtma TAHRIRLANGANDA yetishmagan (backorder) miqdorga bog'liq
        zakazni moslaydi:
          - Miqdor oshsa → shu buyurtmaning faol zakazi miqdori ham oshadi
            ("yana shuncha qo'shildi"), tarixга yoziladi.
          - Miqdor kamaysa → zakaz miqdori kamayadi.
          - Yetishmagan qolmasa (backorder=0) va zakaz hali 'new' bo'lsa →
            zakaz bekor qilinadi (kerak emas). 'confirmed'/'ordered' bo'lsa —
            tegilmaydi (etkazuvchiga allaqachon berilgan).
          - Umuman zakazi bo'lmagan yangi yetishmovchilikка yangi zakaz ochiladi.
        """
        for item in self.items.all():
            need  = item.backorder_qty
            zakaz = (self.zakazlar
                     .filter(product=item.product,
                             status__in=(Zakaz.NEW, Zakaz.CONFIRMED, Zakaz.ORDERED))
                     .order_by('id').first())
            if zakaz is None:
                continue  # yangilar pastda create_backorder_zakaz orqali ochiladi

            if need > 0 and zakaz.quantity != need:
                old   = zakaz.quantity
                delta = need - old
                zakaz.quantity = need
                zakaz.save(update_fields=['quantity'])
                sign = f'+{delta}' if delta > 0 else str(delta)
                ZakazHistory.objects.create(
                    zakaz=zakaz, changed_by=user, action=ZakazHistory.EDITED,
                    contract_number=zakaz.contract_number,
                    contract_date=zakaz.contract_date,
                    asos=(f'Buyurtma #{self.pk} tahrirlandi — zakaz miqdori '
                          f'{old} → {need} ({sign} dona).'),
                )
            elif need <= 0 and zakaz.status == Zakaz.NEW and zakaz.received_qty == 0:
                zakaz.status = Zakaz.CANCELLED
                zakaz.asos   = 'Buyurtma tahriri — yetishmagan miqdor qolmadi.'
                zakaz.save(update_fields=['status', 'asos'])
                ZakazHistory.objects.create(
                    zakaz=zakaz, changed_by=user,
                    action=ZakazHistory.STATUS_CHANGED,
                    old_status=Zakaz.NEW, new_status=Zakaz.CANCELLED,
                    contract_number=zakaz.contract_number,
                    asos='Buyurtma tahriri — yetishmagan miqdor qolmadi.',
                )
                register_contract(
                    item.product, ProductContract.ZAKAZ_CANCELLED,
                    contract_number=zakaz.contract_number,
                    asos='Buyurtma tahriri — yetishmagan miqdor qolmadi.',
                    order=self, zakaz=zakaz, user=user,
                )

        # Zakazi umuman yo'q, yangi paydo bo'lgan yetishmovchilikка yangi zakaz
        self.create_backorder_zakaz(user=user)


class OrderItem(TimeStampedModel):
    """
    Buyurtma qatori — bitta buyurtma ichidagi bitta mahsulot.
    Bron/backorder har qator bo'yicha alohida yuritiladi.
    """
    order        = ForeignKey(Order, on_delete=CASCADE, related_name='items')
    product      = ForeignKey('warehouse.Product', on_delete=PROTECT,
                              related_name='order_items')
    quantity     = PositiveIntegerField(help_text='Buyurtma qilingan miqdor')
    unit_price   = DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                help_text='Birlik narxi (sotuv narxi)')
    reserved_qty = PositiveIntegerField(default=0,
                                        help_text='Hozirda bron qilingan miqdor')
    comment      = TextField(blank=True, null=True)

    class Meta:
        db_table            = 'orders_order_item'
        ordering            = ('id',)
        verbose_name        = 'Buyurtma qatori'
        verbose_name_plural = 'Buyurtma qatorlari'

    def __str__(self):
        return f'{self.product.name} x{self.quantity} (order #{self.order_id})'

    @property
    def backorder_qty(self):
        """
        Hali bronlanmagan, kelishi kutilayotgan miqdor.
        Yetkazilgan/bekor qilingan buyurtmada 0 (kutiladigan narsa yo'q).
        """
        if self.order.status in (Order.FULFILLED, Order.CANCELLED):
            return 0
        return max(0, self.quantity - self.reserved_qty)

    @property
    def total(self):
        """Qator summasi (unit_price * quantity)."""
        if self.unit_price is None:
            return None
        return self.unit_price * self.quantity

    @property
    def has_active_zakaz(self):
        """Shu mahsulot uchun faol (yakunlanmagan) zakaz bormi?"""
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
        self.save(update_fields=['reserved_qty'])

    @transaction.atomic
    def release(self):
        """Bron bo'shatadi (bekor qilish yoki miqdor kamayishi uchun)."""
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
        self.save(update_fields=['reserved_qty'])

    @transaction.atomic
    def resync_reservation(self):
        """
        Miqdor tahrirlanganda bronni qayta moslaydi:
        ortsa — qo'shimcha bron oladi, kamaysa — hammasini bo'shatib qaytadan.
        """
        if self.reserved_qty > self.quantity:
            self.release()
        self.reserve()
        allocate_pending_orders(self.product)

    @transaction.atomic
    def fulfill_reserved(self):
        """Bron qilingan miqdorni ham quantity, ham reserved dan ayiradi."""
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
        self.save(update_fields=['reserved_qty'])


# ── Zakaz (Etkazuvchidan buyurtma) ───────────────────────────────────────────

class Zakaz(TimeStampedModel):
    """
    Etkazuvchidan mahsulot zakaz qilish (procurement order).

    Yaratish: operator yoki manager (status avtomatik 'new'), yoki buyurtmadagi
    yetishmagan qator uchun avtomatik.
    Status o'zgartirish: FAQAT manager.

    Muhim qoidalar:
        - HAR BIR holat o'zgarishida asos MAJBURIY.
        - confirmed / ordered / received — shartnoma raqami MAJBURIY.
        - Tasdiqlashda sana bo'sh bo'lsa avtomatik bugungi kun (Asia/Tashkent).
        - Qabul qilishda (received) qo'shimcha faktura MAJBURIY.

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

    # Shartnoma (dogovor) — har bir ish holati uchun asos
    contract_number    = CharField(max_length=100, blank=True, null=True,
                                   help_text='Shartnoma (dogovor) raqami — tasdiqlash/yuborish/qabul uchun majburiy')
    contract_date      = DateField(null=True, blank=True,
                                   help_text='Shartnoma sanasi (tasdiqlashda avtomatik bugungi kun)')
    confirmed_at       = DateTimeField(null=True, blank=True,
                                       help_text='Tasdiqlangan aniq sana/vaqt (Tashkent)')

    # Asos (har holat o'tishida yangilanadi) + faktura (qabulda)
    asos               = TextField(blank=True, null=True,
                                   help_text='Oxirgi holat o\'tishining asosi')
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
    def receive(self, user=None):
        """
        Zakaz qabul qilindi:
        1. received_qty (yoki quantity) ni omborga qo'shadi.
        2. Pending/partial orderlarga avtomatik bron ajratadi va
           HAR BIR yangilangan buyurtma tarixiga iz qoldiradi
           (qaysi zakaz, qaysi shartnoma/faktura asosida).
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

        # Taqsimotdan OLDINGI bron holati (keyin farqni aniqlash uchun)
        pending_items = OrderItem.objects.filter(
            product=self.product,
            order__status__in=(Order.PENDING, Order.PARTIAL))
        before = {i.pk: i.reserved_qty for i in pending_items}

        # Pending orderlarga bron ajrat
        allocate_pending_orders(self.product)

        # Buyurtmalar qismini YANGILAB, tarixга iz qoldiramiz
        gained_by_order = {}
        for i in (OrderItem.objects.filter(pk__in=before)
                  .select_related('order')):
            gained = i.reserved_qty - before[i.pk]
            if gained > 0:
                gained_by_order.setdefault(i.order, 0)
                gained_by_order[i.order] += gained
        for order, gained in gained_by_order.items():
            # ASOS = SHARTNOMA: bron ajratish zakaz shartnomasi asosida bo'ladi
            OrderHistory.objects.create(
                order=order, changed_by=user,
                action=OrderHistory.ALLOCATED,
                contract_number=self.contract_number,
                asos=(f'Shartnoma №{self.contract_number or "—"} asosida '
                      f'(Zakaz #{self.pk}, faktura {self.faktura or "—"}) — '
                      f'{gained} dona avtomatik bron ajratildi.'),
            )

        # Low-stock bildirishnomani yop (agar qoldiq etarli bo'lsa)
        self.product.refresh_from_db()
        if self.product.available_quantity > self.product.min_quantity:
            Notification.resolve_low_stock_notifications(self.product)


# ── Mahsulot shartnomalari reestri ───────────────────────────────────────────

class ProductContract(TimeStampedModel):
    """
    MAHSULOTGA bog'langan shartnomalar reestri.

    Har bir holat va detal (buyurtma yaratildi/tahrirlandi, zakaz
    tasdiqlandi/yuborildi/qabul qilindi...) uchun shartnoma raqami + asos
    AVTOMATIK shu yerga yoziladi. Davlat va mijozlar oldida har bir mahsulot
    bo'yicha qaysi shartnoma va qaysi asos bilan ish qilingani doim tayyor
    turadi — hech narsa yo'qolmaydi.
    """
    ORDER_CREATED   = 'order_created'
    ORDER_EDITED    = 'order_edited'
    ORDER_FULFILLED = 'order_fulfilled'
    ORDER_CANCELLED = 'order_cancelled'
    ZAKAZ_CREATED   = 'zakaz_created'
    ZAKAZ_CONFIRMED = 'zakaz_confirmed'
    ZAKAZ_ORDERED   = 'zakaz_ordered'
    ZAKAZ_RECEIVED  = 'zakaz_received'
    ZAKAZ_CANCELLED = 'zakaz_cancelled'
    STOCK_IN        = 'stock_in'

    SOURCE_CHOICES = (
        (ORDER_CREATED,   'Buyurtma yaratildi'),
        (ORDER_EDITED,    'Buyurtma tahrirlandi'),
        (ORDER_FULFILLED, 'Buyurtma yetkazildi'),
        (ORDER_CANCELLED, 'Buyurtma bekor qilindi'),
        (ZAKAZ_CREATED,   'Zakaz yaratildi'),
        (ZAKAZ_CONFIRMED, 'Zakaz tasdiqlandi'),
        (ZAKAZ_ORDERED,   'Zakaz yuborildi'),
        (ZAKAZ_RECEIVED,  'Zakaz qabul qilindi'),
        (ZAKAZ_CANCELLED, 'Zakaz bekor qilindi'),
        (STOCK_IN,        'Kirim (mahsulot keldi)'),
    )

    product         = ForeignKey('warehouse.Product', on_delete=CASCADE,
                                 related_name='contracts')
    contract_number = CharField(max_length=100, blank=True, null=True)
    contract_date   = DateField(null=True, blank=True)
    asos            = TextField(blank=True, null=True)
    faktura         = CharField(max_length=100, blank=True, null=True)
    source_type     = CharField(max_length=20, choices=SOURCE_CHOICES)
    order           = ForeignKey('orders.Order', on_delete=SET_NULL,
                                 null=True, blank=True,
                                 related_name='contract_entries')
    zakaz           = ForeignKey('orders.Zakaz', on_delete=SET_NULL,
                                 null=True, blank=True,
                                 related_name='contract_entries')
    created_by      = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                                 null=True, blank=True,
                                 related_name='product_contracts')

    class Meta:
        db_table            = 'orders_product_contract'
        ordering            = ('-created_at',)
        verbose_name        = 'Mahsulot shartnomasi'
        verbose_name_plural = 'Mahsulot shartnomalari'
        indexes = [
            models.Index(fields=['product', 'contract_number']),
        ]

    def __str__(self):
        return (f'{self.product.name} — №{self.contract_number or "—"} '
                f'[{self.get_source_type_display()}]')


def register_contract(product, source_type, *, contract_number=None,
                      contract_date=None, asos=None, faktura=None,
                      order=None, zakaz=None, user=None):
    """
    Shartnoma reestriga AVTOMATIK yozuv (background).
    Har bir holat/detal o'z yozuvi bilan saqlanadi — o'chirilmaydi,
    ustidan yozilmaydi.
    """
    return ProductContract.objects.create(
        product=product,
        source_type=source_type,
        contract_number=contract_number,
        contract_date=contract_date,
        asos=asos,
        faktura=faktura,
        order=order,
        zakaz=zakaz,
        created_by=user,
    )


# ── Audit tarixi ──────────────────────────────────────────────────────────────

class OrderHistory(models.Model):
    """
    Buyurtmaning har bir yaratilishi/tahriri tarixi.
    Shartnoma raqami + asos + aniq sana/vaqt bilan (audit uchun).
    """
    CREATED   = 'created'
    EDITED    = 'edited'
    ALLOCATED = 'allocated'
    FULFILLED = 'fulfilled'
    CANCELLED = 'cancelled'

    ACTION_CHOICES = (
        (CREATED,   'Yaratildi'),
        (EDITED,    'Tahrirlandi'),
        (ALLOCATED, 'Bron ajratildi (zakazdan)'),
        (FULFILLED, 'Yetkazildi'),
        (CANCELLED, 'Bekor qilindi'),
    )

    order           = ForeignKey(Order, on_delete=CASCADE, related_name='history')
    changed_by      = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                                 null=True, blank=True, related_name='order_changes')
    action          = CharField(max_length=12, choices=ACTION_CHOICES)
    contract_number = CharField(max_length=100, blank=True, null=True)
    faktura         = CharField(max_length=100, blank=True, null=True)
    asos            = TextField(blank=True, null=True, help_text='Tahrir/amal asosi (izoh)')
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
    Mahsulot qoldig'i o'zgarganda pending/partial buyurtma QATORLARIGA
    due_date tartibida (eng yaqin deadline birinchi) bron ajratadi.
    """
    items = (
        OrderItem.objects
        .filter(product=product,
                order__status__in=(Order.PENDING, Order.PARTIAL))
        .select_related('order')
        .order_by('order__due_date', 'order__created_at', 'id')
        .select_for_update()
    )
    touched_orders = {}
    for item in items:
        item.reserve()
        touched_orders[item.order_id] = item.order
    for order in touched_orders.values():
        order.refresh_status()
