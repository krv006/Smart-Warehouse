"""Shartnoma raqami — har bir kun uchun alohida o'suvchi tartib raqam.

Format: `{tartib}/{DDMM}`. Tartib raqam HAR KUNI 1 dan boshlanadi va o'sha
kun ichida yaratilgan har bir hujjat (buyurtma, import/zakaz, elektron
shartnoma) uchun bittaga oshadi. Raqam ketma-ketligi `ContractSequence`
jadvalida saqlanadi va `select_for_update` bilan ajratiladi — bir vaqtda
kelgan so'rovlar bir xil raqam olmaydi.
"""
import re

from django.db import models, transaction
from django.db.models import CharField, DateField, PositiveIntegerField
from django.utils import timezone

CONTRACT_NUMBER_RE = re.compile(r'^(\d+)/(\d{4})$')


class ContractSequence(models.Model):
    """Sana bo'yicha oxirgi ajratilgan shartnoma tartib raqami."""

    contract_date = DateField(unique=True, verbose_name='Sana')
    date_part = CharField(max_length=4, verbose_name='DDMM')
    last_number = PositiveIntegerField(default=0,
                                       verbose_name='Oxirgi tartib raqam')

    class Meta:
        db_table = 'common_contract_sequence'
        ordering = ('-contract_date',)
        verbose_name = 'Shartnoma raqami ketma-ketligi'
        verbose_name_plural = 'Shartnoma raqamlari ketma-ketligi'

    def __str__(self):
        return f'{self.contract_date}: {self.last_number}'


def parse_contract_number(value):
    """`12/1108` → (12, '1108'). Formatga mos kelmasa None."""
    match = CONTRACT_NUMBER_RE.match((value or '').strip())
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def _used_numbers(date_part):
    """Bazadagi mavjud hujjatlardan o'sha kun raqamlarini yig'adi.

    Ketma-ketlik jadvali yo'q paytda (eski ma'lumot) boshlang'ich qiymatni
    to'g'ri tiklash uchun kerak.
    """
    from apps.invoices.models import ElectronicInvoice
    from apps.orders.models import Order, Zakaz

    numbers = {0}
    suffix = f'/{date_part}'
    querysets = (
        Order.objects.filter(contract_number__endswith=suffix),
        Zakaz.objects.filter(contract_number__endswith=suffix),
        ElectronicInvoice.objects.filter(contract_number__endswith=suffix),
    )
    for queryset in querysets:
        for value in queryset.values_list('contract_number', flat=True):
            parsed = parse_contract_number(value)
            if parsed and parsed[1] == date_part:
                numbers.add(parsed[0])
    return numbers


def _resolve_date(contract_date=None):
    return contract_date or timezone.localdate()


def peek_contract_number(contract_date=None):
    """Keyingi raqamni QAYTARADI, lekin band qilmaydi (formada ko'rsatish uchun)."""
    date_value = _resolve_date(contract_date)
    date_part = date_value.strftime('%d%m')
    row = ContractSequence.objects.filter(contract_date=date_value).first()
    last = row.last_number if row else 0
    last = max(last, max(_used_numbers(date_part)))
    return f'{last + 1}/{date_part}'


@transaction.atomic
def allocate_contract_number(contract_date=None):
    """Keyingi raqamni ATOMAR band qiladi va qaytaradi."""
    date_value = _resolve_date(contract_date)
    date_part = date_value.strftime('%d%m')
    row, created = ContractSequence.objects.get_or_create(
        contract_date=date_value,
        defaults={'date_part': date_part, 'last_number': 0},
    )
    row = ContractSequence.objects.select_for_update().get(pk=row.pk)
    # Ketma-ketlikdan tashqarida (qo'lda) kiritilgan raqamlarni ham hisobga olamiz
    baseline = max(row.last_number, max(_used_numbers(date_part)))
    row.last_number = baseline + 1
    row.date_part = date_part
    row.save(update_fields=['last_number', 'date_part'])
    return f'{row.last_number}/{date_part}'
