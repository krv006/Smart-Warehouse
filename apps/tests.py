from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.models import User, Product, Stock, Sale
from apps.serializers import SaleSerializer


class SaleLogicTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Laptop', model='X1', serial_number='SN-1',
            purchase_price=Decimal('1000.00'),
        )
        Stock.objects.create(
            product=self.product, quantity=10, warehouse_location='A1'
        )

    def test_quantity_in_stock(self):
        self.assertEqual(self.product.quantity_in_stock, 10)

    def test_sale_decrements_stock(self):
        serializer = SaleSerializer(data={
            'product': self.product.id,
            'sold_price': '1300.00',
            'quantity': 3,
            'sold_to': 'Ali',
            'sold_date': date.today().isoformat(),
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        sale = serializer.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_in_stock, 7)
        # profit = (1300 - 1000) * 3
        self.assertEqual(sale.profit, Decimal('900.00'))
        self.assertEqual(sale.total_amount, Decimal('3900.00'))

    def test_cannot_sell_more_than_stock(self):
        serializer = SaleSerializer(data={
            'product': self.product.id,
            'sold_price': '1300.00',
            'quantity': 50,
            'sold_date': date.today().isoformat(),
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('quantity', serializer.errors)


class RoleTests(TestCase):
    def test_role_helpers(self):
        operator = User.objects.create_user('op', role=User.OPERATOR)
        manager = User.objects.create_user('mng', role=User.MANAGEMENT)
        self.assertTrue(operator.is_operator)
        self.assertFalse(operator.is_management)
        self.assertTrue(manager.is_management)
        self.assertFalse(manager.is_operator)


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            'manager', password='pass1234', role=User.MANAGEMENT
        )
        self.operator = User.objects.create_user(
            'operator', password='pass1234', role=User.OPERATOR
        )

    def test_login_returns_tokens(self):
        res = self.client.post(reverse('login'),
                               {'username': 'manager', 'password': 'pass1234'})
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)
        self.assertEqual(res.data['user']['role'], User.MANAGEMENT)

    def test_login_wrong_password(self):
        res = self.client.post(reverse('login'),
                               {'username': 'manager', 'password': 'wrong'})
        self.assertEqual(res.status_code, 400)

    def test_management_can_create_operator(self):
        self.client.force_authenticate(self.manager)
        res = self.client.post(reverse('register-operator'), {
            'username': 'newop',
            'password': 'securepass123',
        })
        self.assertEqual(res.status_code, 201)
        new_user = User.objects.get(username='newop')
        self.assertEqual(new_user.role, User.OPERATOR)

    def test_operator_cannot_create_operator(self):
        self.client.force_authenticate(self.operator)
        res = self.client.post(reverse('register-operator'), {
            'username': 'newop2',
            'password': 'securepass123',
        })
        self.assertEqual(res.status_code, 403)
