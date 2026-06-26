from rest_framework.serializers import ModelSerializer

from apps.clients.encryption import encrypt, decrypt
from apps.clients.models import Client


class ClientSerializer(ModelSerializer):
    class Meta:
        model  = Client
        fields = ('id', 'full_name', 'company_name', 'inn',
                  'phone', 'email', 'address', 'comment',
                  'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['full_name'] = decrypt(instance.full_name)
        data['inn']       = decrypt(instance.inn)
        data['phone']     = decrypt(instance.phone)
        return data

    def to_internal_value(self, data):
        raw = super().to_internal_value(data)
        if 'full_name' in raw:
            raw['full_name'] = encrypt(raw['full_name'])
        if 'inn' in raw and raw['inn']:
            raw['inn'] = encrypt(raw['inn'])
        if 'phone' in raw and raw['phone']:
            raw['phone'] = encrypt(raw['phone'])
        return raw


class ClientListSerializer(ModelSerializer):
    class Meta:
        model  = Client
        fields = ('id', 'full_name', 'company_name', 'is_active')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['full_name'] = decrypt(instance.full_name)
        return data
