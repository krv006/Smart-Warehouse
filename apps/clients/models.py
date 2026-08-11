import uuid

from django.db.models import (UUIDField, CharField, TextField, BooleanField,
                              EmailField)

from apps.common.models import TimeStampedModel


class Client(TimeStampedModel):
    """
    Mijoz modeli.
    INN, passport va telefon maydonlari Fernet (symmetric) shifrlash bilan saqlanadi.
    Shifrlash/shifr ochish apps/clients/encryption.py orqali bajariladi.
    """
    INDIVIDUAL = 'individual'
    LEGAL      = 'legal'
    CLIENT_TYPE_CHOICES = (
        (INDIVIDUAL, 'Jismoniy shaxs'),
        (LEGAL, 'Yuridik shaxs'),
    )

    id           = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Shifrlangan maydonlar TextField: Fernet ciphertext plaintext'dan sezilarli
    # uzun bo'ladi (~100 + 4/3x) — CharField(512) uzun qiymatlarda DataError berardi
    full_name    = TextField(help_text='Shifrlangan (Fernet)')
    first_name   = TextField(blank=True, null=True, help_text='Shifrlangan (Fernet)')
    last_name    = TextField(blank=True, null=True, help_text='Shifrlangan (Fernet)')
    middle_name  = TextField(blank=True, null=True, help_text='Shifrlangan (Fernet)')
    pinfl        = TextField(blank=True, null=True, help_text='Shifrlangan (Fernet)')
    client_type  = CharField(max_length=20, choices=CLIENT_TYPE_CHOICES,
                             default=INDIVIDUAL)
    company_name = CharField(max_length=512, blank=True, null=True)
    inn          = TextField(blank=True, null=True,
                             help_text='Shifrlangan (Fernet)')
    # Yuridik shaxs — rahbar va bank rekvizitlari
    director_jshshr = TextField(blank=True, null=True,
                                help_text='Rahbar JSHSHIR (shifrlangan)')
    director_fish   = TextField(blank=True, null=True,
                                help_text='Rahbar F.I.Sh. (shifrlangan)')
    mfo             = CharField(max_length=10, blank=True, null=True)
    oked            = CharField(max_length=20, blank=True, null=True)
    bank_name       = CharField(max_length=255, blank=True, null=True)
    bank_account    = TextField(blank=True, null=True,
                                help_text='Hisob raqami (shifrlangan)')
    passport_number = TextField(blank=True, null=True, help_text='Shifrlangan (Fernet)')
    phone        = TextField(blank=True, null=True, help_text='Shifrlangan (Fernet)')
    email        = EmailField(blank=True, null=True)
    address      = TextField(blank=True, null=True)
    comment      = TextField(blank=True, null=True)
    is_active    = BooleanField(default=True)

    class Meta:
        db_table         = 'clients_client'
        ordering         = ('company_name', 'full_name')
        verbose_name     = 'Mijoz'
        verbose_name_plural = 'Mijozlar'

    def __str__(self):
        if self.company_name:
            return self.company_name
        # full_name shifrlangan — ochib ko'rsatamiz (Excel/Telegram/adminda
        # base64 ko'rinmasin)
        from apps.clients.encryption import decrypt
        return (decrypt(self.full_name) if self.full_name else None) or str(self.id)
