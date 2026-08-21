from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.orders.models import Booking
from apps.users.models import User
from apps.warehouse.models import Product, Stock


class BookingWorkflowTests(TestCase):
    """
    Sales bron so'rovi: darhol band qiladi, ikkinchi sales xodimi bandlangan
    miqdordan ortiq bron qila olmaydi, Admin tasdiqlaydi/rad etadi/bekor
    qiladi/boshqa xodimga o'tkazadi.
    """

    def setUp(self):
        self.api = APIClient()
        self.sales1 = User.objects.create_user('sales1', password='x', role=User.SALES)
        self.sales2 = User.objects.create_user('sales2', password='x', role=User.SALES)
        self.manager = User.objects.create_user('mng', password='x', role=User.MANAGEMENT)
        self.product = Product.objects.create(
            name='Server X', serial_number='SRV-1',
            purchase_price=Decimal('500.00'),
        )
        Stock.objects.create(product=self.product, quantity=5, warehouse_location='A1')

    def _create_booking(self, user, quantity=3):
        self.api.force_authenticate(user)
        return self.api.post('/api/v1/orders/booking/', {
            'product': self.product.id, 'quantity': quantity,
        })

    def test_sales_can_create_booking_and_it_reserves_stock(self):
        res = self._create_booking(self.sales1, quantity=3)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['status'], Booking.PENDING)
        self.assertEqual(res.data['sales_rep'], self.sales1.id)
        stock = Stock.objects.get(product=self.product)
        self.assertEqual(stock.reserved_quantity, 3)

    def test_second_sales_rep_blocked_when_stock_already_booked(self):
        res1 = self._create_booking(self.sales1, quantity=4)
        self.assertEqual(res1.status_code, 201, res1.data)
        res2 = self._create_booking(self.sales2, quantity=2)
        self.assertEqual(res2.status_code, 400)

    def test_sales_only_sees_own_bookings(self):
        self._create_booking(self.sales1, quantity=1)
        self.api.force_authenticate(self.sales2)
        self.api.post('/api/v1/orders/booking/', {'product': self.product.id, 'quantity': 1})
        self.api.force_authenticate(self.sales1)
        res = self.api.get('/api/v1/orders/booking/')
        self.assertEqual(res.status_code, 200)
        rep_ids = {row['sales_rep'] for row in res.data['results']} if isinstance(res.data, dict) and 'results' in res.data else {row['sales_rep'] for row in res.data}
        self.assertEqual(rep_ids, {self.sales1.id})

    def test_management_sees_all_bookings(self):
        self._create_booking(self.sales1, quantity=1)
        self.api.force_authenticate(self.sales2)
        self.api.post('/api/v1/orders/booking/', {'product': self.product.id, 'quantity': 1})
        self.api.force_authenticate(self.manager)
        res = self.api.get('/api/v1/orders/booking/')
        count = res.data['count'] if isinstance(res.data, dict) and 'count' in res.data else len(res.data)
        self.assertEqual(count, 2)

    def test_management_confirm_reject_cancel_reassign(self):
        res = self._create_booking(self.sales1, quantity=2)
        booking_id = res.data['id']

        self.api.force_authenticate(self.sales1)
        forbidden = self.api.post(f'/api/v1/orders/booking/{booking_id}/confirm/')
        self.assertEqual(forbidden.status_code, 403)

        self.api.force_authenticate(self.manager)
        confirm_res = self.api.post(f'/api/v1/orders/booking/{booking_id}/confirm/')
        self.assertEqual(confirm_res.status_code, 200, confirm_res.data)
        self.assertEqual(confirm_res.data['status'], Booking.CONFIRMED)

        reassign_res = self.api.post(
            f'/api/v1/orders/booking/{booking_id}/reassign/', {'sales_rep': self.sales2.id})
        self.assertEqual(reassign_res.status_code, 200, reassign_res.data)
        self.assertEqual(reassign_res.data['sales_rep'], self.sales2.id)
        stock = Stock.objects.get(product=self.product)
        self.assertEqual(stock.reserved_quantity, 2)  # reassign keeps the reservation

        cancel_res = self.api.delete(f'/api/v1/orders/booking/{booking_id}/')
        self.assertEqual(cancel_res.status_code, 204)
        stock.refresh_from_db()
        self.assertEqual(stock.reserved_quantity, 0)  # cancel releases it

    def test_reject_releases_stock(self):
        res = self._create_booking(self.sales1, quantity=2)
        booking_id = res.data['id']
        self.api.force_authenticate(self.manager)
        reject_res = self.api.post(f'/api/v1/orders/booking/{booking_id}/reject/')
        self.assertEqual(reject_res.status_code, 200, reject_res.data)
        stock = Stock.objects.get(product=self.product)
        self.assertEqual(stock.reserved_quantity, 0)

    def test_new_booking_notifies_management(self):
        from apps.notifications.models import Notification
        res = self._create_booking(self.sales1, quantity=1)
        self.assertEqual(res.status_code, 201, res.data)
        notif = Notification.objects.filter(recipient=self.manager, booking_id=res.data['id']).first()
        self.assertIsNotNone(notif)
