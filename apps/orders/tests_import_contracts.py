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
from apps.warehouse.models import Category, Product, ProductOrigin, Stock


class ContractSequenceTests(TestCase):
    """Har bir SANA uchun alohida o'suvchi tartib raqam: `{n}/{DDMM}`,
    har kuni 1 dan qayta boshlanadi."""

    def test_allocation_increments_within_a_day(self):
        today = date(2026, 8, 19)
        self.assertEqual(allocate_contract_number(today), f'1/{today.strftime("%d%m")}')
        self.assertEqual(allocate_contract_number(today), f'2/{today.strftime("%d%m")}')
        self.assertEqual(allocate_contract_number(today), f'3/{today.strftime("%d%m")}')

    def test_restarts_on_different_date(self):
        self.assertEqual(allocate_contract_number(date(2026, 8, 13)), '1/1308')
        # boshqa sana — mustaqil hisoblagich, 1 dan boshlanadi
        self.assertEqual(allocate_contract_number(date(2026, 8, 14)), '1/1408')
        self.assertEqual(allocate_contract_number(date(2026, 8, 13)), '2/1308')

    def test_peek_does_not_consume(self):
        d = date(2026, 8, 19)
        self.assertEqual(peek_contract_number(d), f'1/{d.strftime("%d%m")}')
        self.assertEqual(peek_contract_number(d), f'1/{d.strftime("%d%m")}')
        self.assertEqual(allocate_contract_number(d), f'1/{d.strftime("%d%m")}')

    def test_leftover_document_continues_previous_day_count(self):
        """Kecha 3 ta zakaz bo'lgan sanaga bugun kirim qo'shilsa — hisoblagich
        o'sha kunning mavjud hujjatlar sonidan davom etadi (4/1808)."""
        yesterday = date(2026, 8, 18)
        for _ in range(3):
            Zakaz.objects.create(
                product=Product.objects.create(name='Kabel'),
                quantity=1, contract_date=yesterday,
                contract_number=allocate_contract_number(yesterday),
            )
        self.assertEqual(allocate_contract_number(yesterday), '4/1808')

    def test_manual_number_is_taken_into_account_on_first_use(self):
        """Hisoblagich shu sana uchun birinchi marta ishga tushganda,
        bazadagi qo'lda kiritilgan raqamlarni ham hisobga oladi — orqaga
        qaytib takrorlamaydi."""
        Zakaz.objects.create(
            product=Product.objects.create(name='Kabel'),
            quantity=1, contract_number='7', contract_date=date(2026, 8, 13),
        )
        self.assertEqual(allocate_contract_number(date(2026, 8, 13)), '2/1308')

    def test_free_form_contract_number_is_accepted(self):
        """Xodim istagan ko'rinishda (masalan '412412412') qo'lda
        kiritishi mumkin — format tekshirilmaydi."""
        zakaz = Zakaz.objects.create(
            product=Product.objects.create(name='Stol'),
            quantity=1, contract_number='412412412',
        )
        self.assertEqual(zakaz.contract_number, '412412412')


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
        first_n, first_date = first.data['zakazlar'][0]['contract_number'].split('/')
        second_n, second_date = second.data['zakazlar'][0]['contract_number'].split('/')
        self.assertEqual(first_date, second_date)
        self.assertEqual(int(second_n), int(first_n) + 1)

    def test_next_contract_number_endpoint_peeks(self):
        res = self.api.get('/api/v1/orders/next-contract-number/',
                           {'contract_date': '2026-08-13'})
        self.assertEqual(res.status_code, 200, res.data)
        first_peek = res.data['contract_number']
        second_peek = self.api.get(
            '/api/v1/orders/next-contract-number/',
            {'contract_date': '2026-08-13'}).data['contract_number']
        # Peek band qilmaydi — ikkalasi ham bir xil bo'lishi kerak
        self.assertEqual(first_peek, second_peek)

    def test_custom_free_form_contract_number_is_accepted(self):
        """Xodim /orders/zakaz/ orqali ham istagan ko'rinishda raqam
        kiritishi mumkin — format tekshirilmaydi."""
        res = self.api.post('/api/v1/orders/zakaz/', {
            'new_product': {'name': 'Erkin raqamli tovar', 'unit': 'piece',
                            'category': self.category.pk},
            'quantity': 1, 'unit_price': '1000.00', 'selling_price': '1500.00',
            'contract_number': '124151245124',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['contract_number'], '124151245124')


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

    def test_reducing_quantity_below_paid_amount_is_rejected(self):
        """Miqdorni kamaytirish jami summani paid_amount dan pastga tushirsa — 400.

        Aks holda paid_amount > total holati tekshirilmasdan saqlanib qolardi.
        """
        zakaz = Zakaz.objects.create(product=self.product, quantity=2,
                                     zakaz_type=Zakaz.MANUAL,
                                     unit_price=Decimal('100000'),
                                     payment_status=Zakaz.PARTIAL,
                                     paid_amount=Decimal('180000'))  # 200000 dan kam
        res = self.api.patch(f'/api/v1/orders/zakaz/{zakaz.pk}/',
                             {'quantity': 1}, format='json')  # jami endi 100000
        self.assertEqual(res.status_code, 400, res.data)
        zakaz.refresh_from_db()
        self.assertEqual(zakaz.quantity, 2)
        self.assertEqual(zakaz.paid_amount, Decimal('180000'))

    def test_comment_only_edit_is_not_blocked_by_payment_check(self):
        """To'lov/miqdor/narxga tegilmagan tahrir bloklanmasligi kerak."""
        zakaz = Zakaz.objects.create(product=self.product, quantity=2,
                                     zakaz_type=Zakaz.MANUAL,
                                     unit_price=Decimal('100000'),
                                     payment_status=Zakaz.PARTIAL,
                                     paid_amount=Decimal('180000'))
        res = self.api.patch(f'/api/v1/orders/zakaz/{zakaz.pk}/',
                             {'comment': 'izoh'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)


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

    def test_import_bulk_creates_new_product_without_category(self):
        """Kategoriya funksiyasi o'chirilgan — yangi import mahsuloti
        kategoriyasiz ham muammosiz yaratiladi."""
        res = self.api.post('/api/v1/orders/zakaz/bulk/', {
            'items': [{'new_product': {'name': 'Kategoriyasiz import'},
                       'quantity': 1, 'unit_price': '1000.00',
                       'selling_price': '2000.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)

    def test_product_create_does_not_require_category(self):
        res = self.api.post('/api/v1/warehouse/products/',
                            {'name': 'Kategoriyasiz', 'unit': 'piece'},
                            format='json')
        self.assertEqual(res.status_code, 201, res.data)


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

    def test_duplicate_serial_across_lines_with_different_names_is_rejected(self):
        """Ikki qator bir xil (yangi) seriyani boshqa nom bilan ishlatsa — 400.

        Aks holda ikkinchi qator birinchi qator yaratgan mahsulotga jimgina
        bog'lanib, o'z nomi va mahsuloti butunlay yo'qolib qolardi.
        """
        payload = {
            'document_type': 'contract_sk',
            'contract_date': '2026-08-13',
            'client': str(self.client_obj.pk),
            'lines': [
                {'product_name': 'Mahsulot A', 'category': self.category.pk,
                 'identification_code': 'DUP-1', 'quantity': 2,
                 'unit_price': '5000.00', 'selling_price': '9000.00'},
                {'product_name': 'Mahsulot B', 'category': self.category.pk,
                 'identification_code': 'DUP-1', 'quantity': 3,
                 'unit_price': '6000.00', 'selling_price': '10000.00'},
            ],
        }
        res = self.api.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertFalse(Product.objects.filter(name='Mahsulot A').exists())
        self.assertFalse(Product.objects.filter(name='Mahsulot B').exists())

    def test_same_serial_same_name_two_lines_is_allowed(self):
        """Bitta yangi mahsulot ikki qatorga bo'linsa (bir xil nom) — ruxsat."""
        payload = {
            'document_type': 'contract_sk',
            'contract_date': '2026-08-13',
            'client': str(self.client_obj.pk),
            'lines': [
                {'product_name': 'Bo\'lingan tovar', 'category': self.category.pk,
                 'identification_code': 'SPLIT-1', 'quantity': 2,
                 'unit_price': '5000.00', 'selling_price': '9000.00'},
                {'product_name': 'Bo\'lingan tovar', 'category': self.category.pk,
                 'identification_code': 'SPLIT-1', 'quantity': 3,
                 'unit_price': '5000.00', 'selling_price': '9000.00'},
            ],
        }
        res = self.api.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Product.objects.filter(name='Bo\'lingan tovar').count(), 1)
        product = Product.objects.get(name='Bo\'lingan tovar')
        self.assertEqual(set(res.data['lines'][i]['product'] for i in (0, 1)), {product.pk})

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

    def test_unknown_product_is_created_without_category(self):
        """Kategoriya funksiyasi o'chirilgan — yangi mahsulot kategoriyasiz
        ham muammosiz yaratiladi."""
        payload = self._payload('Kategoriyasiz tovar')
        payload['lines'][0].pop('category', None)
        res = self.api.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        product = Product.objects.get(name='Kategoriyasiz tovar')
        self.assertIsNone(product.category_id)

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

    def test_contract_number_increments_within_the_day(self):
        first = self.api.post(self.URL, self._payload('A tovar'), format='json')
        second = self.api.post(self.URL, self._payload('B tovar'), format='json')
        first_n, first_date = first.data['contract_number'].split('/')
        second_n, second_date = second.data['contract_number'].split('/')
        self.assertEqual(first_date, second_date)
        self.assertEqual(int(second_n), int(first_n) + 1)


class InvoiceKassaSyncTests(TestCase):
    """
    Regressiya: shartnoma (SK) fakturasi kassaga (Expense — chiqim)
    umuman ulanmagan edi. Ombordagi (import bo'lmagan) mahsulot bo'yicha
    qator kassadan chiqim yozishi, yangi (import) mahsulot esa o'z Zakaz
    oqimi orqali hisoblanib, shu yerda ikki marta hisoblanmasligi kerak.
    """

    URL = '/api/v1/invoices/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_inv_kassa', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.client_obj = Client.objects.create(company_name='Mijoz OOO')
        self.category = Category.objects.create(name='Kategoriya')
        self.product = Product.objects.create(name='Ombordagi divan')

    def _import_payload(self, name):
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

    def test_existing_product_line_records_kassa_expense(self):
        from apps.expenses.models import Expense

        payload = {
            'document_type': 'contract_sk',
            'contract_number': 'SH-2026/777',
            'contract_date': '2026-08-13',
            'client': str(self.client_obj.pk),
            'lines': [{
                'product': self.product.pk,
                'quantity': 5,
                'unit_price': '100000.00',
                'vat_percent': '12',
            }],
        }
        res = self.api.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        expense = Expense.objects.get(invoice_id=res.data['id'])
        # delivery = 5*100000 = 500000; QQS 12% = 60000; jami = 560000
        self.assertEqual(expense.amount, Decimal('560000.00'))
        self.assertIn('SH-2026/777', expense.comment)

    def test_new_import_product_line_is_not_double_counted(self):
        """Yangi mahsulot — o'z Zakazi orqali hisoblanadi, faktura darajasida emas."""
        from apps.expenses.models import Expense

        res = self.api.post(self.URL, self._import_payload('Import qator'), format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertFalse(Expense.objects.filter(invoice_id=res.data['id']).exists())

    def test_non_contract_document_does_not_touch_kassa(self):
        from apps.expenses.models import Expense

        payload = {
            'document_type': 'invoice',
            'client': str(self.client_obj.pk),
            'lines': [{
                'product': self.product.pk,
                'quantity': 3,
                'unit_price': '50000.00',
            }],
        }
        res = self.api.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertFalse(Expense.objects.filter(invoice_id=res.data['id']).exists())

    def test_editing_quantity_resyncs_expense_amount(self):
        from apps.expenses.models import Expense

        payload = {
            'document_type': 'contract_sk',
            'contract_number': 'SH-2026/778',
            'client': str(self.client_obj.pk),
            'lines': [{
                'product': self.product.pk,
                'quantity': 2,
                'unit_price': '100000.00',
            }],
        }
        res = self.api.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        invoice_id = res.data['id']
        line_id = res.data['lines'][0]['id']
        expense = Expense.objects.get(invoice_id=invoice_id)
        self.assertEqual(expense.amount, Decimal('200000.00'))

        res2 = self.api.patch(f'{self.URL}{invoice_id}/', {
            'lines': [{'id': line_id, 'product': self.product.pk,
                      'quantity': 4, 'unit_price': '100000.00'}],
        }, format='json')
        self.assertEqual(res2.status_code, 200, res2.data)
        expense.refresh_from_db()
        self.assertEqual(expense.amount, Decimal('400000.00'))

    def test_deleting_invoice_removes_kassa_expense(self):
        from apps.expenses.models import Expense

        payload = {
            'document_type': 'contract_sk',
            'contract_number': 'SH-2026/779',
            'client': str(self.client_obj.pk),
            'lines': [{
                'product': self.product.pk,
                'quantity': 1,
                'unit_price': '100000.00',
            }],
        }
        res = self.api.post(self.URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        invoice_id = res.data['id']
        self.assertTrue(Expense.objects.filter(invoice_id=invoice_id).exists())

        del_res = self.api.delete(f'{self.URL}{invoice_id}/')
        self.assertEqual(del_res.status_code, 204, getattr(del_res, 'data', None))
        self.assertFalse(Expense.objects.filter(invoice_id=invoice_id).exists())


# Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
# class ProductCategoryFilterTests(TestCase):
#     """`?category=` — tanlangan kategoriya va uning ost-kategoriyalari."""
#
#     URL = '/api/v1/warehouse/products/'
#
#     def setUp(self):
#         from apps.warehouse.models import Category
#
#         self.api = APIClient()
#         self.manager = User.objects.create_user('mng_cat', password='x',
#                                                 role=User.MANAGEMENT)
#         self.api.force_authenticate(self.manager)
#         self.parent = Category.objects.create(name='Texnika')
#         self.child = Category.objects.create(name='Monitorlar', parent=self.parent)
#         self.other = Category.objects.create(name='Mebel')
#         Product.objects.create(name='Monitor', category=self.child)
#         Product.objects.create(name='Noutbuk', category=self.parent)
#         Product.objects.create(name='Stol', category=self.other)
#
#     def _names(self, category_id):
#         res = self.api.get(self.URL, {'category': category_id, 'page_size': 50})
#         self.assertEqual(res.status_code, 200, res.data)
#         rows = res.data.get('results', res.data)
#         return sorted(row['name'] for row in rows)
#
#     def test_parent_category_includes_children(self):
#         self.assertEqual(self._names(self.parent.pk), ['Monitor', 'Noutbuk'])
#
#     def test_child_category_only(self):
#         self.assertEqual(self._names(self.child.pk), ['Monitor'])
#
#     def test_other_category(self):
#         self.assertEqual(self._names(self.other.pk), ['Stol'])


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

    def test_bulk_rejects_repeated_serial_inside_one_request(self):
        """Bitta so'rovdagi ikki qatorda bir xil seriya — 400, 500 emas."""
        item = lambda name: {
            'new_product': {'name': name, 'serial_number': 'SN-TAKROR',
                            'category': self.category.pk},
            'quantity': 1, 'unit_price': '1000.00', 'selling_price': '2000.00',
        }
        res = self.api.post(self.BULK_URL,
                            {'items': [item('Birinchi'), item('Ikkinchi')]},
                            format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertFalse(Product.objects.filter(serial_number='SN-TAKROR').exists())


class RepeatZakazForActiveProductTests(TestCase):
    """Bir mahsulot uchun faol (yakunlanmagan) zakaz allaqachon mavjud
    bo'lsa ham, o'sha mahsulotga yana zakaz berish mumkin bo'lishi kerak
    — turli buyurtmalar/holatlar bir xil mahsulotni talab qilishi mumkin,
    global "faol zakaz bor" taqig'i noto'g'ri edi (endi olib tashlandi)."""

    BULK_URL = '/api/v1/orders/zakaz/bulk/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_repeat', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.category = Category.objects.create(name='Kategoriya')
        self.product = Product.objects.create(
            name='Canon Printer', serial_number='SN-REPEAT',
            category=self.category)

    def _bulk(self, qty):
        return self.api.post(self.BULK_URL, {
            'items': [{'product': self.product.pk, 'quantity': qty,
                       'unit_price': '10000.00', 'selling_price': '15000.00'}],
        }, format='json')

    def test_second_zakaz_for_same_product_is_allowed(self):
        first = self._bulk(5)
        self.assertEqual(first.status_code, 201, first.data)
        second = self._bulk(3)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(
            Zakaz.objects.filter(product=self.product, status=Zakaz.NEW).count(), 2)


class PaymentPaidCreditsStockTests(TestCase):
    """payment_status 'paid' ga o'tganda — rasmiy qabul (status=received)
    bosqichidan o'tmagan bo'lsa ham — mahsulot manbasi Import'dan Ombor'ga
    o'zgarishi va ombor qoldig'iga miqdor qo'shilishi kerak."""

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_pay_stock', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.category = Category.objects.create(name='Kategoriya')
        self.product = Product.objects.create(
            name='Canon Canon-XX651', serial_number='SN-CANON-1',
            category=self.category, origin=ProductOrigin.IMPORT)
        self.zakaz = Zakaz.objects.create(
            product=self.product, quantity=7, zakaz_type=Zakaz.MANUAL,
            unit_price=Decimal('100000'), selling_price=Decimal('150000'),
            status=Zakaz.NEW, payment_status=Zakaz.UNPAID,
        )

    def test_marking_paid_flips_origin_and_adds_stock(self):
        res = self.api.patch(f'/api/v1/orders/zakaz/{self.zakaz.pk}/',
                             {'payment_status': 'paid'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.origin, ProductOrigin.WAREHOUSE)
        stock = Stock.objects.get(product=self.product)
        self.assertEqual(stock.quantity, 7)
        self.zakaz.refresh_from_db()
        self.assertTrue(self.zakaz.stock_credited)

    def test_marking_paid_twice_does_not_double_stock(self):
        self.api.patch(f'/api/v1/orders/zakaz/{self.zakaz.pk}/',
                       {'payment_status': 'paid'}, format='json')
        res = self.api.patch(f'/api/v1/orders/zakaz/{self.zakaz.pk}/',
                             {'comment': 'yangilandi'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        stock = Stock.objects.get(product=self.product)
        self.assertEqual(stock.quantity, 7)

    def test_receive_after_paid_does_not_double_credit(self):
        self.api.patch(f'/api/v1/orders/zakaz/{self.zakaz.pk}/',
                       {'payment_status': 'paid'}, format='json')
        self.api.patch(f'/api/v1/orders/zakaz/{self.zakaz.pk}/',
                       {'status': 'confirmed', 'asos': 'Tasdiqlandi',
                        'contract_number': 'SH-1'}, format='json')
        self.api.patch(f'/api/v1/orders/zakaz/{self.zakaz.pk}/',
                       {'status': 'ordered', 'asos': 'Yuborildi'}, format='json')
        res = self.api.patch(f'/api/v1/orders/zakaz/{self.zakaz.pk}/',
                             {'status': 'received', 'asos': 'Qabul qilindi',
                              'faktura': 'F-1', 'received_qty': 7}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        stock = Stock.objects.get(product=self.product)
        self.assertEqual(stock.quantity, 7)


class BulkCreatePaidCreditsStockTests(TestCase):
    """Bulk import yaratilishida to'lov holati darhol 'paid' bo'lsa —
    mahsulot yaratilgan zahoti ombor qoldig'iga tushishi kerak."""

    BULK_URL = '/api/v1/orders/zakaz/bulk/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user('mng_bulk_paid', password='x',
                                                role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        self.category = Category.objects.create(name='Kategoriya')

    def test_paid_on_create_credits_stock_immediately(self):
        res = self.api.post(self.BULK_URL, {
            'payment_status': 'paid',
            'items': [{'new_product': {'name': 'Darhol tolangan tovar',
                                       'category': self.category.pk},
                       'quantity': 4, 'unit_price': '20000.00',
                       'selling_price': '30000.00'}],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        product = Product.objects.get(name='Darhol tolangan tovar')
        self.assertEqual(product.origin, ProductOrigin.WAREHOUSE)
        stock = Stock.objects.get(product=product)
        self.assertEqual(stock.quantity, 4)
