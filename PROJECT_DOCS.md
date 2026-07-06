# Smart Warehouse — To'liq loyiha hujjati (0 → 100)

Django REST Framework asosida qurilgan ombor / savdo / kassa boshqaruv API'si.
Uch rol (**Operator**, **Accountant**, **Management**), bron/zakaz tizimi,
**shartnoma (dogovor) + asos + faktura audit zanjiri**, in-app bildirishnomalar
va Excel hisobotlar bilan.

---

## Mundarija
1. [Texnologiyalar](#1-texnologiyalar)
2. [O'rnatish](#2-ornatish)
3. [Fake ma'lumot (seed)](#3-fake-malumot-seed)
4. [Rollar va ruxsatlar](#4-rollar-va-ruxsatlar)
5. [Buyurtma → Zakaz oqimi (YANGI, asosiy biznes-jarayon)](#5-buyurtma--zakaz-oqimi)
6. [Modullar va API](#6-modullar-va-api)
7. [Audit / Tarix tizimi](#7-audit--tarix-tizimi)
8. [Muhim biznes-logika](#8-muhim-biznes-logika)
9. [Migratsiya va deploy](#9-migratsiya-va-deploy)
10. [Swagger UI](#10-swagger-ui)

---

## 1. Texnologiyalar

| Kutubxona | Maqsad |
|-----------|--------|
| Django ≥ 5.2 | Asosiy framework |
| Django REST Framework | REST API |
| djangorestframework-simplejwt | JWT autentifikatsiya |
| django-mptt | Daraxt kategoriya (parent → children) |
| django-filter | Filtr va qidiruv |
| drf-spectacular | Swagger / OpenAPI |
| django-jazzmin | Admin tema |
| django-cors-headers | CORS |
| cryptography (Fernet) | Mijoz ma'lumotlarini shifrlash |
| celery + django-celery-beat | Fon vazifalar (kechikkan to'lov, backup) |
| openpyxl | Excel export |
| Faker | Fake test ma'lumotlari |

**Vaqt zonasi:** `Asia/Tashkent` (`USE_TZ=True`) — barcha sana/vaqtlar Tashkent bo'yicha.

---

## 2. O'rnatish

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

## 3. Fake ma'lumot (seed)

```bash
python manage.py seed --clear              # hammasini tozalab, to'liq to'ldiradi
python manage.py seed --only-types         # faqat rasxod toifalari

# sonlarni sozlash
python manage.py seed --products 60 --orders 30 --zakazlar 20 --clients 25
```

| Modul | Tavsif |
|-------|--------|
| Users | 3 ta belgilangan: `operator1/op1pass`, `accountant1/acc1pass`, `manager1/mgr1pass` + tasodifiy |
| Categories | 8 ta ota + bola kategoriyalar (MPTT) |
| Products | ~20% narxsiz, `selling_price` + `min_quantity` bilan |
| Stock | Har mahsulotga 1–3 lokatsiya |
| Sales | `available_quantity` ga qarab, mijozga bog'langan |
| Orders (bron) | Shartnoma raqami + oldindan to'lov (~60% da) bilan; bron ajratilgan, ~35% tahrirlangan (asos + tarix), yetishmaganlarга avto-zakaz, ba'zisi fulfilled/cancelled |
| Zakazlar | Statuslar taqsimoti; tasdiqlanganlari shartnoma + `confirmed_at` bilan, qabul qilinganlari asos + faktura bilan (received → ombor to'ldiriladi), to'liq tarix (ZakazHistory) |
| Order/Zakaz tarixi | Har amal uchun audit yozuvlari (created/edited/status_changed/received) |
| Expenses | Har bir toifa + tip qamrab olinadi |
| Payments | Turli statuslar (paid/partial/overdue/pending) |
| Notifications | Narxsiz + low-stock bildirishnomalar |

---

## 4. Rollar va ruxsatlar

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
| Buyurtma yaratish/tahrirlash | ✅ | ❌ | ✅ |
| Zakaz yaratish | ✅ | ✅ | ✅ |
| **Zakaz status o'zgartirish** | ❌ | ❌ | ✅ **faqat** |
| Zakaz tasdiqlash / qabul qilish | ❌ | ❌ | ✅ **faqat** |
| Hisobotlar | ❌ | ✅ | ✅ |

> Operator uchun `purchase_price` va `selling_price` API javobida umuman **yo'q**
> (`ProductViewSet.get_serializer_class()` → `ProductOperatorSerializer`).

---

## 5. Buyurtma → Zakaz oqimi

**Bu loyihaning asosiy biznes-jarayoni. Ikki etap:**

```
┌────────────────── 1-ETAP: BUYURTMA OLISH ──────────────────┐
│ POST /orders/                                              │
│  • contract_number (shartnoma raqami) — MAJBURIY           │
│  • contract_date — yuborilmasa bugungi kun (Tashkent)      │
│  • prepaid_amount — oldindan to'lov (pul, qanchadir qism)  │
│  • Ombordagi mavjud qoldiqdan FIFO bron ajratiladi         │
│  • balance_due = total − prepaid_amount                    │
│  • PUL KASSAGA TUSHADI: bitta amalda kassada to'lov yozuvi │
│    ochiladi (jami summa + to'langan + status avtomatik)    │
└────────────────────────────┬───────────────────────────────┘
                             │ yetishmagan (backorder) miqdor bo'lsa
                             ▼ AVTOMATIK
┌────────────────── 2-ETAP: ZAKAZ (procurement) ─────────────┐
│ Zakaz avtomatik ochiladi:                                  │
│  • order (manba buyurtma) bog'lanadi                       │
│  • contract_number/contract_date buyurtmadan MEROS oladi   │
│    → yetishmagan mahsulot QAYSI shartnoma asosida zakaz    │
│      qilingani har doim aniq (asos zanjiri)                │
│  • Zakaz /orders/zakaz/ ro'yxatida ko'rinadi               │
│                                                            │
│ Status oqimi (FAQAT Manager):                              │
│   new → confirmed → ordered → received                     │
│                                                            │
│ ⚠ HAR BIR holat o'zgarishida ASOS MAJBURIY!                │
│ ⚠ confirmed / ordered / received — SHARTNOMA MAJBURIY!     │
│                                                            │
│ TASDIQLASH (confirmed):                                    │
│  • contract_number kiritilmaguncha tasdiqlab BO'LMAYDI     │
│  • asos MAJBURIY (aynan shu o'tish uchun)                  │
│  • contract_date bo'sh bo'lsa → avtomatik BUGUN (Tashkent) │
│  • buyurtmadan kelgan (eski kungi) shartnoma → o'sha kun   │
│    SAQLANADI                                               │
│  • confirmed_at — aniq sana/vaqt avtomatik yoziladi        │
│                                                            │
│ YUBORILDI (ordered):                                       │
│  • shartnoma raqami MAJBURIY (tasdiqdagi meros yoki yangi) │
│  • asos MAJBURIY                                           │
│                                                            │
│ QABUL QILISH (received):                                   │
│  • shartnoma + asos + faktura — UCHALASI MAJBURIY          │
│  • received_qty omborga qo'shiladi                         │
│  • pending/partial buyurtmalarga avtomatik bron ajratiladi │
│                                                            │
│ BEKOR QILISH (cancelled): asos MAJBURIY                    │
│                                                            │
│ HAR BIR holat → MAHSULOT SHARTNOMALARI REESTRIGA avtomatik │
│ yoziladi (davlat/mijozlar oldida asos — hech narsa         │
│ yo'qolmaydi)                                               │
└────────────────────────────────────────────────────────────┘
```

### Buyurtmani tahrirlash (edit)

Buyurtmani **bir necha bor** tahrirlash mumkin (bu zakaz bilan bog'liq emas):

- Har tahrirda **`asos`** (tahrir sababi) — MAJBURIY.
- Har tahrir **shartnoma raqami + asos + aniq sana/vaqt** bilan tarixga
  (`OrderHistory`) yoziladi — "qo'limda hammasi asosli" printsipi.
- Miqdor o'zgartirilsa bron avtomatik qayta moslanadi.
- `fulfilled` / `cancelled` buyurtmani tahrirlab bo'lmaydi.

### Shartnoma sanasi qoidasi

| Holat | Sana |
|-------|------|
| 1-etap: buyurtma bugun olindi | Shartnoma sanasi = o'sha (bugungi) kun |
| 2-etap: zakaz buyurtmadan meros oldi | Buyurtmadagi shartnomaning **o'sha kuni saqlanadi** |
| Zakaz tasdiqlashda yangi shartnoma kiritildi | Sana avtomatik **bugun** (Tashkent) |

---

## 6. Modullar va API

**Bazaviy URL:** `/api/v1/`

### 6.1 Auth

| Method | URL | Tavsif |
|--------|-----|--------|
| POST | `/auth/login/` | Username + parol → JWT + `user` (role, can_view_clients) |
| POST | `/auth/token/refresh/` | Refresh → yangi access |

> Login paytida Management userga narxsiz mahsulotlar bo'yicha bildirishnomalar avtomatik yaratiladi.

---

### 6.2 Warehouse

#### Product
| Method | URL | Tavsif |
|--------|-----|--------|
| GET/POST | `/warehouse/products/` | Ro'yxat / yangi |
| GET/PATCH/DELETE | `/warehouse/products/{id}/` | Bitta / tahrirlash |

| Field | Tavsif |
|-------|--------|
| `purchase_price` | Kelish narxi (nullable — operator kiritmaydi, ko'rmaydi) |
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

#### Category
`/warehouse/categories/` — MPTT daraxt (`parent → children`).

---

### 6.3 Sales (Sotuv)

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

### 6.4 Orders (Buyurtma / Bron)

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/orders/` | Ro'yxat (filtr: `?status=`, `?product=`, `?client=`, `?contract_number=`) |
| POST | `/orders/` | Yangi buyurtma — **shartnoma majburiy, avto-zakaz** |
| POST | `/orders/bulk/` | Bir vaqtda bir nechta mahsulot |
| GET | `/orders/{id}/` | Bitta (to'liq `history` bilan) |
| PATCH | `/orders/{id}/` | **Tahrirlash — `asos` majburiy, tarixga yoziladi** |
| POST | `/orders/{id}/fulfill/` | Yetkazildi (tarixga yoziladi) |
| POST | `/orders/{id}/cancel/` | Bekor qilish (tarixga yoziladi) |
| POST | `/orders/{id}/create-zakaz/` | Yetishmagan miqdorga qo'lda zakaz (odatda avto) |

**Order fieldlari:**

| Field | Tavsif |
|-------|--------|
| `contract_number` | **Shartnoma (dogovor) raqami — MAJBURIY** |
| `contract_date` | Shartnoma sanasi (default: bugun, Tashkent) |
| `prepaid_amount` | Oldindan to'langan summa (pul, qisman to'lov) |
| `balance_due` | Qolgan to'lov = `total − prepaid_amount` |
| `quantity`, `unit_price`, `total` | Miqdor, birlik narxi, jami |
| `reserved_qty`, `backorder_qty` | Bron qilingan / yetishmagan |
| `has_active_zakaz` | Shu mahsulotga faol zakaz bormi |
| `status` | `pending` / `partial` / `reserved` / `fulfilled` / `cancelled` |
| `asos` | *(faqat yozish)* Tahrir sababi — PATCH da majburiy |
| `history` | *(faqat o'qish)* To'liq audit tarixi |

**Yangi buyurtma namunasi:**
```json
POST /orders/
{
  "client": "<uuid>",
  "product": 12,
  "quantity": 10,
  "unit_price": "3900000",
  "prepaid_amount": "10000000",
  "contract_number": "SH-2026/045",
  "due_date": "2026-08-01"
}
```
→ Omborda 3 ta bo'lsa: `reserved_qty=3`, `backorder_qty=7`, status=`partial`
→ **7 ta uchun avtomatik Zakaz** ochiladi (`SH-2026/045` shartnoma asosida)
→ **Kassada avtomatik to'lov yozuvi**: jami 39 mln, to'langan 10 mln, status=`partial`.

**Tahrirlash namunasi:**
```json
PATCH /orders/{id}/
{
  "quantity": 12,
  "asos": "Mijoz miqdorni oshirdi (tel. orqali kelishildi)"
}
```

**Bulk namunasi:**
```json
POST /orders/bulk/
{
  "client": "<uuid>",
  "due_date": "2026-08-01",
  "contract_number": "SH-2026/045",
  "prepaid_amount": "5000000",
  "items": [
    { "product": 12, "quantity": 4, "unit_price": "3900000" },
    { "product": 7,  "quantity": 2, "unit_price": "1200000" }
  ]
}
```

---

### 6.5 Zakaz (Etkazuvchidan buyurtma)

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/orders/zakaz/` | Ro'yxat (filtr: `?status=`, `?product=`, `?order=`, `?contract_number=`) |
| POST | `/orders/zakaz/` | Yangi zakaz (status=`new`) — odatda avto ochiladi |
| POST | `/orders/zakaz/bulk/` | Bir nechta mahsulot uchun |
| GET | `/orders/zakaz/{id}/` | Bitta (to'liq `history` bilan) |
| PATCH | `/orders/zakaz/{id}/` | Yangilash (status — faqat Manager) |

**Zakaz fieldlari:**

| Field | Tavsif |
|-------|--------|
| `order` | Manba buyurtma (avto-zakazda bog'lanadi) |
| `order_contract` | Manba buyurtmaning shartnoma raqami + sanasi (asos zanjiri) |
| `contract_number` | Shartnoma raqami — **tasdiqlash uchun majburiy** |
| `contract_date` | Shartnoma sanasi (tasdiqlashda avto-bugun / merosda o'sha kun) |
| `confirmed_at` | Tasdiqlangan aniq sana/vaqt (Tashkent) |
| `asos` | **Qabul qilish uchun asos — `received` da majburiy** |
| `faktura` | **Faktura raqami — `received` da majburiy** |
| `quantity`, `received_qty` | Zakaz / qabul qilingan miqdor |
| `supplier`, `expected_date`, `warehouse_location` | Etkazuvchi, kutilgan sana, joy |
| `status` | `new` / `confirmed` / `ordered` / `received` / `cancelled` |
| `history` | *(faqat o'qish)* To'liq audit tarixi |

**Tasdiqlash namunasi (faqat Manager):**
```json
PATCH /orders/zakaz/{id}/
{
  "status": "confirmed",
  "contract_number": "SH-2026/051",
  "asos": "Rahbariyat ko'rib chiqib tasdiqladi"
}
```
→ `contract_date` avtomatik bugungi kun (Tashkent), `confirmed_at` — aniq vaqt.
→ Shartnomasiz yoki asossiz yuborilsa: **400**.

**Yuborildi namunasi (faqat Manager):**
```json
PATCH /orders/zakaz/{id}/
{
  "status": "ordered",
  "asos": "SH-2026/051 shartnoma asosida etkazuvchiga yuborildi"
}
```
→ Shartnoma raqami zakazda bo'lishi SHART (yo'q bo'lsa **400**), asos MAJBURIY.

**Qabul qilish namunasi (faqat Manager):**
```json
PATCH /orders/zakaz/{id}/
{
  "status": "received",
  "received_qty": 20,
  "warehouse_location": "B-2-3",
  "asos": "Qabul dalolatnomasi №77",
  "faktura": "F-2026/555"
}
```
→ `asos` yoki `faktura` bo'lmasa: **400**.
→ Ombor +20, pending buyurtmalar avtomatik bronlanadi.

---

### 6.5.1 Shartnomalar reestri (Product bilan bog'langan)

**Barcha shartnomalar MAHSULOTGA bog'lanadi** — har bir holat va detal uchun
shartnoma raqami + asos avtomatik reestrga yoziladi. Davlat va mijozlar oldida
har bir mahsulot bo'yicha to'liq hujjatli asos doim tayyor turadi.

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/orders/contracts/` | Reestr (filtr: `?product=`, `?contract_number=`, `?source_type=`, `?order=`, `?zakaz=`) |
| GET | `/orders/contracts/{id}/` | Bitta yozuv |
| GET | `/warehouse/products/{id}/contracts/` | **Shu mahsulotning barcha shartnomalari** |

**Reestrga avtomatik yoziladigan holatlar (`source_type`):**

| source_type | Qachon |
|-------------|--------|
| `order_created` | Buyurtma yaratildi (shartnoma bilan) |
| `order_edited` | Buyurtma tahrirlandi (asos bilan) |
| `order_fulfilled` | Buyurtma yetkazildi |
| `order_cancelled` | Buyurtma bekor qilindi |
| `zakaz_created` | Zakaz ochildi (avto/qo'lda, buyurtma shartnomasi meros) |
| `zakaz_confirmed` | Zakaz tasdiqlandi (shartnoma + asos) |
| `zakaz_ordered` | **Zakaz yuborildi (shartnoma + asos)** |
| `zakaz_received` | Zakaz qabul qilindi (shartnoma + asos + faktura) |
| `zakaz_cancelled` | Zakaz bekor qilindi (asos) |

- Yozuvlar **faqat tizim tomonidan** yaratiladi — API orqali o'zgartirib/o'chirib
  bo'lmaydi (audit butunligi); adminda ham readonly
- Har yozuvda: mahsulot, shartnoma raqami/sanasi, asos, faktura, manba
  (order/zakaz), kim, aniq sana/vaqt

---

### 6.6 Cash (Kassa)

| Method | URL | Tavsif |
|--------|-----|--------|
| GET/POST | `/cash/payments/` | To'lovlar |
| GET/PATCH/DELETE | `/cash/payments/{id}/` | Bitta (tranzaksiyalar bilan) |
| POST | `/cash/payments/{id}/pay/` | **Qo'shimcha to'lov (bo'lib to'lash)** |
| GET | `/cash/payments/summary/` | Kassa xulosasi |

- Status: `pending` / `partial` / `paid` / `overdue`
- Komissiya avtomatik 15% (faqat sotuv to'lovlarida; buyurtma to'lovlarida 0)
- **Kechikkan** = `status ∈ (pending, partial, overdue)` AND `due_date < bugun`

**To'lov manbalari (`source`):**

| source | Bog'lanish | Qachon yaratiladi |
|--------|-----------|-------------------|
| `sale` | `sale` FK | Sotuv to'lovi (qo'lda, Accountant) |
| `order` | `order` FK | **Buyurtma berilganda AVTOMATIK** — bitta amalda |

**Buyurtma → Kassa (avtomatik):**
- Narxli (`unit_price` bor) buyurtma yaratilganda kassada darhol yozuv ochiladi:
  `total_amount` = buyurtma jami, `paid_amount` = oldindan to'lov,
  status avtomatik (`pending`/`partial`/`paid`)
- Buyurtma tahrirlanganda (miqdor/narx/oldindan to'lov) kassa yozuvi ham yangilanadi
- Bitta buyurtma = bitta kassa yozuvi (takrorlanmaydi)
- `order_info` maydonida: shartnoma raqami, jami, oldindan to'lov, qoldiq (`balance_due`)
- Filtr: `?order=5` · qidiruv shartnoma raqami bo'yicha ham ishlaydi

`/cash/payments/summary/` da buyurtma to'lovlari alohida ko'rinadi:
`order_payments_count`, `sum_order_total_uzs`, `sum_order_prepaid_uzs`, `sum_order_due_uzs`.

**Bo'lib to'lash (tranzaksiyalar):**

Har bitta pul harakati alohida **tranzaksiya** (`PaymentTransaction`) bo'lib yoziladi —
qisman to'lov qilgan mijoz keyinroq yana to'lasa, kassada tayyor yozuvga qo'shimcha
to'lov qabul qilinadi:

```json
POST /cash/payments/{id}/pay/
{ "amount": "5000000", "comment": "Ikkinchi bo'lib to'lash" }
```

- `paid_amount` yig'ilib boradi, status avtomatik: `pending → partial → paid`
- Qoldiqdan ortiq to'lov RAD etiladi; to'liq to'langaniga qo'shimcha RAD etiladi
- Har tranzaksiyada: summa, **kim qabul qildi** (`received_by`), izoh, aniq sana/vaqt
- Buyurtma to'lovida buyurtmadagi `prepaid_amount` ham avtomatik sinxronlanadi
  (buyurtma tahririda oshirilgan to'lov ham farq sifatida tranzaksiya bo'ladi)
- `paid_amount` PATCH orqali o'zgartirilsa ham farq tranzaksiya bo'lib yoziladi —
  ledger doim `sum(transactions) == paid_amount`
- API javobida `transactions` ro'yxati to'liq qaytadi

---

### 6.7 Expenses (Rasxod)

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/expenses/expense-types/` | Toifalar (read-only) |
| GET/POST | `/expenses/expense-subtypes/` | Tiplar |
| GET/POST | `/expenses/expenses/` | Rasxodlar |
| GET | `/expenses/expenses/summary/` | Statistika |

- Filtr: `?expense_type=1` · `?sub_type=5` · `?currency=UZS` · `?date_from=...&date_to=...`
- `responsible` (Mas'ul) — rasxodni **qo'shgan foydalanuvchiga** avtomatik bog'lanadi (read-only)
- "Boshqa" toifasida `comment` majburiy

---

### 6.8 Clients (Mijozlar)

| Method | URL | Tavsif |
|--------|-----|--------|
| GET/POST | `/clients/` | Ro'yxat / yangi |
| GET/PATCH/DELETE | `/clients/{id}/` | Bitta |

- `id` — UUID
- `full_name`, `inn`, `phone` — bazada **Fernet** shifrlangan, API javobida ochiq matn
- Faqat `can_view_clients=true` operator ko'radi

---

### 6.9 Notifications (Bildirishnoma)

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

### 6.10 Reports (Hisobot)

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/reports/summary/` | Umumiy moliyaviy xulosa |
| GET | `/reports/warehouse/` | Ombor hisoboti |
| GET | `/reports/cash/` | Kassa hisoboti |
| GET | `/reports/expenses/` | Rasxod hisoboti |
| GET | `/reports/top-products/` | Eng ko'p sotilgan mahsulotlar |
| GET | `/reports/excel/sales/` | Excel: sotuvlar |
| GET | `/reports/excel/stock/` | Excel: ombor |
| GET | `/reports/excel/expenses/` | Excel: rasxod |
| GET | `/reports/excel/payments/` | Excel: kassa |

Hammasi `?date_from` / `?date_to` qabul qiladi.

---

## 7. Audit / Tarix tizimi

**Printsip: har bir amal — shartnoma raqami + asos + aniq sana/vaqt bilan.
Hech narsa asossiz o'zgarmaydi, hamma narsa qo'lda (hujjatda) qoladi.**

### OrderHistory (`orders_order_history`)

Har bir buyurtma amali avtomatik yoziladi:

| action | Qachon |
|--------|--------|
| `created` | Buyurtma yaratildi (shartnoma raqami bilan) |
| `edited` | Har bir tahrir (**asos majburiy**, o'zgargan maydonlar JSON) |
| `fulfilled` | Yetkazildi |
| `cancelled` | Bekor qilindi |

Yozuvda: `contract_number`, `asos`, `changes` (eski→yangi JSON), `changed_by`,
`created_at` (aniq sana/vaqt, Tashkent).

### ZakazHistory (`orders_zakaz_history`)

| action | Qachon |
|--------|--------|
| `created` | Zakaz yaratildi (avto yoki qo'lda) |
| `status_changed` | Har status o'zgarishi (old→new) |
| `edited` | Oddiy tahrir |
| `received` | Qabul qilindi (**asos + faktura bilan**) |

Yozuvda: `old_status`, `new_status`, `contract_number`, `contract_date`,
`asos`, `faktura`, `changes`, `changed_by`, `created_at`.

Tarix API javobida `history` maydonida qaytadi va admin panelda inline ko'rinadi.

---

## 8. Muhim biznes-logika

### To'liq real stsenariy

```
Mijoz 10 ta so'raydi, omborda 3 ta bor. Shartnoma SH-2026/045, 10 mln oldindan to'lov.
  → POST /orders/ { contract_number:"SH-2026/045", prepaid_amount:"10000000", ... }
  → reserved_qty=3, backorder_qty=7, status="partial", balance_due hisoblanadi
  → AVTOMATIK: Zakaz #N ochiladi (7 dona, SH-2026/045 asosida) → Zakazlar ro'yxatida
  → AVTOMATIK: kassada to'lov yozuvi (jami / to'langan 10 mln / status) → /cash/payments/

Manager zakazni boshqaradi:
  → PATCH /orders/zakaz/N/ { status:"confirmed" }        # shartnoma bor — o'tadi
    (shartnoma bo'lmasa: 400 — kiritilmaguncha tasdiqlanmaydi;
     sana avto-bugun / buyurtmadan kelganda o'sha kun saqlanadi)
  → PATCH /orders/zakaz/N/ { status:"ordered" }

Tovar keldi:
  → PATCH /orders/zakaz/N/ { status:"received", received_qty:20,
                             warehouse_location:"B-2-3",
                             asos:"Qabul dalolatnomasi №77", faktura:"F-2026/555" }
  → ombor +20, buyurtma avtomatik to'liq bronlanadi → status="reserved"

Buyurtma o'zgardi (mijoz 12 ta so'radi):
  → PATCH /orders/{id}/ { quantity:12, asos:"Mijoz miqdorni oshirdi" }
  → bron qayta moslanadi, tahrir tarixga tushadi (bu zakazga ta'sir qilmaydi)

Topshirish:
  → POST /orders/{id}/fulfill/ → ombordan ayrildi, status="fulfilled", tarixga yozildi
```

### FIFO
Sotuv va bron ombordagi eng eski Stock yozuvidan (id bo'yicha) boshlab ayiradi.

### available_quantity himoyasi
Sotuv faqat `available_quantity` (bron qilinmagan qoldiq) dan amalga oshadi —
bron qilingan mahsulotni boshqa mijozga sotib bo'lmaydi.

### Takroriy zakaz himoyasi
Mahsulotga faol (`new`/`confirmed`/`ordered`) zakaz bo'lsa — yangi zakaz
ochilmaydi (`has_active_zakaz`), avto-zakaz ham takrorlanmaydi.

### Avtomatik bron taqsimoti
Yangi qoldiq kelganda (zakaz qabul / bekor / fulfill) pending va partial
buyurtmalarga `due_date` tartibida (eng yaqin deadline birinchi) bron ajratiladi.

---

## 9. Migratsiya va deploy

```bash
git pull origin main
python manage.py makemigrations
python manage.py migrate
python manage.py seed --clear     # ixtiyoriy — test uchun
# service restart (gunicorn/uwsgi)
```

**Asosiy jadvallar:** `warehouse_product`, `warehouse_stock`, `sales_sale`,
`orders_order`, `orders_zakaz`, `orders_order_history`, `orders_zakaz_history`,
`cash_payment`, `expenses_expense`, `clients_client`, `notifications_notification`.

**Oxirgi yangilanish (shartnoma + audit) qo'shgan narsalar:**

| Jadval | Yangi maydonlar |
|--------|-----------------|
| `orders_order` | `contract_number`, `contract_date`, `prepaid_amount` |
| `orders_zakaz` | `order` (FK), `contract_number`, `contract_date`, `confirmed_at`, `asos`, `faktura` |
| `orders_order_history` | **yangi jadval** — buyurtma auditi |
| `orders_zakaz_history` | **yangi jadval** — zakaz auditi |
| `cash_payment` | `order` (FK, nullable), `sale` endi nullable — buyurtma to'lovlari kassada |
| `cash_payment_transaction` | **yangi jadval** — har bitta to'lov (bo'lib to'lash) tranzaksiyasi |
| `orders_product_contract` | **yangi jadval** — mahsulot shartnomalari reestri (har holat avtomatik) |

---

## 10. Swagger UI

| URL | Tavsif |
|-----|--------|
| `/` | Swagger UI |
| `/api/redoc/` | ReDoc |
| `/api/schema/` | OpenAPI JSON |
| `/admin/` | Admin panel (Jazzmin) |
