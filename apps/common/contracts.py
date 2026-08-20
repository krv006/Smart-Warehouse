"""Shartnoma raqami — HAR KUN uchun alohida (1 dan qayta boshlanadigan)
o'suvchi tartib raqam, `{tartib}/{DDMM}` formatida.

Masalan: bugun 19-avgust bo'lsa va kecha (18-avgust, "1808") uchun 3 ta
shartnoma yaratilgan bo'lsa, kechagi sana tanlanib to'rtinchi shartnoma
kiritilganda raqam `4/1808` bo'ladi. Hisoblagich sananing o'zi bo'yicha
mustaqil — har bir sana uchun alohida davom etadi, kunlar aralashmaydi.

Bu FAQAT bo'sh qoldirilganda ishlaydigan STANDART qiymat — xodim istasa
shartnoma raqamini istalgan boshqa ko'rinishda (masalan "412412412")
qo'lda kiritishi mumkin, hech qanday format tekshiruvi qo'llanmaydi.
"""
import re

from django.db import IntegrityError, models, transaction
from django.utils import timezone

_LEADING_NUMBER_RE = re.compile(r'^(\d+)')

# Avtomatik yaratilgan (va eski) kunlik format — faqat ko'rsatish/parslash
# maqsadida.
CONTRACT_NUMBER_RE = re.compile(r'^(\d+)/(\d{4})$')


class ContractSequence(models.Model):
    """Har bir SANA uchun alohida o'suvchi tartib raqam hisoblagichi."""

    date        = models.DateField(unique=True, verbose_name='Sana')
    last_number = models.PositiveIntegerField(
        default=0, verbose_name='Oxirgi tartib raqam')

    class Meta:
        db_table = 'common_contract_sequence'
        verbose_name = 'Shartnoma raqami ketma-ketligi'
        verbose_name_plural = 'Shartnoma raqami ketma-ketligi'

    def __str__(self):
        return f'{self.date}: {self.last_number}'


def parse_contract_number(value):
    """`12/1108` → (12, '1108')."""
    match = CONTRACT_NUMBER_RE.match((value or '').strip())
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def _seed_baseline_for_date(contract_date):
    """Berilgan sana uchun hisoblagich birinchi marta yaratilganda —
    o'sha sanaga tegishli mavjud (Order/Zakaz/Invoice) shartnomalar sonidan
    boshlang'ich qiymat sifatida foydalanadi, orqaga qaytib eskilarini
    takrorlamasin."""
    from apps.invoices.models import ElectronicInvoice
    from apps.orders.models import Order, Zakaz

    total = 0
    querysets = (
        Order.objects.filter(contract_date=contract_date).exclude(contract_number=''),
        Zakaz.objects.filter(contract_date=contract_date).exclude(contract_number=''),
        ElectronicInvoice.objects.filter(contract_date=contract_date).exclude(contract_number=''),
    )
    for queryset in querysets:
        total += queryset.count()
    return total


def _get_or_init_row(contract_date, _retries=3):
    """Berilgan sana uchun qatorni qaytaradi — birinchi marta yaratilsa,
    o'sha sanadagi mavjud ma'lumotlardan boshlang'ich qiymat bilan.

    Bir vaqtda ikki so'rov bir xil (hali mavjud bo'lmagan) sana uchun
    qator yaratmoqchi bo'lsa — yutqazgan tomon `IntegrityError` oladi.
    G'olib tomonning tranzaksiyasi hali COMMIT bo'lmagan bo'lishi mumkin
    (masalan, u katta buyurtma yaratish tranzaksiyasi ichida hali davom
    etmoqda) — shu sabab darhol `.get()` ham qator topilmasligi (`DoesNotExist`)
    mumkin. Shuning uchun bir necha marta qayta urinamiz.

    ESLATMA: bu — Django o'zining `get_or_create()`si ishlatadigan xuddi shu
    (bitta urinishli) naqsh, faqat bir necha marta qayta urinadigan qilingan.
    Postgres'ning standart READ COMMITTED izolyatsiyasida buni HAR safar
    to'g'ri hal qiladi (har bir SQL so'rov o'z boshida eng so'nggi COMMIT
    qilingan holatni ko'radi). Loyiha ushbu standart darajani o'zgartirmaydi
    (`DATABASES` sozlamasida maxsus ISOLATION LEVEL yo'q) — REPEATABLE READ/
    SERIALIZABLE'ga o'tilsa, bu yerdagi mantiqni ham qayta ko'rib chiqish
    kerak bo'ladi."""
    row = ContractSequence.objects.filter(date=contract_date).first()
    if row is not None:
        return row
    try:
        with transaction.atomic():
            return ContractSequence.objects.create(
                date=contract_date,
                last_number=_seed_baseline_for_date(contract_date))
    except IntegrityError:
        row = ContractSequence.objects.filter(date=contract_date).first()
        if row is not None:
            return row
        if _retries > 0:
            return _get_or_init_row(contract_date, _retries - 1)
        raise


def peek_contract_number(contract_date=None):
    """Keyingi (sana bo'yicha) raqamni QAYTARADI, lekin band qilmaydi
    (formada ko'rsatish uchun). `contract_date` berilmasa — bugungi kun."""
    contract_date = contract_date or timezone.localdate()
    row = _get_or_init_row(contract_date)
    return f'{row.last_number + 1}/{contract_date.strftime("%d%m")}'


@transaction.atomic
def allocate_contract_number(contract_date=None):
    """Keyingi (sana bo'yicha) raqamni ATOMAR band qiladi va qaytaradi.
    `contract_date` berilmasa — bugungi kun."""
    contract_date = contract_date or timezone.localdate()
    _get_or_init_row(contract_date)
    row = ContractSequence.objects.select_for_update().get(date=contract_date)
    row.last_number += 1
    row.save(update_fields=['last_number'])
    return f'{row.last_number}/{contract_date.strftime("%d%m")}'
