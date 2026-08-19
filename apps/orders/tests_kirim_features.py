"""
Kirim (Zakaz) feature testlari: import_type, supplier_client, prepaid_percent,
Zakaz to'liq tahrirlash (rol cheklovlari yumshatilgan) va Buyurtmadan
omborda yo'q mahsulot uchun avtomatik MANUAL zakaz ochilishi.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.orders.models import Order, OrderItem, Zakaz
from apps.users.models import User
from apps.warehouse.models import Category, Product, ProductOrigin, Stock


class ImportTypeTests(TestCase):
    """`import_type` — 3 tanlov, saqlanadi va ro'yxatda filtrlanadi."""

    ZAKAZ_URL = '/api/v1/orders/zakaz/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            'mng_it', password='x', role=User.MANAGEMENT)
        self.product = Product.objects.create(
            name='Monitor', serial_number='MON-1',
            purchase_price=Decimal('300000'))

    def test_default_is_domestic(self):
        zakaz = Zakaz.objects.create(
            product=self.product, quantity=5, zakaz_type=Zakaz.MANUAL)
        self.assertEqual(zakaz.import_type, Zakaz.DOMESTIC)

    def test_create_with_import_type_persists(self):
        self.api.force_authenticate(self.manager)
        res = self.api.post(self.ZAKAZ_URL, {
            'product': self.product.pk, 'quantity': 4,
            'unit_price': '100000', 'selling_price': '150000',
            'import_type': Zakaz.IMPORT,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['import_type'], Zakaz.IMPORT)

    def test_filter_by_import_type(self):
        Zakaz.objects.create(product=self.product, quantity=1,
                             zakaz_type=Zakaz.MANUAL, import_type=Zakaz.IMPORT)
        Zakaz.objects.create(product=self.product, quantity=2,
                             zakaz_type=Zakaz.MANUAL, import_type=Zakaz.CHARTER)
        self.api.force_authenticate(self.manager)
        res = self.api.get(self.ZAKAZ_URL, {'import_type': Zakaz.IMPORT})
        self.assertEqual(res.status_code, 200, res.data)
        results = res.data['results'] if isinstance(res.data, dict) else res.data
        self.assertTrue(all(r['import_type'] == Zakaz.IMPORT for r in results))
        self.assertEqual(len(results), 1)


class SupplierClientTests(TestCase):
    """`supplier_client` — mijozlar bazasidan yetkazuvchi tanlash (FK)."""

    ZAKAZ_URL = '/api/v1/orders/zakaz/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            'mng_sc', password='x', role=User.MANAGEMENT)
        self.product = Product.objects.create(
            name='Kabel', serial_number='KB-1',
            purchase_price=Decimal('1000'))
        self.supplier = Client.objects.create(
            client_type=Client.LEGAL, company_name='Yetkazuvchi MChJ')
        self.zakaz = Zakaz.objects.create(
            product=self.product, quantity=10, zakaz_type=Zakaz.MANUAL)

    def test_patch_supplier_client(self):
        self.api.force_authenticate(self.manager)
        res = self.api.patch(f'{self.ZAKAZ_URL}{self.zakaz.pk}/',
                             {'supplier_client': str(self.supplier.pk)},
                             format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['supplier_client_name'], 'Yetkazuvchi MChJ')
        self.zakaz.refresh_from_db()
        self.assertEqual(self.zakaz.supplier_client_id, self.supplier.pk)

    def test_free_text_supplier_still_works(self):
        """Erkin matn (`supplier`) fallback saqlanib qoladi."""
        self.api.force_authenticate(self.manager)
        res = self.api.patch(f'{self.ZAKAZ_URL}{self.zakaz.pk}/',
                             {'supplier': 'Qo\'lda kiritilgan nom'},
                             format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['supplier'], 'Qo\'lda kiritilgan nom')
        self.assertIsNone(res.data['supplier_client'])


class PrepaidPercentTests(TestCase):
    """`prepaid_percent` — Zakaz VA Order ikkalasida ham, default 30%."""

    ZAKAZ_URL = '/api/v1/orders/zakaz/'
    ORDER_URL = '/api/v1/orders/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            'mng_pp', password='x', role=User.MANAGEMENT)
        self.product = Product.objects.create(
            name='SSD', serial_number='SSD-1',
            purchase_price=Decimal('500000'), selling_price=Decimal('700000'))
        Stock.objects.create(product=self.product, quantity=10,
                             warehouse_location='A1')

    def test_zakaz_default_prepaid_percent(self):
        zakaz = Zakaz.objects.create(product=self.product, quantity=3,
                                     zakaz_type=Zakaz.MANUAL)
        self.assertEqual(zakaz.prepaid_percent, Decimal('30'))

    def test_zakaz_prepaid_percent_editable(self):
        zakaz = Zakaz.objects.create(product=self.product, quantity=3,
                                     zakaz_type=Zakaz.MANUAL)
        self.api.force_authenticate(self.manager)
        res = self.api.patch(f'{self.ZAKAZ_URL}{zakaz.pk}/',
                             {'prepaid_percent': '15'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Decimal(res.data['prepaid_percent']), Decimal('15'))

    def test_order_default_prepaid_percent(self):
        order = Order.objects.create(contract_number='PP-001')
        self.assertEqual(order.prepaid_percent, Decimal('30'))

    def test_order_prepaid_percent_editable(self):
        self.api.force_authenticate(self.manager)
        res = self.api.post(self.ORDER_URL, {
            'contract_number': 'PP-002',
            'items': [{'product': self.product.pk, 'quantity': 2,
                       'unit_price': '700000'}],
            'prepaid_percent': '10',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        order_id = res.data['id']
        patch = self.api.patch(f'{self.ORDER_URL}{order_id}/', {
            'asos': 'Oldindan to\'lov foizi o\'zgardi',
            'prepaid_percent': '5',
        }, format='json')
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertEqual(Decimal(patch.data['prepaid_percent']), Decimal('5'))


class ZakazFullEditAccessTests(TestCase):
    """
    2#4: Kirim yozuvining BARCHA maydonlari avtorizatsiyalangan foydalanuvchi
    tomonidan PATCH qilinishi mumkin — status o'tishidan tashqari (u alohida
    Management-only qoida bo'lib qoladi). Backorder zakazda ilgari operator
    uchun quantity/product/unit_price bloklangan edi — endi ochiq.
    """

    ZAKAZ_URL = '/api/v1/orders/zakaz/'

    def setUp(self):
        self.api = APIClient()
        self.operator = User.objects.create_user(
            'op_fe', password='x', role=User.OPERATOR)
        self.product = Product.objects.create(
            name='Klaviatura', serial_number='KB-FE-1',
            purchase_price=Decimal('50000'))
        Stock.objects.create(product=self.product, quantity=1,
                             warehouse_location='A1')
        # 5 so'raladi, omborda 1 ta → 4 ta backorder → avtomatik zakaz
        self.order = Order.objects.create(contract_number='FE-001')
        OrderItem.objects.create(order=self.order, product=self.product,
                                 quantity=5, unit_price=Decimal('80000'))
        self.order.reserve()
        self.backorder = self.order.create_backorder_zakaz()[0]

    def test_operator_can_edit_non_status_field_without_asos(self):
        """Status o'zgarmasa — asos talab qilinmaydi (mavjud qoida saqlanadi)."""
        self.api.force_authenticate(self.operator)
        res = self.api.patch(f'{self.ZAKAZ_URL}{self.backorder.pk}/',
                             {'supplier': 'Yangi yetkazuvchi'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['supplier'], 'Yangi yetkazuvchi')

    def test_operator_can_edit_quantity_on_backorder_zakaz(self):
        """Ilgari bloklangan — endi operator ham miqdorni o'zgartira oladi."""
        self.api.force_authenticate(self.operator)
        res = self.api.patch(f'{self.ZAKAZ_URL}{self.backorder.pk}/',
                             {'quantity': 6}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['quantity'], 6)

    def test_operator_can_edit_import_type(self):
        self.api.force_authenticate(self.operator)
        res = self.api.patch(f'{self.ZAKAZ_URL}{self.backorder.pk}/',
                             {'import_type': Zakaz.CHARTER}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['import_type'], Zakaz.CHARTER)

    def test_operator_still_cannot_set_received_qty(self):
        """Ombor hisobiga bevosita ta'sir qiladigan received_qty — Management-only saqlanadi."""
        self.api.force_authenticate(self.operator)
        res = self.api.patch(f'{self.ZAKAZ_URL}{self.backorder.pk}/',
                             {'received_qty': 2}, format='json')
        self.assertEqual(res.status_code, 403, res.data)

    def test_status_transition_still_requires_management(self):
        """Status o'tishi hali ham FAQAT Management — bu qoida o'zgarmagan."""
        self.api.force_authenticate(self.operator)
        res = self.api.patch(f'{self.ZAKAZ_URL}{self.backorder.pk}/',
                             {'status': 'confirmed', 'contract_number': 'FE-001',
                              'asos': 'test'}, format='json')
        self.assertEqual(res.status_code, 403, res.data)


class OrderNewProductCreatesKirimTests(TestCase):
    """
    #3: Buyurtmada omborda yo'q mahsulot ko'rsatilsa — yangi Product
    (origin=import) yaratiladi va unga MUSTAQIL (manual) Zakaz ochiladi.
    """

    ORDER_URL = '/api/v1/orders/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            'mng_np', password='x', role=User.MANAGEMENT)
        self.category = Category.objects.create(name='Yangi turkum')

    def test_new_product_via_order_creates_manual_zakaz(self):
        self.api.force_authenticate(self.manager)
        res = self.api.post(self.ORDER_URL, {
            'contract_number': 'NP-001',
            'items': [{
                'new_product': {'name': 'Omborda yo\'q noutbuk',
                                'category': self.category.pk},
                'quantity': 7,
                'unit_price': '9000000',
            }],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)

        product = Product.objects.get(name='Omborda yo\'q noutbuk')
        self.assertEqual(product.origin, ProductOrigin.IMPORT)

        zakazlar = Zakaz.objects.filter(product=product)
        self.assertEqual(zakazlar.count(), 1)
        zakaz = zakazlar.first()
        self.assertEqual(zakaz.zakaz_type, Zakaz.MANUAL)
        self.assertEqual(zakaz.quantity, 7)
        self.assertEqual(zakaz.status, Zakaz.NEW)
        self.assertEqual(zakaz.order_id, res.data['id'])

    def test_new_product_via_order_does_not_duplicate_as_backorder(self):
        """Yangi mahsulot uchun MANUAL zakaz ochilgach, create_backorder_zakaz
        takror (backorder) zakaz OCHMASLIGI kerak — bitta zakaz bo'lishi shart."""
        self.api.force_authenticate(self.manager)
        res = self.api.post(self.ORDER_URL, {
            'contract_number': 'NP-002',
            'items': [{
                'new_product': {'name': 'Yana bir yangi mahsulot',
                                'category': self.category.pk},
                'quantity': 3,
                'unit_price': '1000000',
            }],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        product = Product.objects.get(name='Yana bir yangi mahsulot')
        self.assertEqual(Zakaz.objects.filter(product=product).count(), 1)


class BackorderShortfallRegressionTests(TestCase):
    """
    #3 (ikkinchi punkt) regressiyasi: mavjud mahsulotda ombor kam bo'lsa —
    avtomatik BACKORDER zakaz miqdori aynan YETISHMAGAN miqdorga teng
    bo'lishi kerak (butun so'ralgan miqdorga emas).
    """

    def test_shortfall_zakaz_quantity_matches_gap_exactly(self):
        product = Product.objects.create(
            name='Yetishmovchi mahsulot', serial_number='SHORT-1',
            purchase_price=Decimal('100'))
        Stock.objects.create(product=product, quantity=4,
                             warehouse_location='A1')
        order = Order.objects.create(contract_number='SHORT-001')
        OrderItem.objects.create(order=order, product=product,
                                 quantity=15, unit_price=Decimal('200'))
        order.reserve()
        zakazlar = order.create_backorder_zakaz()
        self.assertEqual(len(zakazlar), 1)
        zakaz = zakazlar[0]
        self.assertEqual(zakaz.zakaz_type, Zakaz.BACKORDER)
        # 15 so'raldi, omborda 4 ta bor → 11 ta yetishmagan
        self.assertEqual(zakaz.quantity, 11)
        self.assertNotEqual(zakaz.quantity, 15)
