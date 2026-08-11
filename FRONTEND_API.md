# Frontend API qo‘llanma — Smart Warehouse

Bu hujjat frontend uchun amaldagi backend kontraktidir. Bazaviy URL:

```text
/api/v1
```

## 0. Umumiy qoidalar

### Auth

Barcha private endpointlar JWT talab qiladi:

```http
Authorization: Bearer <access_token>
```

Access token tugasa frontend refresh token bilan yangilaydi:

```http
POST /api/v1/auth/token/refresh/
```

```json
{ "refresh": "<refresh_token>" }
```

Javob:

```json
{ "access": "<new_access_token>" }
```

### Ro‘yxatlar

Ko‘p ro‘yxat endpointlari pagination qaytaradi:

```json
{
  "count": 120,
  "next": "...",
  "previous": null,
  "results": []
}
```

Frontend `results` bo‘lsa shuni, oddiy array bo‘lsa arrayni ishlatishi kerak.

### Xatoliklar

Maydon xatosi:

```json
{ "contract_number": ["Shartnoma raqami noto‘g‘ri."] }
```

Umumiy xato:

```json
{ "detail": "Bu amalni bajarish uchun ruxsatingiz yo‘q." }
```

HTML qaytsa, backend/proxy noto‘g‘ri ishlayapti. Frontend buni JSON deb parse qilmasligi kerak.

### Sana formatlari

Sana:

```text
YYYY-MM-DD
```

Shartnoma raqami:

```text
{kunlik_buyurtma_raqami}/{DDMM}
```

Misol:

```text
12/1108
```

Harf bo‘lmaydi. Backend regex:

```text
^\d+/\d{4}$
```

Bo‘sh yuborilsa backend avtomatik yaratadi.

## 1. Auth va user sessiya

### Login

```http
POST /api/v1/auth/login/
```

Token talab qilmaydi. Rate limit: `10/min`.

So‘rov:

```json
{
  "username": "demo_ombor",
  "password": "Demo@2026!"
}
```

Javob:

```json
{
  "access": "<jwt>",
  "refresh": "<jwt>",
  "user": {
    "id": 2,
    "username": "demo_ombor",
    "first_name": "",
    "last_name": "",
    "role": "MANAGEMENT",
    "can_view_clients": true,
    "is_staff": true,
    "is_superuser": true,
    "abilities": {
      "dashboard": true,
      "orders_view": true,
      "orders_manage": true,
      "warehouse_view": true,
      "warehouse_manage": true,
      "clients_view": true,
      "clients_manage": true,
      "sales_view": true,
      "sales_manage": true,
      "cash_view": true,
      "cash_manage": true,
      "expenses_view": true,
      "expenses_manage": true,
      "reports_view": true,
      "notifications_view": true,
      "procurement_view": true,
      "procurement_manage": true,
      "contracts_view": true,
      "categories_view": true,
      "stocks_view": true,
      "users_view": true,
      "users_manage": true
    }
  }
}
```

### Joriy user

```http
GET /api/v1/auth/me/
```

Frontend login/session restore paytida shu endpointdan user va `abilities` ni yangilaydi.

### User yaratish

```http
POST /api/v1/auth/register/
```

Faqat `MANAGEMENT`.

So‘rov:

```json
{
  "username": "operator_toshkent",
  "password": "StrongPass2026!",
  "first_name": "Akmal",
  "last_name": "Karimov",
  "role": "OPERATOR",
  "phone": "+998901112233",
  "telegram_id": "123456789",
  "can_view_clients": false
}
```

Role qiymatlari:

```text
OPERATOR
ACCOUNTANT
MANAGEMENT
```

### User management

```http
GET /api/v1/auth/users/?page_size=20&search=akmal&role=OPERATOR&is_active=true
GET /api/v1/auth/users/{id}/
PATCH /api/v1/auth/users/{id}/
DELETE /api/v1/auth/users/{id}/
```

`POST /auth/users/` ishlatilmaydi. Yangi user faqat `/auth/register/` orqali yaratiladi.

Superuser oddiy manager ro‘yxatida ko‘rinmaydi. Manager superuserni o‘zgartira/o‘chira olmaydi. User o‘zini o‘chira olmaydi.

## 2. Role va UI permission

Frontend menyuni `abilities` bo‘yicha ko‘rsatadi. Ruxsat yo‘q menu UI’da ko‘rinmasligi kerak.

| Ability | Ma’nosi |
|---|---|
| `dashboard` | bosh sahifa statistikasi |
| `orders_view` | buyurtmalarni ko‘rish |
| `orders_manage` | buyurtma yaratish/tahrirlash/amallar |
| `warehouse_view` | mahsulotlarni ko‘rish |
| `warehouse_manage` | mahsulot/kirim boshqarish |
| `clients_view` | mijozlarni ko‘rish |
| `clients_manage` | mijoz CRUD |
| `sales_view` | sotuvlarni ko‘rish |
| `sales_manage` | sotuv yaratish/tahrirlash |
| `cash_view` | kassa ko‘rish |
| `cash_manage` | to‘lov qabul qilish |
| `expenses_view` | xarajatlarni ko‘rish |
| `expenses_manage` | xarajat yaratish/tahrirlash |
| `reports_view` | hisobotlar |
| `notifications_view` | bildirishnomalar |
| `procurement_view` | zakazlar |
| `procurement_manage` | zakaz yaratish/tahrirlash |
| `contracts_view` | shartnomalar reestri |
| `categories_view` | kategoriyalar |
| `stocks_view` | qoldiqlar |
| `users_view` | userlarni ko‘rish |
| `users_manage` | user boshqarish |

Operator uchun narx/foyda maydonlari ayrim javoblarda qaytmaydi. Frontend bunday maydonlar yo‘qligiga tayyor bo‘lsin.

## 3. Valyuta kursi

Backend Infinbank sahifasidan USD `MB kurs` ni oladi:

```text
https://www.infinbank.com/uz/private/exchange-rates/
```

HTML ichida `rates-table` dan `MB kurs` qatori va `USD` ustuni ajratiladi.

### Oxirgi USD kurs

```http
GET /api/v1/cash/exchange-rates/latest/?refresh=false
GET /api/v1/cash/exchange-rates/latest/?refresh=true
```

`refresh=true` tashqi manbadan qayta olib kelishga urinadi. Agar tashqi manba ishlamasa, backend bazadagi oxirgi kursni fallback qiladi. Fallback ham bo‘lmasa `503`.

Javob:

```json
{
  "id": 1,
  "currency": "USD",
  "mb_rate": "11934.61",
  "buy_rate": "11934.61",
  "sell_rate": "11934.61",
  "rate_date": "2026-08-11",
  "source": "infinbank",
  "manual_override": false,
  "note": "",
  "created_at": "2026-08-11T..."
}
```

### Qo‘lda kurs saqlash

```http
POST /api/v1/cash/exchange-rates/
```

So‘rov:

```json
{
  "currency": "USD",
  "mb_rate": "11950.00",
  "buy_rate": "11950.00",
  "sell_rate": "11950.00",
  "manual_override": true,
  "note": "Qo‘lda kiritilgan kurs"
}
```

Backend `currency=USD`, `source=manual`, `manual_override=true`, `rate_date=today` qilib saqlaydi.

## 4. Buyurtmalar

Base:

```http
/api/v1/orders/
```

### Ro‘yxat

```http
GET /api/v1/orders/?page_size=20&search=12/1108&status=partial&client=<uuid>&contract_number=12/1108
```

Statuslar:

```text
pending
partial
reserved
fulfilled
cancelled
```

### Detail

```http
GET /api/v1/orders/{id}/
```

Javobda `items`, `history`, `total`, `balance_due`, `reserved_qty`, `backorder_qty`, `has_active_zakaz` bor.

### Yangi buyurtma

```http
POST /api/v1/orders/
```

JSON:

```json
{
  "client": "<uuid>",
  "contract_number": "12/1108",
  "contract_date": "2026-08-11",
  "prepaid_amount": "1000000",
  "due_date": "2026-08-20",
  "comment": "Mijoz bilan kelishildi",
  "items": [
    { "product": 1, "quantity": 2, "unit_price": "15000000" },
    { "product": 3, "quantity": 1, "unit_price": "2300000" }
  ]
}
```

Multipart form ham ishlaydi, `contract_file` yuborish mumkin. `items` JSON string sifatida yuboriladi.

Legacy bitta mahsulot format ham ishlaydi:

```json
{
  "client": "<uuid>",
  "product": 1,
  "quantity": 2,
  "unit_price": "15000000"
}
```

Yaratilganda:

- buyurtma bitta hujjat bo‘ladi;
- har mahsulot `items[]` qatori bo‘ladi;
- qoldiq yetsa bron qilinadi;
- qoldiq yetmasa backorder va avtomatik zakaz ochiladi;
- kassa payment avtomatik yaratiladi;
- shartnomalar reestriga yoziladi;
- tarix yoziladi.

### Bulk buyurtma

```http
POST /api/v1/orders/bulk/
```

Natija baribir bitta order. Frontend ko‘p mahsulotli forma ishlatsa oddiy `POST /orders/` yetadi; bulk endpoint ham backendda bor.

### Tahrirlash

```http
PATCH /api/v1/orders/{id}/
```

`asos` majburiy.

Miqdor o‘zgartirish:

```json
{
  "asos": "Mijoz miqdorni oshirdi",
  "items": [
    { "id": 5, "quantity": 25 }
  ]
}
```

Yangi qator qo‘shish:

```json
{
  "asos": "Mijoz mahsulot qo‘shdi",
  "items": [
    { "product": 9, "quantity": 3, "unit_price": "700000" }
  ]
}
```

Qator o‘chirish:

```json
{
  "asos": "Mijoz voz kechdi",
  "items": [
    { "id": 7, "remove": true }
  ]
}
```

Cheklovlar:

- oxirgi qatorni o‘chirib bo‘lmaydi;
- `fulfilled` va `cancelled` order tahrirlanmaydi;
- `prepaid_amount` totaldan oshmasligi kerak.

### Order amallari

Yetkazish:

```http
POST /api/v1/orders/{id}/fulfill/
```

Bekor qilish:

```http
POST /api/v1/orders/{id}/cancel/
```

Qo‘lda zakaz:

```http
POST /api/v1/orders/{id}/create-zakaz/
```

So‘rov:

```json
{
  "contract_number": "12/1108",
  "asos": "Mijozga topshirildi",
  "faktura": "F-2026/900",
  "supplier": "Toshkent Logistika",
  "expected_date": "2026-08-25"
}
```

`contract_number` va `asos` majburiy. `faktura`, `supplier`, `expected_date` ixtiyoriy. Har amal history va product contracts reestriga yoziladi.

## 5. Zakazlar

Base:

```http
/api/v1/orders/zakaz/
```

### Ro‘yxat

```http
GET /api/v1/orders/zakaz/?page_size=30&status=new&product=1&order=5&contract_number=12/1108
```

Status oqimi:

```text
new
confirmed
ordered
received
cancelled
```

### Yangi zakaz

```http
POST /api/v1/orders/zakaz/
```

```json
{
  "product": 5,
  "quantity": 20,
  "supplier": "Guangzhou Medical Supply",
  "contract_number": "13/1108",
  "contract_date": "2026-08-11",
  "expected_date": "2026-08-25",
  "comment": "Yetkazuvchi bilan kelishildi"
}
```

### Bulk zakaz

```http
POST /api/v1/orders/zakaz/bulk/
```

Bir nechta mahsulot uchun zakaz yaratadi.

### Status PATCH

```http
PATCH /api/v1/orders/zakaz/{id}/
```

Tasdiqlash:

```json
{
  "status": "confirmed",
  "contract_number": "13/1108",
  "asos": "Rahbariyat tasdiqladi"
}
```

Buyurtma berildi:

```json
{
  "status": "ordered",
  "asos": "Yetkazuvchiga yuborildi"
}
```

Qabul:

```json
{
  "status": "received",
  "received_qty": 20,
  "warehouse_location": "A-2-4",
  "asos": "Kirim qabul qilindi",
  "faktura": "F-2026/900"
}
```

Bekor:

```json
{
  "status": "cancelled",
  "asos": "Yetkazuvchi bekor qildi"
}
```

Qabul qilinganda ombor to‘ladi, pending/backorder orderlarga avtomatik bron ajratiladi, history va reestr yoziladi.

## 6. Shartnomalar reestri

```http
GET /api/v1/orders/contracts/?page_size=30&product=1&contract_number=12/1108&source_type=order_created&order=5&zakaz=3
GET /api/v1/orders/contracts/{id}/
```

Read-only.

`source_type` qiymatlari:

```text
order_created
order_edited
order_fulfilled
order_cancelled
zakaz_created
zakaz_confirmed
zakaz_ordered
zakaz_received
zakaz_cancelled
stock_in
```

Mahsulot detailidan reestr:

```http
GET /api/v1/warehouse/products/{id}/contracts/
```

## 7. Ombor

### Kategoriyalar

```http
GET /api/v1/warehouse/categories/?page_size=30&search=texnika
POST /api/v1/warehouse/categories/
GET /api/v1/warehouse/categories/{id}/
PATCH /api/v1/warehouse/categories/{id}/
DELETE /api/v1/warehouse/categories/{id}/
```

So‘rov:

```json
{
  "name": "Med texnika",
  "parent": null
}
```

Javobda `children` bor.

### Mahsulotlar

```http
GET /api/v1/warehouse/products/?page_size=30&search=monitor&category=1
POST /api/v1/warehouse/products/
GET /api/v1/warehouse/products/{id}/
PATCH /api/v1/warehouse/products/{id}/
DELETE /api/v1/warehouse/products/{id}/
```

So‘rov:

```json
{
  "category": 1,
  "name": "Samsung Odyssey G5 monitor",
  "model": "G55C",
  "serial_number": "SM-G55C-2026-001",
  "purchase_price": "2100000",
  "selling_price": "2600000",
  "source": "Toshkent distribyutor",
  "min_quantity": 3,
  "quantity": 10,
  "warehouse_location": "A-1-2"
}
```

`quantity` yuborilsa `warehouse_location` majburiy va Stock yaratiladi.

Javob maydonlari:

```text
quantity_in_stock
reserved_quantity
available_quantity
stock_status
category_name
```

Operator uchun `purchase_price`, `selling_price` qaytmasligi mumkin.

### Kirim

```http
POST /api/v1/warehouse/products/{id}/add-stock/
```

```json
{
  "quantity": 20,
  "warehouse_location": "B-2-3",
  "asos": "Kirim orderi №77",
  "contract_number": "13/1108",
  "faktura": "F-2026/900"
}
```

`asos` majburiy. Kirimdan keyin pending orderlarga bron avtomatik ajratiladi. Javobda `allocated_orders` bo‘lishi mumkin.

### Qoldiqlar

```http
GET /api/v1/warehouse/stocks/?page_size=30&product=1&category=2&status=low_stock
POST /api/v1/warehouse/stocks/
GET /api/v1/warehouse/stocks/{id}/
PATCH /api/v1/warehouse/stocks/{id}/
DELETE /api/v1/warehouse/stocks/{id}/
```

`reserved_quantity` read-only.

## 8. Mijozlar

```http
GET /api/v1/clients/?page_size=30&search=smart
POST /api/v1/clients/
GET /api/v1/clients/{uuid}/
PATCH /api/v1/clients/{uuid}/
DELETE /api/v1/clients/{uuid}/
```

`can_view_clients` ruxsati kerak.

So‘rov:

```json
{
  "client_type": "legal",
  "company_name": "Samarqand Med Texnika MChJ",
  "full_name": "",
  "first_name": "",
  "last_name": "",
  "middle_name": "",
  "inn": "310776556",
  "pinfl": "",
  "passport_number": "",
  "phone": "+998901112233",
  "email": "info@example.uz",
  "address": "Samarqand shahri, Universitet xiyoboni 12",
  "comment": "Doimiy mijoz",
  "is_active": true
}
```

`full_name`, `first_name`, `last_name`, `middle_name`, `pinfl`, `inn`, `passport_number`, `phone` bazada shifrlanadi. Javobda ochiq matn qaytadi.

Hozir Soliq/DIDox kabi external auto-fill endpoint yo‘q. Rejalangan to‘g‘ri arxitektura:

```http
GET /api/v1/clients/lookup/?identifier=310776556
```

Avval local DB, keyin tashqi Soliq provider. Bu hali qo‘shilmagan.

## 9. Sotuvlar

```http
GET /api/v1/sales/?page_size=30&product=1&client=<uuid>&sold_date=2026-08-11
POST /api/v1/sales/
GET /api/v1/sales/{id}/
PATCH /api/v1/sales/{id}/
DELETE /api/v1/sales/{id}/
POST /api/v1/sales/bulk/
```

Bitta sotuv:

```json
{
  "product": 1,
  "quantity": 2,
  "sold_price": "2600000",
  "client": "<uuid>",
  "sold_to": "Samarqand Med Texnika MChJ",
  "destination": "Samarqand",
  "sold_date": "2026-08-11",
  "comment": "Naqd savdo"
}
```

Bulk:

```json
{
  "client": "<uuid>",
  "sold_to": "Samarqand Med Texnika MChJ",
  "destination": "Samarqand",
  "sold_date": "2026-08-11",
  "items": [
    { "product": 1, "quantity": 2, "sold_price": "2600000", "comment": "" },
    { "product": 4, "quantity": 1, "sold_price": "800000", "comment": "" }
  ]
}
```

Backend FIFO bo‘yicha ombordan ayiradi. Qoldiq yetmasa `400`. Operator javobida foyda/narx maydonlari yashirilishi mumkin.

## 10. Kassa

### Payments

```http
GET /api/v1/cash/payments/?page_size=30&status=partial&order=5&sale=7&client=<uuid>&currency=UZS
POST /api/v1/cash/payments/
GET /api/v1/cash/payments/{id}/
PATCH /api/v1/cash/payments/{id}/
DELETE /api/v1/cash/payments/{id}/
```

Payment sotuv yoki orderga bog‘lanadi, ikkalasiga bir vaqtda emas.

Javobda:

```text
source
sale_info
order_info
client_name
remaining
transactions
```

### Qo‘shimcha to‘lov

```http
POST /api/v1/cash/payments/{id}/pay/
```

```json
{
  "amount": "5000000",
  "comment": "Ikkinchi bo‘lib to‘lash"
}
```

Har to‘lov `PaymentTransaction` bo‘lib yoziladi. `paid_amount` transactionlar yig‘indisiga teng. Qoldiqdan ortiq to‘lov `400`.

Order payment bo‘lsa order `prepaid_amount` ham sinxronlanadi.

### Summary

```http
GET /api/v1/cash/payments/summary/
```

Javob:

```json
{
  "total_pending": 3,
  "total_partial": 2,
  "total_paid": 10,
  "total_overdue": 1,
  "sum_paid_uzs": "15000000",
  "sum_paid_usd": "0",
  "total_commission_uzs": "0",
  "order_payments_count": 4,
  "sum_order_total_uzs": "50000000",
  "sum_order_prepaid_uzs": "10000000",
  "sum_order_due_uzs": "40000000"
}
```

## 11. Xarajatlar

### Toifalar

```http
GET /api/v1/expenses/expense-types/?page_size=50&search=ijara
GET /api/v1/expenses/expense-types/{id}/
```

Read-only. Admin orqali boshqariladi.

### Subtype

```http
GET /api/v1/expenses/expense-subtypes/?page_size=100&expense_type=1
POST /api/v1/expenses/expense-subtypes/
GET /api/v1/expenses/expense-subtypes/{id}/
```

### Xarajatlar

```http
GET /api/v1/expenses/expenses/?page_size=30&expense_type=1&sub_type=2&currency=UZS&date_from=2026-08-01&date_to=2026-08-31
POST /api/v1/expenses/expenses/
GET /api/v1/expenses/expenses/{id}/
PATCH /api/v1/expenses/expenses/{id}/
DELETE /api/v1/expenses/expenses/{id}/
```

Multipart file upload qo‘llanadi.

So‘rov:

```json
{
  "expense_type": 1,
  "sub_type": 2,
  "amount": "1200000",
  "currency": "UZS",
  "date": "2026-08-11",
  "comment": "Ombor ijara to‘lovi"
}
```

### Summary

Asosiy:

```http
GET /api/v1/expenses/expenses/summary/?date_from=2026-08-01&date_to=2026-08-31&currency=UZS
```

Alias:

```http
GET /api/v1/expenses/summary/
```

Javob:

```json
{
  "total_uzs": "1200000",
  "total_usd": "0",
  "count": 1,
  "by_type": [
    {
      "expense_type": 1,
      "name": "Ijara",
      "total_uzs": "1200000",
      "total_usd": "0"
    }
  ]
}
```

## 12. Bildirishnomalar

```http
GET /api/v1/notifications/?page_size=30&is_read=false
GET /api/v1/notifications/{id}/
POST /api/v1/notifications/{id}/mark_read/
POST /api/v1/notifications/mark_all_read/
```

Frontend browser push permission so‘raydi. Polling 30s. Bir xil toast takror chiqmasligi kerak.

## 13. Hisobotlar

```http
GET /api/v1/reports/summary/
GET /api/v1/reports/warehouse/
GET /api/v1/reports/cash/
GET /api/v1/reports/expenses/
GET /api/v1/reports/top-products/
```

Accountant/Management.

Excel export:

```http
GET /api/v1/reports/excel/sales/?date_from=2026-08-01&date_to=2026-08-31
GET /api/v1/reports/excel/stock/
GET /api/v1/reports/excel/expenses/?date_from=2026-08-01&date_to=2026-08-31
GET /api/v1/reports/excel/payments/?date_from=2026-08-01&date_to=2026-08-31
```

Frontend blob download qiladi. Operator uchun `403`.

## 14. Frontend performance va dev/prod

Vite dev server:

```text
http://localhost:5173
```

Dev mode Cloudflare tunnel orqali sekin bo‘lishi mumkin, chunki module requestlar ko‘p:

```text
/@vite/client
/src/main.jsx
/src/App.jsx
...
```

Global test uchun production preview:

```bash
cd frontend
npm run build
npm run preview -- --host 0.0.0.0 --port 4173
cloudflared tunnel --url http://localhost:4173
```

Backend alohida ishlashi kerak:

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

Frontend API timeout: `8s`. Backend o‘chiq bo‘lsa uzoq loading emas, aniq xabar chiqadi.

Auto refresh:

```text
resource/dashboard: 30s
notifications: 30s
```

## 15. Frontend checklist

- JWT access token har so‘rovda yuborilsin.
- Access token 401 bo‘lsa refresh qilinsin, request bir marta retry bo‘lsin.
- Refresh ham ishlamasa session tozalansin.
- `abilities` bo‘yicha sidebar/bottom nav menyular yashirilsin.
- Ruxsatsiz menu UI’da ko‘rinmasin.
- 403 toast dedupe bo‘lsin.
- Buyurtma shartnoma raqami faqat `12/1108` format.
- Buyurtma yaratishda `items[]` ishlatilsin.
- Tahrirda `asos` majburiy so‘ralsin.
- Fulfill/cancel/create-zakaz modalida `contract_number` + `asos` so‘ralsin.
- Zakaz `received` bo‘lsa `faktura` majburiy.
- Kassa payment qabul qilinganda payment summary refetch qilinsin.
- Order tahrirlanganda payments va reports refetch qilinsin.
- File uploadda `FormData` ishlatilsin.
- Excel exportda blob download ishlatilsin.
- Operator uchun narx/foyda maydonlari yo‘q bo‘lishiga UI tayyor bo‘lsin.
- Mobile’da sidebar emas, bottom navigation ko‘rsatilsin.
- Desktop sidebar collapse holati saqlansin.

## 16. Hali backendda yo‘q, alohida modul bo‘ladigan qism

Didox uslubidagi to‘liq elektron hisob-faktura moduli hozir backendda yo‘q.

Yo‘q qismlar:

- hamkor STIR/JSHSHIR lookup external Soliq API orqali;
- korxona rekvizitlari auto-fill;
- bank, MFO, hisob raqami, OKED maydonlari;
- MXIK/IKPU katalog lookup;
- QQS hisoblash;
- teskari hisob;
- hujjat preview;
- shablon saqlash;
- ERI/imzolash;
- Didox/Soliq real integratsiya.

Bu kerak bo‘lsa, alohida backend + frontend modul sifatida qo‘shiladi.
