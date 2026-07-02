# Buyurtma (Order/Bron) va Zakaz tizimi
> **Versiya:** 2026-07-02 | Backend: Django REST Framework
> Bu fayl `apps/orders/` app ichidagi ikkita yangi modul — **Order (Bron)** va **Zakaz (Etkazuvchidan buyurtma)** — haqida to'liq texnik va API hujjat.

---

## Mundarija
1. [Muammo va yechim](#1-muammo-va-yechim)
2. [Order (Mijoz bron/buyurtmasi)](#2-order-mijoz-bronbuyurtmasi)
3. [Zakaz (Etkazuvchidan buyurtma)](#3-zakaz-etkazuvchidan-buyurtma)
4. [Ikkalasi qanday bog'lanadi](#4-ikkalasi-qanday-boglanadi)
5. [Permission jadvali](#5-permission-jadvali)
6. [API endpointlar to'liq ro'yxati](#6-api-endpointlar-toliq-royxati)
7. [Field lug'ati](#7-field-lugati)
8. [Xato holatlari](#8-xato-holatlari)
9. [Fake data (seed)](#9-fake-data-seed)
10. [Migratsiya](#10-migratsiya)

---

## 1. Muammo va yechim

**Real hayotiy stsenariy:**
> Mijoz keldi, 10 ta printer so'radi. Omborda faqat 3 ta bor. Qolgan 7 tasini biz **etkazuvchidan zakaz qilishimiz** kerak. Bu 3 ta esa endi **shu mijozga bron** bo'lishi kerak — boshqa birortasiga sota olmaymiz.

Bu ikki alohida jarayon, shuning uchun ikki alohida model:

| Model | Nima uchun | Kim yaratadi | Kim status o'zgartiradi |
|-------|-----------|---------------|--------------------------|
| **Order** | Mijoz buyurtmasi — ombordagi qoldiqni **bron** qiladi | Operator / Manager | Tizim avtomatik (+ `/fulfill/`, `/cancel/` action) |
| **Zakaz** | Etkazuvchidan mahsulot **buyurtma qilish** (yetishmagan qism uchun) | Operator / Manager | **Faqat Manager** |

---

## 2. Order (Mijoz bron/buyurtmasi)

### Qachon ishlatiladi
Mijoz mahsulot so'raganda, va omborda **kamida 1 dona mavjud** (`available_quantity > 0`) bo'lganda.

> ⚠️ **Agar `available_quantity == 0` bo'lsa — Order yaratib bo'lmaydi!**
> Bunday holda avval [Zakaz](#3-zakaz-etkazuvchidan-buyurtma) berish kerak.

### Holat (status) diagrammasi
```
                    ┌──────────┐
     yaratildi ───► │ pending  │  (hech narsa bron qilinmagan)
                    └────┬─────┘
                         │ qisman qoldiq bor
                         ▼
                    ┌──────────┐
                    │ partial  │  (reserved_qty < quantity)
                    └────┬─────┘
                         │ to'liq qoldiq keldi
                         ▼
                    ┌──────────┐
                    │ reserved │  (reserved_qty == quantity)
                    └────┬─────┘
                         │ /fulfill/
                         ▼
                    ┌───────────┐
                    │ fulfilled │  (yakuniy, ombordan ayirildi)
                    └───────────┘

     har qanday holatdan ──► /cancel/ ──► cancelled
```

### Ishlash mexanizmi

**1. Order yaratilganda (`POST /orders/`):**
```
1. available_quantity tekshiriladi. Agar 0 bo'lsa → 400 xato.
2. Ombordagi Stock yozuvlaridan FIFO tartibida bron ajratiladi
   (Stock.reserved_quantity ortadi).
3. status avtomatik hisoblanadi:
   - reserved_qty == quantity → "reserved"
   - 0 < reserved_qty < quantity → "partial"
   - reserved_qty == 0 (bu holat amalda kam, chunki available>0 talab qilinadi)
```

**2. Yangi qoldiq kelganda (Stock PATCH yoki Zakaz.receive()):**
```
allocate_pending_orders(product) avtomatik chaqiriladi:
  - product bo'yicha barcha "pending"/"partial" Order'lar olinadi
  - due_date bo'yicha tartiblanadi (eng yaqin deadline birinchi!)
  - har biriga navbat bilan bron ajratiladi
```

**3. `/fulfill/` (yetkazildi):**
```
- reserved_qty ombordan HAM quantity, HAM reserved_quantity dan ayiriladi
  (ya'ni mahsulot jismoniy chiqib ketdi)
- status → "fulfilled"
- allocate_pending_orders() qayta chaqiriladi (boshqalar uchun joy ochilishi mumkin)
```

**4. `/cancel/` (bekor qilish):**
```
- Bron bo'shatiladi (Stock.reserved_quantity kamayadi, quantity o'zgarmaydi)
- status → "cancelled"
- allocate_pending_orders() chaqiriladi — bo'shagan joy boshqa
  pending buyurtmalarga avtomatik beriladi
```

### Operator mahsulotni "bron qilingan"ligini qanday ko'radi

`GET /warehouse/products/{id}/` javobida:
```json
{
  "quantity_in_stock": 10,
  "reserved_quantity": 7,
  "available_quantity": 3,
  "stock_status": "low_stock"
}
```

`available_quantity = 0` bo'lsa — operator bu mahsulotni **boshqa hech kimga sota olmaydi** (Sale serializer `available_quantity` ga qarab tekshiradi, aks holda 400 xato).

---

## 3. Zakaz (Etkazuvchidan buyurtma)

### Qachon ishlatiladi
Mahsulot omborda yetarli emas (yoki umuman yo'q) va yetkazuvchidan **jismoniy buyurtma** berish kerak bo'lganda.

### Holat (status) diagrammasi
```
   yaratildi ──► new ──► confirmed ──► ordered ──► received
                  │           │            │
                  └───────────┴────────────┴──► cancelled
```

| Status | Ma'nosi | Kim o'zgartiradi |
|--------|---------|-------------------|
| `new` | Yangi — hali hech kim ko'rmagan | Avtomatik (yaratilganda) |
| `confirmed` | Tasdiqlandi — buyurtma berish rejalashtirilgan | **Manager** |
| `ordered` | Etkazuvchiga yuborildi | **Manager** |
| `received` | Qabul qilindi — ombor to'ldirildi | **Manager** |
| `cancelled` | Bekor qilindi | **Manager** |

### ⚠️ MUHIM QOIDA — Ruxsatlar
```
✅ Operator:  Zakaz YARATA oladi (status avtomatik "new")
✅ Operator:  supplier, expected_date, comment, warehouse_location ni PATCH qila oladi
❌ Operator:  status ni O'ZGARTIRA OLMAYDI

✅ Manager:   status ni istalgan bosqichga o'zgartira oladi
✅ Manager:   received_qty ni kiritadi (status="received" bo'lganda)
```

Status boshqa userga tegishli emas — `ZakazSerializer.update()` da tekshiriladi:
```python
if new_status and new_status != instance.status:
    if not user.is_management:
        raise PermissionDenied(
            'Status faqat boshqaruv (Management) tomonidan o\'zgartirilishi mumkin.'
        )
```

### `status = "received"` bo'lganda avtomatik nima sodir bo'ladi

```
PATCH /orders/zakaz/{id}/
{ "status": "received", "received_qty": 45, "warehouse_location": "B-2-3" }
```

1. **Ombor to'ldiriladi:** `Stock` yozuvi (product + warehouse_location) topiladi yoki yaratiladi, `quantity += received_qty`
2. **Pending buyurtmalarga bron:** `allocate_pending_orders(product)` chaqiriladi — barcha kutayotgan Order'lar (`pending`/`partial`) `due_date` bo'yicha tartiblanib, navbat bilan bron oladi
3. **Bildirishnoma yopiladi:** agar `available_quantity > min_quantity` bo'lsa, "Qoldiq kam!" bildirishnomasi avtomatik `is_read=True` qilinadi

> Agar `received_qty` berilmasa — `quantity` (asl zakaz qilingan miqdor) ishlatiladi.

---

## 4. Ikkalasi qanday bog'lanadi

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Mijoz 10 ta so'raydi, omborda 3 ta bor                        │
│     → POST /orders/  { product: 12, quantity: 10 }                │
│     → Order: reserved_qty=3, backorder_qty=7, status="partial"    │
├─────────────────────────────────────────────────────────────────┤
│  2. Operator yetishmagan 7 (yoki ko'proq) tani zakaz qiladi        │
│     → POST /orders/zakaz/  { product: 12, quantity: 20 }          │
│     → Zakaz: status="new"                                         │
├─────────────────────────────────────────────────────────────────┤
│  3. Manager zakazni boshqaradi                                    │
│     → PATCH /orders/zakaz/{id}/  { status: "confirmed" }          │
│     → PATCH /orders/zakaz/{id}/  { status: "ordered" }            │
├─────────────────────────────────────────────────────────────────┤
│  4. Tovar keldi — Manager qabul qiladi                            │
│     → PATCH /orders/zakaz/{id}/                                   │
│        { status: "received", received_qty: 20,                   │
│          warehouse_location: "B-2-3" }                            │
│     → Ombor +20, Order (1-qadamdagi) avtomatik to'ldiriladi:       │
│        reserved_qty=10, status="reserved" (backorder_qty=0)       │
├─────────────────────────────────────────────────────────────────┤
│  5. Mahsulot mijozga topshiriladi                                 │
│     → POST /orders/{id}/fulfill/                                  │
│     → Order: status="fulfilled", ombordan 10 ta rasman ayrildi    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Permission jadvali

| Amal | Operator | Accountant | Management |
|------|:--------:|:----------:|:----------:|
| **Order** — ro'yxat/ko'rish | ✅ | ✅ | ✅ |
| **Order** — yaratish | ✅ | ❌ | ✅ |
| **Order** — PATCH (due_date, comment) | ✅ | ❌ | ✅ |
| **Order** — `/fulfill/` | ✅ | ❌ | ✅ |
| **Order** — `/cancel/` | ✅ | ❌ | ✅ |
| **Zakaz** — ro'yxat/ko'rish | ✅ | ✅ | ✅ |
| **Zakaz** — yaratish | ✅ | ✅ | ✅ |
| **Zakaz** — PATCH (supplier, comment va h.k.) | ✅ | ✅ | ✅ |
| **Zakaz** — `status` o'zgartirish | ❌ | ❌ | ✅ **faqat** |
| **Zakaz** — `received_qty` kiritish | ❌ | ❌ | ✅ **faqat** |

---

## 6. API endpointlar to'liq ro'yxati

### Order (Bron)
```
GET    /api/v1/orders/                    — ro'yxat
POST   /api/v1/orders/                    — yangi buyurtma + avtomatik bron
GET    /api/v1/orders/{id}/               — bitta buyurtma
PATCH  /api/v1/orders/{id}/               — due_date / comment yangilash
POST   /api/v1/orders/{id}/fulfill/       — yetkazildi deb belgilash
POST   /api/v1/orders/{id}/cancel/        — bekor qilish (bron bo'shatiladi)
```
> **DELETE yo'q!** O'chirish o'rniga `/cancel/` ishlatiladi.
> **PUT yo'q!** Faqat PATCH — to'liq almashtirish mantiqsiz (reserved_qty/status tizim tomonidan boshqariladi).

### Zakaz
```
GET    /api/v1/orders/zakaz/              — ro'yxat
POST   /api/v1/orders/zakaz/              — yangi zakaz (status="new")
GET    /api/v1/orders/zakaz/{id}/         — bitta zakaz
PATCH  /api/v1/orders/zakaz/{id}/         — yangilash (status faqat Manager)
```
> **DELETE va PUT yo'q.** Zakazni bekor qilish uchun `{ "status": "cancelled" }` PATCH qilinadi (Manager).

---

## 7. Field lug'ati

### Order
| Field | Tip | Tavsif |
|-------|-----|--------|
| `id` | int | — |
| `client` | UUID, null | Mijoz (ixtiyoriy) |
| `client_name` | string, read-only | Mijoz nomi |
| `product` | int | Mahsulot ID |
| `product_name` | string, read-only | Mahsulot nomi |
| `quantity` | int | Jami buyurtma qilingan soni |
| `reserved_qty` | int, read-only | Hozirda bron qilingan (omborda ajratilgan) |
| `backorder_qty` | int, read-only | `quantity - reserved_qty` — hali yo'q, zakaz kerak |
| `due_date` | date, null | Yetkazish muddati |
| `status` | enum, read-only | `pending` / `partial` / `reserved` / `fulfilled` / `cancelled` |
| `comment` | text, null | Izoh |
| `created_at` | datetime, read-only | — |

### Zakaz
| Field | Tip | Tavsif |
|-------|-----|--------|
| `id` | int | — |
| `product` | int | Mahsulot ID |
| `product_name` | string, read-only | Mahsulot nomi |
| `quantity` | int | Zakaz qilingan miqdor |
| `received_qty` | int, read-only (Manager PATCH qiladi) | Qabul qilingan miqdor |
| `supplier` | string, null | Etkazuvchi nomi/manzili |
| `status` | enum | `new` / `confirmed` / `ordered` / `received` / `cancelled` |
| `status_display` | string, read-only | O'zbekcha nom (masalan "Qabul qilindi") |
| `expected_date` | date, null | Kutilayotgan kelish sanasi |
| `warehouse_location` | string, null | Qaysi joyga qo'yiladi (received bo'lganda) |
| `created_by` | int, read-only | Kim yaratgan |
| `created_by_name` | string, read-only | — |
| `comment` | text, null | — |
| `created_at` | datetime, read-only | — |

---

## 8. Xato holatlari

### Order yaratishda — mahsulot butunlay tugagan
```
POST /orders/
{ "product": 12, "quantity": 5 }
```
```json
// 400 Bad Request
{
  "product": [
    "\"HP LaserJet\" mahsuloti to'liq bron qilingan yoki omborda qolmagan (mavjud: 0 dona). Mahsulot kelishi uchun Zakaz bering."
  ]
}
```
> **Frontend uchun signal:** shu xato kelsa — foydalanuvchiga "Zakaz berish" formasini taklif qiling (`POST /orders/zakaz/`).

### Zakaz status — operator o'zgartirmoqchi bo'lsa
```
PATCH /orders/zakaz/{id}/
{ "status": "confirmed" }
```
Operator token bilan yuborilsa:
```json
// 403 Forbidden
{ "detail": "Status faqat boshqaruv (Management) tomonidan o'zgartirilishi mumkin." }
```

### Zakaz — allaqachon yakunlangan statusni o'zgartirish
```json
// 400 Bad Request
{ "detail": "\"Qabul qilindi\" statusidagi zakazni o'zgartirib bo'lmaydi." }
```

### Order `/fulfill/` — bron yo'q bo'lsa
```json
// 400 Bad Request
{ "detail": "Bron qilingan miqdor yo'q. Avval omborda qoldiq bo'lishi kerak." }
```

### Order `/cancel/` — allaqachon yakunlangan
```json
// 400 Bad Request
{ "detail": "\"Yetkazildi\" holatidagi buyurtmani bekor qilib bo'lmaydi." }
```

---

## 9. Fake data (seed)

```bash
python manage.py seed --clear                    # hammasi (orders + zakazlar bilan)
python manage.py seed --orders 30 --zakazlar 20   # sonlarni sozlash
```

**Zakaz seed statuslar taqsimoti:**
| Status | Ehtimollik |
|--------|-----------|
| `new` | 25% |
| `confirmed` | 15% |
| `ordered` | 20% |
| `received` | 30% (ombor haqiqatan to'ldiriladi!) |
| `cancelled` | 10% |

> `received` statusidagi fake zakazlar **haqiqatan** `Stock.quantity` ni oshiradi — real oqimni simulyatsiya qilish uchun.

**Order seed:** 20 ta buyurtma yaratiladi, mavjud qoldiqdan bron ajratiladi (ba'zilari `partial`/`pending` qoladi — omborda yetmasa), so'ng bir nechtasi `fulfilled` va `cancelled` ga o'tkaziladi (real holatni aks ettirish uchun).

---

## 10. Migratsiya

Server yangi kodni olgandan keyin:
```bash
git pull origin main
python manage.py makemigrations orders
python manage.py migrate
python manage.py seed --clear     # ixtiyoriy — test ma'lumotlari uchun
```

**Yangi jadvallar:**
- `orders_order` — Order (bron)
- `orders_zakaz` — Zakaz (etkazuvchidan buyurtma)

**O'zgargan jadval:**
- `warehouse_stock` — `reserved_quantity` field qo'shildi

---

## Frontend uchun UI tavsiyalari

### Order (Bron) sahifasi
- `status` bo'yicha tab/filter: Zakaz kutilmoqda / Qisman bron / To'liq bron / Yetkazilgan / Bekor
- `backorder_qty > 0` bo'lsa qizil badge: "7 dona yetishmayapti"
- Bunday holatda "Zakaz berish" tugmasi ko'rsatilsin (Zakaz formasiga o'tadi, `product` va `quantity=backorder_qty` bilan avtomatik to'ldirilgan)
- `due_date` yaqinlashganda (< 3 kun) sariq ogohlantirish

### Zakaz sahifasi
- Operator: faqat "Yangi zakaz" tugmasi va o'z yaratganlarini ko'rish/tahrirlash (supplier/comment)
- Manager: status dropdown (`new → confirmed → ordered → received`) + "Bekor qilish"
- `status = "received"` ga o'tkazish formasi alohida modal: `received_qty` + `warehouse_location` majburiy inputlar bilan
- Status badge ranglari: `new`=ko'k, `confirmed`=binafsha, `ordered`=to'q sariq, `received`=yashil, `cancelled`=kulrang

---

*Oxirgi yangilanish: 2026-07-02 | Backend: krv006*
