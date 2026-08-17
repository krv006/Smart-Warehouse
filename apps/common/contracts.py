"""Shartnoma raqami — yagona, UMUMIY (global) o'suvchi tartib raqam.

Avval har kun uchun alohida (1 dan qayta boshlanadigan, `{tartib}/{DDMM}`
formatidagi) raqam ajratilardi. Endi BITTA umumiy hisoblagichdan olinadi —
kim va qaysi kuni yaratishidan qat'i nazar, raqam doim o'sib boradi, kunlik
qayta boshlanmaydi. Standart (avtomatik) qiymat — oddiy o'suvchi son
(masalan "1", "2", "3", ...).

Bu FAQAT bo'sh qoldirilganda ishlaydigan STANDART qiymat — xodim istasa
shartnoma raqamini istalgan boshqa ko'rinishda (masalan "412412412")
qo'lda kiritishi mumkin, hech qanday format tekshiruvi qo'llanmaydi.
"""
import re

from django.db import IntegrityError, models, transaction

_LEADING_NUMBER_RE = re.compile(r'^(\d+)')

# Eski (kunlik) format bilan yaratilgan shartnomalarni ham parslash uchun —
# faqat ko'rsatish/moslik maqsadida saqlangan, yangi raqam yaratishda
# ishlatilmaydi.
CONTRACT_NUMBER_RE = re.compile(r'^(\d+)/(\d{4})$')


class ContractSequence(models.Model):
    """Yagona (singleton, `pk=1`) umumiy shartnoma raqami hisoblagichi."""

    last_number = models.PositiveIntegerField(
        default=0, verbose_name='Oxirgi umumiy tartib raqam')

    class Meta:
        db_table = 'common_contract_sequence'
        verbose_name = 'Shartnoma raqami ketma-ketligi'
        verbose_name_plural = 'Shartnoma raqami ketma-ketligi'

    def __str__(self):
        return f'Umumiy shartnoma raqami: {self.last_number}'


def parse_contract_number(value):
    """`12/1108` → (12, '1108'). Eski (kunlik) format uchun — faqat
    moslik/ko'rsatish maqsadida qoldirilgan, yangi yaratishda ishlatilmaydi."""
    match = CONTRACT_NUMBER_RE.match((value or '').strip())
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def _seed_baseline():
    """Birinchi marta ishga tushganda — bazadagi mavjud BARCHA shartnoma
    raqamlaridan (eski kunlik format ham, qo'lda kiritilganlar ham) eng
    katta boshlang'ich sonni topadi, yangi umumiy hisoblagich shundan
    davom etsin — raqamlar orqaga qaytib eskilarini takrorlamasin."""
    from apps.invoices.models import ElectronicInvoice
    from apps.orders.models import Order, Zakaz

    highest = 0
    querysets = (
        Order.objects.exclude(contract_number=''),
        Zakaz.objects.exclude(contract_number=''),
        ElectronicInvoice.objects.exclude(contract_number=''),
    )
    for queryset in querysets:
        for value in queryset.values_list('contract_number', flat=True):
            match = _LEADING_NUMBER_RE.match((value or '').strip())
            if match:
                highest = max(highest, int(match.group(1)))
    return highest


def _get_or_init_row():
    """Singleton qatorni qaytaradi — birinchi marta yaratilsa, mavjud
    ma'lumotlardan boshlang'ich qiymat bilan (`_seed_baseline`, faqat
    shu bir martalik holatda ishlaydi, har chaqiriqda emas)."""
    row = ContractSequence.objects.filter(pk=1).first()
    if row is not None:
        return row
    try:
        with transaction.atomic():
            return ContractSequence.objects.create(pk=1, last_number=_seed_baseline())
    except IntegrityError:
        return ContractSequence.objects.get(pk=1)


def peek_contract_number(contract_date=None):
    """Keyingi umumiy raqamni QAYTARADI, lekin band qilmaydi (formada
    ko'rsatish uchun). `contract_date` endi raqamga ta'sir qilmaydi —
    faqat eski chaqiruvchi kod bilan moslik uchun qabul qilinadi."""
    row = _get_or_init_row()
    return str(row.last_number + 1)


@transaction.atomic
def allocate_contract_number(contract_date=None):
    """Keyingi umumiy raqamni ATOMAR band qiladi va qaytaradi.
    `contract_date` endi raqamga ta'sir qilmaydi — faqat eski chaqiruvchi
    kod bilan moslik uchun qabul qilinadi."""
    _get_or_init_row()
    row = ContractSequence.objects.select_for_update().get(pk=1)
    row.last_number += 1
    row.save(update_fields=['last_number'])
    return str(row.last_number)
