from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.sales.models import Sale
from apps.sales.serializers import SaleSerializer
from apps.users.models import User
from apps.warehouse.models import Product, Stock


def _make_product(serial='SN-1', purchase='1000.00'):
    return Product.objects.create(
        name='Laptop', model='X1', serial_number=serial,
        purchase_price=Decimal(purchase),
    )


class SaleLogicTests(TestCase):
    def setUp(self):
        self.product = _make_product()
        self.stock = Stock.objects.create(
            product=self.product, quantity=10, warehouse_location='A1'
        )

    def _sale_data(self, quantity):
        return {
            'product': self.product.id,
            'sold_price': '1300.00',
            'quantity': quantity,
            'sold_to': 'Ali',
            'sold_date': date.today().isoformat(),
        }

    def test_quantity_in_stock(self):
        self.assertEqual(self.product.quantity_in_stock, 10)
        self.assertEqual(self.product.available_quantity, 10)

    def test_sale_decrements_stock(self):
        serializer = SaleSerializer(data=self._sale_data(3))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        sale = serializer.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_in_stock, 7)
        # profit = (1300 - 1000) * 3
        self.assertEqual(sale.profit, Decimal('900.00'))
        self.assertEqual(sale.total_amount, Decimal('3900.00'))

    def test_cannot_sell_more_than_stock(self):
        serializer = SaleSerializer(data=self._sale_data(50))
        self.assertFalse(serializer.is_valid())
        self.assertIn('quantity', serializer.errors)

    def test_sale_does_not_consume_reserved_stock(self):
        """Buyurtma uchun bron qilingan qoldiq sotuvga ketmasligi kerak."""
        self.stock.reserved_quantity = 6
        self.stock.save(update_fields=['reserved_quantity'])
        # available = 10 - 6 = 4 → 5 ta sotib bo'lmaydi
        serializer = SaleSerializer(data=self._sale_data(5))
        self.assertFalse(serializer.is_valid())
        self.assertIn('quantity', serializer.errors)
        # 4 ta sotish mumkin, bron tegilmaydi
        serializer = SaleSerializer(data=self._sale_data(4))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 6)
        self.assertEqual(self.stock.reserved_quantity, 6)

    def test_deplete_skips_fully_reserved_row(self):
        """To'liq bron qilingan qatordan sotuv olinmaydi (FIFO keyingisiga o'tadi)."""
        self.stock.reserved_quantity = 10
        self.stock.save(update_fields=['reserved_quantity'])
        Stock.objects.create(
            product=self.product, quantity=5, warehouse_location='B2'
        )
        serializer = SaleSerializer(data=self._sale_data(5))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)   # bronli qator tegilmadi
        other = self.product.stocks.get(warehouse_location='B2')
        self.assertEqual(other.quantity, 0)


class SaleUpdateDeleteAPITests(TestCase):
    """Sotuv tahrirlanganda/o'chirilganda ombor qoldig'i mos tuzatiladi."""

    def setUp(self):
        self.client_api = APIClient()
        self.operator = User.objects.create_user(
            'op', password='pass1234', role=User.OPERATOR
        )
        self.client_api.force_authenticate(self.operator)
        self.product = _make_product()
        self.stock = Stock.objects.create(
            product=self.product, quantity=10, warehouse_location='A1'
        )
        serializer = SaleSerializer(data={
            'product': self.product.id,
            'sold_price': '1300.00',
            'quantity': 3,
            'sold_date': date.today().isoformat(),
        })
        serializer.is_valid(raise_exception=True)
        self.sale = serializer.save()  # stock: 10 → 7

    def test_increase_quantity_depletes_more(self):
        res = self.client_api.patch(
            f'/api/v1/sales/{self.sale.id}/', {'quantity': 5}
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)

    def test_decrease_quantity_restores_stock(self):
        res = self.client_api.patch(
            f'/api/v1/sales/{self.sale.id}/', {'quantity': 1}
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 9)

    def test_same_quantity_keeps_stock(self):
        res = self.client_api.patch(
            f'/api/v1/sales/{self.sale.id}/', {'quantity': 3}
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 7)

    def test_cannot_increase_beyond_available(self):
        # available = 7, o'zining 3 tasi qaytadi → maksimum 10
        res = self.client_api.patch(
            f'/api/v1/sales/{self.sale.id}/', {'quantity': 11}
        )
        self.assertEqual(res.status_code, 400)

    def test_delete_restores_stock(self):
        res = self.client_api.delete(f'/api/v1/sales/{self.sale.id}/')
        self.assertEqual(res.status_code, 204)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)
        self.assertFalse(Sale.objects.filter(pk=self.sale.pk).exists())


class ProfitSnapshotTests(TestCase):
    """
    Regressiya: profit sotuv paytidagi tannarx bilan muhrlanadi — keyin
    mahsulot narxi o'zgarsa ham tarixiy sotuvlar foydasi o'zgarmaydi.
    """

    def test_profit_frozen_at_sale_time(self):
        product = _make_product(serial='SNAP-1', purchase='1000.00')
        sale = Sale.objects.create(
            product=product, quantity=2, sold_price=Decimal('1300.00'),
            sold_date=date.today())
        self.assertEqual(sale.profit, Decimal('600.00'))

        # Tannarx keyin oshdi — eski sotuv foydasi o'zgarmasligi kerak
        product.purchase_price = Decimal('1200.00')
        product.save()
        sale.refresh_from_db()
        self.assertEqual(sale.profit, Decimal('600.00'))
