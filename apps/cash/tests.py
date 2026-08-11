from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.cash.models import Payment
from apps.sales.models import Sale
from apps.users.models import User
from apps.warehouse.models import Product


def _make_sale_payment():
    product = Product.objects.create(
        name='Monitor', serial_number='MN-1',
        purchase_price=Decimal('500000.00'))
    sale = Sale.objects.create(
        product=product, quantity=2, sold_price=Decimal('1000000.00'),
        sold_date=date.today())
    return Payment.objects.create(sale=sale)


class PaymentBoundsTests(TestCase):
    """
    Regressiya: PATCH orqali paid_amount manfiy yoki total_amount'dan
    katta qilib qo'yish mumkin edi — /pay/ dagi hamma tekshiruvlar
    chetlab o'tilardi.
    """

    def setUp(self):
        self.api = APIClient()
        self.accountant = User.objects.create_user(
            'acc_c', password='x', role=User.ACCOUNTANT)
        self.payment = _make_sale_payment()  # total = 2 000 000
        self.api.force_authenticate(self.accountant)
        self.url = f'/api/v1/cash/payments/{self.payment.pk}/'

    def test_negative_paid_amount_rejected(self):
        res = self.api.patch(self.url, {'paid_amount': '-100'}, format='json')
        self.assertEqual(res.status_code, 400, res.data)

    def test_paid_amount_over_total_rejected(self):
        res = self.api.patch(self.url, {'paid_amount': '999999999'},
                             format='json')
        self.assertEqual(res.status_code, 400, res.data)

    def test_pay_over_remaining_rejected(self):
        res = self.api.post(f'{self.url}pay/', {'amount': '3000000'},
                            format='json')
        self.assertEqual(res.status_code, 400, res.data)

    def test_valid_patch_writes_ledger_transaction(self):
        res = self.api.patch(self.url, {'paid_amount': '500000'},
                             format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.paid_amount, Decimal('500000'))
        self.assertEqual(
            sum(t.amount for t in self.payment.transactions.all()),
            self.payment.paid_amount)


class PaymentOperatorAccessTests(TestCase):
    """
    Regressiya: operator to'lovlar ro'yxatini o'qib sotuv narxi/komissiyani
    ko'ra olardi — endi kassa operator uchun butunlay yopiq.
    """

    def setUp(self):
        self.api = APIClient()
        self.operator = User.objects.create_user(
            'op_c', password='x', role=User.OPERATOR)
        self.accountant = User.objects.create_user(
            'acc_c2', password='x', role=User.ACCOUNTANT)
        _make_sale_payment()

    def test_operator_cannot_list_payments(self):
        self.api.force_authenticate(self.operator)
        res = self.api.get('/api/v1/cash/payments/')
        self.assertEqual(res.status_code, 403)

    def test_accountant_can_list_payments(self):
        self.api.force_authenticate(self.accountant)
        res = self.api.get('/api/v1/cash/payments/')
        self.assertEqual(res.status_code, 200)
