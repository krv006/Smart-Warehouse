"""Shartnoma raqami ketma-ketligi, import narxlari va mahsulot holati testlari."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.common.contracts import allocate_contract_number, peek_contract_number
from apps.clients.models import Client
from apps.invoices.models import InvoiceLineItem
from apps.orders.models import Zakaz
from apps.users.models import User
from apps.warehouse.models import Category, Product, ProductOrigin


class ContractSequenceTests(TestCase):
    """Har kun uchun alohida o'suvchi tartib raqam: 1/1308, 2/1308, ..."""

    def test_allocation_increments_per_day(self):
        day = date(2026, 8, 13)
        self.assertEqual(allocate_contract_number(day), '1/1308')
        self.assertEqual(allocate_contract_number(day), '2/1308')
        self.assertEqual(allocate_contract_number(day), '3/1308')

    def test_new_day_restarts_from_one(self):
        self.assertEqual(allocate_contract_number(date(2026, 8, 13)), '1/1308')
        self.assertEqual(allocate_contract_number(date(2026, 8, 14)), '1/1408')

    def test_peek_does_not_consume(self):
        day = date(2026, 8, 13)
        self.assertEqual(peek_contract_number(day), '1/1308')
        self.assertEqual(peek_contract_number(day), '1/1308')
        self.assertEqual(allocate_contract_number(day), '1/1308')

    def test_manual_number_is_taken_into_account(self):
        day = date(2026, 8, 13)
        Zakaz.objects.create(
            product=Product.objects.create(name='Kabel'),
            quantity=1, contract_number='7/1308', contract_date=day,
        )
        self.assertEqual(allocate_contract_number(day), '8/1308')


class ImportContractNumberAPITests(TestCase):
    BULK_URL = '/api/v1/orders/zakaz/bulk/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_seq', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.category = Category.objects.create(name='Kategoriya')

    def _bulk(self):
        return self.api.post(self.BULK_URL, {
            'contract_date': '2026-08-13',
            'items': [{'new_product': {'name': 'Tovar', 'unit': 'piece',
                                       'category': self.category.pk},
                       'quantity': 2, 'unit_price': '1000.00',
                       'selling_price': '1500.00'}],
        }, format='json')

    def test_each_import_gets_next_number(self):
        first = self._bulk()
        second = self._bulk()
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(first.data['zakazlar'][0]['contract_number'], '1/1308')
        self.assertEqual(second.data['zakazlar'][0]['contract_number'], '2/1308')

    def test_next_contract_number_endpoint_peeks(self):
        res = self.api.get('/api/v1/orders/next-contract-number/',
                           {'contract_date': '2026-08-13'})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['contract_number'], '1/1308')
        self.assertEqual(
            self.api.get('/api/v1/orders/next-contract-number/',
                         {'contract_date': '2026-08-13'}).data['contract_number'],
            '1/1308')


class ImportPriceTests(TestCase):
    BULK_URL = '/api/v1/orders/zakaz/bulk/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_price', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.category = Category.objects.create(name='Kategoriya')

    def test_prices_and_vat_are_stored(self):
        res = self.api.post(self.BULK_URL, {
            'items': [{'new_product': {'name': 'Monitor', 'unit': 'piece',
                                       'category': self.category.pk},
                       'quantity': 3, 'unit_price': '100000.00',
                       'selling_price': '150000.00', 'vat_percent': '12'}],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        zakaz = Zakaz.objects.get(pk=res.data['zakazlar'][0]['id'])
        self.assertEqual(zakaz.unit_price, Decimal('100000.00'))
        self.assertEqual(zakaz.selling_price, Decimal('150000.00'))
        # QQS KELISH narxi asosida: 3 × 100000 × 12%
        self.assertEqual(zakaz.vat_amount, Decimal('36000.00'))
        self.assertEqual(zakaz.product.purchase_price, Decimal('100000.00'))
        self.assertEqual(zakaz.product.selling_price, Decimal('150000.00'))

    def test_selling_price_is_required(self):
        res = self.api.post(self.BULK_URL, {
            'items': [{'new_product': {'name': 'Klaviatura',
                                       'category': self.category.pk},
                       'quantity': 1, 'unit_price': '1000.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)

    def test_serial_number_is_not_generated(self):
        res = self.api.post(self.BULK_URL, {
            'items': [{'new_product': {'name': 'Sichqoncha',
                                       'category': self.category.pk},
                       'quantity': 1, 'unit_price': '1000.00',
                       'selling_price': '2000.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        product = Zakaz.objects.get(pk=res.data['zakazlar'][0]['id']).product
        self.assertIsNone(product.serial_number)
        self.assertEqual(str(product), 'Sichqoncha')


class PartialPaymentLimitTests(TestCase):
    """Qisman to'langan summa jami import summasidan oshmasligi kerak."""

    BULK_URL = '/api/v1/orders/zakaz/bulk/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_pay', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.product = Product.objects.create(name='Tovar 200k')

    def test_bulk_rejects_paid_above_total(self):
        res = self.api.post(self.BULK_URL, {
            'payment_status': 'partial', 'paid_amount': '500000.00',
            'items': [{'product': self.product.pk, 'quantity': 1,
                       'unit_price': '200000.00', 'selling_price': '250000.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('paid_amount', res.data)

    def test_patch_rejects_paid_above_total(self):
        zakaz = Zakaz.objects.create(product=self.product, quantity=1,
                                     zakaz_type=Zakaz.MANUAL,
                                     unit_price=Decimal('200000'))
        res = self.api.patch(f'/api/v1/orders/zakaz/{zakaz.pk}/',
                             {'payment_status': 'partial',
                              'paid_amount': '500000.00'}, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        zakaz.refresh_from_db()
        self.assertEqual(zakaz.paid_amount, Decimal('0'))

    def test_patch_rejects_partial_without_price(self):
        """Narx yo'q importda qisman to'lov — summani tekshirib bo'lmaydi."""
        zakaz = Zakaz.objects.create(product=self.product, quantity=1,
                                     zakaz_type=Zakaz.MANUAL)
        res = self.api.patch(f'/api/v1/orders/zakaz/{zakaz.pk}/',
                             {'payment_status': 'partial',
                              'paid_amount': '500000.00'}, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        zakaz.refresh_from_db()
        self.assertEqual(zakaz.payment_status, Zakaz.UNPAID)

    def test_patch_accepts_paid_below_total(self):
        zakaz = Zakaz.objects.create(product=self.product, quantity=2,
                                     zakaz_type=Zakaz.MANUAL,
                                     unit_price=Decimal('200000'))
        res = self.api.patch(f'/api/v1/orders/zakaz/{zakaz.pk}/',
                             {'payment_status': 'partial',
                              'paid_amount': '150000.00'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        zakaz.refresh_from_db()
        self.assertEqual(zakaz.paid_amount, Decimal('150000.00'))


class ProductOriginTests(TestCase):
    """Import mahsuloti qabul qilingach oddiy ombor mahsulotiga aylanadi."""

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_org', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)

    def test_receive_switches_origin_to_warehouse(self):
        from apps.warehouse.models import Category

        product = Product.objects.create(name='Import tovar',
                                         origin=ProductOrigin.IMPORT)
        zakaz = Zakaz.objects.create(product=product, quantity=3,
                                     zakaz_type=Zakaz.MANUAL,
                                     unit_price=Decimal('1000'),
                                     status=Zakaz.ORDERED,
                                     contract_number='1/1308',
                                     faktura='F-1')
        zakaz.received_qty = 3
        zakaz.save(update_fields=['received_qty'])
        zakaz.receive(user=self.manager)
        product.refresh_from_db()
        self.assertEqual(product.origin, ProductOrigin.WAREHOUSE)
        self.assertEqual(product.quantity_in_stock, 3)
        # kategoriya majburiyligi faqat API darajasida — ORM ga ta'sir qilmaydi
        self.assertIsNone(product.category)
        self.assertFalse(Category.objects.exists())

    def test_import_bulk_requires_category_for_new_product(self):
        res = self.api.post('/api/v1/orders/zakaz/bulk/', {
            'items': [{'new_product': {'name': 'Kategoriyasiz import'},
                       'quantity': 1, 'unit_price': '1000.00',
                       'selling_price': '2000.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)

    def test_product_create_requires_category(self):
        res = self.api.post('/api/v1/warehouse/products/',
                            {'name': 'Kategoriyasiz', 'unit': 'piece'},
                            format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('category', res.data)


class InvoiceLineVatTests(TestCase):
    """QQS har doim qatordagi narxdan hisoblanadi — teskari hisobda ham."""

    def test_forward_calculation(self):
        delivery, vat, total = InvoiceLineItem.compute_line(
            1, Decimal('150000'), '15')
        self.assertEqual(delivery, Decimal('150000.00'))
        self.assertEqual(vat, Decimal('22500.00'))
        self.assertEqual(total, Decimal('172500.00'))

    def test_reverse_uses_price_when_present(self):
        # Eski qiymatlar (narx 1 bo'lgan paytdan) qolib ketgan bo'lsa ham
        # yangi narx bo'yicha qayta hisoblanadi
        delivery, vat, total = InvoiceLineItem.compute_line(
            1, Decimal('150000'), '15',
            delivery_amount=Decimal('1'), vat_amount=Decimal('0.15'),
            total_amount=Decimal('1.15'), reverse=True)
        self.assertEqual(delivery, Decimal('150000.00'))
        self.assertEqual(vat, Decimal('22500.00'))
        self.assertEqual(total, Decimal('172500.00'))

    def test_reverse_from_total_when_price_missing(self):
        delivery, vat, total = InvoiceLineItem.compute_line(
            1, None, '15', total_amount=Decimal('115'), reverse=True)
        self.assertEqual(delivery, Decimal('100.00'))
        self.assertEqual(vat, Decimal('15.00'))
        self.assertEqual(total, Decimal('115.00'))


class InvoiceAutoProductTests(TestCase):
    """Buyurtmada bazada yo'q mahsulot — darhol ombor ro'yxatiga `import` holatida."""

    URL = '/api/v1/invoices/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_inv', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.client_obj = Client.objects.create(company_name='Mijoz OOO')
        self.category = Category.objects.create(name='Kategoriya')

    def _payload(self, name):
        return {
            'document_type': 'contract_sk',
            'contract_date': '2026-08-13',
            'client': str(self.client_obj.pk),
            'lines': [{
                'product_name': name,
                'category': self.category.pk,
                'unit': 'piece',
                'quantity': 2,
                'unit_price': '5000.00',
                'selling_price': '9000.00',
                'vat_percent': '12',
            }],
        }

    def test_line_prices_land_on_product_and_import(self):
        """«Narxi» — kelish narxi, «Sotuv narxi» — ketish narxi."""
        res = self.api.post(self.URL, self._payload('Narxli tovar'), format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(res.data['lines'][0]['selling_price']),
                         Decimal('9000.00'))
        product = Product.objects.get(name='Narxli tovar')
        self.assertEqual(product.purchase_price, Decimal('5000.00'))
        self.assertEqual(product.selling_price, Decimal('9000.00'))
        zakaz = Zakaz.objects.get(product=product)
        self.assertEqual(zakaz.unit_price, Decimal('5000.00'))
        self.assertEqual(zakaz.selling_price, Decimal('9000.00'))

    def test_unknown_product_is_created_with_import_origin(self):
        res = self.api.post(self.URL, self._payload('Yangi tovar'), format='json')
        self.assertEqual(res.status_code, 201, res.data)
        product = Product.objects.get(name='Yangi tovar')
        self.assertEqual(product.origin, ProductOrigin.IMPORT)
        self.assertEqual(res.data['lines'][0]['product'], product.pk)

    def test_unknown_product_also_lands_in_import_section(self):
        res = self.api.post(self.URL, self._payload('Import tovar'), format='json')
        self.assertEqual(res.status_code, 201, res.data)
        zakaz = Zakaz.objects.get(product__name='Import tovar')
        self.assertEqual(zakaz.zakaz_type, Zakaz.MANUAL)
        self.assertEqual(zakaz.status, Zakaz.NEW)
        self.assertEqual(zakaz.payment_status, Zakaz.UNPAID)
        self.assertEqual(zakaz.quantity, 2)
        self.assertEqual(zakaz.unit_price, Decimal('5000.00'))     # kelish
        self.assertEqual(zakaz.selling_price, Decimal('9000.00'))  # sotuv
        self.assertEqual(zakaz.contract_number,
                         res.data['contract_number'])

    def test_invoice_requires_category_for_unknown_product(self):
        payload = self._payload('Kategoriyasiz tovar')
        payload['lines'][0].pop('category')
        res = self.api.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 400, res.data)

    def test_created_product_gets_category(self):
        res = self.api.post(self.URL, self._payload('Kategoriyali tovar'),
                            format='json')
        self.assertEqual(res.status_code, 201, res.data)
        product = Product.objects.get(name='Kategoriyali tovar')
        self.assertEqual(product.category_id, self.category.pk)

    def test_known_product_creates_no_import_row(self):
        Product.objects.create(name='Ombordagi tovar')
        res = self.api.post(self.URL, self._payload('Ombordagi tovar'),
                            format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertFalse(Zakaz.objects.filter(product__name='Ombordagi tovar').exists())

    def test_pending_import_quantity_is_reported(self):
        """Qoldiq 0 bo'lsa ham nechta dona yo'lda ekani ko'rinadi."""
        res = self.api.post(self.URL, self._payload('Yo‘ldagi tovar'), format='json')
        self.assertEqual(res.status_code, 201, res.data)
        product = Product.objects.get(name='Yo‘ldagi tovar')
        self.assertEqual(product.available_quantity, 0)
        self.assertEqual(product.pending_import_quantity, 2)
        listing = self.api.get(f'/api/v1/warehouse/products/{product.pk}/')
        self.assertEqual(listing.data['pending_import_quantity'], 2)

    def test_import_list_shows_product_name_without_serial(self):
        Product.objects.create(name='rv', serial_number='rv')
        res = self.api.post('/api/v1/orders/zakaz/bulk/', {
            'items': [{'product': Product.objects.get(name='rv').pk,
                       'quantity': 1, 'unit_price': '1000.00',
                       'selling_price': '2000.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['zakazlar'][0]['product_name'], 'rv')

    def test_known_product_is_linked_not_duplicated(self):
        existing = Product.objects.create(name='Mavjud tovar',
                                          origin=ProductOrigin.WAREHOUSE)
        res = self.api.post(self.URL, self._payload('Mavjud tovar'), format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Product.objects.filter(name='Mavjud tovar').count(), 1)
        self.assertEqual(res.data['lines'][0]['product'], existing.pk)

    def test_vat_follows_line_price_in_reverse_mode(self):
        payload = self._payload('QQS tovar')
        payload['reverse_calculation'] = True
        payload['lines'][0].update({
            'quantity': 1,
            'unit_price': '150000.00',
            'vat_percent': '15',
            # eski (narx 1 bo'lgan paytdagi) qiymatlar
            'delivery_amount': '1.00',
            'vat_amount': '0.15',
            'total_amount': '1.15',
        })
        res = self.api.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        line = res.data['lines'][0]
        self.assertEqual(Decimal(line['delivery_amount']), Decimal('150000.00'))
        self.assertEqual(Decimal(line['vat_amount']), Decimal('22500.00'))
        self.assertEqual(Decimal(line['total_amount']), Decimal('172500.00'))

    def test_contract_number_is_allocated_per_day(self):
        first = self.api.post(self.URL, self._payload('A tovar'), format='json')
        second = self.api.post(self.URL, self._payload('B tovar'), format='json')
        self.assertEqual(first.data['contract_number'], '1/1308')
        self.assertEqual(second.data['contract_number'], '2/1308')


class ProductCategoryFilterTests(TestCase):
    """`?category=` — tanlangan kategoriya va uning ost-kategoriyalari."""

    URL = '/api/v1/warehouse/products/'

    def setUp(self):
        from apps.warehouse.models import Category

        self.api = APIClient()
        self.manager = User.objects.create_user('mng_cat', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.parent = Category.objects.create(name='Texnika')
        self.child = Category.objects.create(name='Monitorlar', parent=self.parent)
        self.other = Category.objects.create(name='Mebel')
        Product.objects.create(name='Monitor', category=self.child)
        Product.objects.create(name='Noutbuk', category=self.parent)
        Product.objects.create(name='Stol', category=self.other)

    def _names(self, category_id):
        res = self.api.get(self.URL, {'category': category_id, 'page_size': 50})
        self.assertEqual(res.status_code, 200, res.data)
        rows = res.data.get('results', res.data)
        return sorted(row['name'] for row in rows)

    def test_parent_category_includes_children(self):
        self.assertEqual(self._names(self.parent.pk), ['Monitor', 'Noutbuk'])

    def test_child_category_only(self):
        self.assertEqual(self._names(self.child.pk), ['Monitor'])

    def test_other_category(self):
        self.assertEqual(self._names(self.other.pk), ['Stol'])


class DuplicateSerialTests(TestCase):
    """Band seriya raqami — 500 (IntegrityError) emas, tushunarli 400."""

    BULK_URL = '/api/v1/orders/zakaz/bulk/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_dup', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.category = Category.objects.create(name='Kategoriya')
        Product.objects.create(name='Mavjud tovar', serial_number='SN-BAND',
                               category=self.category)

    def test_bulk_rejects_taken_serial(self):
        res = self.api.post(self.BULK_URL, {
            'items': [{'new_product': {'name': 'Yangi tovar', 'serial_number': 'SN-BAND',
                                       'category': self.category.pk},
                       'quantity': 1, 'unit_price': '1000.00',
                       'selling_price': '2000.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)

    def test_product_endpoint_rejects_taken_serial(self):
        res = self.api.post('/api/v1/warehouse/products/', {
            'name': 'Boshqa tovar', 'serial_number': 'SN-BAND',
            'category': self.category.pk, 'unit': 'piece',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('serial_number', res.data)

    def test_empty_serial_is_always_allowed(self):
        res = self.api.post(self.BULK_URL, {
            'items': [
                {'new_product': {'name': 'Seriyasiz 1', 'category': self.category.pk},
                 'quantity': 1, 'unit_price': '1000.00', 'selling_price': '2000.00'},
                {'new_product': {'name': 'Seriyasiz 2', 'category': self.category.pk},
                 'quantity': 1, 'unit_price': '1000.00', 'selling_price': '2000.00'},
            ],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)

    def test_new_product_does_not_require_product_id(self):
        """`product` MAJBURIY emas — `new_product` bilan import yaratiladi."""
        res = self.api.post(self.BULK_URL, {
            'supplier': 'uzb',
            'items': [{'new_product': {'name': 'Faqat yangi tovar',
                                       'serial_number': 'SN-YANGI',
                                       'category': self.category.pk,
                                       'unit': 'piece', 'vat_percent': '12'},
                       'quantity': 10, 'unit_price': '10000.00',
                       'selling_price': '15000.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['zakazlar'][0]['product_name'], 'Faqat yangi tovar')
