# Zakaz tizimi qayta ishlandi — 2 xil zakaz, status oqimi va summa sinxroni

> **Sana:** 2026-07-14
> **Qamrov:** `apps/orders` (models, serializers, views, admin, migrations, tests) va
> `apps/cash` bilan bog'liqlik.
> **Testlar:** 29 ta test o'tadi (`python manage.py test`).

Bu hujjat siz aytgan kamchiliklarni va ular qanday tuzatilganini to'liq bayon qiladi.
Har bir bo'lim: **muammo → yechim → kod → misol**.

---

## 0. Qisqacha (TL;DR)

| # | Muammo | Holat |
|---|--------|-------|
| 1 | Zakaz miqdori (quantity) har doim o'zgaruvchan bo'lishi kerak | ✅ Qabul qilingunga qadar o'zgaradi |
| 2 | Zakaz 2 xil bo'lishi kerak (backorder / mustaqil) | ✅ `zakaz_type` maydoni qo'shildi |
| 3 | Status oqimi: `Etkazuvchiga yuborildi` ortiqcha | ✅ Olib tashlandi: `yangi → tasdiqlandi → qabul` |
| 4 | Qabul qilinganda buyurtma avtomatik `bron qilingan` bo'lsin | ✅ Faqat backorder zakaz uchun |
| 5 | Mustaqil zakazda narx + summa + valyuta + to'lov holati | ✅ Qo'shildi, summa avtomatik |
| 6 | Miqdor o'zgarsa summa hamma joyda mos kelsin | ✅ `total` avtomatik hisoblanadi |
| 7 | **Buyurtma tahrirlanganda kassa Jami eski summada qolib ketardi** | ✅ Bug topildi va tuzatildi (§4.1) |

---

## 1. Zakaz endi IKKI XIL (`zakaz_type`)

Avval bitta umumiy Zakaz bor edi. Endi tizim ikki turni ajratadi:

### 1.1. `backorder` — buyurtmadan avtomatik (narxsiz)

- **Qachon:** mijoz buyurtma beradi, ombordagi qoldiq yetmaydi →
  yetishmagan miqdorga **avtomatik** zakaz ochiladi (`order` maydoni to'ladi).
- **Narx yo'q:** pul mijoz buyurtmasi tomonida (`Payment`/kassa) hisoblanadi,
  zakazда takror hisoblanmaydi. `total = None`.
- **Qabul qilinganda:** ombor to'ladi va bog'langan buyurtma
  **`qisman bron` → `bron qilingan`** ga avtomatik o'tadi.

### 1.2. `manual` — mustaqil zakaz (narxli)

- **Qachon:** operator/manager biror mahsulotni o'zi zakaz qiladi
  (`order` bo'sh, buyurtmaga bog'liq emas).
- **Narx MAJBURIY:** `unit_price`, `currency`, **`total` = narx × miqdor
  (avtomatik)**, `payment_status` (etkazuvchiga to'lov holati).
- **Summa faqat zakazda ko'rinadi**, kassaga (`Payment`) yozilmaydi
  *(sizning tanlovingiz bo'yicha)*.

Kod (`apps/orders/models.py`):

```python
class Zakaz(TimeStampedModel):
    BACKORDER = 'backorder'
    MANUAL    = 'manual'
    TYPE_CHOICES = (
        (BACKORDER, 'Buyurtmadan (yetishmagan)'),
        (MANUAL,    'Mustaqil zakaz'),
    )
    zakaz_type = CharField(max_length=10, choices=TYPE_CHOICES, default=MANUAL)

    @property
    def total(self):
        """narx × miqdor — MANUAL uchun avtomatik. BACKORDER da None."""
        if self.unit_price is None:
            return None
        return self.unit_price * self.quantity
```

---

## 2. Status oqimi soddalashtirildi

**Avval:** `yangi → tasdiqlandi → etkazuvchiga yuborildi → qabul qilindi`
**Endi:**  `yangi → tasdiqlandi → qabul qilindi` *(+ istalgan holatdan `bekor`)*

`Etkazuvchiga yuborildi` (`ordered`) butunlay olib tashlandi — siz shuni
so'ragan edingiz ("yetkazish emas boshqa status kere").

| Holat | Talab |
|-------|-------|
| `tasdiqlandi` | shartnoma raqami + asos majburiy; sana bo'sh bo'lsa bugungi kun (Tashkent) |
| `qabul qilindi` | shartnoma + **faktura** + asos majburiy; ombor to'ladi |

> Mavjud bazadagi `ordered` holatдаги zakazlar migratsiyada avtomatik
> `confirmed` ga o'tkazildi (`0011_zakaz_backfill_type_and_status`).

**Faol holatlar** (takror zakaz bermaslik uchun) endi `ACTIVE_STATUSES = (new, confirmed)`.

---

## 3. Qabul qilinganda buyurtma avtomatik "bron qilingan"

Backorder zakaz qabul qilinganda (`received`):

1. `received_qty` (yoki `quantity`) omborga qo'shiladi;
2. Kutayotgan buyurtmalarga `due_date` tartibida bron ajratiladi;
3. To'liq qoplangan buyurtma **`qisman bron` → `bron qilingan`** bo'ladi;
4. Har bir buyurtma tarixiga iz qoladi (qaysi zakaz/shartnoma/faktura asosida).

Bu **faqat buyurtmadan yetmay qolgan** (backorder) holat uchun mazmuniy —
aynan siz aytganday. Kod `Zakaz.receive()` da (`apps/orders/models.py`) va
`allocate_pending_orders()` orqali ishlaydi.

Test bilan tasdiqlangan (`BackorderZakazFlowTests.test_receive_flips_order_to_reserved`):

```
5 so'raldi, omborda 2 → 3 backorder zakaz
manager: tasdiqlandi → qabul (3 dona)
natija: order.reserved_qty == 5, status == RESERVED ✅
```

---

## 4. Summa/miqdor sinxroni (kassa muammosi)

**Sizning misolingiz:** 10 ta server × 1 000 000 = 10 000 000. Zakazdan keyin
miqdor 20 ga o'zgartirildi → buyurtmada 20 000 000, zakazда hali 10 000 000.

**Sabab:** avval zakaz summasi hech qayerda saqlanmas edi.
**Yechim:** `total` endi **hisoblanadigan xususiyat** (`unit_price × quantity`).
Miqdor yoki narx o'zgargan zahoti `total` yangi qiymatni qaytaradi — hech qachon
eski qiymatда qolmaydi.

Test bilan tasdiqlangan (`ManualZakazTests.test_total_recomputes_when_quantity_changes`):

```
narx 1 000 000, miqdor 10 → total 10 000 000
PATCH quantity=20        → total 20 000 000 ✅
```

> Eslatma: sizning tanlovingiz bo'yicha mustaqil zakaz summasi **kassaga
> (Payment) yozilmaydi** — faqat zakazда ko'rinadi. Mijoz buyurtmasi tomonidagi
> kassa esa avval ishlagandek `Order` o'zgarganida avtomatik sinxronlanadi
> (`apps/orders/signals.py`).

### 4.1. BUG: buyurtma tahrirlanganda kassa "Jami" eski summada qolardi

**Muammo (siz topgan):** Buyurtma 1-marta 60 mln edi (35M + 25M), oldindan
to'lov 5M. Keyin tahrir qilib **yana bitta mahsulot qo'shildi** → buyurtma
65 mln bo'ldi. Lekin **kassada "Jami" hamon 60 mln** turardi (65 − 5, xuddi
oldindan to'lov ayirilganday). Ya'ni: *zakazni/buyurtmani edit qilsam,
summasi ham edit bo'lsa — kassada ham shunday bo'lishi kerak.*

**Reproduksiya (tuzatishdan oldin):**

```
[CREATE] order.total = 60 000 000   payment.total_amount = 60 000 000   ✅
[EDIT]   order.total = 65 000 000   payment.total_amount = 60 000 000   ❌
```

**Asl sabab:** buyurtma tahrirlanganда xotiradagi `order` obyekti **eski
(prefetch keshidagi)** qatorlarni ushlab turardi. Qatorlar yangilangach ham
oxirgi `order.sync_payment()` kassaga aynan shu **eski `order.total`** ni
(60 mln) qaytadan yozib qo'yardi.

**Tuzatish (2 ta):**

1. `apps/cash/models.py` — `Payment.save()` endi buyurtma summasini
   xotiradagi obyektdan emas, **to'g'ridan-to'g'ri bazadan (aggregate)**
   hisoblaydi. Kassa har doim bazadagi haqiqiy qatorlarga teng:

   ```python
   total = (OrderItem.objects
            .filter(order_id=self.order_id, unit_price__isnull=False)
            .aggregate(t=Sum(F('unit_price') * F('quantity'), ...))['t'])
   ```

2. `apps/orders/serializers.py` — `OrderSerializer.update()` qatorlar
   o'zgargach eski prefetch keshini tozalaydi
   (`order._prefetched_objects_cache = {}`), shunda holat (`refresh_status`)
   va oldindan-to'lov tekshiruvi ham yangi qatorlardan hisoblanadi.

**Natija (tuzatishdan keyin):**

```
[EDIT] order.total = 65 000 000   payment.total_amount = 65 000 000
       to'langan = 5 000 000       qoldiq = 60 000 000   ✅
```

Regressiya testlari: `OrderEditKassaSyncTests` (miqdor o'zgarishi **va**
yangi mahsulot qo'shish — ikkalasi ham).

---

## 5. Yangi maydonlar (Zakaz modeli)

| Maydon | Tur | Izoh |
|--------|-----|------|
| `zakaz_type` | `backorder` / `manual` | Yaratishda o'rnatiladi, keyin o'zgarmaydi |
| `unit_price` | Decimal(14,2), null | Birlik narxi (mustaqil zakaz uchun majburiy) |
| `currency` | `UZS` / `USD` | Zakaz valyutasi |
| `total` | *(read-only)* | narx × miqdor — avtomatik |
| `payment_status` | `unpaid` / `partial` / `paid` | Etkazuvchiga to'lov holati |

Migratsiyalar:
- `0010_zakaz_currency_zakaz_payment_status_zakaz_unit_price_and_more.py` — maydonlar
- `0011_zakaz_backfill_type_and_status.py` — eski ma'lumotlarni to'ldirish

---

## 6. API o'zgarishlari

Endpoint: `POST /api/v1/orders/zakaz/`

### 6.1. Mustaqil zakaz yaratish (narx MAJBURIY)

```json
POST /api/v1/orders/zakaz/
{
  "product": 12,
  "quantity": 10,
  "unit_price": "1000000",
  "currency": "UZS",
  "supplier": "Germaniya",
  "expected_date": "2026-08-15",
  "contract_number": "SH-2026/045",
  "faktura": "F-2026/900",
  "asos": "Ombor to'ldirish"
}
```

Javob (qisqartirilgan):

```json
{
  "id": 5,
  "zakaz_type": "manual",
  "type_display": "Mustaqil zakaz",
  "quantity": 10,
  "unit_price": "1000000.00",
  "currency": "UZS",
  "total": "10000000.00",
  "payment_status": "unpaid",
  "status": "new"
}
```

Narxsiz yuborilsa → `400 { "unit_price": "Mustaqil zakaz uchun narx kiritilishi shart." }`

### 6.2. Miqdorni o'zgartirish (summa avtomatik)

```json
PATCH /api/v1/orders/zakaz/5/
{ "quantity": 20 }
→ total: "20000000.00"
```

Qabul qilingan/bekor qilingan zakazда miqdor/narx o'zgartirsa → `400` (qotib qoladi).

### 6.3. Status o'zgartirish (faqat Manager)

```json
PATCH /api/v1/orders/zakaz/5/
{ "status": "confirmed", "contract_number": "SH-2026/045", "asos": "Tasdiqlandi" }

PATCH /api/v1/orders/zakaz/5/
{ "status": "received", "received_qty": 20,
  "contract_number": "SH-2026/045", "faktura": "F-900", "asos": "Qabul qilindi" }
```

### 6.4. Yangi filtrlar

```
?zakaz_type=manual|backorder
?payment_status=unpaid|partial|paid
?status=new|confirmed|received|cancelled
```

### 6.5. Bulk mustaqil zakaz

`POST /api/v1/orders/zakaz/bulk/` — har qatorда `unit_price` majburiy,
ixtiyoriy `currency`.

---

## 7. O'zgargan fayllar

| Fayl | O'zgarish |
|------|-----------|
| `apps/orders/models.py` | `zakaz_type`, narx/valyuta/to'lov maydonlari, `total`, `is_backorder`; `ordered` olib tashlandi; `ACTIVE_STATUSES` |
| `apps/orders/serializers.py` | Yangi maydonlar, mustaqil zakaz validatsiyasi, status oqimidan `ordered` chiqarildi, bulkда narx |
| `apps/orders/views.py` | `zakaz_type` va `payment_status` filtrlari |
| `apps/orders/admin.py` | Yangi ustunlar (tur, narx, summa, to'lov holati), `ordered` rangi olib tashlandi |
| `apps/orders/migrations/0010, 0011` | Sxema + ma'lumot migratsiyasi |
| **`apps/cash/models.py`** | **BUG tuzatildi:** `Payment.save()` summani bazadan (aggregate) hisoblaydi — kassa tahrirdan keyin sinxron (§4.1) |
| `apps/orders/tests.py` | +8 test: mustaqil zakaz, summa avtomat, backorder oqimi, **kassa sinxroni** |

---

## 8. Tekshirish

```bash
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py test apps.orders   # 15 OK
.venv/Scripts/python.exe manage.py test               # 32 OK
```

> ⚠️ **Muhim:** loyihani doim `.venv` bilan ishga tushiring
> (`django_celery_beat` global Python'da yo'q). Prodда `.env` da
> `FERNET_KEY` majburiy — aks holda mijoz ma'lumotlari ochiq matnda saqlanadi.

---

## 9. Ochiq qolgan / keyingi qadamlar (ixtiyoriy)

- **Frontend:** "Zakazni tahrirlash" modaliga mustaqil zakaz uchun *narx,
  valyuta, to'lov holati* maydonlarini qo'shish; backorder zakazда bularni
  yashirish (`zakaz_type` orqali).
- **Etkazuvchi to'lovlari kassasi:** hozir mustaqil zakaz summasi kassaga
  tushmaydi. Agar keyinchalik "etkazuvchiga chiqim" ledgeri kerak bo'lsa —
  alohida model bilan qo'shsa bo'ladi (bu hujjatда qamralmagan).
```
