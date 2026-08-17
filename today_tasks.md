# Bugungi ishlar — 2026-08-17

## Umumiy maqsad

Loyihaning har bir qismi kassa (`apps/cash`) atrofida qurilishi kerak edi. Avval loyiha kassaga qaysi qismlar ulanmagani bo‘yicha tahlil qilindi, so‘ng aniqlangan bo‘shliqlarning barchasi (+ tekshiruv jarayonida topilgan qo‘shimchalari) ulandi, keyin foydalanuvchi ko‘rsatgan 4 ta eski xato tuzatildi va kassa integratsiyasi yana bir bor chuqur tekshirilib, yana 2 ta jiddiy bo‘shliq topilib tuzatildi.

---

## 1-bosqich — Tahlil: kassaga ulanmagan qismlar ro‘yxati

Loyiha to‘liq ko‘rib chiqilib, quyidagi 5 ta qism kassaga (to‘liq yoki qisman) ulanmagani aniqlandi:

1. Elektron faktura (Invoices, `apps/invoices`) moduli — umuman kassaga bog‘lanmagan edi.
2. Ombor "Kirim" (`add-stock`) — kassaga yozilmasdi.
3. Mahsulot yaratishda boshlang‘ich `quantity` — kassaga yozilmasdi.
4. Import bo‘lmagan Expenselar (ofis, transport, oylik, …) — kassa umumiy balansiga kirmasdi.
5. Sotuvni o‘chirish — `Payment.sale` FK `PROTECT` bo‘lgani uchun `500` xato bilan yiqilardi.

Foydalanuvchi tasdiqlab, "barchasini qil" dedi.

---

## 2-bosqich — 5 ta bo‘shliqni kassaga ulash

| # | Nima qilindi | Fayllar |
|---|---|---|
| 1 | `sync_invoice_expense()` — shartnoma (SK) fakturasidagi **ombordagi** mahsulot qatorlari bo‘yicha summa kassadan chiqim (`Expense`) sifatida yoziladi/yangilanadi. Yangi (import) mahsulot qatorlari bu yerda hisoblanmaydi (ular alohida Zakaz orqali kassaga tushadi — ikki marta hisoblanmasin uchun). Faktura o‘chirilsa chiqim ham o‘chadi. | `apps/invoices/expense_sync.py` *(yangi)*, `apps/invoices/serializers.py`, `apps/invoices/views.py`, `apps/expenses/models.py` (`invoice` FK + migratsiya) |
| 2–3 | `record_stock_in_expense()` — `add-stock` va mahsulot yaratishdagi boshlang‘ich `quantity`, agar `purchase_price` bo‘lsa, kassadan chiqim yozadi. | `apps/warehouse/stock_expense.py` *(yangi)*, `apps/warehouse/views.py`, `apps/warehouse/serializers.py` |
| 4 | `apps/cash/ledger.py` — `build_ledger_entries`/`ledger_totals` endi **barcha** `Expense`larni hisoblaydi (avval faqat zakazga bog‘langanlarni). Yangi `source=expense`, `expense_type` maydonlari; `sum_out_uzs/usd` qo‘shildi; `net_balance_uzs/usd` endi to‘g‘ri. | `apps/cash/ledger.py` |
| 5 | Sotuv o‘chirilganda bog‘liq `Payment` ham o‘chiriladi (`PROTECT` xatosi bartaraf etildi). | `apps/sales/views.py` |

**Qo‘shimcha topilgan va tuzatilgan (5-band tekshiruvi paytida):** `sync_sale_payment` ichida `self.context['request']` — request yo‘q holatda `KeyError` berayotgani aniqlandi va xavfsiz `self.context.get('request')`ga tuzatildi.

Yangi testlar: `apps/warehouse/tests.py` *(yangi)*, `apps/cash/tests.py`ga qo‘shimcha, `apps/sales/tests.py`ga qo‘shimcha, `apps/orders/tests_import_contracts.py`ga `InvoiceKassaSyncTests`.

`PROJECT_DOCS.md` — yangi kassa integratsiyasi bo‘limi va "Oxirgi yangilanish" jadvali qo‘shildi.

---

## 3-bosqich — 4 ta eski xato tuzatildi

| # | Muammo | Tashxis | Tuzatish |
|---|---|---|---|
| 1 | `apps/orders/views.py` fulfill/cancel’da `NameError: transaction` (500 beradi) | `from django.db import transaction` import qilinmagan edi | Import qo‘shildi |
| 2 | `apps/cash/tests.py` — `_make_sale_payment()` ikki marta chaqirilsa bir xil `serial_number` (unique maydon to‘qnashuvi) | Test helperida serial hardcoded edi | Har chaqiriqda o‘ziga xos serial (counter) |
| 3 | `test_operator_cannot_list_payments` — operator kassa ro‘yxatini ko‘ra oladi (403 kutilgan, 200 kelmoqda) | Git tarixini tekshirib chiqildi: bu aslida **eskirgan test** — `82ab9a4` commitda operatorga kassani **ko‘rish** (summasiz, `PaymentOperatorSerializer`) huquqi ataylab berilgan, lekin test yangilanmay qolgan | Test joriy qoidaga moslab yangilandi (200 + summasiz maydonlar tekshiriladi, yozish 403); `cash/views.py`dagi eskirgan izoh ham tuzatildi |
| 4 | `apps/common/tests_validators.py` — JSHSHIR testi | Test ma’lumoti 15 xonali edi (validator 14 talab qiladi) | 14 xonali to‘g‘ri qiymatga almashtirildi |

---

## 4-bosqich — Qo‘shimcha chuqur tekshiruv: yana 2 ta jiddiy bo‘shliq

Foydalanuvchi so‘ragan holda, "kassaga integratsiya qilinmagan qismlar — kirim, chiqim, hammasi" yana bir bor tekshirildi. Natijada eng muhim biznes-jarayonning o‘zida ikkita jiddiy uzilish topildi:

| # | Muammo | Sabab | Tuzatish |
|---|---|---|---|
| 5 | **Operator yaratgan buyurtma kassaga umuman tushmasdi** | `_can_manage_prices` operator uchun `unit_price`ni butunlay olib tashlar edi → `Order.total = None` → `sync_payment()` hech narsa yozmasdan chiqib ketardi | Sale’dagi kabi qoida qo‘llanildi: operator narx yubormasa (yoki yuborsa ham, e’tiborga olinmaydi) — mahsulotning belgilangan `selling_price`sidan avtomatik olinadi (`_fill_operator_item_prices`) |
| 6 | **Sotuv narxi/miqdori tahrirlanganda kassa yangilanmasdi** | `Payment.save()` sotuv summasini faqat **yaratishda** hisoblardi (`if not self.pk`); `SaleSerializer.update()` esa `sync_sale_payment`ni umuman chaqirmasdi | `Payment.save()` endi sotuv summasini **har safar** qayta hisoblaydi (buyurtma bilan bir xil qoida); `update()` endi `sync_sale_payment`ni chaqiradi, farq (oshgan/kamaygan) tranzaksiya bo‘lib yoziladi |

Fayllar: `apps/orders/serializers.py`, `apps/orders/tests.py` (+ yangi `OperatorOrderPriceAutofillTests`), `apps/cash/models.py`, `apps/sales/sale_payment.py`, `apps/sales/serializers.py`, `apps/sales/tests.py` (+ yangi `SalePriceEditKassaSyncTests`).

`PROJECT_DOCS.md`ga yangi jadval qatorlari va **ochiq savol** qo‘shildi (pastga qarang).

### Ochiq qoldirilgan savol (hal qilinmagan)

Buyurtma `/cancel/` bilan bekor qilinganda bog‘liq kassa yozuvi (`Payment`) hozircha **tegilmaydi**. Agar oldindan to‘lov bo‘lgan bo‘lsa, pul **qaytariladimi** (refund) yoki oldindan to‘lov **qaytarilmas** hisoblanadimi — bu biznes qoidasi loyihada hech qayerda aniqlanmagani uchun avtomatik o‘zgartirilmadi, foydalanuvchi qaroriga qoldirildi.

Shuningdek: `/reports/summary/` (bosh sahifa) dagi `net_balance_uzs` hamon **faqat zakaz** chiqimini hisoblaydi (`_import_paid_totals`, o‘zgartirilmagan) — `/cash/payments/summary/` dagi (Kassa sahifasi) `net_balance_uzs` esa endi **barcha** chiqimni hisoblaydi. Ikkalasi bir xil davr uchun turli balans qaytarishi mumkin — bu `FRONTEND_API.md`ga ochiq nomuvofiqlik sifatida yozib qo‘yildi.

---

## 5-bosqich — Hujjatlar yangilandi

- **`PROJECT_DOCS.md`** — kassa integratsiyasi bo‘yicha yangi bo‘limlar (§6.6, §9, "Oxirgi yangilanish" jadvallari) va ochiq savol qo‘shildi.
- **`FRONTEND_API.md`** — bugungi barcha o‘zgarishlar frontend nuqtai nazaridan hujjatlashtirildi:
  - Kassa (`/cash/payments/`) — Operator o‘qish huquqi (summasiz) aniqlashtirildi; `DELETE` ruxsati tuzatildi (Accountant **yoki** Management, faqat Management emas).
  - Kassa jurnali (`/cash/payments/ledger/`) — yangi `source=expense` qiymati, `expense_type` maydoni, yangilangan JSON namunalar.
  - `paymentsSummary` — yangi `sum_out_uzs`/`sum_out_usd` maydonlari va ularning `sum_import_uzs`dan farqi tushuntirildi.
  - Buyurtmalar (`/invoices/`) — SK faktura → kassa chiqimi integratsiyasi hujjatlashtirildi.
  - Ombor Kirim (`add-stock` va mahsulot yaratish) — kassa chiqimi integratsiyasi hujjatlashtirildi.
  - Buyurtma yaratish (`/orders/`) — Operator narxi e’tiborga olinmasligi (bug tuzatilgani) hujjatlashtirildi.
  - Sotuvlar — tahrir/o‘chirishda kassa sinxronizatsiyasi hujjatlashtirildi.
  - §17c "Kassa jurnali va avtomatik moliyaviy sinxron" — to‘liq qayta yozildi (barcha yangi oqimlar, backend fayllar jadvali).
  - §21 Rol matritsasi va §22 — yangilandi.
  - Bosh sahifa balansi bilan Kassa sahifasi balansi o‘rtasidagi nomuvofiqlik ochiq eslatma sifatida qo‘shildi.
- **`today_tasks.md`** *(yangi)* — ushbu fayl.

---

## 6-bosqich — To‘liq backend audit (kassadan tashqari)

Foydalanuvchi so‘ragan holda, butun backend yana bir marta boshdan oxirigacha ko‘rib chiqildi — mantiqiy xatolar, DB’ga yozilmay/DB’dan o‘qilmay qolayotgan holatlar va boshqa muammoli backend holatlari izlandi. Ko‘rib chiqilgan modullar: `cash`, `orders` (model metodlari — `reserve`/`release`/`fulfill`/`receive`/`allocate_pending_orders`), `sales`, `warehouse` (`Stock`/`Product` aggregatlari), `invoices`, `expenses`, `notifications` (model + celery tasklar), `clients` (shifrlash), `users` (`abilities`), `common/contracts.py` (shartnoma raqami — atomarlik), `root/settings.py` (xavfsizlik sozlamalari).

**Topilgan va tuzatilgan qo‘shimcha xato:**

| Fayl | Muammo | Tuzatish |
|------|--------|----------|
| `root/celery.py` | `check-overdue-payments-daily` (kechikkan to‘lovlar haqida Telegram xabari) `schedule: 32400` (butun son) bilan rejalashtirilgan edi. Celeryda butun/kasr son `schedule`si **interval** (har N soniyada bir marta, beat protsessi ishga tushgan vaqtdan boshlab hisoblanadi) degani — izohda yozilgan "har kuni 09:00 UTC" **degani emas**. Amalda vazifa kuniga ~2.67 marta, tasodifiy vaqtlarda ishlab, muddati o‘tgan to‘lovlar haqida xabar bermay qolishi yoki ortiqcha takrorlanishi mumkin edi. | `from celery.schedules import crontab` qo‘shildi, `schedule: crontab(hour=9, minute=0)` — endi haqiqatan ham har kuni aynan 09:00 UTC (14:00 Toshkent) da ishlaydi. Boshqa ikkita vazifa (`check-delayed-imports-hourly`, `refresh-infinbank-usd-rate-hourly`) — bular haqiqatan ham "har soatda" (interval) bo‘lgani uchun to‘g‘ri edi, tegilmadi. |

**Tekshirilib, muammo topilmagan (izchil ekanligi tasdiqlangan) joylar:**

- `Order.reserve/release/fulfill`, `OrderItem.reserve/release` — FIFO bron/bo‘shatish, `select_for_update` bilan himoyalangan, race condition yo‘q.
- `Zakaz.receive()` — ombor kirimi, mahsulot `origin` almashinuvi, low-stock bildirishnoma yopilishi, kassa chiqimi (backorder zakazda `unit_price` bo‘lsa ham) — barchasi izchil va **ataylab** shunday (agar Management backorder zakazga tannarx kiritsa, bu haqiqiy yetkazuvchiga to‘lov bo‘lgani uchun chiqim yozilishi to‘g‘ri, ikki marta hisoblanish emas).
- `apps/common/contracts.py` (`allocate_contract_number`) — shartnoma raqami ketma-ketligi `select_for_update` + Django `get_or_create`ning unique-constraint retry mexanizmi bilan to‘g‘ri himoyalangan, parallel so‘rovlar bir xil raqam olmaydi.
- `apps/clients/serializers.py` — shifrlash/shifr ochish, yuridik/jismoniy shaxs maydonlarini tozalash mantig‘i izchil.
- `apps/users/serializers.py` (`user_abilities`) — `cash_view` operatorga ham berilgan, bugungi kassa o‘qish huquqi tuzatishiga mos.
- `root/settings.py` — `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`/`CORS` production uchun to‘g‘ri qattiqlashtirilgan (`PROJECT_DOCS.md` §9.1 bilan mos).

Yakunda `python manage.py check` va to‘liq test to‘plami yana bir bor ishga tushirildi — **137/137 o‘tdi**, yangi regressiya yo‘q.

---

## Tekshiruv (barcha bosqichlarda takrorlangan)

- `python manage.py check` → muammosiz.
- `python manage.py makemigrations --check --dry-run` → o‘zgarish yo‘q (migratsiya to‘liq yaratilgan: `expenses/0004_expense_invoice.py`).
- To‘liq test to‘plami (`python manage.py test apps`) → **137/137 o‘tdi**, hech qanday regressiya yo‘q (boshlang‘ich holatda 15+ ta oldindan mavjud xato bor edi — barchasi tuzatildi yoki testlar joriy holatga moslab yangilandi).

---

## O‘zgargan / qo‘shilgan fayllar ro‘yxati

**Yangi fayllar:**
- `apps/invoices/expense_sync.py`
- `apps/warehouse/stock_expense.py`
- `apps/warehouse/tests.py`
- `apps/expenses/migrations/0004_expense_invoice.py`
- `today_tasks.md`

**O‘zgartirilgan fayllar:**
- `apps/cash/ledger.py`, `apps/cash/models.py`, `apps/cash/tests.py`, `apps/cash/views.py`
- `apps/common/tests_validators.py`
- `apps/expenses/models.py`
- `apps/invoices/serializers.py`, `apps/invoices/views.py`
- `apps/orders/serializers.py`, `apps/orders/tests.py`, `apps/orders/tests_import_contracts.py`, `apps/orders/views.py`
- `apps/sales/sale_payment.py`, `apps/sales/serializers.py`, `apps/sales/tests.py`, `apps/sales/views.py`
- `apps/warehouse/serializers.py`, `apps/warehouse/views.py`
- `root/celery.py`
- `PROJECT_DOCS.md`, `FRONTEND_API.md`
