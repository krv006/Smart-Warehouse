from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import (CharField, ForeignKey, CASCADE, PROTECT, SET_NULL,
                              DecimalField, DateField, TextField,
                              PositiveIntegerField, BooleanField)
from django.utils import timezone

from apps.common.models import TimeStampedModel

class ExchangeRate(TimeStampedModel):
    USD = 'USD'
    CURRENCY_CHOICES = ((USD, 'USD'),)

    currency       = CharField(max_length=3, choices=CURRENCY_CHOICES, default=USD)
    mb_rate        = DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    buy_rate       = DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    sell_rate      = DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    rate_date      = DateField(default=timezone.localdate)
    source         = CharField(max_length=50, default='infinbank')
    manual_override = BooleanField(default=False)
    note           = TextField(blank=True, null=True)

    class Meta:
        db_table = 'cash_exchangerate'
        ordering = ('-rate_date', '-created_at')
        verbose_name = 'Valyuta kursi'
        verbose_name_plural = 'Valyuta kurslari'

    def __str__(self):
        return f'{self.currency} {self.mb_rate} ({self.rate_date})'

    @classmethod
    def get_latest(cls, currency='USD'):
        return cls.objects.filter(currency=currency).order_by('-rate_date', '-created_at').first()


class Payment(TimeStampedModel):
    PENDING  = 'pending'
    PARTIAL  = 'partial'
    PAID     = 'paid'
    OVERDUE  = 'overdue'

    STATUS_CHOICES = (
        (PENDING, 'Kutilmoqda'),
        (PARTIAL, 'Qisman toʻlandi'),
        (PAID,    'Toʻlandi'),
        (OVERDUE, 'Muddati oʻtdi'),
    )

    UZS = 'UZS'
    USD = 'USD'
    CURRENCY_CHOICES = ((UZS, 'UZS'), (USD, 'USD'))

    COMMISSION_RATE = Decimal('0.15')

    sale        = ForeignKey('sales.Sale', on_delete=PROTECT,
                             null=True, blank=True, related_name='payments')
    order       = ForeignKey('orders.Order', on_delete=PROTECT,
                             null=True, blank=True, related_name='payments',
                             help_text='Buyurtma to\'lovi (oldindan to\'lov kassada ko\'rinadi)')
    zakaz       = ForeignKey('orders.Zakaz', on_delete=PROTECT,
                             null=True, blank=True, related_name='payments',
                             help_text='Import (zakaz) etkazuvchiga to\'lov')
    client      = ForeignKey('clients.Client', on_delete=SET_NULL,
                             null=True, blank=True, related_name='payments')
    total_amount = DecimalField(max_digits=14, decimal_places=2,
                                help_text='Jami summa (sotuv narxi asosida)')
    commission   = DecimalField(max_digits=14, decimal_places=2,
                                help_text='15% komissiya')
    paid_amount  = DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    currency     = CharField(max_length=3, choices=CURRENCY_CHOICES, default=UZS)
    due_date     = DateField(null=True, blank=True)
    status       = CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    comment      = TextField(blank=True, null=True)

    class Meta:
        db_table         = 'cash_payment'
        ordering         = ('-created_at',)
        verbose_name     = 'Toʻlov'
        verbose_name_plural = 'Toʻlovlar'

    def __str__(self):
        return f'Payment #{self.pk} — {self.status} ({self.total_amount} {self.currency})'

    def save(self, *args, **kwargs):
        if self.sale_id:
            # Sotuv tahrirlansa (narx/miqdor) ham kassa jami summasi qayta
            # hisoblanishi uchun HAR safar (nafaqat yaratishda) qayta olinadi
            # — buyurtma (order_id) bilan bir xil qoida.
            self.total_amount = self.sale.sold_price * self.sale.quantity
            self.commission   = (self.total_amount * self.COMMISSION_RATE).quantize(Decimal('0.01'))
        elif self.zakaz_id:
            if not self.pk:
                z = self.zakaz
                if z.total is not None:
                    self.total_amount = z.total
                self.commission = Decimal('0')
        elif self.order_id:
            # Buyurtma to'lovi — summa buyurtmadan olinadi, buyurtma
            # tahrirlanganda kassa ham yangilanadi. Komissiya sotuvga tegishli,
            # buyurtma to'loviga qo'llanmaydi.
            #
            # MUHIM: summani `self.order.total` orqali emas, TO'G'RIDAN-TO'G'RI
            # bazadan (aggregate) hisoblaymiz. Sabab: buyurtma tahrirlanganda
            # xotiradagi `order` obyekti eski (prefetch keshidagi) qatorlarni
            # ushlab turishi mumkin — u holda kassa eski summada qolib ketardi.
            from django.db.models import Sum, F, DecimalField
            from apps.orders.models import OrderItem
            total = (OrderItem.objects
                     .filter(order_id=self.order_id, unit_price__isnull=False)
                     .aggregate(t=Sum(
                         F('unit_price') * F('quantity'),
                         output_field=DecimalField(max_digits=20, decimal_places=2),
                     ))['t'])
            if total is not None:
                self.total_amount = total
            if self.commission is None:
                self.commission = Decimal('0')
        self._sync_status()
        super().save(*args, **kwargs)

    def _sync_status(self):
        from django.utils import timezone
        if self.paid_amount >= self.total_amount:
            self.status = self.PAID
        elif self.paid_amount > 0:
            self.status = self.PARTIAL
        elif self.due_date and self.due_date < timezone.now().date():
            self.status = self.OVERDUE
        else:
            self.status = self.PENDING

    @property
    def remaining_amount(self):
        """Qolgan to'lov."""
        return self.total_amount - self.paid_amount

    @transaction.atomic
    def add_payment(self, amount, user=None, comment=None):
        """
        Qo'shimcha (bo'lib-bo'lib) to'lov qabul qilish.

        Har bir to'lov alohida tranzaksiya (PaymentTransaction) bo'lib yoziladi:
        qisman to'lov qilgan mijoz keyinroq yana to'lasa — yangi tranzaksiya
        qo'shiladi, paid_amount yig'ilib boradi, status avtomatik yangilanadi
        (pending → partial → paid). Buyurtma to'lovi bo'lsa buyurtmadagi
        prepaid_amount ham sinxronlanadi.
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError('To\'lov summasi musbat bo\'lishi kerak.')

        # Qatorni qulflab qoldiqni QAYTA tekshiramiz — ikkita parallel to'lov
        # ikkalasi ham eski qoldiqni o'qib, jami total'dan oshib ketmasin
        locked = type(self).objects.select_for_update().get(pk=self.pk)
        if amount > locked.remaining_amount:
            raise ValueError(
                f'To\'lov qoldiqdan ({locked.remaining_amount}) oshib ketdi.')

        txn = locked.transactions.create(
            amount=amount,
            received_by=user,
            comment=comment,
        )
        locked.paid_amount += amount
        locked.save()

        # Buyurtma to'lovi — buyurtmadagi oldindan to'lov ham yangilanadi
        if locked.order_id:
            locked.order.prepaid_amount = locked.paid_amount
            locked.order.save(update_fields=['prepaid_amount'])

        # Chaqiruvchidagi obyekt eskirib qolmasin
        self.paid_amount = locked.paid_amount
        self.status      = locked.status
        return txn


class PaymentTransaction(TimeStampedModel):
    """
    Kassa tranzaksiyasi — har bitta to'lov (bo'lib to'lash) yozuvi.

    Payment.paid_amount = shu tranzaksiyalar yig'indisi.
    Qisman to'lovdan keyingi har bir qo'shimcha to'lov alohida qator
    bo'lib turadi (kim qabul qildi, qachon, qancha).
    """
    payment     = ForeignKey(Payment, on_delete=CASCADE,
                             related_name='transactions')
    amount      = DecimalField(max_digits=14, decimal_places=2,
                               help_text='To\'lov summasi (korrektsiyada manfiy bo\'lishi mumkin)')
    received_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                             null=True, blank=True,
                             related_name='received_payments',
                             verbose_name='Qabul qilgan')
    comment     = TextField(blank=True, null=True)

    class Meta:
        db_table            = 'cash_payment_transaction'
        ordering            = ('-created_at',)
        verbose_name        = 'Kassa tranzaksiyasi'
        verbose_name_plural = 'Kassa tranzaksiyalari'

    def __str__(self):
        return f'Txn #{self.pk} — {self.amount} (payment #{self.payment_id})'


class CashConversion(TimeStampedModel):
    """
    Kassadagi UZS <-> USD valyuta konvertatsiyasi.

    Har bir konvertatsiya kassa balansi orasida pul ko'chiradi: manba
    valyutadan `amount_from` ayiriladi, maqsad valyutaga `amount_to`
    qo'shiladi (`ledger.ledger_totals()` ikkalasini ham hisobga oladi).
    """
    UZS_TO_USD = 'uzs_to_usd'
    USD_TO_UZS = 'usd_to_uzs'
    DIRECTION_CHOICES = (
        (UZS_TO_USD, 'UZS → USD'),
        (USD_TO_UZS, 'USD → UZS'),
    )

    direction   = CharField(max_length=16, choices=DIRECTION_CHOICES)
    amount_from = DecimalField(max_digits=18, decimal_places=2,
                               help_text='Manba valyutadan ayiriladigan summa')
    amount_to   = DecimalField(max_digits=18, decimal_places=2,
                               help_text='Maqsad valyutaga qo\'shiladigan summa')
    rate        = DecimalField(max_digits=14, decimal_places=4,
                               help_text='Ishlatilgan kurs (1 USD = necha UZS)')
    comment     = TextField(blank=True, null=True)
    created_by  = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                             null=True, blank=True, related_name='cash_conversions')

    class Meta:
        db_table            = 'cash_conversion'
        ordering            = ('-created_at',)
        verbose_name        = 'Valyuta konvertatsiyasi'
        verbose_name_plural = 'Valyuta konvertatsiyalari'

    def __str__(self):
        return f'{self.get_direction_display()}: {self.amount_from} → {self.amount_to}'


class CashBalanceAdjustment(TimeStampedModel):
    """
    Kassa balansini (UZS yoki USD) qo'lda tuzatish.

    Balans o'zi saqlanmaydi (`ledger.ledger_totals()` orqali hisoblanadi) —
    bu yozuv shunchaki balansga qo'shiladigan/ayiriladigan farqni (`amount`,
    manfiy bo'lishi mumkin) va MAJBURIY asosni saqlaydi. Har bir tuzatish
    kassa jurnalida (`build_ledger_entries`) alohida qator sifatida ko'rinadi
    — kim, qachon, qancha, nima uchun.
    """
    UZS = 'UZS'
    USD = 'USD'
    CURRENCY_CHOICES = ((UZS, 'UZS'), (USD, 'USD'))

    currency   = CharField(max_length=3, choices=CURRENCY_CHOICES)
    amount     = DecimalField(max_digits=18, decimal_places=2,
                              help_text='Balansga qo\'shiladigan farq (manfiy — ayiriladi)')
    asos       = TextField(help_text='Tuzatish sababi — MAJBURIY')
    created_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL,
                            null=True, blank=True, related_name='cash_balance_adjustments')

    class Meta:
        db_table            = 'cash_balance_adjustment'
        ordering            = ('-created_at',)
        verbose_name        = 'Kassa balansi tuzatishi'
        verbose_name_plural = 'Kassa balansi tuzatishlari'

    def __str__(self):
        return f'{self.currency} {self.amount:+} — {self.asos[:40]}'


class ExchangeRateSettings(TimeStampedModel):
    """Valyuta kursi sozlamalari (singleton)."""

    INFINBANK = 'infinbank'
    MANUAL = 'manual'
    BANK = 'bank'
    BUY = 'buy'
    SELL = 'sell'
    SOURCE_CHOICES = (
        (INFINBANK, 'Infinbank'),
        (MANUAL, 'Qo\'lda'),
        (BANK, 'Bank'),
    )
    SIDE_CHOICES = (
        (BUY, 'Sotib olish'),
        (SELL, 'Sotish'),
    )

    auto_fetch_enabled = BooleanField(default=True,
                                      help_text='Infin Bank kursini avtomatik olish')
    preferred_rate_source = CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default=INFINBANK,
        help_text='USD hisob-kitoblarida qaysi kurs ishlatiladi',
    )
    preferred_bank_code = CharField(
        max_length=10,
        blank=True,
        default='',
        help_text='preferred_rate_source=bank bo‘lganda bankxizmatlari.uz bank kodi',
    )
    preferred_bank_side = CharField(
        max_length=4,
        choices=SIDE_CHOICES,
        default=SELL,
        help_text='Bank kursining qaysi ustuni hisob-kitobda ishlatiladi',
    )

    class Meta:
        db_table = 'cash_exchangerate_settings'
        verbose_name = 'Valyuta kursi sozlamasi'
        verbose_name_plural = 'Valyuta kursi sozlamalari'

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
