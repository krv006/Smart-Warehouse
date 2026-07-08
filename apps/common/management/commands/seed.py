"""
Fake ma'lumotlar bilan bazani to'ldirish.

Ishlatish:
    python manage.py seed              # standart (barcha modullar)
    python manage.py seed --clear      # avval tozalab keyin to'ldiradi
    python manage.py seed --users 10   # 10 ta foydalanuvchi
"""
import json
import random
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

fake = Faker(['uz_UZ', 'ru_RU'])
fake_en = Faker('en_US')

PRODUCT_CATEGORIES = [
    ('Server', ['Tower Server', 'Rack Server', 'Blade Server']),
    ('Tarmoq uskunalari', ['Switch', 'Router', 'Firewall', 'Access Point']),
    ('Saqlash qurilmalari', ['SSD', 'HDD', 'NAS', 'SAN']),
    ('Kompyuter', ['Desktop', 'All-in-One', 'Mini PC']),
    ('Monitor', ['24 dyuym', '27 dyuym', '32 dyuym', '4K Monitor']),
    ('Noutbuk', ['Business', 'Gaming', 'Ultrabook']),
    ('Printer', ['Lazerli', 'Inkjet', 'MFP']),
    ('UPS', ['600VA', '1000VA', '2000VA', '3000VA']),
]

BRANDS = ['HP', 'Dell', 'Lenovo', 'Cisco', 'Huawei', 'Samsung', 'LG',
          'Epson', 'Canon', 'Acer', 'Asus', 'MSI', 'APC', 'Schneider']

UZBEK_CITIES = [
    'Toshkent', 'Samarqand', 'Namangan', 'Andijon', "Farg'ona",
    'Buxoro', 'Nukus', 'Qarshi', 'Jizzax', 'Termiz',
]
SOURCES = [
    'Xitoy, Guangzhou', 'Rossiya, Moskva', 'UAE, Dubai',
    'Germaniya, Frankfurt', 'Turkiya, Istanbul', 'Koreya, Seul',
    'AKSH, New York', 'Singapur', 'Malayziya', 'Polsha, Varshava',
]
COMPANIES = [
    'Texnopark LLC', 'Uzinfocom', 'IT Solutions', 'DataCenter Uz',
    'Smart Systems', 'TechnoHub', 'Digital Future', 'NetPro',
    'InfoSystems', 'CyberSoft',
]
WAREHOUSE_LOCATIONS = [
    f'{r}-{s}-{n}' for r in 'ABCD' for s in range(1, 5) for n in range(1, 6)
]

EDIT_ASOSLAR = [
    'Mijoz miqdorni o\'zgartirdi (tel. orqali kelishildi)',
    'Yetkazish muddati mijoz iltimosiga ko\'ra surildi',
    'Shartnomaga qo\'shimcha kelishuv imzolandi',
    'Narx qayta kelishildi',
    'Mijoz manzili aniqlashtirildi',
]
QABUL_ASOSLAR = [
    'Qabul dalolatnomasi №{n}',
    'Kirim orderi №{n}',
    'TTN (yuk xati) №{n}',
]


def _contract_number():
    """Tasodifiy shartnoma raqami: SH-2026/NNN."""
    return f'SH-2026/{random.randint(1, 999):03d}'


def _faktura_number():
    return f'F-2026/{random.randint(100, 9999)}'

EXPENSE_TYPES_DATA = [
    ('office',        'Ofis rasxod'),
    ('import',        'Import rasxod'),
    ('declaration',   'Deklaratsiya rasxod'),
    ('certificate',   'Sertifikat rasxod'),
    ('transport',     'Transport rasxod'),
    ('business_trip', 'Komandirovka rasxod'),
    ('salary',        'Oylik rasxod'),
    ('other',         'ITG / boshqa rasxod'),
]
EXPENSE_SUBTYPES_DATA = {
    'office':        ['Ijara', 'Kommunal', 'Internet', 'Ofis jihozlari', 'Tozalash'],
    'import':        ["Boj to'lovi", "Sug'urta", 'Agentlik xizmati'],
    'declaration':   ['Deklaratsiya rasmiylashtirish', 'Broker xizmati'],
    'certificate':   ['Sertifikatlash', 'Laboratoriya tekshiruvi'],
    'transport':     ["Yoqilg'i", "Ta'mirlash", 'Shahar ichi', 'Shahar tashqarisi'],
    'business_trip': ['Mehmonxona', 'Aviabilet', 'Kunlik xarajat'],
    'salary':        ['Asosiy oylik', 'Mukofot', 'Bonus'],
    'other':         [],
}


def ok(msg):
    return f'[OK]  {msg}'


class Command(BaseCommand):
    help = "Fake ma'lumotlar bilan bazani to'ldiradi"

    def add_arguments(self, parser):
        parser.add_argument('--clear',      action='store_true', help='Avval bazani tozala')
        parser.add_argument('--only-types', action='store_true', help='Faqat rasxod toifalari (boshqa narsaga tegmaydi)')
        parser.add_argument('--users',    type=int, default=8,  help='Foydalanuvchilar soni')
        parser.add_argument('--products', type=int, default=40, help='Mahsulotlar soni')
        parser.add_argument('--sales',    type=int, default=60, help='Sotuvlar soni')
        parser.add_argument('--expenses', type=int, default=50, help='Rasxodlar soni')
        parser.add_argument('--clients',  type=int, default=15, help='Mijozlar soni')
        parser.add_argument('--payments', type=int, default=40, help="To'lovlar soni")
        parser.add_argument('--orders',   type=int, default=20, help='Buyurtmalar soni')
        parser.add_argument('--zakazlar', type=int, default=15, help='Zakazlar soni')

    @transaction.atomic
    def handle(self, *args, **options):
        # Faqat rasxod toifalari rejimi
        if options['only_types']:
            self.stdout.write('>>> Faqat rasxod toifalari seed...\n')
            self._seed_expense_types()
            self.stdout.write(self.style.SUCCESS('>>> Toifalar yaratildi!'))
            return

        if options['clear']:
            self._clear()

        self.stdout.write('>>> Seed boshlandi...\n')

        users     = self._seed_users(options['users'])
        cats      = self._seed_categories()
        products  = self._seed_products(options['products'], cats)
        self._seed_stocks(products)
        exp_types = self._seed_expense_types()
        clients   = self._seed_clients(options['clients'])
        sales     = self._seed_sales(options['sales'], products, clients)
        self._seed_expenses(options['expenses'], exp_types, users)
        self._seed_payments(options['payments'], sales, clients)
        self._seed_orders(options['orders'], products, clients, users)
        self._seed_zakazlar(options['zakazlar'], products, users)
        self._seed_notifications(products, users)
        self._seed_telegram_settings()

        self.stdout.write(self.style.SUCCESS('\n>>> Seed muvaffaqiyatli yakunlandi!'))

    # ── Clear ─────────────────────────────────────────────────────────────────
    def _clear(self):
        from apps.cash.models import Payment
        from apps.clients.models import Client
        from apps.expenses.models import Expense, ExpenseSubType, ExpenseType
        from apps.notifications.models import Notification, TelegramSettings
        from apps.orders.models import Order, Zakaz
        from apps.sales.models import Sale
        from apps.users.models import User
        from apps.warehouse.models import Category, Product, Stock

        self.stdout.write('>>> Baza tozalanmoqda...')
        Payment.objects.all().delete()   # PROTECT: Order/Sale dan oldin
        Zakaz.objects.all().delete()
        Order.objects.all().delete()
        Sale.objects.all().delete()
        Notification.objects.all().delete()
        Stock.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Expense.objects.all().delete()
        ExpenseSubType.objects.all().delete()
        ExpenseType.objects.all().delete()
        Client.objects.all().delete()
        TelegramSettings.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.WARNING('>>> Tozalandi.\n'))

    # ── Users ─────────────────────────────────────────────────────────────────
    def _seed_users(self, count):
        from apps.users.models import User
        roles = [User.OPERATOR, User.OPERATOR, User.OPERATOR,
                 User.ACCOUNTANT, User.ACCOUNTANT, User.MANAGEMENT]
        users = []
        fixed = [
            ('operator1',   'op1pass',  User.OPERATOR,   False),
            ('accountant1', 'acc1pass', User.ACCOUNTANT, False),
            ('manager1',    'mgr1pass', User.MANAGEMENT, True),
        ]
        for username, pwd, role, can_view in fixed:
            u, _ = User.objects.get_or_create(
                username=username,
                defaults=dict(
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    email=f'{username}@warehouse.uz',
                    password=make_password(pwd),
                    role=role,
                    phone=fake_en.numerify('+99890#######'),
                    can_view_clients=can_view,
                )
            )
            users.append(u)

        for _ in range(count):
            role     = random.choice(roles)
            username = fake_en.unique.user_name()[:20]
            u = User.objects.create(
                username=username,
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                email=f'{username}@warehouse.uz',
                password=make_password('test1234'),
                role=role,
                phone=fake_en.numerify('+99890#######'),
            )
            users.append(u)

        self.stdout.write(ok(f'{len(users)} ta foydalanuvchi yaratildi'))
        return users

    # ── Categories ────────────────────────────────────────────────────────────
    def _seed_categories(self):
        from apps.warehouse.models import Category
        cats = []
        for parent_name, children in PRODUCT_CATEGORIES:
            parent, _ = Category.objects.get_or_create(name=parent_name)
            cats.append(parent)
            for child_name in children:
                child, _ = Category.objects.get_or_create(
                    name=child_name, parent=parent
                )
                cats.append(child)
        self.stdout.write(ok(f'{len(cats)} ta kategoriya yaratildi'))
        return cats

    # ── Products ──────────────────────────────────────────────────────────────
    def _seed_products(self, count, cats):
        from apps.warehouse.models import Category, Product
        leaf_cats = list(Category.objects.filter(children__isnull=True))
        products  = []
        used_serials = set()

        for i in range(count):
            brand  = random.choice(BRANDS)
            model  = f'{brand}-{fake_en.bothify("??###").upper()}'
            serial = f'SN-{fake_en.bothify("####-????").upper()}'
            while serial in used_serials:
                serial = f'SN-{fake_en.bothify("####-????").upper()}'
            used_serials.add(serial)

            purchase = Decimal(str(random.randint(500_000, 45_000_000)))
            # ~20% mahsulot narxsiz (operator qo'shgan kabi)
            has_price    = random.random() > 0.20
            has_selling  = has_price and random.random() > 0.15
            margin       = Decimal(str(round(random.uniform(1.15, 1.6), 2)))
            selling      = (purchase * margin).quantize(Decimal('1000')) if has_selling else None
            min_qty      = random.choice([3, 5, 5, 5, 10, 10, 15, 20])

            p = Product.objects.create(
                category=random.choice(leaf_cats),
                name=f'{brand} {model}',
                model=model,
                serial_number=serial,
                purchase_price=purchase if has_price else None,
                selling_price=selling,
                source=random.choice(SOURCES),
                min_quantity=min_qty,
            )
            products.append(p)

        self.stdout.write(ok(f'{len(products)} ta mahsulot yaratildi '
                             f'({sum(1 for p in products if p.purchase_price is None)} ta narxsiz)'))
        return products

    # ── Stocks ────────────────────────────────────────────────────────────────
    def _seed_stocks(self, products):
        from apps.warehouse.models import Stock
        count = 0
        for product in products:
            locations = random.sample(WAREHOUSE_LOCATIONS, random.randint(1, 3))
            for loc in locations:
                Stock.objects.get_or_create(
                    product=product,
                    warehouse_location=loc,
                    defaults={
                        'quantity':          random.randint(2, 30),
                        'reserved_quantity': 0,
                    },
                )
                count += 1
        self.stdout.write(ok(f'{count} ta ombor qoldig\'i yaratildi'))

    # ── Expense Types ─────────────────────────────────────────────────────────
    def _seed_expense_types(self):
        from apps.expenses.models import ExpenseSubType, ExpenseType
        types = {}
        for code, name in EXPENSE_TYPES_DATA:
            et, _ = ExpenseType.objects.get_or_create(code=code, defaults={'name': name})
            for sub_name in EXPENSE_SUBTYPES_DATA.get(code, []):
                ExpenseSubType.objects.get_or_create(expense_type=et, name=sub_name)
            types[code] = et
        self.stdout.write(ok(f'{len(types)} ta rasxod toifasi yaratildi'))
        return types

    # ── Clients ───────────────────────────────────────────────────────────────
    def _seed_clients(self, count):
        from apps.clients.encryption import encrypt
        from apps.clients.models import Client
        clients = []
        for _ in range(count):
            company = random.choice(COMPANIES) + f' {fake_en.company_suffix()}'
            c = Client.objects.create(
                full_name=encrypt(fake.name()),
                company_name=company,
                inn=encrypt(fake_en.numerify('#########')),
                phone=encrypt(fake_en.numerify('+99890#######')),
                email=fake_en.company_email(),
                address=f'{random.choice(UZBEK_CITIES)}, {fake.street_address()}',
                is_active=random.random() > 0.1,
            )
            clients.append(c)
        self.stdout.write(ok(f'{len(clients)} ta mijoz yaratildi'))
        return clients

    # ── Sales ─────────────────────────────────────────────────────────────────
    def _seed_sales(self, count, products, clients):
        from apps.sales.models import Sale
        sales = []
        for _ in range(count):
            product   = random.choice(products)
            # available_quantity ga qarab (bron hisobga olinadi)
            avail_qty = product.available_quantity
            if avail_qty < 1:
                continue
            qty = random.randint(1, min(3, avail_qty))

            # Narx yo'q bo'lsa sold_price bazaviy qiymat ishlat
            if product.selling_price:
                base_price = product.selling_price
            elif product.purchase_price:
                margin     = Decimal(str(round(random.uniform(1.1, 1.5), 2)))
                base_price = (product.purchase_price * margin).quantize(Decimal('1000'))
            else:
                base_price = Decimal(str(random.randint(500_000, 10_000_000)))

            sold_date = fake_en.date_between(start_date='-180d', end_date='today')

            # FIFO — faqat bron bo'lmagan qoldiqdan ayir
            remaining = qty
            for st in product.stocks.filter(quantity__gt=0).order_by('id'):
                if remaining <= 0:
                    break
                free = st.quantity - st.reserved_quantity
                if free <= 0:
                    continue
                take = min(free, remaining)
                st.quantity -= take
                st.save(update_fields=['quantity'])
                remaining -= take

            if remaining > 0:
                continue

            s = Sale.objects.create(
                product=product,
                client=random.choice(clients) if clients and random.random() > 0.3 else None,
                quantity=qty,
                sold_price=base_price,
                sold_to=random.choice(COMPANIES),
                destination=random.choice(UZBEK_CITIES),
                sold_date=sold_date,
                comment=fake.sentence() if random.random() < 0.3 else None,
            )
            sales.append(s)

        self.stdout.write(ok(f'{len(sales)} ta sotuv yaratildi'))
        return sales

    # ── Expenses ──────────────────────────────────────────────────────────────
    def _seed_expenses(self, count, exp_types, users):
        from apps.expenses.models import Expense, ExpenseSubType
        accountants = [u for u in users if u.is_accountant or u.is_management]
        if not accountants:
            accountants = users

        def make_expense(et, sub):
            is_other = et.code == 'other'
            currency = random.choice(['UZS', 'UZS', 'UZS', 'USD'])
            amount   = (Decimal(str(random.randint(50_000, 5_000_000)))
                        if currency == 'UZS'
                        else Decimal(str(random.randint(50, 2000))))
            Expense.objects.create(
                expense_type=et,
                sub_type=sub,
                amount=amount,
                currency=currency,
                date=fake_en.date_between(start_date='-180d', end_date='today'),
                responsible=random.choice(accountants),
                comment=fake.sentence() if is_other or random.random() < 0.2 else None,
            )

        made = 0
        # 1) Har bir toifa VA har bir tip (subtype) uchun kamida bittadan yozuv
        for et in exp_types.values():
            subs = list(ExpenseSubType.objects.filter(expense_type=et))
            if subs:
                for sub in subs:
                    make_expense(et, sub)
                    made += 1
            else:
                # "other" — subtype yo'q, lekin toifa bo'sh qolmasin
                make_expense(et, None)
                made += 1

        # 2) Qolganini tasodifiy to'ldirish (jami `count` ga yetguncha)
        while made < count:
            et  = random.choice(list(exp_types.values()))
            sub = (ExpenseSubType.objects
                   .filter(expense_type=et)
                   .order_by('?').first())
            make_expense(et, sub)
            made += 1

        self.stdout.write(ok(f'{made} ta rasxod yaratildi (barcha toifa/tip qamrovda)'))

    # ── Payments ──────────────────────────────────────────────────────────────
    def _seed_payments(self, count, sales, clients):
        from apps.cash.models import Payment
        if not sales:
            return
        made = 0
        for sale in random.sample(sales, min(count, len(sales))):
            total      = sale.sold_price * sale.quantity
            commission = (total * Payment.COMMISSION_RATE).quantize(Decimal('0.01'))
            r          = random.random()
            if r < 0.35:
                paid, status = total, Payment.PAID
            elif r < 0.6:
                paid   = (total * Decimal(str(round(random.uniform(0.1, 0.9), 2)))).quantize(Decimal('0.01'))
                status = Payment.PARTIAL
            elif r < 0.8:
                paid, status = Decimal('0'), Payment.OVERDUE
            else:
                paid, status = Decimal('0'), Payment.PENDING

            p = Payment.objects.create(
                sale=sale,
                client=sale.client or (random.choice(clients) if clients else None),
                total_amount=total,
                commission=commission,
                paid_amount=paid,
                currency='UZS',
                due_date=fake_en.date_between(start_date='-30d', end_date='+60d'),
                status=status,
                comment=fake.sentence() if random.random() < 0.25 else None,
            )
            # To'langan summa tranzaksiyalarga bo'linadi (bo'lib to'lash tarixi)
            if paid > 0:
                if random.random() < 0.5 and paid > 1000:
                    first = (paid * Decimal(str(round(random.uniform(0.3, 0.7), 2)))
                             ).quantize(Decimal('0.01'))
                    p.transactions.create(amount=first,
                                          comment='Birinchi bo\'lib to\'lash')
                    p.transactions.create(amount=paid - first,
                                          comment='Qo\'shimcha to\'lov')
                else:
                    p.transactions.create(amount=paid, comment='To\'lov')
            made += 1
        self.stdout.write(ok(f"{made} ta to'lov yaratildi (tranzaksiyalar bilan)"))

    # ── Orders (Bron) ─────────────────────────────────────────────────────────
    def _seed_orders(self, count, products, clients, users):
        from apps.orders.models import (Order, OrderItem, OrderHistory,
                                        ProductContract, register_contract,
                                        allocate_pending_orders)

        operators = [u for u in users if u.is_operator] or users

        made = 0
        edited = 0
        auto_zakaz = 0
        for _ in range(count):
            client  = random.choice(clients) if clients else None
            creator = random.choice(operators)

            # BITTA buyurtma — 1-3 mahsulot qatori
            order_products = random.sample(products,
                                           k=min(random.randint(1, 3), len(products)))

            # Shartnoma — har buyurtmada MAJBURIY
            contract_number = _contract_number()
            contract_date   = fake_en.date_between(start_date='-60d', end_date='today')

            order = Order.objects.create(
                client=client,
                prepaid_amount=0,
                contract_number=contract_number,
                contract_date=contract_date,
                due_date=fake_en.date_between(start_date='+3d', end_date='+90d'),
                comment=fake.sentence() if random.random() < 0.3 else None,
            )

            total = Decimal('0')
            for product in order_products:
                qty        = random.randint(2, 15)
                unit_price = (product.selling_price
                              or Decimal(str(random.randint(500_000, 20_000_000))))
                OrderItem.objects.create(
                    order=order, product=product,
                    quantity=qty, unit_price=unit_price,
                )
                total += unit_price * qty

            # Oldindan to'lov: ~40% yo'q, ~40% qisman, ~20% to'liq
            r = random.random()
            if r < 0.4:
                prepaid = Decimal('0')
            elif r < 0.8:
                prepaid = (total * Decimal(str(round(random.uniform(0.2, 0.7), 2)))
                           ).quantize(Decimal('1000'))
            else:
                prepaid = total
            if prepaid:
                order.prepaid_amount = prepaid
                order.save(update_fields=['prepaid_amount'])

            # Bron ajratish (barcha qatorlar, FIFO)
            order.reserve()

            # Tarix: yaratildi + shartnomalar reestri (har qator mahsuloti)
            names = ', '.join(p.name for p in order_products)
            created_asos = (f'Buyurtma yaratildi ({names}) — '
                            f'shartnoma №{contract_number}.')
            OrderHistory.objects.create(
                order=order, changed_by=creator, action=OrderHistory.CREATED,
                contract_number=contract_number,
                asos=created_asos,
            )
            for product in order_products:
                register_contract(
                    product, ProductContract.ORDER_CREATED,
                    contract_number=contract_number, contract_date=contract_date,
                    asos=created_asos, order=order, user=creator,
                )

            # Pul (summa + oldindan to'lov) kassaga tushadi
            payment = order.sync_payment(user=creator)

            # ~40% qisman to'laganlar keyinroq QO'SHIMCHA to'lov qilgan
            if (payment and payment.remaining_amount > 0
                    and payment.paid_amount > 0 and random.random() < 0.4):
                extra = (payment.remaining_amount
                         * Decimal(str(round(random.uniform(0.2, 0.8), 2)))
                         ).quantize(Decimal('1000'))
                if extra > 0:
                    payment.add_payment(
                        extra, user=creator,
                        comment='Qo\'shimcha to\'lov (bo\'lib to\'lash)')

            # 2-etap: yetishmagan qatorlarga AVTO-ZAKAZ (~60% holatda)
            if order.backorder_qty > 0 and random.random() < 0.6:
                zakazlar = order.create_backorder_zakaz(user=creator)
                auto_zakaz += len(zakazlar)

            # ~35% buyurtma tahrirlangan (asos + tarix + reestr bilan)
            if random.random() < 0.35:
                old_due = order.due_date
                new_due = fake_en.date_between(start_date='+5d', end_date='+120d')
                order.due_date = new_due
                order.save(update_fields=['due_date'])
                editor    = random.choice(operators)
                edit_asos = random.choice(EDIT_ASOSLAR)
                OrderHistory.objects.create(
                    order=order, changed_by=editor,
                    action=OrderHistory.EDITED,
                    contract_number=contract_number,
                    asos=edit_asos,
                    changes=json.dumps(
                        {'due_date': {'old': str(old_due), 'new': str(new_due)}},
                        ensure_ascii=False),
                )
                for product in order_products:
                    register_contract(
                        product, ProductContract.ORDER_EDITED,
                        contract_number=contract_number, contract_date=contract_date,
                        asos=edit_asos, order=order, user=editor,
                    )
                edited += 1

            made += 1

        # Ba'zi buyurtmalar YETKAZILADI — REAL fulfill() bilan:
        # bron ombordan ayiriladi, reserved=0 bo'ladi (ma'lumot izchil qoladi).
        # Faqat TO'LIQ bronlangan buyurtmalar yetkaziladi (real hayotdagidek).
        fulfilled_n = 0
        candidates = [o for o in Order.objects.all() if o.status == Order.RESERVED]
        for order in random.sample(candidates, min(3, len(candidates))):
            actor = random.choice(operators)
            order.fulfill()
            OrderHistory.objects.create(
                order=order, changed_by=actor,
                action=OrderHistory.FULFILLED,
                contract_number=order.contract_number,
                asos='Buyurtma yetkazildi.',
            )
            for item in order.items.all():
                register_contract(
                    item.product, ProductContract.ORDER_FULFILLED,
                    contract_number=order.contract_number,
                    contract_date=order.contract_date,
                    asos='Buyurtma yetkazildi.', order=order, user=actor,
                )
            # Topshirishda ko'pchilik to'liq hisob-kitob qiladi (~70%)
            payment = order.payments.order_by('id').first()
            if (payment and payment.remaining_amount > 0
                    and random.random() < 0.7):
                payment.add_payment(
                    payment.remaining_amount, user=actor,
                    comment='Topshirishda to\'liq hisob-kitob')
            fulfilled_n += 1

        # Ba'zilari BEKOR qilinadi — REAL release() bilan (bron bo'shatiladi,
        # boshqa kutayotgan buyurtmalarga qayta taqsimlanadi).
        cancelled_n = 0
        candidates = list(Order.objects.exclude(
            status__in=(Order.FULFILLED, Order.CANCELLED)))
        for order in random.sample(candidates, min(2, len(candidates))):
            actor = random.choice(operators)
            order.release()
            order.status = Order.CANCELLED
            order.save(update_fields=['status'])
            OrderHistory.objects.create(
                order=order, changed_by=actor,
                action=OrderHistory.CANCELLED,
                contract_number=order.contract_number,
                asos='Mijoz buyurtmani bekor qildi.',
            )
            for item in order.items.all():
                allocate_pending_orders(item.product)
                register_contract(
                    item.product, ProductContract.ORDER_CANCELLED,
                    contract_number=order.contract_number,
                    contract_date=order.contract_date,
                    asos='Mijoz buyurtmani bekor qildi.', order=order, user=actor,
                )
            cancelled_n += 1

        self.stdout.write(ok(f'{made} ta buyurtma/bron yaratildi '
                             f'({edited} tahrirlangan, {auto_zakaz} avto-zakaz, '
                             f'{fulfilled_n} yetkazilgan, {cancelled_n} bekor)'))

    # ── Zakazlar (Etkazuvchidan buyurtma) ────────────────────────────────────────
    def _seed_zakazlar(self, count, products, users):
        from apps.orders.models import (Zakaz, ZakazHistory, ProductContract,
                                        register_contract)
        from apps.warehouse.models import Stock
        from django.db.models import F

        operators = [u for u in users if u.is_operator] or users
        managers  = [u for u in users if u.is_management] or users

        # status taqsimoti: new / confirmed / ordered / received / cancelled
        status_weights = [
            (Zakaz.NEW,       0.25),
            (Zakaz.CONFIRMED, 0.15),
            (Zakaz.ORDERED,   0.20),
            (Zakaz.RECEIVED,  0.30),
            (Zakaz.CANCELLED, 0.10),
        ]
        statuses = [s for s, w in status_weights for _ in range(int(w * 100))]

        # Faol zakazi bor mahsulotlarga takror zakaz bermaymiz (biznes qoida —
        # avto-zakazlar _seed_orders da allaqachon ochilgan bo'lishi mumkin)
        busy_ids = set(
            Zakaz.objects
            .filter(status__in=(Zakaz.NEW, Zakaz.CONFIRMED, Zakaz.ORDERED))
            .values_list('product_id', flat=True)
        )
        free_products = [p for p in products if p.id not in busy_ids] or products

        made = 0
        for _ in range(count):
            product  = random.choice(free_products)
            qty      = random.randint(5, 50)
            status   = random.choice(statuses)
            supplier = f'{random.choice(SOURCES)} — {fake_en.company()}'
            creator  = random.choice(operators)
            manager  = random.choice(managers)

            zakaz = Zakaz.objects.create(
                product=product,
                quantity=qty,
                supplier=supplier,
                status=Zakaz.NEW,  # avval NEW, keyin real holatga o'tkazamiz
                expected_date=fake_en.date_between(start_date='+2d', end_date='+45d'),
                created_by=creator,
                comment=fake.sentence() if random.random() < 0.3 else None,
            )
            ZakazHistory.objects.create(
                zakaz=zakaz, changed_by=creator, action=ZakazHistory.CREATED,
                new_status=Zakaz.NEW, asos='Zakaz yaratildi.',
            )
            register_contract(
                product, ProductContract.ZAKAZ_CREATED,
                asos='Zakaz yaratildi.', zakaz=zakaz, user=creator,
            )

            if status == Zakaz.NEW:
                made += 1
                continue

            if status == Zakaz.CANCELLED:
                cancel_asos = 'Etkazuvchi bilan kelishilmadi — bekor qilindi.'
                zakaz.status = Zakaz.CANCELLED
                zakaz.asos   = cancel_asos
                zakaz.save(update_fields=['status', 'asos'])
                ZakazHistory.objects.create(
                    zakaz=zakaz, changed_by=manager,
                    action=ZakazHistory.STATUS_CHANGED,
                    old_status=Zakaz.NEW, new_status=Zakaz.CANCELLED,
                    asos=cancel_asos,
                )
                register_contract(
                    product, ProductContract.ZAKAZ_CANCELLED,
                    asos=cancel_asos, zakaz=zakaz, user=manager,
                )
                made += 1
                continue

            # confirmed / ordered / received — avval TASDIQLASH bosqichi:
            # HAR BIR holatda shartnoma + asos MAJBURIY (API qoidasiga mos)
            contract_number = _contract_number()
            contract_date   = fake_en.date_between(start_date='-30d', end_date='today')
            confirm_asos    = f'Tasdiqlandi — shartnoma №{contract_number}.'
            zakaz.contract_number = contract_number
            zakaz.contract_date   = contract_date
            zakaz.confirmed_at    = timezone.now()
            zakaz.asos            = confirm_asos
            zakaz.status          = Zakaz.CONFIRMED
            zakaz.save(update_fields=['contract_number', 'contract_date',
                                      'confirmed_at', 'asos', 'status'])
            ZakazHistory.objects.create(
                zakaz=zakaz, changed_by=manager,
                action=ZakazHistory.STATUS_CHANGED,
                old_status=Zakaz.NEW, new_status=Zakaz.CONFIRMED,
                contract_number=contract_number, contract_date=contract_date,
                asos=confirm_asos,
            )
            register_contract(
                product, ProductContract.ZAKAZ_CONFIRMED,
                contract_number=contract_number, contract_date=contract_date,
                asos=confirm_asos, zakaz=zakaz, user=manager,
            )

            if status in (Zakaz.ORDERED, Zakaz.RECEIVED):
                ordered_asos = (f'Etkazuvchiga yuborildi — '
                                f'shartnoma №{contract_number} asosida.')
                zakaz.status = Zakaz.ORDERED
                zakaz.asos   = ordered_asos
                zakaz.save(update_fields=['status', 'asos'])
                ZakazHistory.objects.create(
                    zakaz=zakaz, changed_by=manager,
                    action=ZakazHistory.STATUS_CHANGED,
                    old_status=Zakaz.CONFIRMED, new_status=Zakaz.ORDERED,
                    contract_number=contract_number, contract_date=contract_date,
                    asos=ordered_asos,
                )
                register_contract(
                    product, ProductContract.ZAKAZ_ORDERED,
                    contract_number=contract_number, contract_date=contract_date,
                    asos=ordered_asos, zakaz=zakaz, user=manager,
                )

            if status == Zakaz.RECEIVED:
                received_qty = qty if random.random() > 0.15 else random.randint(1, qty - 1)
                loc     = random.choice(WAREHOUSE_LOCATIONS)
                asos    = random.choice(QABUL_ASOSLAR).format(n=random.randint(10, 999))
                faktura = _faktura_number()

                zakaz.received_qty       = received_qty
                zakaz.warehouse_location = loc
                zakaz.asos               = asos
                zakaz.faktura            = faktura
                zakaz.status             = Zakaz.RECEIVED
                zakaz.save(update_fields=['received_qty', 'warehouse_location',
                                          'asos', 'faktura', 'status'])
                ZakazHistory.objects.create(
                    zakaz=zakaz, changed_by=manager,
                    action=ZakazHistory.RECEIVED,
                    old_status=Zakaz.ORDERED, new_status=Zakaz.RECEIVED,
                    contract_number=contract_number, contract_date=contract_date,
                    asos=asos, faktura=faktura,
                )
                register_contract(
                    product, ProductContract.ZAKAZ_RECEIVED,
                    contract_number=contract_number, contract_date=contract_date,
                    asos=asos, faktura=faktura, zakaz=zakaz, user=manager,
                )

                # REAL qabul: ombor to'ldiriladi + kutayotgan buyurtma
                # qatorlariga avtomatik bron (shartnoma asosida, tarix bilan)
                # + low-stock bildirishnoma yopiladi
                zakaz.receive(user=manager)

            made += 1

        self.stdout.write(ok(f'{made} ta zakaz yaratildi (shartnoma/asos/faktura bilan)'))

    # ── Notifications ─────────────────────────────────────────────────────────
    def _seed_notifications(self, products, users):
        from apps.notifications.models import Notification
        from apps.users.models import User

        managers = [u for u in users if u.is_management]
        if not managers:
            return

        # Narxsiz mahsulotlar uchun bildirishnoma
        unpriced = [p for p in products if p.purchase_price is None]
        count = 0
        for product in unpriced:
            for manager in managers:
                Notification.objects.get_or_create(
                    recipient=manager,
                    product=product,
                    is_read=False,
                    defaults={
                        'title':   'Summasi kiritilmagan!',
                        'message': (
                            f'"{product.name}" ({product.serial_number}) mahsuloti uchun '
                            f'summasini (kelish narxini) kiritmagansiz! Iltimos, kiriting.'
                        ),
                    }
                )
                count += 1

        # Qoldiq kam bo'lgan mahsulotlar uchun bildirishnoma
        for product in products:
            if product.available_quantity <= product.min_quantity and product.available_quantity > 0:
                for manager in managers:
                    Notification.objects.get_or_create(
                        recipient=manager,
                        product=product,
                        title='Qoldiq kam!',
                        is_read=False,
                        defaults={
                            'message': (
                                f'"{product.name}" ({product.serial_number}) qoldig\'i '
                                f'minimal chegaradan ({product.min_quantity} dona) pastga tushdi. '
                                f'Hozirgi qoldiq: {product.available_quantity} dona.'
                            ),
                        }
                    )
                    count += 1

        self.stdout.write(ok(f'{count} ta bildirishnoma yaratildi'))

    # ── Telegram Settings ─────────────────────────────────────────────────────
    def _seed_telegram_settings(self):
        from apps.notifications.models import TelegramSettings
        TelegramSettings.objects.get_or_create(
            pk=1,
            defaults={
                'bot_token': '1234567890:AAFake_Token_For_Development_Only',
                'chat_id':   '-1001234567890',
                'is_active': False,
            }
        )
        self.stdout.write(ok('TelegramSettings yaratildi (is_active=False)'))
