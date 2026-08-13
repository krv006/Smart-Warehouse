from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import ModelSerializer, ValidationError

from apps.clients.encryption import encrypt, decrypt
from apps.clients.models import Client
from apps.common.validators import validate_jshshir

_ENCRYPT_FIELDS = (
    'full_name', 'first_name', 'last_name', 'middle_name',
    'pinfl', 'inn', 'passport_number', 'phone',
    'director_jshshr', 'director_fish', 'bank_account',
)


class ClientSerializer(ModelSerializer):
    class Meta:
        model  = Client
        fields = ('id', 'full_name', 'first_name', 'last_name', 'middle_name',
                  'pinfl', 'client_type', 'company_name', 'inn',
                  'director_jshshr', 'director_fish', 'mfo', 'oked',
                  'bank_name', 'bank_account',
                  'passport_number', 'phone', 'email', 'address', 'comment',
                  'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')
        # Uzunlik OCHIQ matnga qo'llanadi (encrypt'dan oldin tekshiriladi)
        extra_kwargs = {
            'full_name': {'max_length': 512},
            'inn':       {'max_length': 512},
            'phone':     {'max_length': 512},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['full_name'] = decrypt(instance.full_name)
        data['first_name'] = decrypt(instance.first_name)
        data['last_name'] = decrypt(instance.last_name)
        data['middle_name'] = decrypt(instance.middle_name)
        data['pinfl'] = decrypt(instance.pinfl)
        data['inn'] = decrypt(instance.inn)
        data['passport_number'] = decrypt(instance.passport_number)
        data['phone'] = decrypt(instance.phone)
        data['director_jshshr'] = decrypt(instance.director_jshshr)
        data['director_fish'] = decrypt(instance.director_fish)
        data['bank_account'] = decrypt(instance.bank_account)

        if data.get('client_type') == Client.INDIVIDUAL:
            parts = [data.get('last_name') or '', data.get('first_name') or '', data.get('middle_name') or '']
            combined = ' '.join(part for part in parts if part).strip()
            if combined:
                data['full_name'] = combined
        return data

    def _encrypt_field_values(self, raw):
        for field in _ENCRYPT_FIELDS:
            if field in raw and raw.get(field):
                raw[field] = encrypt(raw[field])

    def _validate_plaintext_fields(self, raw):
        client_type = raw.get(
            'client_type',
            getattr(self.instance, 'client_type', Client.INDIVIDUAL),
        )
        try:
            if client_type == Client.INDIVIDUAL:
                if 'pinfl' in raw:
                    validate_jshshir(raw.get('pinfl') or '', required=not self.instance)
                elif not self.instance:
                    validate_jshshir('', required=True)
            elif client_type == Client.LEGAL and raw.get('director_jshshr'):
                validate_jshshir(raw['director_jshshr'])
        except DjangoValidationError as exc:
            raise ValidationError(list(exc.messages)) from exc

    def to_internal_value(self, data):
        raw = super().to_internal_value(data)

        if raw.get('client_type') == Client.INDIVIDUAL:
            parts = [raw.get('last_name') or '', raw.get('first_name') or '', raw.get('middle_name') or '']
            combined = ' '.join(part for part in parts if part).strip()
            if combined and not raw.get('full_name'):
                raw['full_name'] = combined
            raw['company_name'] = ''
            raw['inn'] = ''
            raw['director_jshshr'] = ''
            raw['director_fish'] = ''
            raw['mfo'] = ''
            raw['oked'] = ''
            raw['bank_name'] = ''
            raw['bank_account'] = ''
        elif raw.get('client_type') == Client.LEGAL:
            raw['first_name'] = ''
            raw['last_name'] = ''
            raw['middle_name'] = ''
            raw['pinfl'] = ''
            raw['passport_number'] = ''
            raw['full_name'] = ''

        self._validate_plaintext_fields(raw)
        self._encrypt_field_values(raw)
        return raw


class ClientListSerializer(ModelSerializer):
    class Meta:
        model  = Client
        fields = ('id', 'full_name', 'company_name', 'client_type', 'phone', 'inn',
                  'pinfl', 'passport_number', 'director_jshshr', 'director_fish',
                  'is_active', 'created_at')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['full_name'] = decrypt(instance.full_name)
        data['phone'] = decrypt(instance.phone)
        data['inn'] = decrypt(instance.inn)
        data['pinfl'] = decrypt(instance.pinfl)
        data['passport_number'] = decrypt(instance.passport_number)
        data['director_jshshr'] = decrypt(instance.director_jshshr)
        data['director_fish'] = decrypt(instance.director_fish)
        if data.get('client_type') == Client.INDIVIDUAL:
            parts = [decrypt(instance.last_name), decrypt(instance.first_name), decrypt(instance.middle_name)]
            combined = ' '.join(part for part in parts if part).strip()
            if combined:
                data['full_name'] = combined
        return data
