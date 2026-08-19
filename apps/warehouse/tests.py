from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.expenses.models import Expense
from apps.orders.models import Zakaz
from apps.users.models import User
from apps.warehouse.models import Category, Product, Stock


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


class ProductModelFieldDisabledTests(TestCase):
    """`Product.model` maydoni vaqtincha o'chirilgan — API javobida ko'rinmasin."""

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            'mng2', password='x', role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)

    def test_model_field_absent_from_product_list_and_detail(self):
        product = Product.objects.create(name='Stul', model='ABC-100')
        list_res = self.api.get('/api/v1/warehouse/products/')
        self.assertEqual(list_res.status_code, 200, list_res.data)
        self.assertNotIn('model', list_res.data['results'][0])

        detail_res = self.api.get(f'/api/v1/warehouse/products/{product.id}/')
        self.assertEqual(detail_res.status_code, 200, detail_res.data)
        self.assertNotIn('model', detail_res.data)

    def test_model_field_ignored_on_create_but_column_still_writable(self):
        """DB ustuni saqlanib qolgan — faqat API orqali kiritib bo'lmaydi."""
        res = self.api.post('/api/v1/warehouse/products/', {
            'name': 'Kreslo',
            'model': 'XYZ-1',
        })
        self.assertEqual(res.status_code, 201, res.data)
        self.assertNotIn('model', res.data)
        product = Product.objects.get(name='Kreslo')
        self.assertIsNone(product.model)


class StockListingTests(TestCase):
    """
    Ombor qoldiqlari ro'yxati (`/warehouse/stocks/`):
    - standart ko'rinishda butunlay bo'sh va yo'lda hech narsasi yo'q
      mahsulotlar yashiriladi;
    - qoldig'i 0 bo'lsa-da faol Zakaz/Kirim'i bor mahsulot "on_the_way"
      (Yo'lda) sifatida ko'rinadi — hatto birorta ham Stock qatori yo'q
      bo'lsa ham (sintetik qator);
    - oddiy (musbat) qoldiqli mahsulot avvalgidek ko'rinadi.
    """
    URL = '/api/v1/warehouse/stocks/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            'mng3', password='x', role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)

    def _product_names(self, res):
        return {row['product_name'] for row in res.data['results']}

    def test_zero_stock_zero_pending_excluded_by_default(self):
        empty_product = Product.objects.create(name='Butunlay bo‘sh tovar')
        Stock.objects.create(product=empty_product, quantity=0,
                             warehouse_location='A-1')
        res = self.api.get(self.URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertNotIn('Butunlay bo‘sh tovar', self._product_names(res))

    def test_never_stocked_product_without_pending_is_absent(self):
        """Birorta ham Stock qatori yo'q va yo'lda ham hech narsa yo'q —
        ro'yxatda umuman ko'rinmaydi."""
        Product.objects.create(name='Hech qachon kirim bo‘lmagan tovar')
        res = self.api.get(self.URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertNotIn('Hech qachon kirim bo‘lmagan tovar', self._product_names(res))

    def test_zero_stock_with_pending_import_shows_as_on_the_way(self):
        """Birorta ham Stock qatori yo'q, lekin faol Zakaz bor — sintetik
        "Yo'lda" qator sifatida standart ro'yxatda ko'rinadi."""
        product = Product.objects.create(name='Yo‘ldagi tovar')
        Zakaz.objects.create(product=product, quantity=7, zakaz_type=Zakaz.MANUAL)

        res = self.api.get(self.URL)
        self.assertEqual(res.status_code, 200, res.data)
        row = next(r for r in res.data['results'] if r['product_name'] == 'Yo‘ldagi tovar')
        self.assertEqual(row['stock_status'], 'on_the_way')
        self.assertEqual(row['quantity'], 0)
        self.assertEqual(row['pending_import_quantity'], 7)
        self.assertIsNone(row['id'])

    def test_real_zero_row_with_pending_import_also_shows_as_on_the_way(self):
        """Real (0 miqdorli) Stock qatori bo'lsa ham, yo'lda importi bor
        mahsulot standart ro'yxatda "Yo'lda" sifatida qoladi."""
        product = Product.objects.create(name='Qisman yo‘ldagi tovar')
        Stock.objects.create(product=product, quantity=0, warehouse_location='A-2')
        Zakaz.objects.create(product=product, quantity=3, zakaz_type=Zakaz.MANUAL)

        res = self.api.get(self.URL)
        self.assertEqual(res.status_code, 200, res.data)
        row = next(r for r in res.data['results'] if r['product_name'] == 'Qisman yo‘ldagi tovar')
        self.assertEqual(row['stock_status'], 'on_the_way')
        self.assertIsNotNone(row['id'])

    def test_normal_stock_product_still_shown(self):
        product = Product.objects.create(name='Oddiy tovar', min_quantity=5)
        Stock.objects.create(product=product, quantity=20, warehouse_location='A-3')

        res = self.api.get(self.URL)
        self.assertEqual(res.status_code, 200, res.data)
        row = next(r for r in res.data['results'] if r['product_name'] == 'Oddiy tovar')
        self.assertEqual(row['quantity'], 20)
        self.assertEqual(row['stock_status'], 'in_stock')

    def test_explicit_out_of_stock_filter_excludes_pending(self):
        """`?status=out_of_stock` — faqat chinakam bo'sh (yo'lda hech narsa
        yo'q) qatorlarni qaytaradi, "Yo'lda" mahsulotlarni emas."""
        truly_empty = Product.objects.create(name='Chin bo‘sh')
        Stock.objects.create(product=truly_empty, quantity=0, warehouse_location='A-4')
        pending = Product.objects.create(name='Boshqa yo‘ldagi tovar')
        Stock.objects.create(product=pending, quantity=0, warehouse_location='A-5')
        Zakaz.objects.create(product=pending, quantity=4, zakaz_type=Zakaz.MANUAL)

        res = self.api.get(self.URL, {'status': 'out_of_stock'})
        self.assertEqual(res.status_code, 200, res.data)
        names = self._product_names(res)
        self.assertIn('Chin bo‘sh', names)
        self.assertNotIn('Boshqa yo‘ldagi tovar', names)

    def test_on_the_way_status_filter_returns_only_pending(self):
        in_stock = Product.objects.create(name='Yetarli tovar', min_quantity=1)
        Stock.objects.create(product=in_stock, quantity=10, warehouse_location='A-6')
        pending = Product.objects.create(name='Faqat yo‘lda tovar')
        Zakaz.objects.create(product=pending, quantity=2, zakaz_type=Zakaz.MANUAL)

        res = self.api.get(self.URL, {'status': 'on_the_way'})
        self.assertEqual(res.status_code, 200, res.data)
        names = self._product_names(res)
        self.assertIn('Faqat yo‘lda tovar', names)
        self.assertNotIn('Yetarli tovar', names)

    def test_existing_zero_stock_row_still_editable_directly(self):
        """Standart ro'yxatda yashirilgan bo'lsa ham, mavjud (0 qoldiqli)
        Stock qatorini to'g'ridan-to'g'ri (retrieve/update) ochish/tahrirlash
        ishlashi kerak — ro'yxat filtri detail amallarga ta'sir qilmasin."""
        product = Product.objects.create(name='Alohida ochiladigan tovar')
        stock = Stock.objects.create(product=product, quantity=0, warehouse_location='A-7')

        detail = self.api.get(f'{self.URL}{stock.id}/')
        self.assertEqual(detail.status_code, 200, detail.data)

        update = self.api.patch(f'{self.URL}{stock.id}/', {'quantity': 5})
        self.assertEqual(update.status_code, 200, update.data)
