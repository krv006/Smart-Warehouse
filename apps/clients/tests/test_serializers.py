import os

from cryptography.fernet import Fernet
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.clients import encryption as enc
from apps.clients.encryption import encrypt
from apps.clients.models import Client
from apps.clients.serializers import ClientSerializer

TEST_FERNET_KEY = Fernet.generate_key().decode()


def _use_test_fernet():
    os.environ['FERNET_KEY'] = TEST_FERNET_KEY
    enc._key = TEST_FERNET_KEY.encode()
    enc._fernet = Fernet(enc._key)


class ClientSerializerEncryptionTests(TestCase):
    def setUp(self):
        _use_test_fernet()

    def test_individual_full_name_encrypted_once_and_decrypted_in_response(self):
        factory = APIRequestFactory()
        request = factory.patch('/')
        serializer = ClientSerializer(
            data={
                'client_type': 'individual',
                'full_name': 'KImdir',
                'pinfl': '14141241211114',
                'passport_number': '1313123',
                'phone': '+998936925110',
                'email': '13@gmail.com',
                'is_active': True,
            },
            context={'request': request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        client = serializer.save()

        self.assertNotEqual(client.full_name, 'KImdir')

        output = ClientSerializer(client).data
        self.assertEqual(output['full_name'], 'KImdir')
        self.assertEqual(output['pinfl'], '14141241211114')
        self.assertEqual(output['phone'], '+998936925110')

    def test_update_individual_full_name_stays_readable(self):
        client = Client.objects.create(
            client_type=Client.INDIVIDUAL,
            full_name=encrypt('Eski ism'),
            pinfl=encrypt('14141241211114'),
            passport_number=encrypt('1313123'),
            phone=encrypt('+998936925110'),
        )

        factory = APIRequestFactory()
        request = factory.patch('/')
        serializer = ClientSerializer(
            client,
            data={
                'client_type': 'individual',
                'full_name': 'KImdir',
                'pinfl': '14141241211114',
                'passport_number': '1313123',
                'phone': '+998936925110',
                'is_active': True,
            },
            context={'request': request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()

        output = ClientSerializer(updated).data
        self.assertEqual(output['full_name'], 'KImdir')
