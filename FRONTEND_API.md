# Frontend API qo'llanma — Smart Warehouse

Frontchi uchun to'liq endpoint qo'llanma. Barcha oxirgi o'zgarishlar bilan
(ko'p mahsulotli buyurtma, qator o'chirish, majburiy shartnoma+izoh+faktura,
kassa bo'lib to'lash, kirim, zakaz avtomatik moslashuvi).

> To'liq biznes-logika: [PROJECT_DOCS.md](PROJECT_DOCS.md)

---

## Yangilanish — 10.07.2026 (kassa avto-sinxron)

**API kontrakti O'ZGARMADI** — yangi endpoint yo'q, so'rov/javob formatlari
avvalgidek. Backendda buyurtma ↔ kassa bog'lanishi mustahkamlandi:

Buyurtma QANDAY yo'l bilan o'zgarmasin (`PATCH /orders/{id}/`, admin panel,
ichki kod) — unga bog'liq kassa yozuvi (`/cash/payments/`) **avtomatik**
qayta hisoblanadi:

| Buyurtmada o'zgardi | Kassada avtomatik yangilanadi |
|---------------------|-------------------------------|
| Qator miqdori / narxi / yangi qator / qator o'chirildi | `total_amount` (jami) |
| `prepaid_amount` (oldindan to'lov) | `paid_amount` + yangi tranzaksiya yoziladi |
| `due_date` (yetkazish muddati) | `due_date` (to'lov muddati) |
| `client` | `client` |
| — har qanday o'zgarishda | `status` (`pending/partial/paid/overdue`) |

**Frontend uchun YAGONA talab:** buyurtma tahriri (PATCH) muvaffaqiyatli
bo'lgandan keyin kassa ma'lumotlarini **qayta yuklang** (refetch):
- `GET /cash/payments/` (yoki `?order={id}`) — ro'yxat/qoldiq
- `GET /cash/payments/summary/` — yuqoridagi kartochkalar (Yig'ilgan, Qoldiq...)
- Tushum prognozi ham shu ma'lumotdan — birga yangilanadi

React Query/SWR ishlatilsa: order mutation `onSuccess` da `payments` va
`payments-summary` query'larini **invalidate** qiling. Kassa sahifasi ochiq
turgan bo'lsa ham eski raqam ko'rinib qolmasligi uchun shu yetarli.

---

## 0. Asoslar

**Bazaviy URL:** `/api/v1/`

**Autentifikatsiya:** JWT (Bearer). Har so'rovda header:
```
Authorization: Bearer <access_token>
```

**Sana/vaqt:** hammasi `Asia/Tashkent`. Sanalar `YYYY-MM-DD`.

**Xatolik formati (400):** maydon → xabar ro'yxati
```json
{ "contract_number": ["Shartnoma raqami kiritilishi shart."],
  "asos": ["Izoh (asos) kiritilishi shart."] }
```
Boshqa xatolar: `{ "detail": "..." }` (400/401/403/404). `403` — rol yetmaydi.

**Sahifalash:** ro'yxatlar `?page=1` — javob `{count, next, previous, results: [...]}`.
`?search=...` va `?ordering=...` ko'pchilik ro'yxatда bor.

---

## 1. Auth

### Login
`POST /auth/login/` — token talab qilmaydi
```json
// so'rov
{ "username": "operator1", "password": "op1pass" }
// javob
{
  "access": "<jwt>",
  "refresh": "<jwt>",
  "user": { "id": 1, "username": "operator1", "role": "OPERATOR", "can_view_clients": false }
}
```
> Login `10/min` bilan cheklangan (brute-force himoyasi).

### Token yangilash
`POST /auth/token/refresh/`
```json
{ "refresh": "<jwt>" }        // → { "access": "<yangi jwt>" }
```

### Foydalanuvchi yaratish (faqat Management)
`POST /auth/register/`
```json
{ "username": "op2", "password": "kuchli-parol-8+", "role": "OPERATOR",
  "first_name": "Ali", "last_name": "Valiyev", "phone": "+99890..." }
```
> Parol Django validatoridan o'tadi (zaif parol RAD). `role`: `OPERATOR` / `ACCOUNTANT` / `MANAGEMENT`.

### Foydalanuvchilar (faqat Management)
`GET/POST/PATCH/DELETE /auth/users/` — filtr `?role=`, `?is_active=`.

---

## 2. Rollar — kim nimani ko'radi

| Funksiya | Operator | Accountant | Management |
|----------|:--------:|:----------:|:----------:|
| Mahsulot qo'shish | ✅ | ❌ | ✅ |
| Narx (`purchase_price`/`selling_price`) ko'rish | ❌ | ✅ | ✅ |
| Sotuvda summa/foyda ko'rish | ❌ | ✅ | ✅ |
| Buyurtma yaratish/tahrirlash | ✅ | ❌ | ✅ |
| Zakaz **status** o'zgartirish | ❌ | ❌ | ✅ |
| Kassa / Rasxod | ko'rish | ✅ | ✅ |
| Hisobot / Excel | ❌ | ✅ | ✅ |

> **Muhim:** Operator uchun API javobida `purchase_price`, `selling_price`,
> sotuvda `sold_price`/`total_amount`/`profit` **umuman qaytmaydi** —
> frontend bu maydonlar yo'qligiga tayyor bo'lsin.

---

## 3. Buyurtmalar (Orders) — BITTA buyurtma, ko'p mahsulot

Buyurtma — bitta hujjat, ichida `items[]` (mahsulot qatorlari). Nechta mahsulot
bo'lsa ham buyurtma bitta.

### Ro'yxat
`GET /orders/` — filtr: `?status=`, `?items__product=<id>`, `?client=<uuid>`,
`?contract_number=`, qidiruv `?search=` (mahsulot/shartnoma/mijoz).

Status: `pending` (kutilmoqda) · `partial` (qisman bron) · `reserved` (to'liq bron)
· `fulfilled` (yetkazildi) · `cancelled` (bekor).

### Bitta buyurtma (tarix bilan)
`GET /orders/{id}/`
```json
{
  "id": 2, "client": "<uuid>", "client_name": "MAAB",
  "contract_number": "DIS", "contract_date": "2026-07-01",
  "items": [
    { "id": 5, "product": 2, "product_name": "server (AD123)",
      "quantity": 20, "unit_price": "5000000", "total": "100000000",
      "reserved_qty": 10, "backorder_qty": 10, "has_active_zakaz": true }
  ],
  "total_quantity": 20, "total": "100000000",
  "prepaid_amount": "2000000", "balance_due": "98000000",
  "reserved_qty": 10, "backorder_qty": 10,
  "due_date": "2026-07-16", "status": "partial",
  "history": [ { "action": "created", "action_display": "Yaratildi",
                 "contract_number": "DIS", "asos": "...", "created_at": "..." } ]
}
```
> **Eslatma:** `backorder_qty` = "Zakaz kutilmoqda" ustuni. Yetkazilgan/bekor
> qilingan buyurtmada **0** bo'ladi (kutiladigan narsa yo'q).

### Yangi buyurtma
`POST /orders/`
```json
{
  "client": "<uuid>",                    // ixtiyoriy
  "contract_number": "SH-2026/045",      // MAJBURIY
  "contract_date": "2026-07-09",         // ixtiyoriy (default: bugun)
  "prepaid_amount": "10000000",          // ixtiyoriy — oldindan to'lov
  "due_date": "2026-08-01",              // ixtiyoriy
  "items": [
    { "product": 12, "quantity": 10, "unit_price": "3900000" },
    { "product": 7,  "quantity": 2,  "unit_price": "1200000" }
  ]
}
```
**Yaratilganda avtomatik:**
- Har qatorga ombordan bron ajratiladi (yetsa `reserved`, yetmasa `partial`)
- Yetishmagan qatorlar uchun **Zakaz** ochiladi (Zakazlar ro'yxatida ko'rinadi)
- **Kassada to'lov yozuvi** ochiladi (jami + oldindan to'lov)

### Buyurtma tahrirlash (mijoz o'zgaruvchan)
`PATCH /orders/{id}/` — **`asos` (izoh) HAR TAHRIRDA MAJBURIY**

**Qator miqdorini o'zgartirish:**
```json
{ "asos": "Mijoz 20 dan 25 ga oshirdi",
  "items": [ { "id": 5, "quantity": 25 } ] }
```
**Yangi mahsulot qo'shish** (id yubormang):
```json
{ "asos": "Mijoz yana mahsulot qo'shdi",
  "items": [ { "product": 9, "quantity": 3, "unit_price": "700000" } ] }
```
**Mahsulotni olib tashlash:**
```json
{ "asos": "Mijoz bu mahsulotdan voz kechdi",
  "items": [ { "id": 7, "remove": true } ] }
```
**Tahrir avtomatik:**
- Miqdor o'zgarsa — bron qayta moslanadi
- **Kassa avtomatik yangilanadi** — jami (`total_amount`), to'lov muddati,
  mijoz, status; oldindan to'lov farqi alohida tranzaksiya bo'lib yoziladi
- **Zakaz miqdori moslanadi** — oshsa "yana qo'shildi", kamaysa kamayadi
  (tarixда: "zakaz miqdori 10 → 15 (+5 dona)")

> ⚠️ **Frontend:** PATCH muvaffaqiyatli bo'lgach kassa so'rovlarini refetch
> qiling (`/cash/payments/`, `/cash/payments/summary/`) — aks holda sahifada
> eski jami/qoldiq ko'rinib turadi. Batafsil: yuqoridagi "Yangilanish —
> 10.07.2026" bo'limi.

**Cheklovlar:**
- Oxirgi qatorni o'chirib bo'lmaydi — butun buyurtma uchun `/cancel/`
- Oldindan to'lov yangi jamidan oshsa 400 → `prepaid_amount` ni ham kamaytiring
- `fulfilled`/`cancelled` buyurtmani tahrirlab bo'lmaydi

### Buyurtma amallari — **shartnoma + izoh MAJBURIY**

| Amal | URL | Majburiy | Ixtiyoriy |
|------|-----|----------|-----------|
| Yetkazish | `POST /orders/{id}/fulfill/` | `contract_number`, `asos` | `faktura` |
| Bekor qilish | `POST /orders/{id}/cancel/` | `contract_number`, `asos` | `faktura` |
| Qo'lda zakaz | `POST /orders/{id}/create-zakaz/` | `contract_number`, `asos` | `faktura`, `supplier`, `expected_date` |

```json
POST /orders/{id}/fulfill/
{ "contract_number": "SH-2026/045", "asos": "Mijozga topshirildi", "faktura": "F-2026/900" }
```
> Bu maydonlarsiz yuborilsa **400** qaytadi. Har amal tarix + shartnomalar
> reestriga yoziladi. Frontendда bu tugmalar bosilganda modal/forma orqali
> `contract_number` + `asos` (+ ixtiyoriy `faktura`) so'ralsin.

---

## 4. Zakazlar (Etkazuvchidan)

### Ro'yxat / bitta
`GET /orders/zakaz/` — filtr `?status=`, `?product=`, `?order=`, `?contract_number=`.
`GET /orders/zakaz/{id}/` — tarix bilan.

Status oqimi: `new → confirmed → ordered → received` (yoki `cancelled`).

### Yangi zakaz (buyurtmasiz — o'zingiz uchun)
`POST /orders/zakaz/`
```json
{ "product": 5, "quantity": 20, "supplier": "Xitoy, Guangzhou",
  "contract_number": "SH-2026/051", "contract_date": "2026-07-01",
  "expected_date": "2026-08-15", "comment": "..." }
```

### Status o'zgartirish — **FAQAT Management**, PATCH
`PATCH /orders/zakaz/{id}/`

| O'tish | Majburiy maydonlar |
|--------|--------------------|
| → `confirmed` (tasdiqlash) | `status`, `asos`, `contract_number` |
| → `ordered` (yuborildi) | `status`, `asos` (shartnoma zakazда bo'lishi shart) |
| → `received` (qabul) | `status`, `asos`, `faktura` (+ `received_qty`, `warehouse_location`) |
| → `cancelled` (bekor) | `status`, `asos` |

```json
// Tasdiqlash
{ "status": "confirmed", "contract_number": "SH-2026/051", "asos": "Rahbariyat tasdiqladi" }
// Qabul qilish
{ "status": "received", "received_qty": 20, "warehouse_location": "B-2-3",
  "asos": "Kirim orderi №77", "faktura": "F-2026/900" }
```
**Avtomatik:**
- Tasdiqlashda sana bo'sh bo'lsa bugungi kun qo'yiladi, `confirmed_at` yoziladi
- **Qabul qilinganda** ombor to'ldiriladi + kutayotgan buyurtmalarga bron
  ajratiladi (buyurtma tarixiga "shartnoma asosida N dona bron ajratildi")
- Har o'tish tarix + reestrga yoziladi

> **Operator** faqat `supplier`/`expected_date`/`comment`/`asos`/`faktura` ni
> o'zgartira oladi; `status` yuborsa **403**.

---

## 5. Kassa (Payments) — bo'lib to'lash bilan

### Ro'yxat / bitta
`GET /cash/payments/` — filtr `?status=`, `?order=`, `?sale=`, `?client=`, `?currency=`.
`GET /cash/payments/{id}/` — tranzaksiyalar bilan.

`source`: `order` (buyurtma to'lovi) yoki `sale` (sotuv to'lovi).
Status: `pending` / `partial` / `paid` / `overdue`.

```json
{
  "id": 101, "source": "order",
  "order": 2, "order_info": {
    "contract_number": "DIS", "total": "100000000",
    "prepaid_amount": "2000000", "balance_due": "98000000",
    "items": [ { "product": "server (AD123)", "quantity": 20, "total": "100000000" } ]
  },
  "total_amount": "100000000", "paid_amount": "2000000",
  "remaining": "98000000", "status": "partial",
  "transactions": [
    { "amount": "2000000", "received_by_name": "operator1",
      "comment": "Oldindan to'lov", "created_at": "..." }
  ]
}
```

### Qo'shimcha to'lov (bo'lib to'lash)
`POST /cash/payments/{id}/pay/` — Accountant/Management
```json
{ "amount": "5000000", "comment": "Ikkinchi bo'lib to'lash" }
```
- Har to'lov alohida tranzaksiya bo'lib qo'shiladi, status avtomatik yangilanadi
- Qoldiqdan ortiq / to'liq to'langaniga yana to'lov → **400**
- Buyurtma to'lovi bo'lsa buyurtmadagi `prepaid_amount` ham sinxronlanadi

### Xulosa
`GET /cash/payments/summary/` — umumiy + buyurtma to'lovlari alohida
(`order_payments_count`, `sum_order_total_uzs`, `sum_order_prepaid_uzs`, `sum_order_due_uzs`).

---

## 6. Ombor (Warehouse)

### Mahsulotlar
`GET/POST /warehouse/products/` · `GET/PATCH/DELETE /warehouse/products/{id}/`
Filtr: `?category=`, `?purchase_price__isnull=true`, `?selling_price__isnull=true`.

Maydonlar: `name`, `model`, `serial_number`, `category`, `min_quantity`,
`quantity_in_stock`, `reserved_quantity`, `available_quantity`, `stock_status`
(`in_stock`/`low_stock`/`out_of_stock`). *(Management uchun qo'shimcha:
`purchase_price`, `selling_price`.)*
Qo'shishда `quantity` + `warehouse_location` yuborilsa Stock avtomatik yaratiladi.

### Kirim — omborda bor mahsulotdan yana kelganda
`POST /warehouse/products/{id}/add-stock/`
```json
{ "quantity": 20, "warehouse_location": "B-2-3",
  "asos": "Kirim orderi №77",           // MAJBURIY
  "contract_number": "SH-2026/051",     // ixtiyoriy
  "faktura": "F-2026/900" }             // ixtiyoriy
```
- Qoldiq oshadi + kutayotgan buyurtmalarga avtomatik bron
- Javobda `allocated_orders` — qaysi buyurtmaga qancha taqsimlangani
> Stock sonini qo'lda tahrirlash o'rniga shu ishlatilsin (asos + avto-taqsimot).

### Shu mahsulotning shartnomalari
`GET /warehouse/products/{id}/contracts/` — barcha holatlar (buyurtma/zakaz/kirim)
shartnoma + asos + faktura bilan.

### Kategoriyalar / Qoldiqlar
`GET/POST /warehouse/categories/` — MPTT daraxt (`parent → children`).
`GET/POST /warehouse/stocks/` — filtr `?product=`, `?status=low_stock`, `?category=`.

---

## 7. Sotuvlar (Sales)

`GET/POST /sales/` · `GET/PATCH/DELETE /sales/{id}/` · `POST /sales/bulk/`
Filtr: `?product=`, `?client=`, `?sold_date=`.

```json
POST /sales/
{ "product": 12, "quantity": 2, "sold_price": "3900000",
  "client": "<uuid>", "sold_to": "Ali", "destination": "Toshkent", "sold_date": "2026-07-02" }
```
- FIFO tartibida ombordan ayiriladi; faqat `available_quantity` yetsa sotiladi
- **Operator javobida** `sold_price`/`total_amount`/`profit` **yo'q** (write-only)

---

## 8. Shartnomalar reestri

`GET /orders/contracts/` — barcha holatlar reestri (read-only).
Filtr: `?product=`, `?contract_number=`, `?source_type=`, `?order=`, `?zakaz=`.

`source_type`: `order_created` · `order_edited` · `order_fulfilled` ·
`order_cancelled` · `zakaz_created` · `zakaz_confirmed` · `zakaz_ordered` ·
`zakaz_received` · `zakaz_cancelled` · `stock_in`.

---

## 9. Boshqa modullar

### Mijozlar (Clients) — `can_view_clients` ruxsati kerak
`GET/POST /clients/` · `GET/PATCH/DELETE /clients/{id}/`
`id` — UUID. `full_name`/`inn`/`phone` — javobda ochiq matn (bazada shifrlangan).

### Rasxod (Expenses)
`GET /expenses/expense-types/` · `GET/POST /expenses/expense-subtypes/`
`GET/POST /expenses/expenses/` · `GET /expenses/expenses/summary/`
Filtr: `?expense_type=`, `?sub_type=`, `?currency=`, `?date_from=&date_to=`.

### Bildirishnomalar (Notifications)
`GET /notifications/` · `GET /notifications/?is_read=false`
`POST /notifications/{id}/mark_read/` · `POST /notifications/mark_all_read/`

### Hisobotlar (Accountant/Management)
`GET /reports/summary/` · `/reports/warehouse/` · `/reports/cash/` ·
`/reports/expenses/` · `/reports/top-products/`
Excel: `/reports/excel/sales/` · `/stock/` · `/expenses/` · `/payments/`
(hammasi `?date_from=&date_to=`). **Operatorга Excel yopiq (403).**

---

## 10. Frontend uchun muhim eslatmalar (checklist)

- [ ] Har so'rovда `Authorization: Bearer` header
- [ ] Buyurtма yaratish/tahrir: `contract_number` majburiy, tahrirда `asos` majburiy
- [ ] Buyurtма qatorlari `items[]` — o'zgartirish `{id, quantity}`, qo'shish
      `{product, quantity, unit_price}`, o'chirish `{id, remove: true}`
- [ ] Yetkazish/bekor/zakaz tugmalari: modal orqali `contract_number` + `asos`
      (+ ixtiyoriy `faktura`) so'rash — aks holda 400
- [ ] Zakaz status (Management): tasdiqlashда shartnoma, qabulda faktura so'rash
- [ ] Kassa "qo'shimcha to'lov" tugmasi → `/cash/payments/{id}/pay/`
- [ ] Kirim tugmasi (mahsulot sahifasi) → `/warehouse/products/{id}/add-stock/`
- [ ] Operator rolда narx/summa maydonlari yo'qligiga tayyor bo'lish
- [ ] `backorder_qty` ("Zakaz kutilmoqda") — yetkazilgan/bekorда 0
- [ ] 400 xatoда maydon → xabar ro'yxatini formada ko'rsatish
