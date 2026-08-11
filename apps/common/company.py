"""Korxona profili — elektron faktura va hujjatlarda ishlatiladi."""
from django.db.models import CharField, TextField, EmailField

from apps.common.models import TimeStampedModel


class CompanyProfile(TimeStampedModel):
    """Bitta korxona profili (singleton)."""

    name = CharField(max_length=512, blank=True, default='',
                     verbose_name='Korxona nomi')
    stir = CharField(max_length=20, blank=True, default='',
                     verbose_name='STIR')
    director_jshshr = CharField(max_length=14, blank=True, default='',
                                verbose_name='Rahbar JSHSHIR')
    director_fish = CharField(max_length=512, blank=True, default='',
                              verbose_name='Rahbar F.I.Sh.')
    mfo = CharField(max_length=10, blank=True, default='', verbose_name='MFO')
    bank_name = CharField(max_length=255, blank=True, default='',
                          verbose_name='Bank nomi')
    oked = CharField(max_length=20, blank=True, default='', verbose_name='OKED')
    bank_account = CharField(max_length=34, blank=True, default='',
                             verbose_name='Hisob raqami')
    address = TextField(blank=True, default='', verbose_name='Manzil')
    phone = CharField(max_length=32, blank=True, default='', verbose_name='Telefon')
    email = EmailField(blank=True, null=True, verbose_name='E-mail')

    class Meta:
        db_table = 'common_company_profile'
        verbose_name = 'Korxona profili'
        verbose_name_plural = 'Korxona profili'

    def __str__(self):
        return self.name or 'Korxona profili'

    @classmethod
    def get_profile(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
