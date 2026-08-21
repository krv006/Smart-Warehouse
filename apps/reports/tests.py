from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.orders.models import Booking
from apps.users.models import User
from apps.warehouse.models import Product, Stock


class SalesRepSummaryViewTests(TestCase):
    URL = '/api/v1/reports/sales-rep-summary/'

    def setUp(self):
        self.api = APIClient()
        self.sales1 = User.objects.create_user('sales1', password='x', role=User.SALES)
        self.sales2 = User.objects.create_user('sales2', password='x', role=User.SALES)
        self.manager = User.objects.create_user('mng', password='x', role=User.MANAGEMENT)
        self.product = Product.objects.create(
            name='Item', serial_number='ITM-1', purchase_price=Decimal('500'))
        Stock.objects.create(product=self.product, quantity=10, warehouse_location='A1')
        Booking(product=self.product, quantity=2, sales_rep=self.sales1).create_and_reserve()

    def test_sales_sees_only_own_summary_ignoring_param(self):
        self.api.force_authenticate(self.sales1)
        res = self.api.get(self.URL, {'sales_rep': self.sales2.id})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['sales_rep'], self.sales1.id)
        self.assertEqual(res.data['bookings']['total'], 1)

    def test_management_requires_sales_rep_param(self):
        self.api.force_authenticate(self.manager)
        res = self.api.get(self.URL)
        self.assertEqual(res.status_code, 400)

    def test_management_can_view_any_sales_rep(self):
        self.api.force_authenticate(self.manager)
        res = self.api.get(self.URL, {'sales_rep': self.sales1.id})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['bookings']['total'], 1)
        self.assertEqual(res.data['bookings']['pending'], 1)

        res2 = self.api.get(self.URL, {'sales_rep': self.sales2.id})
        self.assertEqual(res2.status_code, 200, res2.data)
        self.assertEqual(res2.data['bookings']['total'], 0)
