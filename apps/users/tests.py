from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import User


class RoleTests(TestCase):
    def test_role_helpers(self):
        operator   = User.objects.create_user('op', role=User.OPERATOR)
        accountant = User.objects.create_user('acc', role=User.ACCOUNTANT)
        manager    = User.objects.create_user('mng', role=User.MANAGEMENT)

        self.assertTrue(operator.is_operator)
        self.assertFalse(operator.is_management)
        self.assertFalse(operator.is_accountant)

        self.assertTrue(accountant.is_accountant)
        self.assertFalse(accountant.is_operator)
        self.assertFalse(accountant.is_management)

        self.assertTrue(manager.is_management)
        self.assertFalse(manager.is_operator)

    def test_superuser_has_all_roles(self):
        boss = User.objects.create_superuser('boss', password='x')
        self.assertTrue(boss.is_operator)
        self.assertTrue(boss.is_accountant)
        self.assertTrue(boss.is_management)


class AuthAPITests(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.manager = User.objects.create_user(
            'manager', password='pass1234', role=User.MANAGEMENT
        )
        self.operator = User.objects.create_user(
            'operator', password='pass1234', role=User.OPERATOR
        )

    def test_login_returns_tokens(self):
        res = self.client_api.post(reverse('login'),
                                   {'username': 'manager', 'password': 'pass1234'})
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)
        self.assertEqual(res.data['user']['role'], User.MANAGEMENT)

    def test_login_wrong_password(self):
        res = self.client_api.post(reverse('login'),
                                   {'username': 'manager', 'password': 'wrong'})
        self.assertEqual(res.status_code, 400)

    def test_management_can_create_user(self):
        self.client_api.force_authenticate(self.manager)
        res = self.client_api.post(reverse('register-user'), {
            'username': 'newop',
            'password': 'securepass123',
            'role': User.OPERATOR,
        })
        self.assertEqual(res.status_code, 201, res.data)
        new_user = User.objects.get(username='newop')
        self.assertEqual(new_user.role, User.OPERATOR)

    def test_operator_cannot_create_user(self):
        self.client_api.force_authenticate(self.operator)
        res = self.client_api.post(reverse('register-user'), {
            'username': 'newop2',
            'password': 'securepass123',
            'role': User.OPERATOR,
        })
        self.assertEqual(res.status_code, 403)

    def test_register_rejects_weak_password(self):
        self.client_api.force_authenticate(self.manager)
        res = self.client_api.post(reverse('register-user'), {
            'username': 'weakop',
            'password': '12345678',
            'role': User.OPERATOR,
        })
        self.assertEqual(res.status_code, 400)
