# Savdo (Sale) va Buyurtma (Order) — farqi va bulk (ko'p mahsulot)
> **Versiya:** 2026-07-02 | Backend: Django REST Framework
> Bu hujjat Savdo va Buyurtma orasidagi farqni, hamda ikkalasida ham
> **bir vaqtda bir nechta mahsulot** qo'shish (bulk) imkoniyatini tushuntiradi.

---

## Mundarija
1. [Savdo va Buyurtma — nima farqi bor](#1-savdo-va-buyurtma--nima-farqi-bor)
2. [Nega birlashtirilmaydi](#2-nega-birlashtirilmaydi)
3. [Bulk — Buyurtma (bir nechta mahsulot)](#3-bulk--buyurtma-bir-nechta-mahsulot)
4. [Bulk — Savdo (bir nechta mahsulot)](#4-bulk--savdo-bir-nechta-mahsulot)
5. [Xato holatlari](#5-xato-holatlari)
6. [Frontend UI tavsiyalari](#6-frontend-ui-tavsiyalari)

---

## 1. Savdo va Buyurtma — nima farqi bor

| | **Savdo (Sale)** | **Buyurtma / Bron (Order)** |
|---|---|---|
| **Ma'nosi** | Mahsulot sotildi va ketdi | Mahsulot band qilindi, hali ketmadi |
| **Ombor qoldig'i** | **Kamayadi** (`quantity ↓`) | **Kamaymaydi** — faqat bron (`reserved ↑`) |
| **Pul / foyda** | Hisoblanadi | Hali yo'q |
| **Qoldiq yetmasa** | ❌ Xato — sota olmaysiz | ✅ Qabul qiladi — zakaz kutiladi |
| **Kelajagi** | Yakuniy holat | `fulfill` → ombordan chiqadi |
| **Narx fieldi** | `sold_price` | `unit_price` |
| **Endpoint** | `/api/v1/sales/` | `/api/v1/orders/` |

---

## 2. Nega birlashtirilmaydi

Real oqim (bir hodisa emas, uch bosqich):
```
1. Mijoz keldi, 10 ta so'radi, omborda 3 ta bor
   → BUYURTMA:  3 ta bron + 7 ta zakaz kutilmoqda
   (hali sotilmagan — pul yo'q, ombor kamaymagan)

2. Zakaz keldi, ombor to'ldi
   → Buyurtma to'liq BRON (reserved) bo'ldi

3. Mijoz kelib mahsulotni oldi
   → SAVDO:  endi haqiqatan sotildi (ombor kamaydi, pul kirdi)
```

Agar birlashtirilsa:
- "bron qilingan" va "sotilgan" farqi yo'qoladi
- omborda bron turgan mahsulotni boshqa mijozga sotib yuborish mumkin bo'lib qoladi (bron himoyasi buziladi)
- kassa/foyda hisoboti buziladi (bron — pul emas)

> **Xulosa:** ikkalasi alohida qoladi. Bulk API o'xshashligi — shунчaki qulaylik, ichki mantiq boshqa.

---

## 3. Bulk — Buyurtma (bir nechta mahsulot)

### Endpoint
```
POST /api/v1/orders/bulk/
```

### So'rov
```json
{
  "client": "550e8400-e29b-41d4-a716-446655440000",
  "due_date": "2026-08-01",
  "items": [
    { "product": 12, "quantity": 4, "unit_price": "3900000" },
    { "product": 7,  "quantity": 2, "unit_price": "1200000", "comment": "tezkor" }
  ]
}
```

| Field | Joyi | Tavsif |
|-------|------|--------|
| `client` | umumiy | Mijoz (ixtiyoriy) |
| `due_date` | umumiy | Yetkazish muddati (ixtiyoriy) |
| `items[].product` | qator | Mahsulot ID |
| `items[].quantity` | qator | Miqdor |
| `items[].unit_price` | qator | Birlik narxi (ixtiyoriy) |
| `items[].comment` | qator | Izoh (ixtiyoriy) |

### Javob (201)
```json
{
  "orders": [
    {
      "id": 91, "product": 12, "quantity": 4,
      "unit_price": "3900000.00", "total": "15600000.00",
      "reserved_qty": 4, "backorder_qty": 0,
      "has_active_zakaz": false, "status": "reserved"
    },
    {
      "id": 92, "product": 7, "quantity": 2,
      "unit_price": "1200000.00", "total": "2400000.00",
      "reserved_qty": 0, "backorder_qty": 2,
      "has_active_zakaz": false, "status": "pending"
    }
  ]
}
```

> Har bir mahsulot **alohida Order** yozuvi bo'ladi. Qoldiq yetmasa `pending`/`partial`
> holida saqlanadi (xato bermaydi — bu bron tizimining maqsadi).

---

## 4. Bulk — Savdo (bir nechta mahsulot)

### Endpoint
```
POST /api/v1/sales/bulk/
```

### So'rov
```json
{
  "client": "550e8400-e29b-41d4-a716-446655440000",
  "sold_to": "Aliyev Vohid",
  "destination": "Toshkent",
  "sold_date": "2026-07-02",
  "items": [
    { "product": 12, "quantity": 4, "sold_price": "3900000" },
    { "product": 7,  "quantity": 2, "sold_price": "1200000" }
  ]
}
```

| Field | Joyi | Tavsif |
|-------|------|--------|
| `client` | umumiy | Mijoz (ixtiyoriy) |
| `sold_to` | umumiy | Xaridor ismi (ixtiyoriy) |
| `destination` | umumiy | Manzil (ixtiyoriy) |
| `sold_date` | umumiy | Sotuv sanasi (majburiy) |
| `items[].product` | qator | Mahsulot ID |
| `items[].quantity` | qator | Miqdor |
| `items[].sold_price` | qator | Birlik sotuv narxi (majburiy) |
| `items[].comment` | qator | Izoh (ixtiyoriy) |

### Javob (201)
```json
{
  "sales": [
    {
      "id": 210, "product": 12, "quantity": 4,
      "sold_price": "3900000.00", "total_amount": "15600000.00",
      "profit": "2400000.00", "sold_date": "2026-07-02"
    },
    {
      "id": 211, "product": 7, "quantity": 2,
      "sold_price": "1200000.00", "total_amount": "2400000.00",
      "profit": "600000.00", "sold_date": "2026-07-02"
    }
  ]
}
```

> Har bir mahsulot **alohida Sale** yozuvi bo'ladi, ombordan **FIFO** tartibida ayiriladi.
> Biror mahsulot qoldig'i yetmasa — **hech qaysi savdo yaratilmaydi** (`transaction.atomic`).

---

## 5. Xato holatlari

### Savdo bulk — qoldiq yetmasa
```json
// 400 Bad Request
{
  "items": [
    "\"HP LaserJet\" — sotish mumkin bo'lgan qoldiq yetarli emas (mavjud: 3, so'ralgan: 5)."
  ]
}
```
> Butun so'rov bekor qilinadi — bironta ham Sale saqlanmaydi.

### Buyurtma bulk — mahsulot butunlay tugagan
```json
// 400 Bad Request
{
  "items": [
    "\"HP LaserJet\" — to'liq bron qilingan yoki omborda yo'q (mavjud: 0). Zakaz bering."
  ]
}
```

### Bo'sh items
```json
// 400 Bad Request
{ "items": ["Kamida bitta mahsulot kiritilishi kerak."] }
```

---

## 6. Frontend UI tavsiyalari

### Umumiy forma dizayni (ikkalasi uchun)
```
┌─────────────────────────────────────────────┐
│  Mijoz:  [ Aliyev Kompaniyasi ▼ ]            │  ← umumiy (bir marta)
│  Sana:   [ 02.07.2026 ]                       │
│  Manzil: [ Toshkent ]        (faqat savdo)    │
├─────────────────────────────────────────────┤
│  Mahsulotlar:                    [ + Qator ]  │
│  ┌─────────────────────────────────────────┐ │
│  │ Mahsulot ▼ | Miqdor | Narx | [🗑]         │ │  ← qator (ko'p marta)
│  │ Mahsulot ▼ | Miqdor | Narx | [🗑]         │ │
│  └─────────────────────────────────────────┘ │
│  Jami: 18 000 000 so'm                        │  ← avtomatik hisob
│                            [ Saqlash ]        │
└─────────────────────────────────────────────┘
```

- Har qator uchun mahsulot tanlanganda `available_quantity` ko'rsatilsin
- **Savdo:** `quantity > available_quantity` bo'lsa qator qizil (saqlashga yo'l qo'ymaslik)
- **Buyurtma:** `quantity > available_quantity` bo'lsa "X ta zakaz kutiladi" deb ko'rsatilsin (bloklamaslik)
- "Jami" avtomatik: `Σ (quantity × narx)`
- Operator uchun savdoda narx inputlari yashirin bo'lishi mumkin (rolga qarab)

### Bitta mahsulot uchun (eski usul ham ishlaydi)
```
POST /sales/    { product, quantity, sold_price, ... }
POST /orders/   { product, quantity, unit_price, ... }
```

---

*Oxirgi yangilanish: 2026-07-02 | Backend: krv006*
