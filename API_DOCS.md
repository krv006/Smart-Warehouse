# Smart Warehouse ERP — API Dokumentatsiya

> **Base URL:** `http://localhost:8000`  
> **Swagger UI:** `http://localhost:8000/`  
> **ReDoc:** `http://localhost:8000/api/redoc/`  
> **Auth:** `Bearer <access_token>` — barcha endpointlar uchun (Login va Register bundan mustasno)

---

## Rollar va Ruxsatlar

| Rol | Kim | Huquq |
|-----|-----|-------|
| `OPERATOR` | Ishchi | Ma'lumot kiritish (mahsulot, sotuv, qoldiq) |
| `ACCOUNTANT` | Buxgalter | Rasxod, to'lov boshqaruvi |
| `MANAGEMENT` | Boshqaruvchi | Hammani ko'rish + narxlar + hisobotlar |
| `SUPERUSER` | Admin | Cheksiz huquq |
| `can_view_clients` | Maxsus flag | Faqat 2 ta foydalanuvchi — Mijozlar moduliga kirish |

---

## 1. Auth — `/api/v1/auth/`

### `POST /api/v1/auth/login/`
JWT token olish.

**Ruxsat:** Hamma (AllowAny)

**Request:**
```json
{
  "username": "admin",
  "password": "1234"
}
```

**Response `200`:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

---

### `POST /api/v1/auth/token/refresh/`
Access token yangilash.

**Ruxsat:** Hamma (AllowAny)

**Request:**
```json
{ "refresh": "eyJ..." }
```

**Response `200`:**
```json
{ "access": "eyJ..." }
```

---

### `POST /api/v1/auth/register/`
Yangi foydalanuvchi yaratish.

**Ruxsat:** `MANAGEMENT` only

**Request:**
```json
{
  "username": "operator1",
  "password": "Secure123!",
  "first_name": "Ali",
  "last_name": "Valiyev",
  "role": "OPERATOR",
  "phone": "+998901234567",
  "telegram_id": "123456789"
}
```

**Response `201`:**
```json
{
  "id": 5,
  "username": "operator1",
  "role": "OPERATOR",
  "phone": "+998901234567"
}
```

---

### `GET /api/v1/auth/users/`
Barcha foydalanuvchilar.

**Ruxsat:** `MANAGEMENT` only  
**Filtr:** `?role=OPERATOR`, `?is_active=true`  
**Qidiruv:** `?search=Ali`

---

### `GET /api/v1/auth/users/{id}/`
### `PATCH /api/v1/auth/users/{id}/`
### `DELETE /api/v1/auth/users/{id}/`
Foydalanuvchi boshqaruvi — **`MANAGEMENT` only**

---

## 2. Warehouse (Ombor) — `/api/v1/warehouse/`

### Kategoriyalar

#### `GET /api/v1/warehouse/categories/`
Daraxt strukturali kategoriyalar ro'yxati.

**Ruxsat:** Barcha autentifikatsiya qilinganlar (o'qish)  
**Response:**
```json
[
  {
    "id": 1,
    "name": "Server",
    "children": [
      {
        "id": 2,
        "name": "DDR4",
        "children": [
          { "id": 3, "name": "32GB", "children": [] }
        ]
      }
    ]
  }
]
```

#### `POST /api/v1/warehouse/categories/`
**Ruxsat:** `OPERATOR`

**Request:**
```json
{ "name": "Monitor", "parent": null }
```

#### `GET /api/v1/warehouse/categories/{id}/`
#### `PATCH /api/v1/warehouse/categories/{id}/`
#### `DELETE /api/v1/warehouse/categories/{id}/`
**Ruxsat:** `OPERATOR`

---

### Mahsulotlar

#### `GET /api/v1/warehouse/products/`
**Ruxsat:** Barcha autentifikatsiya qilinganlar  
**Filtr:** `?category=1`  
**Qidiruv:** `?search=server` (name, model, serial_number, source bo'yicha)  
**Tartiblash:** `?ordering=name`, `?ordering=-purchase_price`, `?ordering=-created_at`

> ⚠️ **`purchase_price` (sotib olish narxi) faqat `MANAGEMENT` rolida ko'rinadi.** Operator serialiyzeri bu maydonni yashiradi.

**Response (Management):**
```json
{
  "id": 1,
  "category": 2,
  "name": "HP ProLiant DL380",
  "model": "Gen10",
  "serial_number": "SN-001",
  "purchase_price": "12500000.00",
  "source": "Xitoy, Guangzhou",
  "quantity_in_stock": 5,
  "created_at": "2024-01-15T10:00:00Z"
}
```

**Response (Operator) — `purchase_price` yo'q:**
```json
{
  "id": 1,
  "name": "HP ProLiant DL380",
  "model": "Gen10",
  "serial_number": "SN-001",
  "source": "Xitoy, Guangzhou",
  "quantity_in_stock": 5
}
```

#### `POST /api/v1/warehouse/products/`
**Ruxsat:** `OPERATOR`

**Request:**
```json
{
  "category": 2,
  "name": "HP ProLiant DL380",
  "model": "Gen10",
  "serial_number": "SN-001",
  "purchase_price": "12500000.00",
  "source": "Xitoy, Guangzhou"
}
```

#### `GET /api/v1/warehouse/products/{id}/`
#### `PUT /api/v1/warehouse/products/{id}/`
#### `PATCH /api/v1/warehouse/products/{id}/`
#### `DELETE /api/v1/warehouse/products/{id}/`
**Ruxsat:** `OPERATOR`

---

### Ombor qoldiqlari (Stock)

#### `GET /api/v1/warehouse/stocks/`
**Ruxsat:** Barcha autentifikatsiya qilinganlar  
**Filtr:** `?product=1`, `?warehouse_location=A-1`

**Response:**
```json
{
  "id": 1,
  "product": 1,
  "product_name": "HP ProLiant DL380",
  "quantity": 5,
  "warehouse_location": "A-1-3"
}
```

#### `POST /api/v1/warehouse/stocks/`
**Ruxsat:** `OPERATOR`

```json
{
  "product": 1,
  "quantity": 10,
  "warehouse_location": "A-1-3"
}
```

#### `GET /api/v1/warehouse/stocks/{id}/`
#### `PATCH /api/v1/warehouse/stocks/{id}/`
#### `DELETE /api/v1/warehouse/stocks/{id}/`
**Ruxsat:** `OPERATOR`

---

## 3. Sales (Sotuv) — `/api/v1/sales/`

### `GET /api/v1/sales/`
**Ruxsat:** Barcha autentifikatsiya qilinganlar  
**Filtr:** `?product=1`, `?sold_date=2024-06-01`  
**Qidiruv:** `?search=toshkent` (product name, sold_to, destination)  
**Tartiblash:** `?ordering=-sold_date`, `?ordering=sold_price`

**Response:**
```json
{
  "id": 1,
  "product": 1,
  "product_name": "HP ProLiant DL380",
  "quantity": 2,
  "sold_price": "15000000.00",
  "total_amount": "30000000.00",
  "sold_to": "Bekhzod Ergashev",
  "destination": "Toshkent, Chilonzor",
  "sold_date": "2024-06-10",
  "comment": null,
  "created_at": "2024-06-10T14:00:00Z"
}
```

### `POST /api/v1/sales/`
**Ruxsat:** `OPERATOR`  
> **FIFO:** Sotuv yaratilganda ombor qoldig'i avtomatik FIFO tartibida kamayadi.

**Request:**
```json
{
  "product": 1,
  "quantity": 2,
  "sold_price": "15000000.00",
  "sold_to": "Bekhzod Ergashev",
  "destination": "Toshkent, Chilonzor",
  "sold_date": "2024-06-10",
  "comment": "Naqd to'lov"
}
```

### `GET /api/v1/sales/{id}/`
### `PATCH /api/v1/sales/{id}/`
### `DELETE /api/v1/sales/{id}/`
**Ruxsat:** `OPERATOR`

---

## 4. Expenses (Rasxodlar) — `/api/v1/expenses/`

### Rasxod toifalari

#### `GET /api/v1/expenses/types/`
**Ruxsat:** Barcha autentifikatsiya qilinganlar

**Mavjud kodlar:**

| Kod | Nomi |
|-----|------|
| `office` | Ofis rasxod |
| `import` | Import rasxod |
| `declaration` | Deklaratsiya rasxod |
| `certificate` | Sertifikat rasxod |
| `transport` | Transport rasxod |
| `business_trip` | Komandirovka rasxod |
| `salary` | Oylik (salary) rasxod |
| `other` | ITG / boshqa rasxod ⚠️ *comment majburiy* |

**Response:**
```json
[
  {
    "id": 1,
    "code": "transport",
    "name": "Transport rasxod",
    "sub_types": [
      { "id": 1, "expense_type": 1, "name": "Yoqilg'i" },
      { "id": 2, "expense_type": 1, "name": "Ta'mirlash" }
    ]
  }
]
```

#### `POST /api/v1/expenses/types/`
**Ruxsat:** Barcha autentifikatsiya qilinganlar

#### `GET/PATCH/DELETE /api/v1/expenses/types/{id}/`

---

### Rasxod turlari (SubType)

#### `GET /api/v1/expenses/subtypes/`
**Ruxsat:** Barcha autentifikatsiya qilinganlar  
**Filtr:** `?expense_type=1`

#### `POST /api/v1/expenses/subtypes/`
**Ruxsat:** `ACCOUNTANT`

```json
{ "expense_type": 1, "name": "Yoqilg'i" }
```

---

### Rasxodlar

#### `GET /api/v1/expenses/`
**Ruxsat:** Barcha autentifikatsiya qilinganlar  
**Filtr:** `?expense_type=1`, `?currency=UZS`, `?date=2024-06-01`, `?responsible=3`  
**Qidiruv:** `?search=transport`  
**Tartiblash:** `?ordering=-date`, `?ordering=amount`

**Response:**
```json
{
  "id": 1,
  "expense_type": 1,
  "expense_type_name": "Transport rasxod",
  "sub_type": 1,
  "sub_type_name": "Transport rasxod → Yoqilg'i",
  "amount": "450000.00",
  "currency": "UZS",
  "date": "2024-06-10",
  "responsible": 2,
  "responsible_name": "Jamshid Karimov",
  "comment": null,
  "attachment": null,
  "created_at": "2024-06-10T09:00:00Z"
}
```

#### `POST /api/v1/expenses/`
**Ruxsat:** `ACCOUNTANT`

> ⚠️ `expense_type.code == "other"` bo'lsa **`comment` majburiy!**

```json
{
  "expense_type": 1,
  "sub_type": 1,
  "amount": "450000.00",
  "currency": "UZS",
  "date": "2024-06-10",
  "responsible": 2,
  "comment": null,
  "attachment": null
}
```

**Valyuta:** `UZS` yoki `USD`

#### `GET/PUT/PATCH/DELETE /api/v1/expenses/{id}/`
**Ruxsat:** `ACCOUNTANT`

---

## 5. Cash / Kassa — `/api/v1/cash/`

### `GET /api/v1/cash/`
**Ruxsat:** Barcha autentifikatsiya qilinganlar  
**Filtr:** `?status=pending`, `?status=overdue`, `?status=partial`, `?status=paid`, `?client=1`, `?currency=UZS`  
**Qidiruv:** `?search=laptop`  
**Tartiblash:** `?ordering=due_date`, `?ordering=-total_amount`

**To'lov statuslari:**

| Status | Ma'no |
|--------|-------|
| `pending` | Kutilmoqda |
| `partial` | Qisman to'landi |
| `paid` | To'liq to'landi |
| `overdue` | Muddati o'tdi |

**Response:**
```json
{
  "id": 1,
  "sale": 1,
  "sale_info": {
    "id": 1,
    "product": "HP ProLiant DL380 (SN-001)",
    "quantity": 2,
    "sold_price": "15000000.00",
    "sold_date": "2024-06-10"
  },
  "client": 1,
  "client_name": "Texnopark LLC",
  "total_amount": "30000000.00",
  "commission": "4500000.00",
  "paid_amount": "10000000.00",
  "remaining": "20000000.00",
  "currency": "UZS",
  "due_date": "2024-07-10",
  "status": "partial",
  "comment": null,
  "created_at": "2024-06-10T14:00:00Z"
}
```

> **Eslatma:** `total_amount` va `commission` (15%) sotuv yaratilganda **avtomatik** hisoblanadi. Qo'lda o'zgartirib bo'lmaydi.

### `POST /api/v1/cash/`
**Ruxsat:** `ACCOUNTANT`

```json
{
  "sale": 1,
  "client": 1,
  "paid_amount": "10000000.00",
  "currency": "UZS",
  "due_date": "2024-07-10",
  "comment": "Birinchi bo'lib to'lov"
}
```

### `PATCH /api/v1/cash/{id}/`
To'lov yangilash (faqat quyidagi maydonlar o'zgartiriladi):

```json
{
  "paid_amount": "25000000.00",
  "currency": "UZS",
  "due_date": "2024-07-15",
  "comment": "Ikkinchi qism to'landi"
}
```

### `DELETE /api/v1/cash/{id}/`
**Ruxsat:** `ACCOUNTANT` yoki `MANAGEMENT`

---

### `GET /api/v1/cash/summary/`
Kassa umumiy xulosasi.

**Ruxsat:** `ACCOUNTANT` yoki `MANAGEMENT`

**Response:**
```json
{
  "total_pending": 12,
  "total_partial": 5,
  "total_paid": 38,
  "total_overdue": 3,
  "sum_paid_uzs": "450000000.00",
  "sum_paid_usd": "12500.00",
  "total_commission_uzs": "67500000.00"
}
```

---

## 6. Clients (Mijozlar) — `/api/v1/clients/`

> 🔒 **Bu modul faqat `can_view_clients = True` bo'lgan foydalanuvchilar uchun.**  
> Admin panelda foydalanuvchi profili → `can_view_clients` belgilash.  
> `full_name`, `inn`, `phone` maydonlari **Fernet shifrlash** bilan saqlanadi.

### `GET /api/v1/clients/`
**Ruxsat:** `can_view_clients = True`  
**Filtr:** `?is_active=true`  
**Qidiruv:** `?search=texnopark` (company_name, email bo'yicha)

**Response (list — qisqartirilgan):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "full_name": "Sardor Umarov",
    "company_name": "Texnopark LLC",
    "is_active": true
  }
]
```

### `GET /api/v1/clients/{id}/`
**Response (to'liq):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "Sardor Umarov",
  "company_name": "Texnopark LLC",
  "inn": "123456789",
  "phone": "+998901234567",
  "email": "info@texnopark.uz",
  "address": "Toshkent, Mirzo Ulug'bek tumani",
  "comment": null,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### `POST /api/v1/clients/`
```json
{
  "full_name": "Sardor Umarov",
  "company_name": "Texnopark LLC",
  "inn": "123456789",
  "phone": "+998901234567",
  "email": "info@texnopark.uz",
  "address": "Toshkent, Mirzo Ulug'bek tumani"
}
```

> UUID primary key avtomatik generatsiya qilinadi.

### `PATCH /api/v1/clients/{id}/`
### `DELETE /api/v1/clients/{id}/`
**Ruxsat:** `can_view_clients = True`

---

## 7. Reports (Hisobotlar) — `/api/v1/reports/`

### Excel Yuklab Olish

#### `GET /api/v1/reports/excel/sales/`
Sotuvlar Excel fayli.

**Ruxsat:** Barcha autentifikatsiya qilinganlar  
**Filtr:** `?date_from=2024-01-01&date_to=2024-12-31`  
**Response:** `sotuvlar_YYYY-MM-DD.xlsx` fayl

**Ustunlar:** №, Mahsulot, Kategoriya, Miqdor, Sotuv narxi, Jami summa, Qayerga ketdi, Mijoz, Sana, Izoh

---

#### `GET /api/v1/reports/excel/stock/`
Ombor holati Excel fayli.

**Ruxsat:** Barcha autentifikatsiya qilinganlar  
**Response:** `ombor_YYYY-MM-DD.xlsx` fayl

**Ustunlar:** №, Mahsulot, Kategoriya, Serial №, Qoldiq (dona), Omborxona, Narxi (sotib olish)

---

#### `GET /api/v1/reports/excel/expenses/`
Rasxodlar Excel fayli.

**Ruxsat:** `ACCOUNTANT` yoki `MANAGEMENT`  
**Filtr:** `?date_from=2024-01-01&date_to=2024-12-31`  
**Response:** `rasxodlar_YYYY-MM-DD.xlsx` fayl

**Ustunlar:** №, Toifa, Tur, Summa, Valyuta, Sana, Mas'ul, Izoh

---

#### `GET /api/v1/reports/excel/payments/`
Kassa to'lovlari Excel fayli.

**Ruxsat:** `ACCOUNTANT` yoki `MANAGEMENT`  
**Response:** `kassa_YYYY-MM-DD.xlsx` fayl

**Ustunlar:** №, Sotuv ID, Mahsulot, Mijoz, Jami summa, Komissiya (15%), To'langan, Qoldiq, Valyuta, To'lov muddati, Status

---

### Moliyaviy Xulosa

#### `GET /api/v1/reports/summary/`
**Ruxsat:** `ACCOUNTANT` yoki `MANAGEMENT`

**Response:**
```json
{
  "sales_revenue_total": "850000000.00",
  "expenses_uzs": "45000000.00",
  "expenses_usd": "3500.00",
  "kassa_collected_uzs": "620000000.00",
  "commission_earned": "127500000.00",
  "overdue_payments_count": 3,
  "report_date": "2024-06-26"
}
```

---

## Xato kodlari

| Kod | Ma'no |
|-----|-------|
| `400` | Noto'g'ri ma'lumot (validatsiya xatosi) |
| `401` | Token yo'q yoki muddati o'tgan |
| `403` | Ruxsat yo'q (rol yetarli emas) |
| `404` | Yozuv topilmadi |
| `500` | Server xatosi |

**401 misoli:**
```json
{ "detail": "Given token not valid for any token type", "code": "token_not_valid" }
```

**403 misoli:**
```json
{ "detail": "You do not have permission to perform this action." }
```

**400 misoli (comment majburiy):**
```json
{ "comment": ["\"Boshqa\" toifasida izoh (comment) majburiy."] }
```

---

## Muhim Texnik Tafsilotlar

### FIFO (Sotuv)
`POST /api/v1/sales/` da ombor qoldig'i avtomatik FIFO tartibida kamayadi — eng eski kirim birinchi chiqariladi. `transaction.atomic()` bilan himoyalangan.

### 15% Komissiya (Kassa)
`POST /api/v1/cash/` da `total_amount` va `commission` avtomatik hisoblanadi:
```
total_amount = sold_price × quantity
commission   = total_amount × 0.15
```

### Fernet Shifrlash (Mijozlar)
`full_name`, `inn`, `phone` ma'lumotlari bazada shifrlangan ko'rinishda saqlanadi. API javobida avtomatik shifrdan ochiladi. `.env` faylida `FERNET_KEY` o'rnatilishi shart.

### Token muddati
```
ACCESS_TOKEN:  8 soat
REFRESH_TOKEN: 30 kun
```

---

## Tezkor ishlatish

```bash
# 1. Login
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"1234"}'

# 2. Mahsulotlar ro'yxati
curl http://localhost:8000/api/v1/warehouse/products/ \
  -H "Authorization: Bearer eyJ..."

# 3. Yangi sotuv
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"product":1,"quantity":2,"sold_price":"15000000","destination":"Toshkent","sold_date":"2024-06-26"}'

# 4. Excel yuklash
curl http://localhost:8000/api/v1/reports/excel/sales/?date_from=2024-01-01 \
  -H "Authorization: Bearer eyJ..." \
  -o sotuvlar.xlsx
```
