from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import (CharField, ForeignKey, CASCADE, PROTECT, SET_NULL,
                              DecimalField, DateField, TextField,
                              PositiveIntegerField, BooleanField)

from apps.common.models import TimeStampedModel


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
            if not self.pk:
                self.total_amount = self.sale.sold_price * self.sale.quantity
                self.commission   = (self.total_amount * self.COMMISSION_RATE).quantize(Decimal('0.01'))
        elif self.order_id:
            # Buyurtma to'lovi — summa buyurtmadan olinadi, buyurtma
            # tahrirlanganda kassa ham yangilanadi. Komissiya sotuvga tegishli,
            # buyurtma to'loviga qo'llanmaydi.
            total = self.order.total
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
        if amount > self.remaining_amount:
            raise ValueError(
                f'To\'lov qoldiqdan ({self.remaining_amount}) oshib ketdi.')

        txn = self.transactions.create(
            amount=amount,
            received_by=user,
            comment=comment,
        )
        self.paid_amount += amount
        self.save()

        # Buyurtma to'lovi — buyurtmadagi oldindan to'lov ham yangilanadi
        if self.order_id:
            self.order.prepaid_amount = self.paid_amount
            self.order.save(update_fields=['prepaid_amount'])
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
