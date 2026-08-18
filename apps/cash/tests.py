from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.cash.models import Payment
from apps.cash.services import parse_bankxizmatlari_usd_rates
from apps.expenses.models import Expense
from apps.sales.models import Sale
from apps.users.models import User
from apps.warehouse.models import Product


BANKXIZMATLARI_SAMPLE = """
<div class="item js-element-item" data-usd-buy-bank="11870.00" data-usd-sale-bank="11990.00" data-bank="002">
  <div class="item__header--name">O'zmilliybank</div>
  <span class="item__update--text">Yangilanish vaqti: 11:02, 12.08.2026</span>
</div>
<div class="item js-element-item" data-usd-buy-bank="11875.00" data-usd-sale-bank="11945.00" data-bank="049">
  <div class="item__header--name">Kapitalbank</div>
  <span class="item__update--text">Yangilanish vaqti: 09:02, 12.08.2026</span>
</div>
<div class="item js-element-item" data-usd-buy-bank="11870.00" data-usd-sale-bank="11980.00" data-bank="012">
  <div class="item__header--name">Hamkorbank</div>
  <span class="item__update--text">Yangilanish vaqti: 16:21, 11.08.2026</span>
</div>
<div class="item js-element-item" data-usd-buy-bank="11870.00" data-usd-sale-bank="12000.00" data-bank="006">
  <div class="item__header--name">Xalq banki</div>
  <span class="item__update--text">Yangilanish vaqti: 11:30, 12.08.2026</span>
</div>
<div class="item js-element-item" data-usd-buy-bank="11850.00" data-usd-sale-bank="11940.00" data-bank="004">
  <div class="item__header--name">Agrobank</div>
  <span class="item__update--text">Yangilanish vaqti: 08:52, 12.08.2026</span>
</div>
<div class="item js-element-item" data-usd-buy-bank="11920.00" data-usd-sale-bank="12000.00" data-bank="053">
  <div class="item__header--name">InFinBank</div>
  <span class="item__update--text">Yangilanish vaqti: 12:01, 12.08.2026</span>
</div>
"""


class BankxizmatlariParserTests(TestCase):
    def test_parse_popular_bank_usd_rates(self):
        rates = parse_bankxizmatlari_usd_rates(BANKXIZMATLARI_SAMPLE)
        self.assertEqual(len(rates), 6)
        self.assertEqual(rates[0]['code'], '053')
        self.assertEqual(rates[0]['name'], 'InFinBank')
        self.assertEqual(rates[0]['buy_rate'], Decimal('11920.00'))
        self.assertEqual(rates[0]['sell_rate'], Decimal('12000.00'))
        self.assertEqual(rates[1]['code'], '002')
        self.assertEqual(rates[1]['buy_rate'], Decimal('11870.00'))


_sale_payment_counter = 0


def _make_sale_payment():
    # Regressiya: bitta testda ikki marta chaqirilsa ham serial_number
    # (unique maydon) to'qnashmasin.
    global _sale_payment_counter
    _sale_payment_counter += 1
    product = Product.objects.create(
        name='Monitor', serial_number=f'MN-{_sale_payment_counter}',
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
    Joriy qoida (`IsAccountantWithManagementRead`, role matrix — 4-bo'lim):
    Operator kassani **ko'ra oladi** (ro'yxat/detali), lekin pul
    summalari (`total_amount`/`commission`/`paid_amount`/`remaining`)
    `PaymentOperatorSerializer` orqali javobdan yashirin turadi — yozish
    esa faqat Accountant/Management.
    """

    def setUp(self):
        self.api = APIClient()
        self.operator = User.objects.create_user(
            'op_c', password='x', role=User.OPERATOR)
        self.accountant = User.objects.create_user(
            'acc_c2', password='x', role=User.ACCOUNTANT)
        _make_sale_payment()

    def test_operator_can_list_payments_without_amounts(self):
        self.api.force_authenticate(self.operator)
        res = self.api.get('/api/v1/cash/payments/')
        self.assertEqual(res.status_code, 200)
        row = res.data['results'][0]
        for field in ('total_amount', 'commission', 'paid_amount', 'remaining'):
            self.assertNotIn(field, row)

    def test_operator_cannot_write_payments(self):
        self.api.force_authenticate(self.operator)
        payment = Payment.objects.order_by('-id').first()
        res = self.api.patch(f'/api/v1/cash/payments/{payment.pk}/',
                             {'paid_amount': '100'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_accountant_can_list_payments(self):
        self.api.force_authenticate(self.accountant)
        res = self.api.get('/api/v1/cash/payments/')
        self.assertEqual(res.status_code, 200)
        row = res.data['results'][0]
        self.assertIn('total_amount', row)


class PaymentListFilterTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.accountant = User.objects.create_user(
            'acc_list', password='x', role=User.ACCOUNTANT)
        self.api.force_authenticate(self.accountant)
        self.pending = _make_sale_payment()
        self.paid = _make_sale_payment()
        self.paid.paid_amount = self.paid.total_amount
        self.paid.status = Payment.PAID
        self.paid.save()

    def test_list_hides_paid_by_default(self):
        res = self.api.get('/api/v1/cash/payments/')
        self.assertEqual(res.status_code, 200)
        ids = {row['id'] for row in res.data['results']}
        self.assertIn(self.pending.id, ids)
        self.assertNotIn(self.paid.id, ids)

    def test_list_can_include_paid_with_filter(self):
        res = self.api.get('/api/v1/cash/payments/?status=paid')
        self.assertEqual(res.status_code, 200)
        ids = {row['id'] for row in res.data['results']}
        self.assertIn(self.paid.id, ids)


class LedgerIncludesAllExpensesTests(TestCase):
    """
    Regressiya: umumiy kassa jurnali (ledger) va balans (summary) faqat
    import (zakaz)ga bog'liq chiqimlarni hisoblardi — ofis/transport/oylik
    kabi boshqa rasxod turlari kassa balansiga umuman kirmasdi.
    """

    def setUp(self):
        from apps.expenses.models import ExpenseType

        self.api = APIClient()
        self.accountant = User.objects.create_user(
            'acc_ledger', password='x', role=User.ACCOUNTANT)
        self.api.force_authenticate(self.accountant)

        payment = _make_sale_payment()  # total = 2 000 000
        payment.add_payment(Decimal('2000000'))

        office_type, _ = ExpenseType.objects.get_or_create(
            code=ExpenseType.OFFICE, defaults={'name': 'Ofis rasxod'})
        Expense.objects.create(
            expense_type=office_type, amount=Decimal('300000'),
            currency=Expense.UZS, date=date.today(),
            comment='Ofis ijarasi',
        )

    def test_ledger_lists_non_import_expense_as_out(self):
        res = self.api.get('/api/v1/cash/payments/ledger/?kind=out')
        self.assertEqual(res.status_code, 200, res.data)
        labels = [row['label'] for row in res.data['results']]
        self.assertIn('Ofis ijarasi', labels)
        row = next(r for r in res.data['results'] if r['label'] == 'Ofis ijarasi')
        self.assertEqual(row['source'], 'expense')

    def test_summary_net_balance_subtracts_all_expenses(self):
        res = self.api.get('/api/v1/cash/payments/summary/')
        self.assertEqual(res.status_code, 200, res.data)
        # 2 000 000 kirim - 300 000 (ofis) chiqim = 1 700 000
        self.assertEqual(Decimal(str(res.data['net_balance_uzs'])), Decimal('1700000'))
        self.assertEqual(Decimal(str(res.data['sum_out_uzs'])), Decimal('300000'))
        # Eski "faqat import" maydon o'zgarmasin (bu holatda import chiqimi yo'q)
        self.assertEqual(Decimal(str(res.data['sum_import_uzs'])), Decimal('0'))


class CashConversionTests(TestCase):
    """UZS <-> USD kassa balansi konvertatsiyasi — DBda saqlanadi va
    ikkala valyuta balansiga ham ta'sir qiladi."""

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            'mng_conv', password='x', role=User.MANAGEMENT)
        self.api.force_authenticate(self.manager)
        payment = _make_sale_payment()  # total = 2 000 000 UZS
        payment.add_payment(Decimal('2000000'))

    def test_uzs_to_usd_moves_balance_between_currencies(self):
        res = self.api.post('/api/v1/cash/payments/convert/', {
            'direction': 'uzs_to_usd', 'amount': '1185735', 'rate': '11857.35',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(res.data['amount_to']), Decimal('100.00'))

        summary = self.api.get('/api/v1/cash/payments/summary/').data
        self.assertEqual(Decimal(str(summary['net_balance_uzs'])), Decimal('814265'))
        self.assertEqual(Decimal(str(summary['net_balance_usd'])), Decimal('100.00'))

    def test_usd_to_uzs_reverses_the_move(self):
        self.api.post('/api/v1/cash/payments/convert/', {
            'direction': 'uzs_to_usd', 'amount': '1185735', 'rate': '11857.35',
        }, format='json')
        res = self.api.post('/api/v1/cash/payments/convert/', {
            'direction': 'usd_to_uzs', 'amount': '40', 'rate': '11857.35',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        summary = self.api.get('/api/v1/cash/payments/summary/').data
        self.assertEqual(Decimal(str(summary['net_balance_usd'])), Decimal('60.00'))

    def test_conversion_above_balance_is_rejected(self):
        res = self.api.post('/api/v1/cash/payments/convert/', {
            'direction': 'uzs_to_usd', 'amount': '99999999', 'rate': '11857.35',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)

    def test_converting_usd_without_balance_is_rejected(self):
        res = self.api.post('/api/v1/cash/payments/convert/', {
            'direction': 'usd_to_uzs', 'amount': '10', 'rate': '11857.35',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)


class CashBalanceAdjustmentTests(TestCase):
    """Kassa balansini qo'lda tuzatish — asos majburiy, tarixi saqlanadi."""

    URL = '/api/v1/cash/payments/adjust-balance/'

    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(
            'mng_adj', password='x', role=User.MANAGEMENT)
        self.accountant = User.objects.create_user(
            'acc_adj', password='x', role=User.ACCOUNTANT)
        payment = _make_sale_payment()  # total = 2 000 000 UZS
        payment.add_payment(Decimal('2000000'))

    def test_management_can_adjust_balance_up(self):
        self.api.force_authenticate(self.manager)
        res = self.api.post(self.URL, {
            'currency': 'UZS', 'target_balance': '2500000',
            'asos': 'Inventarizatsiya natijasida farq aniqlandi',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(res.data['amount']), Decimal('500000.00'))
        self.assertEqual(res.data['created_by_name'], 'mng_adj')

        summary = self.api.get('/api/v1/cash/payments/summary/').data
        self.assertEqual(Decimal(str(summary['net_balance_uzs'])), Decimal('2500000'))

    def test_adjust_down_computes_negative_delta(self):
        self.api.force_authenticate(self.manager)
        res = self.api.post(self.URL, {
            'currency': 'UZS', 'target_balance': '1000000',
            'asos': 'Xatolik tuzatildi',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(res.data['amount']), Decimal('-1000000.00'))
        summary = self.api.get('/api/v1/cash/payments/summary/').data
        self.assertEqual(Decimal(str(summary['net_balance_uzs'])), Decimal('1000000'))

    def test_asos_is_required(self):
        self.api.force_authenticate(self.manager)
        res = self.api.post(self.URL, {
            'currency': 'UZS', 'target_balance': '1000000', 'asos': '   ',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)

    def test_accountant_cannot_adjust_balance(self):
        self.api.force_authenticate(self.accountant)
        res = self.api.post(self.URL, {
            'currency': 'UZS', 'target_balance': '1000000', 'asos': 'sabab',
        }, format='json')
        self.assertEqual(res.status_code, 403, res.data)

    def test_adjustment_appears_in_ledger(self):
        self.api.force_authenticate(self.manager)
        self.api.post(self.URL, {
            'currency': 'UZS', 'target_balance': '2500000',
            'asos': 'Inventarizatsiya natijasida farq aniqlandi',
        }, format='json')
        res = self.api.get('/api/v1/cash/payments/ledger/?source=adjustment')
        self.assertEqual(res.status_code, 200, res.data)
        rows = res.data['results']
        self.assertEqual(len(rows), 1)
        self.assertIn('Inventarizatsiya', rows[0]['label'])
        self.assertEqual(rows[0]['client_name'], 'mng_adj')
        self.assertEqual(rows[0]['kind'], 'in')
