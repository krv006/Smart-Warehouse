import uuid

from django.db.models import (UUIDField, CharField, TextField, BooleanField,
                              EmailField)

from apps.common.models import TimeStampedModel


class Client(TimeStampedModel):
    """
    Mijoz modeli.
    INN, ism va telefon maydonlari Fernet (symmetric) shifrlash bilan saqlanadi.
    Shifrlash/shifr ochish apps/clients/encryption.py orqali bajariladi.
    """
    id           = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name    = CharField(max_length=512,
                             help_text='Shifrlangan (Fernet)')
    company_name = CharField(max_length=512, blank=True, null=True)
    inn          = CharField(max_length=512, blank=True, null=True,
                             help_text='Shifrlangan (Fernet)')
    phone        = CharField(max_length=512, blank=True, null=True,
                             help_text='Shifrlangan (Fernet)')
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
        return self.company_name or self.full_name or str(self.id)
