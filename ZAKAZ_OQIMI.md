# Qoldiq yetmaganda "Zakaz berish" oqimi (bitta va ko'p mahsulot)
> **Versiya:** 2026-07-02 | Backend: Django REST Framework
> Bu hujjat mahsulot yetmay qolganda **buyurtma** va **savdo**da nima
> bo'lishini — hamda "Zakaz berish" tugmasi qanday paydo bo'lishini
> tushuntiradi. Bitta va bir nechta mahsulot (bulk) uchun bir xil.

---

## Qisqa javob

| Holat | Buyurtma (Order) | Savdo (Sale) |
|-------|------------------|--------------|
| Qoldiq **yetarli** | To'liq bron (`reserved`) | Sotiladi, ombor kamayadi |
| Qoldiq **qisman** | Qisman bron + backorder (`partial`) | ❌ Sota olmaysiz → Zakaz taklif qilinadi |
| Qoldiq **umuman yo'q** | Backorder (`pending`) | ❌ Sota olmaysiz → Zakaz taklif qilinadi |
| **Bulk** (ko'p mahsulot) | Har biri alohida — yetmagani backorder | Bittasi yetmasa butun so'rov to'xtaydi (atomic) |

> **Muhim o'zgarish:** endi buyurtma **hech qachon xato bermaydi** qoldiq
> yetmasa ham — pending/backorder bo'lib qoladi va undan Zakaz beriladi.
> Bu **bitta va bulk** uchun bir xil ishlaydi.

---

## 1. Buyurtma (Order) — qoldiq yetmasa

Buyurtma har doim yaratiladi. `reserve()` mavjud qoldiqdan bron ajratadi,
qolgani `backorder_qty` bo'lib qoladi.

### Bitta mahsulot
```json
POST /api/v1/orders/
{ "product": 12, "quantity": 10, "unit_price": "3900000" }
```
Omborda 3 ta bor bo'lsa:
```json
{
  "id": 91, "quantity": 10,
  "reserved_qty": 3,
  "backorder_qty": 7,          ← yetishmaydi, zakaz kerak
  "has_active_zakaz": false,   ← hali zakaz yo'q → tugma ko'rinadi
  "status": "partial"
}
```
Omborda 0 ta bo'lsa:
```json
{
  "reserved_qty": 0,
  "backorder_qty": 10,
  "has_active_zakaz": false,
  "status": "pending"          ← to'liq zakaz kutilmoqda
}
```

### Ko'p mahsulot (bulk)
```json
POST /api/v1/orders/bulk/
{
  "client": "<uuid>",
  "due_date": "2026-08-01",
  "items": [
    { "product": 12, "quantity": 10, "unit_price": "3900000" },
    { "product": 7,  "quantity": 2,  "unit_price": "1200000" }
  ]
}
```
Javob — **har biri alohida**, yetmagani backorder bo'ladi, xato **yo'q**:
```json
{
  "orders": [
    { "product": 12, "quantity": 10, "reserved_qty": 3, "backorder_qty": 7, "status": "partial",  "has_active_zakaz": false },
    { "product": 7,  "quantity": 2,  "reserved_qty": 2, "backorder_qty": 0, "status": "reserved", "has_active_zakaz": false }
  ]
}
```

> **Tuzatilgan xatolik:** avval bulk'da bitta mahsulot tugagan bo'lsa
> BUTUN so'rov rad etilardi. Endi har biri mustaqil — yetmagani backorder
> bo'lib, undan zakaz beriladi.

---

## 2. "Zakaz berish" tugmasi qachon ko'rinadi

Frontend har bir buyurtma qatori uchun:
```js
const showZakazButton = order.backorder_qty > 0 && !order.has_active_zakaz;
```

| `backorder_qty` | `has_active_zakaz` | Tugma |
|:---:|:---:|:---:|
| `0` | — | ❌ yashirin (hammasi bron) |
| `> 0` | `false` | ✅ **"Zakaz berish"** ko'rinadi |
| `> 0` | `true` | ❌ yashirin (zakaz allaqachon berilgan) |

**Zakaz berish** bosilganda:
```json
POST /api/v1/orders/zakaz/
{ "product": 12, "quantity": 7, "supplier": "..." }
```
So'ng `has_active_zakaz` → `true` bo'ladi va tugma yo'qoladi (takroriy zakaz oldini oladi).

Zakaz `received`/`cancelled` bo'lsa — `has_active_zakaz` yana `false` bo'ladi.

---

## 3. Savdo (Sale) — qoldiq yetmasa

Savdo **jismonan** ombordan chiqaradi — yo'q narsani sotib bo'lmaydi.
Shuning uchun qoldiq yetmasa **xato** qaytariladi (bu to'g'ri xatti-harakat).

### Bitta mahsulot
```json
POST /api/v1/sales/
{ "product": 12, "quantity": 5, "sold_price": "3900000", "sold_date": "2026-07-02" }
```
Omborda 3 ta bo'lsa:
```json
// 400 Bad Request
{
  "quantity": [
    "\"HP LaserJet\" uchun sotish mumkin bo'lgan qoldiq yetarli emas. Jami: 3, bron: 0, mavjud: 3, so'ralgan: 5."
  ]
}
```

### Ko'p mahsulot (bulk)
```json
POST /api/v1/sales/bulk/
{
  "sold_date": "2026-07-02",
  "items": [
    { "product": 12, "quantity": 5, "sold_price": "3900000" },
    { "product": 7,  "quantity": 2, "sold_price": "1200000" }
  ]
}
```
Bitta mahsulot yetmasa — **hech qaysi savdo yaratilmaydi** (`transaction.atomic`):
```json
// 400 Bad Request
{
  "items": [
    "\"HP LaserJet\" — sotish mumkin bo'lgan qoldiq yetarli emas (mavjud: 3, so'ralgan: 5)."
  ]
}
```

### Savdoda "zakaz berish" oqimi (frontend)
Savdo backend'da avtomatik zakazga o'tmaydi (chunki sotib bo'lmaydi).
O'rniga **frontend** shu xatoni ushlab:
1. Qaysi mahsulot(lar) yetmayotganini ko'rsatadi
2. "Bu mahsulotni bron qilib, zakaz berasizmi?" deb taklif qiladi
3. Rozi bo'lsa → `POST /orders/` (buyurtma yaratadi) → keyin backorder'dan `POST /orders/zakaz/`

> Ya'ni: **savdo qoldiqqa qarab bloklanadi, buyurtma esa har doim yaraladi va zakazga yo'l ochadi.**

---

## 4. Yaxlit oqim diagrammasi

```
        MIJOZ MAHSULOT SO'RADI
                 │
     ┌───────────┴────────────┐
     ▼                         ▼
  SAVDO (darhol olib ketadi)   BUYURTMA (keyin oladi / band qiladi)
     │                         │
  qoldiq yetadimi?          har doim yaratiladi
     │                         │
  ┌──┴───┐                 reserved_qty = mavjud
  ▼      ▼                 backorder_qty = yetishmagan
 ha     yo'q                    │
  │      │                 backorder > 0 ?
sotiladi │                      │
ombor↓   ▼                 ┌────┴────┐
      XATO                 ha       yo'q
   (400)                    │        │
      │              "Zakaz berish"  to'liq bron
      ▼                 tugmasi      (reserved)
 frontend zakaz            │
 taklif qiladi ──────► POST /orders/zakaz/
                           │
                     status: new → ... → received
                           │
                     ombor to'ldiriladi
                           │
                     pending buyurtmalar
                     avtomatik bron oladi
```

---

## 5. O'zgarishlar (shu tuzatishda)

| Fayl | O'zgarish |
|------|-----------|
| `apps/orders/serializers.py` | `OrderSerializer.validate` — `available<=0` hard blok **olib tashlandi** |
| `apps/orders/serializers.py` | `OrderBulkCreateSerializer.validate_items` — bitta mahsulot tugasa butun so'rovni rad etish **olib tashlandi** |

Natija: buyurtma (bitta yoki bulk) qoldiq yetmasa ham yaratiladi, backorder →
"Zakaz berish" tugmasi → zakaz. Savdo esa oldingidek qoldiqqa qarab bloklanadi.

---

## 6. Frontend uchun qisqa qoidalar

```js
// BUYURTMA qatori
const showZakaz = order.backorder_qty > 0 && !order.has_active_zakaz;

// SAVDO xatosi (bulk yoki bitta)
try {
  await api.post('/sales/bulk/', payload);
} catch (e) {
  // e.response.data.items — qaysi mahsulot yetmagani
  // → "Buyurtma qilib zakaz berasizmi?" modalini ko'rsat
}
```

---

*Oxirgi yangilanish: 2026-07-02 | Backend: krv006*
