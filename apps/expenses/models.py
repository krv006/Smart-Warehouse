from django.db.models import (CharField, ForeignKey, CASCADE, SET_NULL, PROTECT,
                              DecimalField, DateField, TextField, FileField)
from apps.common.models import TimeStampedModel


class ExpenseType(TimeStampedModel):
    OFFICE       = 'office'
    IMPORT       = 'import'
    DECLARATION  = 'declaration'
    CERTIFICATE  = 'certificate'
    TRANSPORT    = 'transport'
    BUSINESS_TRIP = 'business_trip'
    SALARY       = 'salary'
    OTHER        = 'other'

    CODE_CHOICES = (
        (OFFICE,        'Ofis rasxod'),
        (IMPORT,        'Import rasxod'),
        (DECLARATION,   'Dekloratsiya rasxod'),
        (CERTIFICATE,   'Sertifikat rasxod'),
        (TRANSPORT,     'Transport rasxod'),
        (BUSINESS_TRIP, 'Komandirovka rasxod'),
        (SALARY,        'Oylik (salary) rasxod'),
        (OTHER,         'ITG / boshqa rasxod'),
    )

    code = CharField(max_length=30, unique=True, choices=CODE_CHOICES)
    name = CharField(max_length=255)

    class Meta:
        db_table = 'expenses_expensetype'
        verbose_name = 'Rasxod toifasi'
        verbose_name_plural = 'Rasxod toifalari'

    def __str__(self):
        return self.name


class ExpenseSubType(TimeStampedModel):
    expense_type = ForeignKey(ExpenseType, on_delete=CASCADE, related_name='sub_types')
    name         = CharField(max_length=255)

    class Meta:
        db_table = 'expenses_expensesubtype'
        verbose_name = 'Rasxod turi'
        verbose_name_plural = 'Rasxod turlari'
        unique_together = ('expense_type', 'name')

    def __str__(self):
        return f'{self.expense_type.name} → {self.name}'


class Expense(TimeStampedModel):
    UZS = 'UZS'
    USD = 'USD'
    CURRENCY_CHOICES = ((UZS, 'UZS'), (USD, 'USD'))

    expense_type = ForeignKey(ExpenseType, on_delete=PROTECT, related_name='expenses')
    sub_type     = ForeignKey(ExpenseSubType, on_delete=SET_NULL,
                              null=True, blank=True, related_name='expenses')
    amount       = DecimalField(max_digits=14, decimal_places=2)
    currency     = CharField(max_length=3, choices=CURRENCY_CHOICES, default=UZS)
    date         = DateField()
    responsible  = ForeignKey('users.User', on_delete=SET_NULL,
                              null=True, blank=True, related_name='expenses')
    comment      = TextField(blank=True, null=True,
                             help_text='"other" toifasida majburiy')
    attachment   = FileField(upload_to='expenses/', null=True, blank=True)

    class Meta:
        db_table = 'expenses_expense'
        ordering = ('-date', '-created_at')
        verbose_name = 'Rasxod'
        verbose_name_plural = 'Rasxodlar'

    def __str__(self):
        return f'{self.expense_type} — {self.amount} {self.currency} ({self.date})'

    def clean(self):
        from django.core.exceptions import ValidationError
        if (self.expense_type
                and self.expense_type.code == ExpenseType.OTHER
                and not self.comment):
            raise ValidationError(
                {'comment': '"Boshqa" toifasida izoh (comment) majburiy.'}
            )
