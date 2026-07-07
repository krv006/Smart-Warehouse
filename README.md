# Smart Warehouse — Ombor boshqaruv tizimi

Django REST Framework asosida qurilgan to'liq ombor / savdo / kassa boshqaruv API'si.
Uch rol (**Operator**, **Accountant**, **Management**), bron/zakaz tizimi, in-app
bildirishnomalar va Excel hisobotlar bilan.

> 📄 **To'liq hujjat (0 → 100):** [PROJECT_DOCS.md](PROJECT_DOCS.md) —
> barcha endpointlar, Buyurtma → Zakaz oqimi (shartnoma, asos, faktura,
> oldindan to'lov), audit/tarix tizimi va biznes qoidalar.

---

## Mundarija
1. [Texnologiyalar](#texnologiyalar)
2. [O'rnatish](#ornatish)
3. [Fake ma'lumot (seed)](#fake-malumot-seed)
4. [Rollar va ruxsatlar](#rollar-va-ruxsatlar)
5. [Modullar va API](#modullar-va-api)
   - [Auth](#auth)
   - [Warehouse (Mahsulot, Stock, Kategoriya)](#warehouse)
   - [Sales (Sotuv)](#sales-sotuv)
   - [Orders (Bron) va Zakaz](#orders-bron-va-zakaz)
   - [Cash (Kassa)](#cash-kassa)
   - [Expenses (Rasxod)](#expenses-rasxod)
   - [Clients (Mijozlar)](#clients-mijozlar)
   - [Notifications (Bildirishnoma)](#notifications-bildirishnoma)
   - [Reports (Hisobot)](#reports-hisobot)
6. [Muhim biznes-logika](#muhim-biznes-logika)
7. [Migratsiya va deploy](#migratsiya-va-deploy)
8. [O'zgarishlar tarixi (changelog)](#ozgarishlar-tarixi-changelog)

---

## Texnologiyalar

| Kutubxona | Maqsad |
|-----------|--------|
| Django ≥ 5.2 | Asosiy framework |
| Django REST Framework | REST API |
| djangorestframework-simplejwt | JWT autentifikatsiya (access 8s, refresh 30k) |
| django-mptt | Daraxt kategoriya (parent → children) |
| django-filter | Filtr va qidiruv |
| drf-spectacular | Swagger / OpenAPI |
| django-jazzmin | Admin tema |
| django-cors-headers | CORS |
| cryptography (Fernet) | Mijoz ma'lumotlarini shifrlash |
| celery + django-celery-beat | Fon vazifalar (kechikkan to'lov, backup) |
| openpyxl | Excel export |
| Faker | Fake test ma'lumotlari |

---

## O'rnatish

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
# .venv\Scripts\activate        # Windows

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### .env

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=*

# PostgreSQL (bo'lmasa SQLite ishlatiladi)
DB_ENGINE=postgres
DB_NAME=warehouse
DB_USER=postgres
DB_PASSWORD=secret
DB_HOST=localhost
DB_PORT=5432

# Mijoz shifrlash kaliti (Fernet)
FERNET_KEY=<base64-32-byte-key>
```

> ⚠️ `migrations/` papkalari `.gitignore` da — har bir muhit o'zi `makemigrations` qiladi.

---

## Fake ma'lumot (seed)

```bash
python manage.py seed --clear              # hammasini tozalab, to'liq to'ldiradi
python manage.py seed --only-types         # faqat rasxod toifalari (boshqasiga tegmaydi)

# sonlarni sozlash
python manage.py seed --products 60 --orders 30 --zakazlar 20 --clients 25
```

**Seed nima yaratadi:**
| Modul | Tavsif |
|-------|--------|
| Users | 3 ta belgilangan: `operator1/op1pass`, `accountant1/acc1pass`, `manager1/mgr1pass` + tasodifiy |
| Categories | 8 ta ota + bola kategoriyalar (MPTT) |
| Products | ~20% narxsiz, `selling_price` + `min_quantity` bilan |
| Stock | Har mahsulotга 1–3 lokatsiya |
| Sales | `available_quantity` ga qarab, mijozga bog'langan |
| Orders (bron) | Bron ajratilgan, ba'zisi fulfilled/cancelled |
| Zakazlar | Statuslar taqsimoti (received → ombor to'ldiriladi) |
| Expenses | Har bir toifa + tip qamrab olinadi |
| Payments | Turli statuslar (paid/partial/overdue/pending) |
| Notifications | Narxsiz + low-stock bildirishnomalar |

---

## Rollar va ruxsatlar

| Rol | Kod | Asosiy vazifa |
|-----|-----|---------------|
| Operator | `OPERATOR` | Mahsulot qo'shish, sotuv, buyurtma, zakaz yaratish |
| Accountant | `ACCOUNTANT` | Kassa, rasxod boshqaruvi |
| Management | `MANAGEMENT` | Narx belgilash, hisobot, zakaz statusini boshqarish |
| Superuser | — | Hamma huquq |

### Rol matritsasi

| Funksiya | Operator | Accountant | Management |
|----------|:--------:|:----------:|:----------:|
| Mahsulot qo'shish | ✅ | ❌ | ✅ |
| `purchase_price` / `selling_price` ko'rish | ❌ | ✅ | ✅ |
| Narx kiritish | ❌ | ❌ | ✅ |
| `min_quantity` o'zgartirish | ❌ | ❌ | ✅ |
| Sotuv | ✅ | ❌ | ✅ |
| Sotuv summasini ko'rish | ❌ | ✅ | ✅ |
| Kassa / Rasxod CRUD | ko'rish | ✅ | ✅ |
| Buyurtma / Bron | ✅ | ❌ | ✅ |
| Zakaz yaratish | ✅ | ✅ | ✅ |
| **Zakaz status o'zgartirish** | ❌ | ❌ | ✅ **faqat** |
| Hisobotlar | ❌ | ✅ | ✅ |

> Operator uchun `purchase_price` va `selling_price` API javobida umuman **yo'q**.

---

## Modullar va API

**Bazaviy URL:** `/api/v1/`

### Auth
| Method | URL | Tavsif |
|--------|-----|--------|
| POST | `/auth/login/` | Username + parol → JWT + `user` (role, can_view_clients) |
| POST | `/auth/token/refresh/` | Refresh → yangi access |

> Login paytida Management userga narxsiz mahsulotlar bo'yicha bildirishnomalar avtomatik yaratiladi.

---

### Warehouse

#### Product
| Method | URL | Tavsif |
|--------|-----|--------|
| GET/POST | `/warehouse/products/` | Ro'yxat / yangi |
| GET/PATCH/DELETE | `/warehouse/products/{id}/` | Bitta / tahrirlash |

**Yangi fieldlar:**
| Field | Tavsif |
|-------|--------|
| `purchase_price` | Kelish narxi (nullable — operator kiritmaydi) |
| `selling_price` | Sotuv/ketish narxi (Management) |
| `min_quantity` | Minimal qoldiq chegarasi (notification uchun) |
| `quantity_in_stock` | Ombordagi jami |
| `reserved_quantity` | Bron qilingan |
| `available_quantity` | Sotish mumkin (`jami − bron`) |
| `stock_status` | `in_stock` / `low_stock` / `out_of_stock` |

Filtr: `?category=3` · `?purchase_price__isnull=true` · `?selling_price__isnull=true`

Mahsulot qo'shishda `quantity` + `warehouse_location` yuborilsa — Stock avtomatik yaratiladi.

#### Stock
| Method | URL | Tavsif |
|--------|-----|--------|
| GET/POST | `/warehouse/stocks/` | Qoldiqlar |
| GET/PATCH/DELETE | `/warehouse/stocks/{id}/` | Bitta |

Filtr: `?product=1` · `?category=3` · `?status=low_stock` · `?date_from=...&date_to=...`
Javobda: `reserved_quantity`, `min_quantity`, `stock_status`.

#### Category
`/warehouse/categories/` — MPTT daraxt (`parent → children`).

---

### Sales (Sotuv)
| Method | URL | Tavsif |
|--------|-----|--------|
| GET/POST | `/sales/` | Ro'yxat / yangi |
| GET/PATCH/DELETE | `/sales/{id}/` | Bitta |

- `client` (FK → Client) + `client_name`
- Sotuv **FIFO** tartibida ombordan ayiradi
- Faqat `available_quantity` yetsa sotiladi (bron qilinganini sota olmaysiz)
- `profit` — `purchase_price` yo'q bo'lsa `null`

Filtr: `?product=1` · `?client=<uuid>` · `?sold_date=...`

---

### Orders (Bron) va Zakaz

> To'liq tavsif: [PROJECT_DOCS.md](PROJECT_DOCS.md#5-buyurtma--zakaz-oqimi)

#### Order (Mijoz bron/buyurtmasi)

**BITTA buyurtma — bir nechta mahsulot (`items`).** Nechta mahsulot bo'lsa ham
buyurtma bitta hujjat.

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/orders/` | Ro'yxat |
| POST | `/orders/` | Buyurtma (`items[]`) — **shartnoma raqami MAJBURIY** |
| POST | `/orders/bulk/` | `items[]` — natija ham BITTA buyurtma (moslik uchun) |
| PATCH | `/orders/{id}/` | Tahrirlash: qator miqdori (`items[{id,...}]`) / yangi qator / sarlavha (**asos majburiy**) |
| POST | `/orders/{id}/fulfill/` | Yetkazildi (barcha qatorlar) |
| POST | `/orders/{id}/cancel/` | Bekor qilish |
| POST | `/orders/{id}/create-zakaz/` | Yetishmagan qatorlarga qo'lda zakaz |

**Order fieldlari:** `items[]` (har qatorda `product`, `quantity`, `unit_price`,
`total`, `reserved_qty`, `backorder_qty`, `has_active_zakaz`), `contract_number`
(majburiy), `contract_date`, `prepaid_amount`, `balance_due`, `total_quantity`,
`total`, `history`, `status` (`pending`/`partial`/`reserved`/`fulfilled`/`cancelled`).

- Buyurtma HAR DOIM yaratiladi — yetishmagan (backorder) qatorlar uchun
  **AVTOMATIK Zakaz** ochiladi, har mahsulotga alohida (shartnoma meros o'tadi)
- Kassada butun buyurtma uchun BITTA to'lov yozuvi
- Har tahrir shartnoma raqami + asos + aniq sana/vaqt bilan tarixga yoziladi
- Yangi qoldiq kelganda pending qatorlar `due_date` bo'yicha avtomatik bronlanadi

#### Zakaz (Etkazuvchidan buyurtma)
| Method | URL | Tavsif |
|--------|-----|--------|
| GET/POST | `/orders/zakaz/` | Ro'yxat / yangi (status="new") |
| POST | `/orders/zakaz/bulk/` | Bir nechta mahsulot uchun |
| PATCH | `/orders/zakaz/{id}/` | Yangilash (status — faqat Manager) |

- Operator yaratadi (yoki buyurtmadan avto); **status faqat Management** o'zgartiradi
- Status oqimi: `new → confirmed → ordered → received → (ombor to'ldiriladi)`
- **HAR BIR holat o'zgarishida `asos` MAJBURIY**; `confirmed`/`ordered`/`received`
  uchun **shartnoma raqami ham MAJBURIY**
- **Tasdiqlash:** shartnoma kiritilmaguncha bo'lmaydi; sana avtomatik bugungi kun
  (Tashkent), buyurtmadan kelgan shartnomada o'sha kun saqlanadi
- **Yuborildi (ordered):** shartnoma + asos majburiy
- **Qabul qilish:** shartnoma + `asos` + `faktura` MAJBURIY; `received_qty` omborga
  qo'shiladi + pending orderlarga bron ajratiladi
- Har bir o'zgarish `history` (audit) ga va **mahsulot shartnomalari reestriga**
  (`/orders/contracts/`, `/warehouse/products/{id}/contracts/`) avtomatik yoziladi

---

### Cash (Kassa)
| Method | URL | Tavsif |
|--------|-----|--------|
| GET/POST | `/cash/payments/` | To'lovlar |
| GET/PATCH/DELETE | `/cash/payments/{id}/` | Bitta |
| GET | `/cash/payments/summary/` | Kassa xulosasi |

- Status: `pending` / `partial` / `paid` / `overdue`
- Komissiya avtomatik 15% (faqat sotuv to'lovlarida)
- **Kechikkan** = `status ∈ (pending, partial, overdue)` AND `due_date < bugun`
- **Buyurtma to'lovlari avtomatik:** narxli buyurtma berilganda kassada darhol
  yozuv ochiladi (jami + oldindan to'lov + status); buyurtma tahrirlanganda
  kassa ham yangilanadi. `source` = `sale` | `order`
- **Bo'lib to'lash:** `POST /cash/payments/{id}/pay/` — qisman to'lagan mijoz
  keyinroq yana to'laydi; har to'lov alohida tranzaksiya (kim/qachon/qancha),
  status avtomatik `pending → partial → paid`, buyurtmadagi `prepaid_amount`
  sinxronlanadi

---

### Expenses (Rasxod)
| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/expenses/expense-types/` | Toifalar (read-only) |
| GET/POST | `/expenses/expense-subtypes/` | Tiplar |
| GET/POST | `/expenses/expenses/` | Rasxodlar |
| GET | `/expenses/expenses/summary/` | Statistika |

- Filtr: `?expense_type=1` · `?sub_type=5` · `?currency=UZS` · `?date_from=...&date_to=...`
- `responsible` (Mas'ul) — rasxodni **qo'shgan foydalanuvchiga** avtomatik bog'lanadi (read-only)
- `responsible_name` — to'liq ism + username
- "Boshqa" toifasida `comment` majburiy

---

### Clients (Mijozlar)
| Method | URL | Tavsif |
|--------|-----|--------|
| GET/POST | `/clients/` | Ro'yxat / yangi |
| GET/PATCH/DELETE | `/clients/{id}/` | Bitta |

- `id` — UUID
- `full_name`, `inn`, `phone` — bazada **Fernet** shifrlangan, API javobida ochiq matn
- Faqat `can_view_clients=true` operator ko'radi

---

### Notifications (Bildirishnoma)
| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/notifications/` | Mening bildirishnomalarim |
| GET | `/notifications/?is_read=false` | O'qilmaganlar |
| POST | `/notifications/{id}/mark_read/` | Bittani o'qilgan |
| POST | `/notifications/mark_all_read/` | Hammasini o'qilgan |

**Turlari (in-app, Telegram yo'q):**
| title | Sababi |
|-------|--------|
| `Summasi kiritilmagan!` | Operator narxsiz mahsulot qo'shdi |
| `Qoldiq kam!` | Qoldiq `min_quantity` dan tushdi |

- Narx kiritilganda / qoldiq ko'tarilganda avtomatik yopiladi
- Login paytida qayta yaratiladi (narx kiritilmaguncha)

---

### Reports (Hisobot)
| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/reports/summary/` | Umumiy moliyaviy xulosa |
| GET | `/reports/warehouse/` | Ombor hisoboti (kam qolgan, kategoriya bo'yicha) |
| GET | `/reports/cash/` | Kassa hisoboti |
| GET | `/reports/expenses/` | Rasxod hisoboti |
| GET | `/reports/top-products/` | Eng ko'p sotilgan mahsulotlar |
| GET | `/reports/excel/sales/` | Excel: sotuvlar |
| GET | `/reports/excel/stock/` | Excel: ombor |
| GET | `/reports/excel/expenses/` | Excel: rasxod |
| GET | `/reports/excel/payments/` | Excel: kassa |

Hammasi `?date_from` / `?date_to` qabul qiladi.

---

## Muhim biznes-logika

### Bron va zakaz oqimi (real stsenariy)
```
Mijoz 10 ta so'raydi, omborda 3 ta bor. Shartnoma SH-2026/045, oldindan to'lov bor.
  → POST /orders/ { contract_number:"SH-2026/045", prepaid_amount:"10000000", ... }
  → reserved_qty=3, backorder_qty=7, status="partial"
  → AVTOMATIK: yetishmagan 7 ta uchun Zakaz ochiladi (SH-2026/045 asosida)
Manager boshqaradi: new → confirmed (shartnoma majburiy, sana avto-bugun) → ordered
Tovar keldi:
  → PATCH /orders/zakaz/{id}/ { status:"received", received_qty:20,
      warehouse_location:"B-2-3", asos:"Dalolatnoma №77", faktura:"F-2026/555" }
  → ombor +20, pending order avtomatik to'ldiriladi → status="reserved"
Topshirish:
  → POST /orders/{id}/fulfill/  → ombordan ayrildi, status="fulfilled"
Har bir amal (yaratish/tahrir/status) shartnoma + asos + sana/vaqt bilan tarixda.
```

### FIFO
Sotuv va bron ombordagi eng eski Stock yozuvidan (id bo'yicha) boshlab ayiradi.

### available_quantity himoyasi
Sotuv faqat `available_quantity` (bron qilinmagan qoldiq) dan amalga oshadi — bron qilingan
mahsulotni boshqa mijozga sotib bo'lmaydi.

---

## Migratsiya va deploy

```bash
git pull origin main
python manage.py makemigrations
python manage.py migrate
python manage.py seed --clear     # ixtiyoriy — test uchun
# service restart (gunicorn/uwsgi)
```

**Asosiy jadvallar:** `warehouse_product`, `warehouse_stock`, `sales_sale`,
`orders_order`, `orders_zakaz`, `cash_payment`, `expenses_expense`,
`clients_client`, `notifications_notification`.

---

## O'zgarishlar tarixi (changelog)

### Narx va qoldiq
- `Product.purchase_price` → nullable (operator narxsiz qo'sha oladi)
- `Product.selling_price` qo'shildi (sotuv narxi)
- `Product.min_quantity` — har mahsulot uchun alohida chegara
- `Stock.reserved_quantity` — bron miqdori
- `available_quantity`, `stock_status` hisoblanadigan fieldlar
- Mahsulot qo'shishda Stock avtomatik yaratiladi

### Bron va Zakaz (yangi `apps/orders`)
- `Order` — mijoz bron/buyurtmasi (FIFO bron, deadline bo'yicha taqsimlash)
- `Zakaz` — etkazuvchidan buyurtma (status faqat Manager)
- `POST /orders/bulk/` — bir vaqtda bir nechta mahsulot
- `Order.unit_price` + `total`, `has_active_zakaz`

### Bildirishnoma (yangi `apps/notifications`)
- In-app bildirishnoma tizimi (Telegram **emas**)
- Narxsiz + low-stock avtomatik xabar

### Savdo va kassa
- `Sale.client` (FK → Client) qo'shildi
- Kassa `summary` overdue hisoblash bugi tuzatildi
- `/cash/payments/` prefiksiga o'tkazildi

### Rasxod
- `date_from/date_to` filtr + `summary` statistika endpoint
- `responsible` avtomatik — qo'shgan foydalanuvchiga bog'lanadi
- Router `expenses/`, `expense-types/`, `expense-subtypes/` ga moslandi

### Hisobot
- Ombor / Kassa / Rasxod alohida hisobotlar + top-products

### Admin
- `format_html` bug tuzatishi (`ValueError: Unknown format code 'f'`)

---

## Swagger UI

| URL | Tavsif |
|-----|--------|
| `/` | Swagger UI |
| `/api/redoc/` | ReDoc |
| `/api/schema/` | OpenAPI JSON |
| `/admin/` | Admin panel (Jazzmin) |
