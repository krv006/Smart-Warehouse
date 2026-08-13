from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.cash.models import Payment
from apps.orders.models import Order, OrderItem, Zakaz
from apps.users.models import User
from apps.warehouse.models import Product, Stock


class OrderActionPermissionTests(TestCase):
    """
    Ombor qoldig'ini siljitadigan amallar (fulfill/cancel/create-zakaz)
    faqat Operator yoki Management uchun — Accountant kirolmaydi.
    """

    ACTION_BODY = {'contract_number': 'SH-2026/001', 'asos': 'Test asos'}

    def setUp(self):
        self.client_api = APIClient()
        self.operator = User.objects.create_user(
            'op', password='x', role=User.OPERATOR)
        self.accountant = User.objects.create_user(
            'acc', password='x', role=User.ACCOUNTANT)
        self.manager = User.objects.create_user(
            'mng', password='x', role=User.MANAGEMENT)

        self.product = Product.objects.create(
            name='Printer', serial_number='PR-1',
            purchase_price=Decimal('500.00'),
        )
        self.stock = Stock.objects.create(
            product=self.product, quantity=10, warehouse_location='A1'
        )
        self.order = Order.objects.create(contract_number='SH-2026/001')
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product,
            quantity=3, unit_price=Decimal('700.00'),
        )
        self.order.reserve()

    def _post(self, user, action, body=None):
        self.client_api.force_authenticate(user)
        return self.client_api.post(
            f'/api/v1/orders/{self.order.pk}/{action}/',
            body if body is not None else self.ACTION_BODY,
        )

    def test_reserve_worked(self):
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.reserved_quantity, 3)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.RESERVED)

    def test_accountant_cannot_fulfill(self):
        res = self._post(self.accountant, 'fulfill')
        self.assertEqual(res.status_code, 403)

    def test_accountant_cannot_cancel(self):
        res = self._post(self.accountant, 'cancel')
        self.assertEqual(res.status_code, 403)

    def test_accountant_cannot_create_zakaz(self):
        res = self._post(self.accountant, 'create-zakaz')
        self.assertEqual(res.status_code, 403)

    def test_operator_can_fulfill(self):
        res = self._post(self.operator, 'fulfill')
        self.assertEqual(res.status_code, 200, res.data)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 7)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.FULFILLED)

    def test_management_can_cancel(self):
        res = self._post(self.manager, 'cancel')
        self.assertEqual(res.status_code, 200, res.data)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)   # qoldiq joyida
        self.assertEqual(self.stock.reserved_quantity, 0)  # bron bo'shadi
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.CANCELLED)

    def test_fulfill_requires_contract_and_asos(self):
        res = self._post(self.operator, 'fulfill', body={})
        self.assertEqual(res.status_code, 400)
        self.assertIn('contract_number', res.data)
        self.assertIn('asos', res.data)


class ManualZakazTests(TestCase):
    """
    2-xil (mustaqil) zakaz: narx MAJBURIY, umumiy summa (narx × miqdor)
    avtomatik hisoblanadi, miqdor o'zgarsa summa ham o'zgaradi.
    """

    ZAKAZ_URL = '/api/v1/orders/zakaz/'

    def setUp(self):
        self.api = APIClient()
        self.operator = User.objects.create_user('op2', password='x',
                                                  role=User.OPERATOR)
        self.manager = User.objects.create_user('mng_manual', password='x',
                                                role=User.MANAGEMENT)
        self.product = Product.objects.create(
            name='Server', serial_number='SRV-1',
            purchase_price=Decimal('900000.00'),
        )

    def _create(self, user, body):
        self.api.force_authenticate(user)
        return self.api.post(self.ZAKAZ_URL, body, format='json')

    def test_operator_manual_zakaz_without_price_allowed(self):
        res = self._create(self.operator, {'product': self.product.pk, 'quantity': 10})
        self.assertEqual(res.status_code, 201, res.data)

    def test_management_manual_zakaz_requires_price(self):
        res = self._create(self.manager, {'product': self.product.pk, 'quantity': 10})
        self.assertEqual(res.status_code, 400)
        self.assertIn('unit_price', res.data)

    def test_manual_zakaz_total_auto(self):
        res = self._create(self.manager, {'product': self.product.pk, 'quantity': 10,
                            'unit_price': '1000000'})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['zakaz_type'], 'manual')
        self.assertEqual(Decimal(res.data['total']), Decimal('10000000'))

    def test_total_recomputes_when_quantity_changes(self):
        res = self._create(self.manager, {'product': self.product.pk, 'quantity': 10,
                            'unit_price': '1000000'})
        zakaz_id = res.data['id']
        patch = self.api.patch(f'{self.ZAKAZ_URL}{zakaz_id}/',
                               {'quantity': 20}, format='json')
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertEqual(Decimal(patch.data['total']), Decimal('20000000'))


class BackorderZakazFlowTests(TestCase):
    """
    1-xil (backorder) zakaz: buyurtmada yetmagan miqdorga avtomatik ochiladi,
    narxsiz. Status oqimi: new → confirmed → received. Qabul qilinganda
    ombor to'ladi va buyurtma avtomatik "qisman bron" → "bron qilingan".
    """

    ZAKAZ_URL = '/api/v1/orders/zakaz/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng2', password='x',
                                                 role=User.MANAGEMENT)
        self.product = Product.objects.create(
            name='Laptop', serial_number='LP-1',
            purchase_price=Decimal('400.00'),
        )
        Stock.objects.create(product=self.product, quantity=2,
                             warehouse_location='A1')
        # 5 so'radi, omborda 2 ta → 3 ta backorder
        self.order = Order.objects.create(contract_number='SH-2026/900')
        OrderItem.objects.create(order=self.order, product=self.product,
                                 quantity=5, unit_price=Decimal('700.00'))
        self.order.reserve()
        self.order.refresh_status()
        self.backorder = self.order.create_backorder_zakaz()[0]

    def test_backorder_zakaz_is_typed_and_priceless(self):
        self.assertEqual(self.backorder.zakaz_type, Zakaz.BACKORDER)
        self.assertEqual(self.backorder.quantity, 3)
        self.assertIsNone(self.backorder.total)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.PARTIAL)

    def test_receive_flips_order_to_reserved(self):
        self.api.force_authenticate(self.manager)
        url = f'{self.ZAKAZ_URL}{self.backorder.pk}/'
        # new → confirmed
        r1 = self.api.patch(url, {'status': 'confirmed',
                                  'contract_number': 'SH-2026/900',
                                  'asos': 'Tasdiqlandi'}, format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        # confirmed → ordered
        r2 = self.api.patch(url, {'status': 'ordered',
                                  'asos': 'Etkazuvchiga yuborildi'}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        # ordered → received (faktura majburiy)
        r3 = self.api.patch(url, {'status': 'received', 'received_qty': 3,
                                  'faktura': 'F-900', 'asos': 'Qabul qilindi'},
                            format='json')
        self.assertEqual(r3.status_code, 200, r3.data)
        # Ombor to'ldi, buyurtma to'liq bronlandi
        self.order.refresh_from_db()
        self.assertEqual(self.order.reserved_qty, 5)
        self.assertEqual(self.order.status, Order.RESERVED)


class OrderEditKassaSyncTests(TestCase):
    """
    Buyurtma tahrirlanganda (miqdor o'zgardi YOKI yangi mahsulot qo'shildi)
    kassadagi jami summa (Payment.total_amount) HAM sinxron bo'lishi kerak.
    Regressiya: avval tahrirdan keyin kassa eski summada qolib ketardi.
    """

    def setUp(self):
        self.api = APIClient()
        self.op = User.objects.create_user('opk', password='x', role=User.OPERATOR)
        self.p1 = Product.objects.create(name='server', serial_number='SS1',
                                         purchase_price=Decimal('1'))
        self.p2 = Product.objects.create(name='Test', serial_number='TT1',
                                         purchase_price=Decimal('1'))
        for p in (self.p1, self.p2):
            Stock.objects.create(product=p, quantity=100, warehouse_location='A')
        self.api.force_authenticate(self.op)

        # 35M + 25M = 60M, oldindan to'lov 5M
        res = self.api.post('/api/v1/orders/', {
            'contract_number': '1/1108', 'prepaid_amount': '5000000',
            'items': [
                {'product': self.p1.pk, 'quantity': 10, 'unit_price': '3500000'},
                {'product': self.p2.pk, 'quantity': 5,  'unit_price': '5000000'},
            ],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.oid = res.data['id']

    def _payment(self):
        return Payment.objects.get(order_id=self.oid)

    def test_initial_total(self):
        self.assertEqual(self._payment().total_amount, Decimal('60000000'))

    def test_edit_quantity_syncs_kassa(self):
        item2 = OrderItem.objects.get(order_id=self.oid, product=self.p2)
        r = self.api.patch(f'/api/v1/orders/{self.oid}/', {
            'asos': 'Miqdor oshdi',
            'items': [{'id': item2.pk, 'quantity': 6}],   # 25M → 30M
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._payment().total_amount, Decimal('65000000'))

    def test_add_new_product_syncs_kassa(self):
        # Aynan foydalanuvchi holati: yana bitta mahsulot qo'shildi
        p3 = Product.objects.create(name='Extra', serial_number='EX1',
                                    purchase_price=Decimal('1'))
        Stock.objects.create(product=p3, quantity=100, warehouse_location='A')
        r = self.api.patch(f'/api/v1/orders/{self.oid}/', {
            'asos': 'Yangi mahsulot qo\'shildi',
            'items': [{'product': p3.pk, 'quantity': 1, 'unit_price': '5000000'}],
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # 60M + 5M = 65M
        pay = self._payment()
        self.assertEqual(pay.total_amount, Decimal('65000000'))
        self.assertEqual(pay.paid_amount, Decimal('5000000'))
        self.assertEqual(pay.remaining_amount, Decimal('60000000'))


class ZakazReceivedQtyGuardTests(TestCase):
    """
    Regressiya: received_qty zakaz miqdoridan oshsa omborga "fantom" tovar
    kirardi; operator received_qty ni umuman o'zgartira olmasligi kerak.
    """

    ZAKAZ_URL = '/api/v1/orders/zakaz/'

    def setUp(self):
        self.api = APIClient()
        self.operator = User.objects.create_user('op3', password='x',
                                                 role=User.OPERATOR)
        self.manager = User.objects.create_user('mng3', password='x',
                                                role=User.MANAGEMENT)
        self.product = Product.objects.create(
            name='Router', serial_number='RT-1',
            purchase_price=Decimal('100.00'))
        self.zakaz = Zakaz.objects.create(
            product=self.product, quantity=3, unit_price=Decimal('100.00'),
            zakaz_type=Zakaz.MANUAL, status=Zakaz.NEW)

    def test_received_qty_cannot_exceed_quantity(self):
        self.api.force_authenticate(self.manager)
        res = self.api.patch(f'{self.ZAKAZ_URL}{self.zakaz.pk}/',
                             {'received_qty': 30}, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('received_qty', res.data)

    def test_operator_cannot_set_received_qty(self):
        self.api.force_authenticate(self.operator)
        res = self.api.patch(f'{self.ZAKAZ_URL}{self.zakaz.pk}/',
                             {'received_qty': 2}, format='json')
        self.assertEqual(res.status_code, 403, res.data)

    def test_operator_patch_ignores_payment_fields(self):
        self.api.force_authenticate(self.operator)
        res = self.api.patch(
            f'{self.ZAKAZ_URL}{self.zakaz.pk}/',
            {'payment_status': 'partial', 'paid_amount': '500000'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.zakaz.refresh_from_db()
        self.assertEqual(self.zakaz.payment_status, Zakaz.UNPAID)
        self.assertEqual(self.zakaz.paid_amount, Decimal('0'))


class ZakazBulkCreateTests(TestCase):
    BULK_URL = '/api/v1/orders/zakaz/bulk/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_bulk', password='x',
                                                role=User.MANAGEMENT)
        self.operator = User.objects.create_user('op_bulk', password='x',
                                                 role=User.OPERATOR)
        self.accountant = User.objects.create_user('acc_bulk', password='x',
                                                   role=User.ACCOUNTANT)
        self.product_a = Product.objects.create(
            name='Router A', serial_number='RT-A',
            purchase_price=Decimal('100000'))
        self.product_b = Product.objects.create(
            name='Switch B', serial_number='SW-B',
            purchase_price=Decimal('50000'))

    def _bulk(self, user, body):
        self.api.force_authenticate(user)
        return self.api.post(self.BULK_URL, body, format='json')

    def test_mixed_product_and_new_product_same_import_batch(self):
        body = {
            'supplier': 'Test supplier',
            'contract_number': '99/1108',
            'contract_date': '2026-08-13',
            'items': [
                {'product': self.product_a.pk, 'quantity': 20,
                 'unit_price': '100000.00'},
                {'new_product': {'name': 'New Item', 'unit': 'piece'},
                 'quantity': 4, 'unit_price': '50000.00'},
            ],
        }
        res = self._bulk(self.manager, body)
        self.assertEqual(res.status_code, 201, res.data)
        zakazlar = res.data['zakazlar']
        self.assertEqual(len(zakazlar), 2)
        batches = {z['import_batch'] for z in zakazlar}
        self.assertEqual(len(batches), 1)
        self.assertIsNotNone(next(iter(batches)))

    def test_bulk_partial_payment_splits_and_persists(self):
        body = {
            'supplier': 'Pay test',
            'contract_number': '88/1108',
            'contract_date': '2026-08-13',
            'payment_status': 'partial',
            'paid_amount': '500000.00',
            'items': [
                {'product': self.product_a.pk, 'quantity': 10,
                 'unit_price': '100000.00'},
                {'product': self.product_b.pk, 'quantity': 5,
                 'unit_price': '50000.00'},
            ],
        }
        res = self._bulk(self.manager, body)
        self.assertEqual(res.status_code, 201, res.data)
        zakazlar = res.data['zakazlar']
        paid_sum = sum(Decimal(z['paid_amount']) for z in zakazlar)
        self.assertEqual(paid_sum, Decimal('500000.00'))
        self.assertTrue(all(z['payment_status'] == 'partial' for z in zakazlar))

    def test_bulk_partial_payment_rounding_remainder_on_last_line(self):
        body = {
            'payment_status': 'partial',
            'paid_amount': '100.00',
            'items': [
                {'product': self.product_a.pk, 'quantity': 1,
                 'unit_price': '100.00'},
                {'product': self.product_b.pk, 'quantity': 1,
                 'unit_price': '100.00'},
                {'product': self.product_a.pk, 'quantity': 1,
                 'unit_price': '100.00'},
            ],
        }
        res = self._bulk(self.manager, body)
        self.assertEqual(res.status_code, 201, res.data)
        paid_sum = sum(Decimal(z['paid_amount']) for z in res.data['zakazlar'])
        self.assertEqual(paid_sum, Decimal('100.00'))

    def test_bulk_append_to_existing_import_batch(self):
        batch_id = __import__('uuid').uuid4()
        body = {
            'import_batch': str(batch_id),
            'supplier': 'Append test',
            'items': [
                {'product': self.product_a.pk, 'quantity': 2,
                 'unit_price': '100000.00'},
            ],
        }
        res = self._bulk(self.manager, body)
        self.assertEqual(res.status_code, 201, res.data)
        zakaz = Zakaz.objects.get(pk=res.data['zakazlar'][0]['id'])
        self.assertEqual(zakaz.import_batch, batch_id)

    def test_create_with_import_batch(self):
        batch_id = __import__('uuid').uuid4()
        self.api.force_authenticate(self.manager)
        res = self.api.post('/api/v1/orders/zakaz/', {
            'product': self.product_a.pk,
            'quantity': 3,
            'unit_price': '100000.00',
            'import_batch': str(batch_id),
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        zakaz = Zakaz.objects.get(pk=res.data['id'])
        self.assertEqual(zakaz.import_batch, batch_id)

    def test_bulk_partial_rejects_without_prices(self):
        body = {
            'payment_status': 'partial',
            'paid_amount': '1000.00',
            'items': [
                {'product': self.product_a.pk, 'quantity': 10,
                 'unit_price': '0.00'},
            ],
        }
        res = self._bulk(self.manager, body)
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('paid_amount', res.data)

    def test_bulk_partial_rejects_paid_above_total(self):
        body = {
            'payment_status': 'partial',
            'paid_amount': '999999999.00',
            'items': [
                {'product': self.product_a.pk, 'quantity': 2,
                 'unit_price': '100000.00'},
            ],
        }
        res = self._bulk(self.manager, body)
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('paid_amount', res.data)

    def test_operator_bulk_strips_payment_fields(self):
        body = {
            'payment_status': 'partial',
            'paid_amount': '500000.00',
            'items': [
                {'product': self.product_a.pk, 'quantity': 3},
            ],
        }
        res = self._bulk(self.operator, body)
        self.assertEqual(res.status_code, 201, res.data)
        zakaz = Zakaz.objects.get(pk=res.data['zakazlar'][0]['id'])
        self.assertEqual(zakaz.payment_status, Zakaz.UNPAID)
        self.assertEqual(zakaz.paid_amount, Decimal('0'))

    def test_accountant_bulk_partial_requires_line_prices(self):
        body = {
            'payment_status': 'partial',
            'paid_amount': '200000.00',
            'items': [
                {'product': self.product_a.pk, 'quantity': 5,
                 'unit_price': '100000.00'},
            ],
        }
        res = self._bulk(self.accountant, body)
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('paid_amount', res.data)


class ZakazBatchEndpointTests(TestCase):
    BATCH_URL = '/api/v1/orders/zakaz/{}/batch/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_batch', password='x',
                                                role=User.MANAGEMENT)
        self.product = Product.objects.create(
            name='Batch Prod', serial_number='BP-1',
            purchase_price=Decimal('1000'))
        self.batch_id = __import__('uuid').uuid4()
        self.z1 = Zakaz.objects.create(
            product=self.product, quantity=10, unit_price=Decimal('100'),
            zakaz_type=Zakaz.MANUAL, import_batch=self.batch_id,
            contract_number='1/1108', contract_date='2026-08-13',
            supplier='Sup', status=Zakaz.NEW, created_by=self.manager)
        self.z2 = Zakaz.objects.create(
            product=self.product, quantity=4, unit_price=Decimal('100'),
            zakaz_type=Zakaz.MANUAL, import_batch=self.batch_id,
            contract_number='1/1108', contract_date='2026-08-13',
            supplier='Sup', status=Zakaz.NEW, created_by=self.manager)

    def test_batch_returns_siblings_by_import_batch(self):
        self.api.force_authenticate(self.manager)
        res = self.api.get(self.BATCH_URL.format(self.z1.pk))
        self.assertEqual(res.status_code, 200, res.data)
        ids = {item['id'] for item in res.data['items']}
        self.assertEqual(ids, {self.z1.pk, self.z2.pk})

    def test_batch_single_without_group_key(self):
        lone = Zakaz.objects.create(
            product=self.product, quantity=1, unit_price=Decimal('100'),
            zakaz_type=Zakaz.MANUAL, status=Zakaz.NEW, supplier='Other')
        self.api.force_authenticate(self.manager)
        res = self.api.get(self.BATCH_URL.format(lone.pk))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(res.data['items']), 1)


class ZakazPartialPaymentPatchTests(TestCase):
    ZAKAZ_URL = '/api/v1/orders/zakaz/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_pay', password='x',
                                                role=User.MANAGEMENT)
        self.accountant = User.objects.create_user('acc_pay', password='x',
                                                   role=User.ACCOUNTANT)
        self.product = Product.objects.create(
            name='Pay Prod', serial_number='PP-1',
            purchase_price=Decimal('1000'))
        self.zakaz = Zakaz.objects.create(
            product=self.product, quantity=10, unit_price=Decimal('100000'),
            zakaz_type=Zakaz.MANUAL, status=Zakaz.NEW,
            payment_status=Zakaz.UNPAID)

    def test_patch_partial_persists_and_capped(self):
        self.api.force_authenticate(self.accountant)
        res = self.api.patch(
            f'{self.ZAKAZ_URL}{self.zakaz.pk}/',
            {'payment_status': 'partial', 'paid_amount': '500000'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['payment_status'], 'partial')
        self.assertEqual(Decimal(res.data['paid_amount']), Decimal('500000'))

        over = self.api.patch(
            f'{self.ZAKAZ_URL}{self.zakaz.pk}/',
            {'payment_status': 'partial', 'paid_amount': '999999999'},
            format='json',
        )
        self.assertEqual(over.status_code, 400, over.data)
        self.assertIn('paid_amount', over.data)
