from rest_framework.serializers import ModelSerializer

from apps.clients.encryption import encrypt, decrypt
from apps.clients.models import Client


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

    def to_internal_value(self, data):
        raw = super().to_internal_value(data)
        if 'full_name' in raw and raw.get('full_name'):
            raw['full_name'] = encrypt(raw['full_name'])
        if 'first_name' in raw and raw.get('first_name'):
            raw['first_name'] = encrypt(raw['first_name'])
        if 'last_name' in raw and raw.get('last_name'):
            raw['last_name'] = encrypt(raw['last_name'])
        if 'middle_name' in raw and raw.get('middle_name'):
            raw['middle_name'] = encrypt(raw['middle_name'])
        if 'pinfl' in raw and raw.get('pinfl'):
            raw['pinfl'] = encrypt(raw['pinfl'])
        if 'inn' in raw and raw.get('inn'):
            raw['inn'] = encrypt(raw['inn'])
        if 'passport_number' in raw and raw.get('passport_number'):
            raw['passport_number'] = encrypt(raw['passport_number'])
        if 'phone' in raw and raw.get('phone'):
            raw['phone'] = encrypt(raw['phone'])
        if 'director_jshshr' in raw and raw.get('director_jshshr'):
            raw['director_jshshr'] = encrypt(raw['director_jshshr'])
        if 'director_fish' in raw and raw.get('director_fish'):
            raw['director_fish'] = encrypt(raw['director_fish'])
        if 'bank_account' in raw and raw.get('bank_account'):
            raw['bank_account'] = encrypt(raw['bank_account'])

        if raw.get('client_type') == Client.INDIVIDUAL:
            parts = [raw.get('last_name') or '', raw.get('first_name') or '', raw.get('middle_name') or '']
            combined = ' '.join(part for part in parts if part).strip()
            if combined and not raw.get('full_name'):
                raw['full_name'] = combined
            if raw.get('full_name'):
                raw['full_name'] = encrypt(raw['full_name'])
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
        return raw


class ClientListSerializer(ModelSerializer):
    class Meta:
        model  = Client
        fields = ('id', 'full_name', 'company_name', 'is_active')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['full_name'] = decrypt(instance.full_name)
        return data
