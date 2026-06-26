from decimal import Decimal

from django.db.models import (CharField, ForeignKey, PROTECT, SET_NULL,
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
                             related_name='payments')
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
        if not self.pk:
            self.total_amount = self.sale.sold_price * self.sale.quantity
            self.commission   = (self.total_amount * self.COMMISSION_RATE).quantize(Decimal('0.01'))
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
