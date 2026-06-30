# Frontend API Dokumentatsiyasi
> **Versiya:** 2026-06-30 | **Backend:** Django REST Framework + JWT  
> Bu fayl frontchiga kerak bo'lgan barcha endpoint, field, permission va logikalarni o'z ichiga oladi.

---

## Mundarija
1. [Autentifikatsiya](#1-autentifikatsiya)
2. [Rollar va ruxsatlar](#2-rollar-va-ruxsatlar)
3. [Mahsulotlar (Warehouse / Products)](#3-mahsulotlar)
4. [Ombor qoldiqlari (Stock)](#4-ombor-qoldiqlari-stock)
5. [Kategoriyalar](#5-kategoriyalar)
6. [Sotuvlar (Sales)](#6-sotuvlar-sales)
7. [Kassa (Cash / Payments)](#7-kassa-cash--payments)
8. [Rasxodlar (Expenses)](#8-rasxodlar-expenses)
9. [Mijozlar (Clients)](#9-mijozlar-clients)
10. [Buyurtmalar / Bron (Orders)](#10-buyurtmalar--bron-orders)
11. [Bildirishnomalar (Notifications)](#11-bildirishnomalar-notifications)
12. [Hisobotlar (Reports)](#12-hisobotlar-reports)
13. [Muhim UI qoidalari](#13-muhim-ui-qoidalari)

---

## 1. Autentifikatsiya

### Base URL
```
https://smart.thesofmebel.uz/api/v1/
```

### Login
```
POST /auth/login/
Body: { "username": "...", "password": "..." }
Response: { "access": "<JWT>", "refresh": "<JWT>", "user": { "id", "username", "role", "can_view_clients" } }
```

### Token yangilash
```
POST /auth/token/refresh/
Body: { "refresh": "<JWT>" }
Response: { "access": "<JWT>" }
```

### Barcha so'rovlarda header
```
Authorization: Bearer <access_token>
```

**Token muddati:** access = 8 soat, refresh = 30 kun.

---

## 2. Rollar va ruxsatlar

| Role | Qiymat | Kim |
|------|--------|-----|
| Operator | `OPERATOR` | Ishchi (mahsulot qo'shadi, sotadi) |
| Accountant | `ACCOUNTANT` | Buxgalter (kassa, rasxod) |
| Management | `MANAGEMENT` | Boshqaruv (narx, hisobot, bron) |
| Superuser | (Django) | Hamma narsa |

### Qaysi role nimani ko'radi/qila oladi

| Funksiya | OPERATOR | ACCOUNTANT | MANAGEMENT |
|----------|----------|------------|------------|
| Mahsulot qo'shish | ✅ | ❌ | ✅ |
| Narx (purchase/selling) ko'rish | ❌ | ✅ | ✅ |
| Narx kiritish | ❌ | ❌ | ✅ |
| min_quantity o'zgartirish | ❌ | ❌ | ✅ |
| Sotuv qo'shish | ✅ | ❌ | ✅ |
| Sotuv summasini ko'rish | ❌ | ✅ | ✅ |
| Kassa | ✅ (faqat ko'rish) | ✅ (CRUD) | ✅ |
| Rasxod | ✅ (faqat ko'rish) | ✅ (CRUD) | ✅ |
| Mijozlar | `can_view_clients` flag ga qarab | ✅ | ✅ |
| Buyurtma/Bron | ✅ | ❌ | ✅ |
| Bildirishnomalar | faqat o'zinikini | faqat o'zinikini | ✅ (management ga keladi) |
| Hisobotlar | ❌ | ✅ | ✅ |

> `can_view_clients` — login javobida keladi. Bu `true` bo'lsa operator ham mijozlar sahifasiga kira oladi.

---

## 3. Mahsulotlar

### Endpointlar
```
GET    /warehouse/products/          — ro'yxat
POST   /warehouse/products/          — yangi mahsulot
GET    /warehouse/products/{id}/     — bitta mahsulot
PUT    /warehouse/products/{id}/     — to'liq yangilash
PATCH  /warehouse/products/{id}/     — qisman yangilash
DELETE /warehouse/products/{id}/     — o'chirish
```

### GET javob — Management (to'liq)
```json
{
  "id": 12,
  "category": 3,
  "category_name": "Printerlar",
  "name": "HP LaserJet",
  "model": "M404n",
  "serial_number": "SN-20240601-001",
  "purchase_price": "1200000.00",
  "selling_price": "1500000.00",
  "source": "Samsung import",
  "min_quantity": 5,
  "quantity_in_stock": 10,
  "reserved_quantity": 7,
  "available_quantity": 3,
  "stock_status": "low_stock",
  "created_at": "2026-06-28T10:00:00Z"
}
```

### GET javob — Operator (narxsiz)
```json
{
  "id": 12,
  "category": 3,
  "category_name": "Printerlar",
  "name": "HP LaserJet",
  "model": "M404n",
  "serial_number": "SN-20240601-001",
  "source": "Samsung import",
  "min_quantity": 5,
  "quantity_in_stock": 10,
  "reserved_quantity": 7,
  "available_quantity": 3,
  "stock_status": "low_stock",
  "created_at": "2026-06-28T10:00:00Z"
}
```
> `purchase_price` va `selling_price` — operator javobida **yo'q**.

### `stock_status` qiymatlari
| Qiymat | Ma'nosi | UI rang |
|--------|---------|---------|
| `in_stock` | Yetarli qoldiq | Yashil |
| `low_stock` | Oz qoldi (≤ min_quantity) | Sariq / To'q sariq |
| `out_of_stock` | Sotish mumkin emas (bron yoki nol) | Qizil |

> **Diqqat:** `stock_status` `available_quantity` ga qaraydi, `quantity_in_stock` ga emas. Bron qilingan mahsulot `out_of_stock` bo'lib ko'rinishi mumkin hatto `quantity_in_stock > 0` bo'lsa ham.

### POST — Mahsulot qo'shish (+ omborda qoldiq)
```json
{
  "category": 3,
  "name": "HP LaserJet",
  "model": "M404n",
  "serial_number": "SN-20240601-001",
  "source": "Samsung import",

  // faqat Management:
  "purchase_price": "1200000",
  "selling_price": "1500000",
  "min_quantity": 5,

  // ixtiyoriy — ombor qoldig'i bir vaqtda yaratiladi:
  "quantity": 20,
  "warehouse_location": "A-1"
}
```
> Agar `quantity` berilsa, avtomatik `Stock` yozuvi yaratiladi. `warehouse_location` majburiy (agar quantity berilsa).

### PATCH — Narx kiritish (Management)
```json
{
  "purchase_price": "1200000",
  "selling_price": "1500000"
}
```
> Narx kiritilganda bildirishnomalar avtomatik yopiladi.

### Filtrlash
```
?category=3                    — kategoriya bo'yicha
?purchase_price__isnull=true   — narxi kiritilmagan mahsulotlar
?selling_price__isnull=true    — sotuv narxi yo'q mahsulotlar
?search=hp                     — qidiruv (name, model, serial_number, source)
?ordering=-created_at          — tartiblash
```

---

## 4. Ombor qoldiqlari (Stock)

### Endpointlar
```
GET    /warehouse/stocks/
POST   /warehouse/stocks/
GET    /warehouse/stocks/{id}/
PUT    /warehouse/stocks/{id}/
PATCH  /warehouse/stocks/{id}/
DELETE /warehouse/stocks/{id}/
```

### GET javob
```json
{
  "id": 5,
  "product": 12,
  "product_name": "HP LaserJet (SN-20240601-001)",
  "product_model": "M404n",
  "quantity": 10,
  "reserved_quantity": 7,
  "warehouse_location": "A-1",
  "min_quantity": 5,
  "stock_status": "low_stock"
}
```

### Filtrlash
```
?product=12                    — mahsulot bo'yicha
?warehouse_location=A-1        — joylashuv bo'yicha
?category=3                    — kategoriya bo'yicha (product__category)
?status=in_stock               — holat bo'yicha (in_stock | low_stock | out_of_stock)
?date_from=2026-06-01          — yaratilgan sana dan
?date_to=2026-06-30            — yaratilgan sana gacha
?search=hp                     — qidiruv
```

> **Ombor jadvali qatorlarini qizil/sariq ajratish uchun** `stock_status` fieldidan foydalaning.

---

## 5. Kategoriyalar

```
GET    /warehouse/categories/     — daraxt ko'rinishida (parent → children)
POST   /warehouse/categories/
GET    /warehouse/categories/{id}/
PUT    /warehouse/categories/{id}/
DELETE /warehouse/categories/{id}/
```

### GET javob (daraxt)
```json
[
  {
    "id": 1,
    "name": "Elektronika",
    "parent": null,
    "children": [
      {
        "id": 3,
        "name": "Printerlar",
        "parent": 1,
        "children": []
      }
    ]
  }
]
```

---

## 6. Sotuvlar (Sales)

### Endpointlar
```
GET    /sales/
POST   /sales/
GET    /sales/{id}/
PUT    /sales/{id}/
PATCH  /sales/{id}/
DELETE /sales/{id}/
```

### GET javob
```json
{
  "id": 45,
  "product": 12,
  "product_name": "HP LaserJet (SN-20240601-001)",
  "client": "550e8400-e29b-41d4-a716-446655440000",
  "client_name": "Aliyev Kompaniyasi",
  "quantity": 3,
  "sold_price": "1500000.00",
  "total_amount": "4500000.00",
  "profit": "900000.00",
  "sold_to": "Aliyev Vohid",
  "destination": "Toshkent",
  "sold_date": "2026-06-30",
  "comment": null,
  "created_at": "2026-06-30T09:00:00Z"
}
```

> **Operator uchun:** `sold_price`, `total_amount`, `profit` — **ko'rsatilmasin** (`sale.viewAmount` ruxsati yo'q). Bu frontend tomonida yashiriladi.

> **`profit`** null bo'lishi mumkin (mahsulot `purchase_price` kiritilmagan bo'lsa).

### POST — Sotuv yaratish
```json
{
  "product": 12,
  "client": "550e8400-e29b-41d4-a716-446655440000",
  "quantity": 3,
  "sold_price": "1500000",
  "sold_to": "Aliyev Vohid",
  "destination": "Toshkent",
  "sold_date": "2026-06-30",
  "comment": null
}
```

> Sotuv yaratilganda ombor qoldig'i **FIFO** tartibida avtomatik kamayadi.  
> Agar `available_quantity < quantity` bo'lsa — **400 xato** qaytariladi (bron qilingan mahsulotni sota olmaysiz).

### Filtrlash
```
?product=12
?sold_date=2026-06-30
?client=<uuid>
?search=aliyev
?ordering=-sold_date
```

---

## 7. Kassa (Cash / Payments)

### Endpointlar
```
GET    /cash/payments/
POST   /cash/payments/
GET    /cash/payments/{id}/
PUT    /cash/payments/{id}/
PATCH  /cash/payments/{id}/
DELETE /cash/payments/{id}/

GET    /cash/payments/summary/   — kassa xulosasi
```

### Payment GET javob
```json
{
  "id": 10,
  "sale": 45,
  "sale_info": {
    "id": 45,
    "product": "HP LaserJet (SN-20240601-001)",
    "quantity": 3,
    "sold_price": "1500000.00",
    "sold_date": "2026-06-30"
  },
  "client": "550e8400-e29b-41d4-a716-446655440000",
  "client_name": "Aliyev Kompaniyasi",
  "total_amount": "4500000.00",
  "commission": "675000.00",
  "paid_amount": "2000000.00",
  "remaining": "2500000.00",
  "currency": "UZS",
  "due_date": "2026-07-15",
  "status": "partial",
  "comment": null,
  "created_at": "2026-06-30T09:00:00Z"
}
```

### Payment status qiymatlari
| Status | Ma'nosi | UI rang |
|--------|---------|---------|
| `pending` | To'lanmagan | Sariq |
| `partial` | Qisman to'langan | To'q sariq |
| `paid` | To'liq to'langan | Yashil |
| `overdue` | Muddati o'tgan | Qizil |

> **Kechikkan to'lovlar** = `status IN (pending, partial, overdue)` AND `due_date < bugun`.  
> `summary` endpoint `total_overdue` fieldida to'g'ri son keladi.

### Summary javob
```json
{
  "total_pending": 5,
  "total_partial": 3,
  "total_paid": 42,
  "total_overdue": 4,
  "sum_paid_uzs": "125000000.00",
  "sum_paid_usd": "1500.00",
  "total_commission_uzs": "18750000.00"
}
```

### PATCH — To'lov yangilash
```json
{ "paid_amount": "3000000", "due_date": "2026-07-20", "comment": "..." }
```

### Filtrlash
```
?status=overdue
?status=pending
?client=<uuid>
?currency=UZS
?due_date=2026-07-15
```

---

## 8. Rasxodlar (Expenses)

### Endpointlar
```
GET    /expenses/expense-types/      — toifalar
GET    /expenses/sub-types/          — turlar
GET    /expenses/expenses/           — rasxodlar ro'yxati
POST   /expenses/expenses/
GET    /expenses/expenses/{id}/
PUT    /expenses/expenses/{id}/
PATCH  /expenses/expenses/{id}/
DELETE /expenses/expenses/{id}/

GET    /expenses/expenses/summary/   — statistika
```

### Expense GET javob
```json
{
  "id": 8,
  "expense_type": 2,
  "expense_type_name": "Transport rasxod",
  "sub_type": 5,
  "sub_type_name": "Transport rasxod → Yuk mashinasi",
  "amount": "850000.00",
  "currency": "UZS",
  "date": "2026-06-30",
  "responsible": 3,
  "responsible_name": "Karimov Sardor",
  "comment": null,
  "attachment": null,
  "created_at": "2026-06-30T10:00:00Z"
}
```

### Filtrlash
```
?expense_type=2
?sub_type=5
?currency=UZS
?responsible=3
?date_from=2026-06-01
?date_to=2026-06-30
?search=transport
?ordering=-date
```

### Summary javob (`GET /expenses/expenses/summary/`)
```json
{
  "total_uzs": "12500000.00",
  "total_usd": "1500.00",
  "by_type": [
    {
      "expense_type": 2,
      "name": "Transport rasxod",
      "total_uzs": "4500000.00",
      "total_usd": "0.00"
    }
  ],
  "count": 42
}
```
> Summary ham `?date_from` / `?date_to` qabul qiladi.

---

## 9. Mijozlar (Clients)

### Endpointlar
```
GET    /clients/
POST   /clients/
GET    /clients/{id}/
PUT    /clients/{id}/
PATCH  /clients/{id}/
DELETE /clients/{id}/
```

> **Diqqat:** `full_name`, `inn`, `phone` — backendda shifrlangan saqlanadi, lekin API javobida **ochiq matn** keladi. Frontchi oddiy matn sifatida ishlatadi.

### GET javob
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "Aliyev Vohid",
  "company_name": "Aliyev Kompaniyasi",
  "inn": "123456789",
  "phone": "+998901234567",
  "email": "aliyev@example.com",
  "address": "Toshkent, Chilonzor 5",
  "comment": null,
  "is_active": true,
  "created_at": "2026-06-01T08:00:00Z"
}
```

> `id` — UUID formatida.

### Filtrlash
```
?is_active=true
?search=aliyev
```

---

## 10. Buyurtmalar / Bron (Orders)

> Bu eng muhim yangi tizim. To'liq o'qing.

### Endpointlar
```
GET    /orders/
POST   /orders/                    — yangi buyurtma + avtomatik bron
GET    /orders/{id}/
PATCH  /orders/{id}/
DELETE /orders/{id}/               — buyurtma o'chiriladi, bron bo'shatiladi

POST   /orders/{id}/fulfill/       — yetkazildi (ombor kamayadi)
POST   /orders/{id}/cancel/        — bekor qilindi (bron bo'shatiladi)
```

### Holat (status) qiymatlari
| Status | Ma'nosi | UI rang |
|--------|---------|---------|
| `pending` | Zakaz — omborda yetarli yo'q, kelishi kutilmoqda | To'q sariq |
| `partial` | Qisman bron — bir qismi bron, qolgani zakaz | Sariq |
| `reserved` | To'liq bron — hamma qoldiqda ajratilgan | Ko'k / Yashil |
| `fulfilled` | Yetkazildi — tugallangan | Yashil (kulrang) |
| `cancelled` | Bekor qilindi | Kulrang |

### POST — Buyurtma yaratish
```json
{
  "client": "550e8400-e29b-41d4-a716-446655440000",
  "product": 12,
  "quantity": 10,
  "due_date": "2026-07-30",
  "comment": "Tezkor kerak"
}
```

### GET javob
```json
{
  "id": 3,
  "client": "550e8400-e29b-41d4-a716-446655440000",
  "client_name": "Aliyev Kompaniyasi",
  "product": 12,
  "product_name": "HP LaserJet (SN-20240601-001)",
  "quantity": 10,
  "reserved_qty": 3,
  "backorder_qty": 7,
  "due_date": "2026-07-30",
  "status": "partial",
  "comment": "Tezkor kerak",
  "created_at": "2026-06-30T11:00:00Z"
}
```

### Field tavsifi
| Field | Ma'nosi |
|-------|---------|
| `quantity` | Jami buyurtma qilingan soni |
| `reserved_qty` | Hozirda omborda ajratilgan (bron) soni |
| `backorder_qty` | Hali omborda yo'q, zakaz soni (`quantity - reserved_qty`) |

### Avtomatik logika (frontchi bilishi kerak)
```
Yangi buyurtma POST qilinganda:
  1. Ombordagi mavjud (bron bo'lmagan) qoldiqdan bron ajratiladi
  2. Yetarli bo'lmasa — qisman bron yoki pending

Yangi kirim kelganida (Stock PATCH/PUT):
  → pending/partial buyurtmalarga avtomatik bron ajratiladi
  → due_date eng yaqin buyurtma birinchi oladi

fulfill() chaqirilganda:
  → reserved_qty qoldiqdan ayiriladi (ombor kamayadi)
  → Boshqa pending orderlarga bo'shatilgan joy bo'lmaydi (fulfilled edi)

cancel() chaqirilganda:
  → Bron bo'shatiladi (reserved_qty → 0)
  → Bo'shatilgan bron boshqa pending buyurtmalarga avtomatik ajratiladi
```

### Operatorda mahsulot "bron" ko'rinishi
Mahsulot ro'yxatida (`/warehouse/products/`) har bir mahsulot uchun:
```
quantity_in_stock: 10   — ombordagi jami
reserved_quantity: 7    — bron qilingan
available_quantity: 3   — sotish mumkin (bron bo'lmagan)
stock_status: "low_stock"
```
> Operator `available_quantity = 0` va `stock_status = "out_of_stock"` bo'lsa bu mahsulotni **sota olmaydi**. Sotuv yaratmoqchi bo'lsa 400 xato qaytariladi.

### Filtrlash
```
?status=pending             — zakaz (ombor kutilmoqda)
?status=reserved            — to'liq bron
?product=12
?client=<uuid>
?search=hp
?ordering=due_date          — deadline bo'yicha tartiblash
```

### UI tavsiyalari
- Buyurtmalar sahifasida `status` bo'yicha tab yoki filter
- `backorder_qty > 0` bo'lsa qizil badge ko'rsating
- `due_date` yaqin (< 3 kun) bo'lsa sariq ogohlantirish
- "Yetkazildi" tugmasi faqat `status = reserved` yoki `partial` bo'lganda active

---

## 11. Bildirishnomalar (Notifications)

### Endpointlar
```
GET  /notifications/               — mening bildirishnomalarim
GET  /notifications/?is_read=false — o'qilmaganlar

POST /notifications/{id}/mark_read/      — bitta o'qilgan deb belgilash
POST /notifications/mark_all_read/       — hammasi o'qilgan
```

### GET javob
```json
{
  "id": 15,
  "product": 12,
  "title": "Summasi kiritilmagan!",
  "message": "\"HP LaserJet\" (SN-001) mahsuloti uchun summasini kiritmagansiz!",
  "is_read": false,
  "created_at": "2026-06-30T09:00:00Z"
}
```

### Bildirishnoma turlari
| title | Sababi | Kimga |
|-------|--------|-------|
| `"Summasi kiritilmagan!"` | Operator narxsiz mahsulot qo'shdi | Management |
| `"Qoldiq kam!"` | Mahsulot qoldig'i `min_quantity` dan tushdi | Management |

### Avtomatik logika
- **Login bo'lganda:** management user uchun narxsiz barcha mahsulotlar bo'yicha o'qilmagan bildirishnomalar yaratiladi (takrorlanmaydi)
- **Narx kiritilganda:** tegishli bildirishnomalar avtomatik `is_read=true` bo'ladi
- **Qoldiq ko'tarilganda:** low_stock bildirishnomalar avtomatik yopiladi

### UI — Bell icon
```
Unread count: GET /notifications/?is_read=false → count
Rang: is_read=false bo'lgan bor ekan qizil nuqta
```

---

## 12. Hisobotlar (Reports)

### Ombor hisoboti
```
GET /reports/warehouse/?date_from=2026-06-01&date_to=2026-06-30
```
```json
{
  "total_product_types": 150,
  "total_quantity": 1240,
  "by_category": [
    { "product__category__name": "Printerlar", "total_qty": 450 }
  ],
  "low_stock": [
    {
      "product__id": 12,
      "product__name": "HP LaserJet",
      "product__serial_number": "SN-001",
      "quantity": 3,
      "product__min_quantity": 5
    }
  ],
  "out_of_stock": [...]
}
```

### Kassa hisoboti
```
GET /reports/cash/?date_from=2026-06-01&date_to=2026-06-30
```
```json
{
  "total_pending": 5,
  "total_partial": 3,
  "total_paid": 42,
  "total_overdue": 4,
  "sum_paid_uzs": "125000000.00",
  "sum_paid_usd": "1500.00",
  "commission_total": "18750000.00"
}
```

### Rasxod hisoboti
```
GET /reports/expenses/?date_from=2026-06-01&date_to=2026-06-30
```
```json
{
  "total_uzs": "12500000.00",
  "total_usd": "1500.00",
  "by_type": [...],
  "count": 42
}
```

### Eng ko'p sotilgan mahsulotlar (Top Products)
```
GET /reports/top-products/?date_from=2026-06-01&date_to=2026-06-30&limit=10
```
```json
[
  {
    "product": 12,
    "name": "HP LaserJet",
    "serial_number": "SN-001",
    "sold_qty": 134,
    "current_stock": 3,
    "min_quantity": 5,
    "is_low": true
  }
]
```
> `is_low: true` bo'lganda qator **qizil** ko'rsatilsin.

### Umumiy moliyaviy xulosa
```
GET /reports/summary/
```
```json
{
  "sales_revenue_total": "450000000.00",
  "expenses_uzs": "12500000.00",
  "expenses_usd": "1500.00",
  "kassa_collected_uzs": "125000000.00",
  "commission_earned": "18750000.00",
  "overdue_payments_count": 4,
  "report_date": "2026-06-30"
}
```

### Excel yuklab olish
```
GET /reports/excel/sales/?date_from=...&date_to=...
GET /reports/excel/stock/
GET /reports/excel/expenses/?date_from=...&date_to=...
GET /reports/excel/payments/
```
> Javob `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` — to'g'ridan-to'g'ri fayl yuklanadi.

---

## 13. Muhim UI qoidalari

### Mahsulot ro'yxati — rang logikasi
```
stock_status == "out_of_stock"  → qizil qator yoki badge
stock_status == "low_stock"     → sariq / to'q sariq qator
purchase_price == null          → management uchun ajratilgan (narx kiritilmagan badge)
```

### Operator mahsulot formasida
- `purchase_price` va `selling_price` inputlari **ko'rsatilmasin**
- `min_quantity` inputi **ko'rsatilmasin** (faqat management)
- `quantity` va `warehouse_location` — yangi mahsulot qo'shganda ko'rsatilsin

### Management mahsulot formasida
- `purchase_price`, `selling_price`, `min_quantity` — ko'rsatilsin va tahrirlansin

### Sotuv formasida
- Mahsulot tanlanganda `available_quantity` ko'rsatilsin
- `available_quantity = 0` bo'lsa "Qoldiq yo'q (bron qilingan)" deb ogohlantiring
- Operator uchun `sold_price` inputi ko'rsatilmasin

### Buyurtma formasida
- `quantity` kiritilganda tanlangan mahsulotning `available_quantity` ni ko'rsating
- `quantity > available_quantity` bo'lsa "Zakaz: X ta kelishini kutasiz" deb ko'rsating
- Buyurtma yaratilgandan keyin javobdagi `reserved_qty` va `backorder_qty` ni ko'rsating

### Bildirishnoma bell icon
```
O'qilmagan soni: /notifications/?is_read=false count
Login bo'lganda refresh qilish
Yangi narx kiritilganda bell ni refresh qilish
```

---

## Xato holatlari

| HTTP kod | Ma'nosi |
|----------|---------|
| `400` | Noto'g'ri ma'lumot (ValidationError) — `detail` yoki field xatolar |
| `401` | Token yo'q yoki muddati o'tgan |
| `403` | Ruxsat yo'q (role mos kelmaydi) |
| `404` | Topilmadi |
| `500` | Server xatosi |

### 400 xato misoli (sotuv)
```json
{
  "quantity": [
    "\"HP LaserJet\" uchun sotish mumkin bo'lgan qoldiq yetarli emas. Jami: 10, bron: 7, mavjud: 3, so'ralgan: 5."
  ]
}
```

---

## Swagger UI

Barcha endpointlarni interaktiv sinash:
```
https://smart.thesofmebel.uz/
```

---

*Oxirgi yangilanish: 2026-06-30 | Backend: krv006*
