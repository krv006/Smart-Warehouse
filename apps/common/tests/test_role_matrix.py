"""11-qoidali rol/permission matritsasi regressiya testlari."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User
from apps.warehouse.models import Category, Product, Stock


class RoleMatrixTests(TestCase):
    """Matritsa qoidalari: Operator / Accountant / Management."""

    def setUp(self):
        self.api = APIClient()
        self.operator = User.objects.create_user('op', password='x', role=User.OPERATOR)
        self.accountant = User.objects.create_user('acc', password='x', role=User.ACCOUNTANT)
        self.manager = User.objects.create_user('mng', password='x', role=User.MANAGEMENT)
        self.category = Category.objects.create(name='Test kategoriya')
        self.product = Product.objects.create(
            category=self.category,
            name='Test', serial_number='SN-MX-1',
            purchase_price=Decimal('1000'), selling_price=Decimal('1500'),
            min_quantity=2,
        )
        Stock.objects.create(product=self.product, quantity=10, warehouse_location='A1')

    def _auth(self, user):
        self.api.force_authenticate(user)

    # 1 — Mahsulot qo'shish
    def test_rule1_product_create_permissions(self):
        # Kategoriya — mahsulot qo'shishda majburiy
        payload = {'name': 'New', 'serial_number': 'SN-NEW-1', 'unit': 'piece',
                   'category': self.category.pk}
        self._auth(self.operator)
        self.assertEqual(self.api.post('/api/v1/warehouse/products/', payload).status_code, 201)
        payload['serial_number'] = 'SN-NEW-2'
        self._auth(self.accountant)
        self.assertEqual(self.api.post('/api/v1/warehouse/products/', payload).status_code, 403)
        payload['serial_number'] = 'SN-NEW-3'
        self._auth(self.manager)
        self.assertEqual(self.api.post('/api/v1/warehouse/products/', payload).status_code, 201)

    # 2 — Operator API: narxlar yo'q
    def test_rule2_operator_product_has_no_prices(self):
        self._auth(self.operator)
        res = self.api.get(f'/api/v1/warehouse/products/{self.product.pk}/')
        self.assertEqual(res.status_code, 200)
        for key in ('purchase_price', 'selling_price', 'delivery_price'):
            self.assertNotIn(key, res.data)

    def test_rule2_accountant_product_has_readonly_prices(self):
        self._auth(self.accountant)
        res = self.api.get(f'/api/v1/warehouse/products/{self.product.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('purchase_price', res.data)
        self.assertIn('selling_price', res.data)

    # 3 — Narx yozish faqat management
    def test_rule3_only_management_writes_prices(self):
        self._auth(self.operator)
        res = self.api.patch(
            f'/api/v1/warehouse/products/{self.product.pk}/',
            {'purchase_price': '2000'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.purchase_price, Decimal('1000.00'))

        self._auth(self.manager)
        res = self.api.patch(
            f'/api/v1/warehouse/products/{self.product.pk}/',
            {'purchase_price': '2500'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.purchase_price, Decimal('2500.00'))

    # 4 — min_quantity faqat management
    def test_rule4_min_quantity_management_only(self):
        self._auth(self.operator)
        res = self.api.get(f'/api/v1/warehouse/products/{self.product.pk}/')
        self.assertNotIn('min_quantity', res.data)

        self._auth(self.manager)
        res = self.api.patch(
            f'/api/v1/warehouse/products/{self.product.pk}/',
            {'min_quantity': 5},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.min_quantity, 5)

    # 5 — Sotuv yaratish
    def test_rule5_sale_create_permissions(self):
        payload = {
            'product': self.product.pk,
            'quantity': 1,
            'sold_date': date.today().isoformat(),
        }
        self._auth(self.operator)
        self.assertEqual(self.api.post('/api/v1/sales/', payload).status_code, 201)
        self._auth(self.accountant)
        self.assertEqual(self.api.post('/api/v1/sales/', payload).status_code, 403)
        self._auth(self.manager)
        payload['sold_price'] = '1600'
        self.assertEqual(self.api.post('/api/v1/sales/', payload).status_code, 201)

    # 6 — Sotuv summasi operator uchun yo'q
    def test_rule6_operator_sale_has_no_amounts(self):
        self._auth(self.manager)
        sale = self.api.post('/api/v1/sales/', {
            'product': self.product.pk,
            'quantity': 1,
            'sold_price': '1600',
            'sold_date': date.today().isoformat(),
        }).data
        self._auth(self.operator)
        res = self.api.get(f'/api/v1/sales/{sale["id"]}/')
        for key in ('sold_price', 'total_amount', 'profit'):
            self.assertNotIn(key, res.data)

        self._auth(self.accountant)
        res = self.api.get(f'/api/v1/sales/{sale["id"]}/')
        for key in ('sold_price', 'total_amount'):
            self.assertIn(key, res.data)

    # 7 — Kassa/Rasxod operator faqat GET
    def test_rule7_operator_cash_expenses_read_only(self):
        self._auth(self.operator)
        self.assertEqual(self.api.get('/api/v1/cash/payments/').status_code, 200)
        self.assertEqual(self.api.get('/api/v1/expenses/expenses/').status_code, 200)
        self.assertEqual(self.api.post('/api/v1/cash/payments/', {}).status_code, 403)
        self.assertEqual(self.api.post('/api/v1/expenses/expenses/', {}).status_code, 403)

        self._auth(self.accountant)
        self.assertIn(self.api.post('/api/v1/expenses/expenses/', {
            'expense_type': 1,
            'amount': '1000',
            'currency': 'UZS',
            'date': date.today().isoformat(),
        }).status_code, (201, 400))  # 400 if expense_type seed yo'q

    def test_rule7_operator_payment_has_no_amounts(self):
        self._auth(self.manager)
        from apps.cash.models import Payment
        from apps.sales.models import Sale
        sale = Sale.objects.create(
            product=self.product, quantity=1, sold_price=Decimal('1500'),
            sold_date=date.today(),
        )
        payment = Payment.objects.create(
            sale=sale, total_amount=Decimal('1500'), currency='UZS',
            due_date=date.today(),
        )
        self._auth(self.operator)
        res = self.api.get(f'/api/v1/cash/payments/{payment.pk}/')
        self.assertEqual(res.status_code, 200)
        for key in ('total_amount', 'paid_amount', 'commission', 'remaining'):
            self.assertNotIn(key, res.data)

    # 8 — Buyurtma yaratish
    def test_rule8_order_create_permissions(self):
        payload = {
            'contract_number': '1/2026',
            'items': [{'product': self.product.pk, 'quantity': 1}],
        }
        self._auth(self.operator)
        self.assertEqual(self.api.post('/api/v1/orders/', payload, format='json').status_code, 201)
        self._auth(self.accountant)
        self.assertEqual(self.api.post('/api/v1/orders/', payload, format='json').status_code, 403)
        self._auth(self.manager)
        payload['contract_number'] = '2/2026'
        self.assertEqual(self.api.post('/api/v1/orders/', payload, format='json').status_code, 201)

    # 9 — Zakaz yaratish — hamma
    def test_rule9_zakaz_create_all_roles(self):
        payload = {
            'product': self.product.pk,
            'quantity': 1,
            'contract_number': 'Z-1/2026',
        }
        for user in (self.operator, self.accountant, self.manager):
            self._auth(user)
            body = dict(payload)
            body['contract_number'] = f'Z-{user.username}/2026'
            res = self.api.post('/api/v1/orders/zakaz/', body, format='json')
            self.assertIn(res.status_code, (201, 400), (user.username, res.data))

    # 10 — Zakaz status faqat management
    def test_rule10_zakaz_status_management_only(self):
        from apps.orders.models import Zakaz
        zakaz = Zakaz.objects.create(
            product=self.product, quantity=3, contract_number='Z-ST/2026',
            status=Zakaz.NEW,
        )
        self._auth(self.operator)
        res = self.api.patch(
            f'/api/v1/orders/zakaz/{zakaz.pk}/',
            {'status': 'confirmed', 'asos': 'test'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)
        self._auth(self.manager)
        res = self.api.patch(
            f'/api/v1/orders/zakaz/{zakaz.pk}/',
            {'status': 'confirmed', 'asos': 'test', 'contract_number': 'Z-ST/2026'},
            format='json',
        )
        self.assertIn(res.status_code, (200, 400))

    # 11 — Hisobotlar
    def test_rule11_reports_accountant_management_only(self):
        self._auth(self.operator)
        self.assertEqual(self.api.get('/api/v1/reports/summary/').status_code, 403)
        self._auth(self.accountant)
        self.assertEqual(self.api.get('/api/v1/reports/summary/').status_code, 200)
        self._auth(self.manager)
        self.assertEqual(self.api.get('/api/v1/reports/summary/').status_code, 200)
