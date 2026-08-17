from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.expenses.models import Expense
from apps.users.models import User
from apps.warehouse.models import Category, Product


class StockInKassaSyncTests(TestCase):
    """
    Regressiya: ombor "kirim" (add-stock, mahsulot yaratish) endpointlari
    kelish narxi bo'lsa — kassadan chiqim (Expense) yozadi.
    """

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            'mng', password='x', role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.category = Category.objects.create(name='Mebel')

    def test_add_stock_records_expense_when_price_set(self):
        product = Product.objects.create(
            name='Stol', category=self.category,
            purchase_price=Decimal('50000.00'),
        )
        res = self.api.post(
            f'/api/v1/warehouse/products/{product.id}/add-stock/',
            {
                'quantity': 10,
                'warehouse_location': 'A-1',
                'asos': 'Kirim orderi №1',
                'contract_number': 'SH-2026/001',
            },
        )
        self.assertEqual(res.status_code, 201, res.data)
        expense = Expense.objects.get(comment__icontains='Stol')
        self.assertEqual(expense.amount, Decimal('500000.00'))
        self.assertIn('SH-2026/001', expense.comment)
        self.assertEqual(expense.expense_type.code, 'import')

    def test_add_stock_skips_expense_without_price(self):
        product = Product.objects.create(name='Kreslo', category=self.category)
        res = self.api.post(
            f'/api/v1/warehouse/products/{product.id}/add-stock/',
            {'quantity': 5, 'warehouse_location': 'A-1', 'asos': 'Kirim'},
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertFalse(Expense.objects.exists())

    def test_product_create_with_initial_quantity_records_expense(self):
        res = self.api.post('/api/v1/warehouse/products/', {
            'name': 'Divan',
            'category': self.category.id,
            'purchase_price': '200000.00',
            'quantity': 4,
            'warehouse_location': 'B-1',
        })
        self.assertEqual(res.status_code, 201, res.data)
        expense = Expense.objects.get(comment__icontains='Divan')
        self.assertEqual(expense.amount, Decimal('800000.00'))
