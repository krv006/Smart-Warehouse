# Frontend API qo‘llanma — Smart Warehouse

**Auditoriya:** Bu hujjat **frontend dasturchilar** (va React ilovasini yig‘ayotgan full-stack dasturchilar) uchun yozilgan — Django REST API bilan integratsiya qilish, endpoint kontraktlari, `abilities` bo‘yicha UI gating va `api.js` mapping.

**Maqsad:** Backend va frontend o‘rtasidagi **amaldagi kontrakt** — ulanish, auth, barcha endpointlar, sahifa ↔ API xaritasi va yangi funksiya qo‘shish tartibi.

Bazaviy URL:

```text
/api/v1
```

Production override: `VITE_API_BASE_URL` (masalan `https://api.example.com/api/v1`).

### Mundarija

| § | Bo‘lim |
|---|---|
| 1 | Kirish — ulanish, auth, formatlar |
| 2 | `api.js` — transport va metodlar |
| 3 | Frontend ↔ Backend xaritasi (sahifalar, grid, editorlar, FX, bulk) |
| 4 | Barcha endpointlar — to‘liq jadval |
| 5 | Auth va user sessiya |
| 6 | Role, `abilities` va **UI gating** |
| 7 | Valyuta kursi (backend + `FxRatePanel`) |
| 8–16 | Modul bo‘yicha batafsil (buyurtma, zakaz, ombor, …) |
| 9a–9b | Import UI — ro‘yxat sahifasi va `ZakazEditor` (tugma matnlari, maydonlar) |
| 17 | Hisobotlar va Excel export |
| 17a | Buyurtmalar — `/invoices/` (batafsil) |
| 17b | Excel export UI — `ReportExportPanel`, `FilterDateRangeCalendar` |
| 17c | Kassa jurnali va avtomatik moliyaviy sinxron |
| 18–22 | Yangi endpoint qo‘shish, performance, checklist, rol matritsasi |

---

## 1. Kirish — ulanish va umumiy qoidalar

### Vite proxy (development)

Frontend dev server `http://localhost:5173` da ishlaydi. `/api` so‘rovlari Django ga proxy qilinadi:

```javascript
// frontend/vite.config.js
proxy: { '/api': { target: 'http://127.0.0.1:8000', timeout: 8000 } }
```

Demak brauzerda `fetch('/api/v1/auth/me/')` → `http://127.0.0.1:8000/api/v1/auth/me/`.

Backend alohida ishlashi shart:

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

### OpenAPI (qoʻshimcha manba)

Backend Swagger UI: `http://127.0.0.1:8000/` · ReDoc: `/api/redoc/` · Schema: `/api/schema/`

Bu hujjat frontend nuqtai nazaridan qisqartirilgan; batafsil schema — Swagger da.

### Auth (JWT)

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

**Yaroqsiz/egasiz refresh token — endi toza `401` (tuzatilgan bug):** agar `refresh` tokeni haqiqiy foydalanuvchiga tegishli bo'lmasa (masalan, baza tozalangan/qayta seed qilingan, yoki user o'chirilgan bo'lsa) — backend endi aniq **`401`** qaytaradi:

```json
{ "detail": "Foydalanuvchi topilmadi — qaytadan kiring.", "code": "token_not_valid" }
```

Avval bunday holatda backend **`500`** (server xatosi) berardi — frontend buni tasodifiy server nosozligi deb, `setAuthFailureHandler` chaqirilmasdan, foydalanuvchiga tushunarsiz xato ko'rsatishi mumkin edi. Endi bu doim `401` bo'lgani uchun, mavjud oqim (`request()` → refresh muvaffaqiyatsiz → `setAuthFailureHandler`) to'g'ri ishlab, foydalanuvchini login sahifasiga qaytaradi — frontendda qo'shimcha o'zgartirish shart emas, mavjud 401-handling shu holatni ham to'g'ri qamrab oladi. Backend: `apps/users/serializers.SafeTokenRefreshSerializer` (`apps/users/urls.py`dagi `token/refresh/` shu serializerni ishlatadi).

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

**429 (rate limit):**

```json
{ "detail": "Request was throttled. Expected available in 14 seconds." }
```

Frontend `request()` buni o‘zbekcha matnga aylantiradi va **bir marta** qayta urinadi (§2). Asosiy sabab — UI ketma-ket ko‘p so‘rov yuborganida backend cheklovi.

**Backend throttle (`root/drf_settings.py`, `root/settings.py`):**

| Sozlam | Qiymat |
|---|---|
| Global `DEFAULT_THROTTLE_CLASSES` | `[]` (olib tashlangan — faqat login alohida himoyalangan) |
| Login | `LoginRateThrottle` — `10/min` (`POST /auth/login/`) |
| `DEBUG=True` | Global throttle butunlay o‘chiriladi (lokal dev) |

Production da token refresh va boshqa ochiq endpointlar uchun alohida scoped throttle qo‘shish tavsiya etiladi; hozir frontend `viewFetchKeyRef` va debounce bilan dublikat so‘rovlarni kamaytiradi.

### Sana formatlari

Sana:

```text
YYYY-MM-DD
```

**Shartnoma raqami (o'zgardi — endi UMUMIY, erkin matn):**

Avval har kun uchun alohida (`{tartib}/{DDMM}`, kuniga 1 dan qayta boshlanadigan) raqam berilardi. Endi **bitta umumiy, hech qachon qayta boshlanmaydigan** ketma-ket son beriladi — kim, qaysi modulda (buyurtma/zakaz/faktura) va qaysi kunda yaratishidan qat'i nazar, bitta hisoblagichdan olinadi:

```text
1, 2, 3, 4, ...
```

Bu — faqat **standart (avtomatik)** qiymat, maydon bo'sh qoldirilganda ishlatiladi. Xodim istasa, shartnoma raqamini **istalgan boshqa ko'rinishda** qo'lda kiritishi mumkin (masalan `124151245124`) — **hech qanday format tekshiruvi endi yo'q** (na backend, na frontendda). Eski `^\d+/\d{4}$` regex talabi butunlay olib tashlandi.

Bo‘sh yuborilsa backend avtomatik yaratadi (`apps/common/contracts.allocate_contract_number`).

---

## 2. `api.js` — transport va umumiy patternlar

Manba: `frontend/src/api.js`.

### Sessiya va transport

| Funksiya | Tavsif |
|---|---|
| `saveSession({ access, refresh, user })` | `localStorage`: `warehouse_access`, `warehouse_refresh`, `warehouse_user` |
| `clearStoredSession()` | Sessiyani tozalash |
| `setAuthFailureHandler(fn)` | 401 refresh muvaffaqiyatsiz bo‘lsa chaqiriladi |
| `refreshAccessToken()` | `POST /auth/token/refresh/` |
| `request(path, options)` | JWT bilan so‘rov; 401 da bir marta refresh + retry |
| `download(path, filename)` | Blob yuklab olish (Excel export); JWT bilan `fetch`, 401 da refresh yo‘q — faqat joriy token |

Timeout: **8 soniya**. Xato klassi: `ApiError(message, status, fields?)` — `fields` maydon xatoliklari (`company_name`, `inn`, …) uchun; forma ostida qizil matn ko‘rsatishda ishlatiladi.

**429 (throttle):** `request()` bir marta qayta urinadi (kutish `Retry-After` yoki javob matnidan, max **5 s**). Xabar o‘zbekcha: «Juda ko‘p so‘rov yuborildi…».

### `api` obyekti

| Metod | HTTP | Path | Query / body |
|---|---|---|---|
| `login(username, password)` | POST | `/auth/login/` | `{ username, password }` — auth yo‘q |
| `me()` | GET | `/auth/me/` | — |
| `registerUser(payload)` | POST | `/auth/register/` | user body |
| `users(params)` | GET | `/auth/users/` | `page_size=20`, `search`, `role`, `is_active` |
| `reports(params)` | GET ×4 | parallel (qarang pastda) | dashboard filter params |
| `monthlyTrend(months, params)` | GET | `/reports/monthly-trend/` | `months` (default 6), filter params |
| `orders(params)` | GET | `/orders/` | `page_size=20`, `search`, `status`, `client`, `contract_number`, `date_from`, `date_to`, `ordering`, `page` |
| `order(id)` | GET | `/orders/{id}/` | — |
| `nextContractNumber(params)` | GET | `/orders/next-contract-number/` | `contract_date` (ixtiyoriy, `YYYY-MM-DD`) |
| `ordersBulk(payload)` | POST | `/orders/bulk/` | bulk order body |
| `fulfillOrder(id, payload)` | POST | `/orders/{id}/fulfill/` | `{ contract_number, asos, ... }` |
| `cancelOrder(id, payload)` | POST | `/orders/{id}/cancel/` | `{ contract_number, asos, ... }` |
| `createOrderZakaz(id, payload)` | POST | `/orders/{id}/create-zakaz/` | zakaz body |
| `zakaz(params)` | GET | `/orders/zakaz/` | `page_size=30`, `status`, `product`, `order`, `contract_number` |
| `zakazBulk(payload)` | POST | `/orders/zakaz/bulk/` | bulk zakaz body; ixtiyoriy `import_batch`, `payment_status`, `paid_amount` |
| `zakazBatch(id)` | GET | `/orders/zakaz/{id}/batch/` | `{ items: Zakaz[] }` — import guruhi (tahrir) |
| `contracts(params)` | GET | `/orders/contracts/` | `page_size=30`, `product`, `contract_number`, `source_type`, `order`, `zakaz` |
| `productContracts(id)` | GET | `/warehouse/products/{id}/contracts/` | — |
| `categories(params)` | GET | `/warehouse/categories/` | `page_size=30`, `search` |
| `products(params)` | GET | `/warehouse/products/` | `page_size=30`, `search`, `category` |
| `stocks(params)` | GET | `/warehouse/stocks/` | `page_size=30`, `product`, `category`, `status` |
| `addStock(id, payload)` | POST | `/warehouse/products/{id}/add-stock/` | kirim body |
| `clients(params)` | GET | `/clients/` | `page_size=30`, `search` (F.I.Sh, INN, JSHSHIR, passport, kompaniya, email), `is_active`, `date_from`, `date_to` |
| `sales(params)` | GET | `/sales/` | `page_size=30`, `product`, `client`, `sold_date`, `date_from`, `date_to`, `search`, `ordering`, `page` |
| `salesBulk(payload)` | POST | `/sales/bulk/` | bulk sales body |
| `payments(params)` | GET | `/cash/payments/` | `page_size=30`, `status`, `order`, `sale`, `client`, `currency`, `include_paid`, `search`, `ordering`, `page` |
| `paymentsSummary()` | GET | `/cash/payments/summary/` | — |
| `kassaLedger(params)` | GET | `/cash/payments/ledger/` | `page`, `page_size`, `search`, `source` (`sale`\|`order`\|`import`\|`expense`) |
| `pay(id, payload)` | POST | `/cash/payments/{id}/pay/` | `{ amount, comment }` |
| `cashConvert(payload)` | POST | `/cash/payments/convert/` | `{ direction: 'uzs_to_usd'\|'usd_to_uzs', amount, rate }` |
| `adjustCashBalance(payload)` | POST | `/cash/payments/adjust-balance/` | `{ currency: 'UZS'\|'USD', target_balance, asos }` |
| `exchangeRateLatest(refresh)` | GET | `/cash/exchange-rates/latest/` | `refresh=true\|false` |
| `exchangeRateSettings()` | GET | `/cash/exchange-rates/settings/` | — |
| `updateExchangeRateSettings(payload)` | PATCH | `/cash/exchange-rates/settings/` | `{ auto_fetch_enabled?, preferred_rate_source?, preferred_bank_code?, preferred_bank_side? }` (`infinbank` \| `manual` \| `bank`; `preferred_bank_side`: `buy` \| `sell`) |
| `companyProfile()` | GET | `/company-profile/` | — |
| `updateCompanyProfile(payload)` | PATCH | `/company-profile/` | korxona rekvizitlari — Management |
| `invoices(params)` | GET | `/invoices/` | `page_size=30`, `document_type`, `client`, `search` |
| `invoice(id)` | GET | `/invoices/{id}/` | — |
| `createInvoice(payload)` | POST | `/invoices/` | buyurtma (invoice) + `lines[]` |
| `updateInvoice(id, payload)` | PATCH | `/invoices/{id}/` | — |
| `removeInvoice(id)` | DELETE | `/invoices/{id}/` | Management |
| `expenses(params)` | GET | `/expenses/expenses/` | `page_size=30`, `expense_type`, `sub_type`, `currency`, `date_from`, `date_to` |
| `expensesSummary()` | GET | `/expenses/summary/` | — |
| `expenseTypes()` | GET | `/expenses/expense-types/` | `page_size=50` |
| `expenseSubtypes()` | GET | `/expenses/expense-subtypes/` | `page_size=100`, `expense_type` |
| `notifications(params)` | GET | `/notifications/` | `page_size=30`, `is_read` |
| `notificationsMarkRead(id)` | POST | `/notifications/{id}/mark_read/` | — |
| `notificationsMarkAllRead()` | POST | `/notifications/mark_all_read/` | — |
| `exportReport(type, params)` | GET | `/reports/excel/{type}/` | Birlashtirilgan Excel yuklab olish (qarang §17b) |
| `exportSales(params)` | GET | `/reports/excel/sales/` | `date_from`, `date_to` → `sotuvlar.xlsx` |
| `exportStock(params)` | GET | `/reports/excel/stock/` | davrsiz → `ombor.xlsx` |
| `exportExpenses(params)` | GET | `/reports/excel/expenses/` | `date_from`, `date_to` → `xarajatlar.xlsx` |
| `exportKassa(params)` | GET | `/reports/excel/kassa/` | `date_from`, `date_to` → `kassa.xlsx` |
| `exportPayments(params)` | GET | `/reports/excel/payments/` | `exportKassa` bilan bir xil backend |
| `exportImports(params)` | GET | `/reports/excel/imports/` | `date_from`, `date_to` → `import.xlsx` |
| `retrieve(path, id)` | GET | `{path}{id}/` | — |
| `create(path, payload)` | POST | `path` | JSON body |
| `createForm(path, payload)` | POST | `path` | `FormData` yoki JSON |
| `update(path, id, payload)` | PATCH | `{path}{id}/` | JSON body |
| `updateForm(path, id, payload)` | PATCH | `{path}{id}/` | `FormData` yoki JSON |
| `remove(path, id)` | DELETE | `{path}{id}/` | — |

### `api.reports(params)` — parallel chaqiriqlar

Bosh sahifa va Hisobotlar sahifasi shu helperdan foydalanadi. `params` bo‘sh bo‘lsa filtrsiz so‘rov ketadi.

```javascript
const [summary, warehouse, cash, topProducts] = await api.reports(params)
```

| # | Endpoint | Query params |
|---|---|---|
| 1 | `GET /reports/summary/` | `params` to‘liq (dashboard filtrlari) |
| 2 | `GET /reports/warehouse/` | **parametr yuborilmaydi** (hozirgi ombor holati) |
| 3 | `GET /reports/cash/` | `date_from`, `date_to`, `client`, `payment_status` |
| 4 | `GET /reports/top-products/` | `limit=10` + dashboard filtrlari |

### Generic CRUD helperlar

Ko‘p sahifalar `resources` jadvalidagi `path` bilan generic helperlarni ishlatadi:

```javascript
// Ro‘yxat
const rows = list(await api.orders({ search: '12/1108' }))

// Detail
const detail = await api.retrieve('/orders/', id)

// Yaratish / tahrirlash / o‘chirish
await api.create('/warehouse/categories/', payload)
await api.update('/sales/', id, payload)
await api.createForm('/orders/', formData)   // multipart
await api.updateForm('/expenses/expenses/', id, formData)
await api.remove('/auth/users/', id)
```

`list()` helperi (`frontend/src/lib/utils.js` yoki `App.jsx` dagi lokal nusxa) pagination `results` yoki oddiy arrayni qaytaradi.

### `api.exportReport(type, params)` — birlashtirilgan Excel export

Manba: `frontend/src/api.js`. Hisobotlar → **Excel** tabi (`ReportExportPanel`) shu metoddan foydalanadi.

| `type` | Backend path | Fayl prefiksi | Davr (`date_from` / `date_to`) |
|---|---|---|---|
| `sales` | `/reports/excel/sales/` | `sotuvlar` | ✅ — `sold_date` bo‘yicha |
| `kassa` | `/reports/excel/kassa/` | `kassa` | ✅ — jurnal sanasi bo‘yicha |
| `payments` | `/reports/excel/payments/` | `kassa` | ✅ — `kassa` bilan bir xil |
| `import` | `/reports/excel/imports/` | `import` | ✅ — `created_at` bo‘yicha |
| `expenses` | `/reports/excel/expenses/` | `xarajatlar` | ✅ — `date` bo‘yicha |
| `stock` | `/reports/excel/stock/` | `ombor` | ❌ — joriy qoldiqlar snapshot |

```javascript
await api.exportReport('sales', { date_from: '2026-08-01', date_to: '2026-08-31' })
// → sotuvlar_2026-08-01.xlsx (yoki date_to / bugun)
```

Parametrlar bo‘sh bo‘lsa (`Barcha davr`) `{}` yuboriladi — backend barcha yozuvlarni oladi (stock bundan mustasno).

Legacy metodlar (`exportSales`, `exportKassa`, …) ham saqlangan; yangi UI faqat `exportReport` ishlatadi.

### Frontend komponentlar (asosiy)

| Komponent | Fayl | Vazifa |
|---|---|---|
| `ReportExportPanel` | `components/ReportExportPanel.jsx` | Hisobotlar → Excel tab: tur tanlash, davr, yuklab olish |
| `FilterDateRangeCalendar` | `components/FilterDateRangeCalendar.jsx` | Oraliq tanlash kalendari (dashboard filtr, export, grid filtr) |
| `KassaPage` | `components/KassaPage.jsx` | Kassa jurnali, metrikalar, to‘lov qabul qilish, valyuta konvertori (yangi) |
| `BuyurtmalarPage` | `App.jsx` | Invoice CRUD, preview, editor |
| `ClientDetailPage` | `components/ClientDetailPage.jsx` | Mijoz kartasi tablari |
| `DataTable` | `components/DataTable.jsx` | Grid, sort, bulk, amallar ustuni |
| `ListFiltersPanel` | `components/ListFiltersPanel.jsx` | Grid filtrlari + kalendardan sana |
| `GlobalSearch` | `components/GlobalSearch.jsx` | Ctrl+K qidiruv |
| `SearchableCombobox` | `components/SearchableCombobox.jsx` | Server qidiruvli dropdown |
| `FxRatePanel` | `App.jsx` | Valyuta kursi (header / compact) |

Yordamchi kutubxonalar: `lib/utils.js` (`money`, `todayValue`, `formatDateUz`, `list`), `lib/permissions.js` (`can`), `lib/clients.js`, `lib/uzValidators.js`, `listFilters.js`, `routes.js`.

---

## 3. Frontend ↔ Backend xaritasi (sahifalar va API)

| UI sahifa | `api.js` | Backend path | Eslatma |
|---|---|---|---|
| Bosh sahifa | `reports`, `monthlyTrend` | `/reports/summary/` | Filtrli dashboard: **Tushum**, **Import chiqim**, **Kassa balansi**, Savdo (`Dashboard` komponenti) |
| Hisobotlar | `reports`, `expensesSummary`, `paymentsSummary`, `exportReport` | `/reports/*`, `/expenses/summary/`, `/cash/payments/summary/` | Tablar: Moliyaviy, Ombor, Sotuvlar, Xarajatlar, **Excel** (`ReportExportPanel`) |
| Buyurtmalar | `invoices`, `invoice`, `createInvoice`, `updateInvoice`, `removeInvoice`, `nextContractNumber`, `companyProfile`, `clients` (qidiruv/qo‘shish) | `/invoices/`, `/company-profile/`, `/clients/` | `BuyurtmalarPage` — ro‘yxat, ko‘rish modali, alohida editor sahifalari (§17a) |
| Import | `zakaz`, `zakazBulk`, `zakazBatch`, `create`, `update` | `/orders/zakaz/`, `/orders/zakaz/bulk/`, `/orders/zakaz/{id}/batch/` | **`ResourcePage`** + **`ZakazEditor`** — ko‘p qator, `import_batch` guruhlash, batch tahrir, kassa chiqimi (§9a–9b, §17c); grid: To‘lov, Summa |
| Shartnomalar | `contracts`, `retrieve` | `/orders/contracts/` | Read-only |
| Korxona profili | `companyProfile`, `updateCompanyProfile` | `/company-profile/` | Profil dropdown |
| Ombor | `products`, `create`, `update`, `addStock`, `productContracts` | `/warehouse/products/` | `warehouse_create` ability |
| Kategoriyalar | `categories`, `create`, `update`, `remove` | `/warehouse/categories/` | |
| Qoldiqlar | `stocks` | `/warehouse/stocks/` | |
| Mijozlar (ro‘yxat) | `clients`, `create`, `update`, `remove` | `/clients/` | Grid + filtr; qator → mijoz kartasi |
| Mijoz kartasi | `retrieve`, `orders`, `sales`, `payments`, `invoices` | `/clients/{uuid}/`, `/orders/`, … | URL: `/mijozlar/{id}[/{tab}]` — `ClientDetailPage` |
| Sotuvlar | `sales`, `salesBulk`, `create`, `update` | `/sales/` | Yaratilganda avtomatik kassaga tushum (`sync_sale_payment`, §17c) |
| Kassa | `kassaLedger`, `paymentsSummary`, `pay`, `create` | `/cash/payments/ledger/`, `/cash/payments/summary/` | **`KassaPage`** (alohida sahifa, `/moliya/kassa`); `ResourcePage` emas |
| Xarajatlar | `expenses`, `expenseTypes`, `expenseSubtypes`, `createForm`, `updateForm` | `/expenses/expenses/` | Multipart |
| Foydalanuvchilar | `users`, `registerUser`, `update`, `remove` | `/auth/users/`, `/auth/register/` | |
| Bildirishnomalar | `notifications`, `notificationsMarkRead`, `notificationsMarkAllRead` | `/notifications/` | 30s polling |
| Valyuta kursi | `exchangeRateLatest`, `exchangeRateSettings`, `updateExchangeRateSettings`, `create('/cash/exchange-rates/')` | `/cash/exchange-rates/` | `FxRatePanel`: `header` (topbar, read-only) yoki `compact` (Import/Rasxod editorlari) |


### URL va layout (`routes.js`, `routes.jsx`)

| Fayl | Vazifa |
|---|---|
| `frontend/src/routes.js` | `PAGE_PATHS`, `parseAppPath()`, path helperlar, `crumbFromPath()` |
| `frontend/src/routes.jsx` | `AppRoutes` — URL → `ClientDetailPage`, `ResourcePage`, dashboard, hisobotlar |
| `frontend/src/pages/LoginPage.jsx` | JWT login (`api.login` → `saveSession`) |
| `frontend/src/main.jsx` | `BrowserRouter` |

**Path helperlar (`routes.js`):**

| Funksiya | Natija | `parseAppPath` → `kind` |
|---|---|---|
| `pathForPage('Buyurtmalar')` | `/buyurtmalar` | `page` |
| `invoiceNewPath()` | `/buyurtmalar/yangi` | `invoice-new` |
| `invoiceEditPath(uuid)` | `/buyurtmalar/{uuid}/tahrir` | `invoice-edit` |
| `invoiceDetailPath(uuid)` | `/buyurtmalar/{uuid}` | `invoice-detail` |
| `clientDetailPath(uuid, tab?)` | `/mijozlar/{uuid}[/{tab}]` | `client-detail` |
| `crumbFromPath(pathname)` | Topbar breadcrumb matni | — |
| `pageFromPath(pathname)` | Sahifa nomi yoki `null` | — |

`crumbFromPath` buyurtma URL lari uchun: `Buyurtmalar / Yangi`, `Buyurtmalar / Tahrir / c076aae7…`, `Buyurtmalar / c076aae7…` (ko‘rish).

Asosiy URL lar (react-router):

| Path | Ko‘rinish |
|---|---|
| `/`, `/buyurtmalar`, `/import`, … | `PAGE_PATHS` dagi ro‘yxat sahifalari |
| `/moliya/kassa` | Kassa (`KassaPage`) |
| `/moliya/xarajatlar` | Xarajatlar grid |
| `/mijozlar/{uuid}` | Mijoz kartasi, tab `umumiy` |
| `/mijozlar/{uuid}/{tab}` | `buyurtmalar`, `sotuvlar`, `tolovlar` |
| `/buyurtmalar/yangi` | Yangi buyurtma (to‘liq sahifa editor) |
| `/buyurtmalar/{uuid}/tahrir` | Mavjud buyurtmani tahrirlash |
| `/buyurtmalar/{uuid}` | To‘g‘ridan-to‘g‘ri URL — shartnoma ko‘rish modali (ro‘yxat + modal) |

Ro‘yxatdan **ko‘z** ikonkasi URL o‘zgartirmaydi — `loadInvoiceForView(id)` bir marta `GET /invoices/{uuid}/` + `GET /clients/{uuid}/` chaqiradi va `InvoiceContractModal` ochiladi.

### Global qidiruv (`GlobalSearch.jsx`)

- Ochish: header tugmasi yoki **Ctrl+K** / **⌘+K** (`useGlobalSearchHotkey`).
- Kamida **2** belgi; debounce bilan parallel so‘rovlar (`page_size=6`):
  - Mijozlar → `api.clients({ search })` — F.I.Sh, INN, JSHSHIR, passport, kompaniya, email
  - Buyurtmalar → `api.invoices({ search })`
  - Mahsulotlar → `api.products({ search })`
  - Shartnomalar → `api.contracts({ search })`
- Mijoz natijasida meta: telefon, INN, JSHSHIR (`pinfl`), passport, rahbar JSHSHIR.
- Placeholder: «F.I.Sh, INN, JSHSHIR, passport, buyurtma…»
- Natija bosilganda: mijoz kartasi, buyurtma detail URL, Ombor yoki Shartnomalar sahifasi.

### Grid ro‘yxatlar, filtr, pagination (`ResourcePage` + `listFilters.js`)

**Grid sahifalar** (`GRID_PAGES` — `App.jsx`): Mijozlar, Sotuvlar, Import, Ombor, Xarajatlar. **Kassa** va **Buyurtmalar** alohida: `KassaPage` (`/moliya/kassa`), `BuyurtmalarPage` (`/invoices/`).

| Parametr | Qiymat |
|---|---|
| `page_size` | 25 (grid); `api.js` defaultlari 20/30 — grid override qiladi) |
| `page`, `ordering` | Server-side sort (`GRID_SORT_FIELDS` mapping) |
| Qidiruv | Form submit → query param `search` |

Filtr paneli: `ListFiltersPanel` + `frontend/src/listFilters.js`.

| Modul | Status | Mijoz | Kategoriya | Sana |
|---|---|---|---|---|
| Mijozlar | `is_active` | — | — | ✅ |
| Sotuvlar | — | ✅ | — | ✅ |
| Import | `status` | — | — | ✅ |
| Ombor | — | — | ✅ `category` | — |
| Kassa | `status` | ✅ | — | ✅ (UI yuboradi; backend `/cash/payments/` hozircha e’tiborsiz) |
| Xarajatlar | — | — | — | ✅ |

`buildListQueryParams(title, filters)` → API query: `status` yoki `is_active`, `client`, `category`, `date_from`, `date_to`.

Kategoriya filtri daraxt ko‘rinishida (`— ` bilan bosqichlangan) va 8 tadan ko‘p bo‘lsa qidiruv maydoni bilan chiqadi; backend tanlangan kategoriya bilan birga **ost-kategoriyalarni** ham qamrab oladi.

Backend sana maydoni (`apps/common/querysets.apply_date_range`):

| Endpoint | Sana maydoni |
|---|---|
| `/clients/` | `created_at` |
| `/orders/`, `/orders/zakaz/` | `created_at` |
| `/sales/` | `sold_date` |
| `/expenses/expenses/` | `date` |
| `/warehouse/stocks/` | `created_at` (custom) |
| `/cash/payments/` | hozircha **`date_from`/`date_to` e’tiborga olinmaydi** (UI yuboradi) |

Komponentlar: `DataTable` (sort, tanlash), `TablePagination`, `StatusChangeModal`, `EmptyState`, `SkeletonRows`.

**Amallar ustuni (`DataTable`):** `renderActions(row)` natijasi `.row-actions` flex wrapper ichida (`DataTable.jsx`). Grid ustunida `.data-table-actions-col .row-actions`:

- `display: flex; flex-direction: row; flex-wrap: nowrap` — barcha tugmalar **bir qator**da
- `.row-action` — `height: 36px`, `min-height: 36px`, `inline-flex`, `align-items: center`
- `gap: 6px`, `justify-content: flex-end`, `flex-shrink: 0` — ikonka va matnli tugmalar bir xil balandlikda hizalanadi

Mobil/product-row kontekstida `.row-actions` `flex-wrap: wrap` bo‘lishi mumkin; grid **Amallar** ustuni doim `nowrap`.

### Editor ma’lumot yuklashi

Forma editorlari mahsulotlarni **mustaqil** yuklaydi; mijozlar faqat `clients_view` bo‘lsa:

| Komponent | Mahsulot | Mijoz |
|---|---|---|
| `SaleEditor` | `api.products({ page_size: 500 })` | `SearchableCombobox` + `searchClients()` (`onSearch`) |
| `BuyurtmalarPage` | `api.products({ page_size: 200 })` | `ClientPickerModal` + `ClientPickerField` (bajaruvchi va hamkor); `searchClients()`; tanlangan mijoz `fetchClient()`; modal ichida **Yangi korxona qo‘shish** — `clients_manage` bo‘lsa `Editor` (`POST /clients/`) |

`clients_view` yo‘q bo‘lsa mijoz combobox ishlamaydi; 403 xato chiqmasligi uchun `api.clients()` chaqirilmaydi.

### Mijoz qidiruv combobox (`SearchableCombobox` + `lib/clients.js`)

Buyurtmalar editoridagi **Hamkorning ma’lumotlari** va **Sotuv** editoridagi mijoz maydoni server qidiruv ishlatadi:

| Frontend | Backend |
|---|---|
| `searchClients(query)` → `api.clients({ search: query, page_size: 20 })` | `ClientSearchFilter` (`apps/clients/filters.py`) |
| `fetchClient(id)` → `GET /clients/{uuid}/` | To‘liq rekvizitlar (hamkor info-grid, preview) |
| `clientOptionLabel()` | Ro‘yxat yorlig‘i: nom + INN/JSHSHIR/passport |
| `clientSearchText()` | Lokal fallback (Sotuv editoridagi oldindan yuklangan ro‘yxat) |

**Qidiriladigan maydonlar** (`search` parametri):

| Tur | Maydonlar |
|---|---|
| F.I.Sh | `full_name`, `first_name`, `last_name`, `middle_name`, `director_fish` |
| INN / STIR | `inn` |
| JSHSHIR | `pinfl` (jismoniy), `director_jshshr` (yuridik) |
| Passport | `passport_number` |
| Boshqa | `company_name`, `email` |

Shifrlangan maydonlar serverda ochiladi. Kamida **2** belgi; debounce **400 ms** (`SearchableCombobox` yoki `ClientPickerModal`). Tanlangan mijoz `GET /clients/{uuid}/` orqali to‘liq yuklanadi (STIR, bank, MFO, manzil va hokazo).

**Buyurtmalar — korxona tanlash modali (`ClientPickerModal`):** «Bajaruvchi korxona» yoki «Mijoz» maydoniga bosilganda modal ochiladi (tovar tanlashdagi `ProductPickerModal` kabi). Qidiruv `searchClients()`; pastda **Yangi korxona qo‘shish** — `clients_manage` bo‘lsa yuridik mijoz editori ochiladi va saqlangach tanlangan tomonga (`client` yoki `executor_client`) biriktiriladi.

**Buyurtma qatorlari — tovar tanlash:** «Tovar nomi» maydoni qo‘lda yoki datalist orqali; yonidagi **quti** ikonkasi `ProductPickerModal` ochadi. Ombor maydoni `serial_number` buyurtma qatorida `identification_code` (UI: **Seriya raqami**). Ombordan tanlanganda FK + maydonlar sinxron; qo‘lda o‘zgartirsangiz frontend `reconcileLineWithProducts()` orqali qayta bog‘laydi yoki FK ni uzadi; saqlashda backend `product` FK bo‘lsa ombordan majburiy sinxron qiladi.

**Bazada yo‘q tovar:** qator nomi (yoki seriya/shtrix kodi) ombordagi hech bir mahsulotga mos kelmasa, saqlashda backend mahsulotni DARHOL ombor ro‘yxatiga qo‘shadi va qatorga bog‘laydi. Bunday mahsulotning `origin` maydoni `import` bo‘ladi (`origin_display` — «Import»), ombor ro‘yxatida **Holati** ustunida ko‘rinadi. Ombordan qo‘lda yaratilganlarda `origin=warehouse`.

Shu bilan birga o‘sha mahsulot uchun **import (zakaz) yozuvi** ham ochiladi — Import bo‘limida ko‘rinadi: `zakaz_type=manual`, `status=new` (Yangi), `payment_status=unpaid`, `quantity` — qator soni, `selling_price` — qatordagi narx, `unit_price` (kelish narxi) **bo‘sh** (hali noma’lum), shartnoma raqami/sanasi hujjatnikidan. Ombordagi mavjud mahsulot uchun takroriy import yozuvi ochilmaydi.

**Import oynasi:** import (`ZakazEditor`) mahsulot qatorlari buyurtma hujjatidagi jadval bilan bir xil — Tovar nomi (+ `ProductPickerModal`), Seriya raqami, Shtrix kod, O‘lchov birligi, Soni, **Kelish narxi**, **Ketish narxi**, Yetkazish qiymati, QQS %, QQS miqdori, Jami, «Teskari hisob» va MXIK havolasi.

### `FxRatePanel` rejimlari (`App.jsx`)

| Prop | Joylashuv | Ko‘rinish | Ruxsat |
|---|---|---|---|
| `header` | Topbar (bosh sahifa) | **Bank dropdown** (Infinbank MB + 6 ta bank + saqlangan qo‘lda) + faol kurs + ixtiyoriy ↻ | Dropdown va ↻ — `users_manage` |
| `compact` | Import / Xarajat editorlari | **Bank dropdown** + **Sotish/Sotib olish** (market bank tanlanganda) + **Qo‘lda** tugmasi. Qo‘lda rejimda input (`Kurs kiriting`), blur/Enter da saqlash | Dropdown, qo‘lda saqlash, ↻ — `users_manage` |

Dropdown ro‘yxati `market_rates.banks` + Infinbank MB (`infinbank.mb_rate`) + ixtiyoriy `manual`. Tanlangan kurs `mb_rate` / «Hisobda: …» da ko‘rsatiladi.

`users_manage` bo‘lmagan foydalanuvchi dropdown `disabled` — faqat faol kurs ko‘rsatiladi.

Backend: `PATCH /cash/exchange-rates/settings/` va `POST /cash/exchange-rates/` (qo‘lda kurs) — **Management** (`IsManagement()`).

### Bulk amallar (grid)

| Amal | Modullar | API |
|---|---|---|
| Tanlangan qatorlarni CSV eksport | Barcha grid sahifalar | Faqat frontend (`exportRowsCsv`) |
| Status o‘zgartirish (inline + bulk) | Import | `order_status_manage` ability; ketma-ket `PATCH /orders/zakaz/{id}/` — `StatusChangeModal` |

`api.ordersBulk`, `api.zakazBulk`, `api.salesBulk` — forma yaratishda (ko‘p qatorli POST), grid bulk status uchun emas.

### Mijoz kartasi tablari (`ClientDetailPage.jsx`)

| Tab | API | Eslatma |
|---|---|---|
| `umumiy` | `GET /clients/{uuid}/` | Rekvizitlar, CTA (tahrir, yangi buyurtma) |
| `buyurtmalar` | `GET /invoices/?client=&page_size=15` | Invoice ro‘yxati; qator → `/buyurtmalar/{uuid}` |
| `sotuvlar` | `GET /sales/?client=&page_size=15` | |
| `tolovlar` | `GET /cash/payments/?client=&page_size=15` | |

Tablar `abilities` bo‘yicha yashirin (`einvoice_view`, `sales_view`, `cash_view`).


---

## 4. Barcha endpointlar — to‘liq jadval

Jami **~95** HTTP endpoint (custom actionlar bilan). ✅ = `api.js` da wrapper bor.

### Auth — `/api/v1/auth/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| POST | `/login/` | `{ username, password }` | Public, 10/min | ✅ `login` |
| GET | `/me/` | — | Auth | ✅ `me` |
| POST | `/token/refresh/` | `{ refresh }` | Public | ✅ `refreshAccessToken` |
| POST | `/register/` | user fields + parol | Management | ✅ `registerUser` |
| GET | `/users/` | `page_size`, `search`, `role`, `is_active` | Management | ✅ `users` |
| GET | `/users/{id}/` | — | Management | ✅ `retrieve` |
| PATCH | `/users/{id}/` | user fields | Management | ✅ `update` |
| DELETE | `/users/{id}/` | — | Management | ✅ `remove` |

`POST /users/` **yo‘q** — yangi user faqat `/register/`.

### Buyurtmalar — `/api/v1/orders/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `page_size`, `search`, `status`, `client`, `contract_number`, `items__product`, `date_from`, `date_to`, `ordering`, `page` | Auth, read | ✅ `orders` |
| POST | `/` | order JSON yoki multipart | Operator+ | ✅ `createForm` |
| GET | `/{id}/` | — | Auth | ✅ `order` / `retrieve` |
| PATCH | `/{id}/` | `{ asos, items[] }` | Operator+ | ✅ `update` |
| GET | `/next-contract-number/` | `contract_date` | Auth | ✅ `nextContractNumber` |
| POST | `/bulk/` | bulk order body | Operator+ | ✅ `ordersBulk` |
| POST | `/{id}/fulfill/` | `{ contract_number, asos, faktura? }` | Operator/Management | ✅ `fulfillOrder` |
| POST | `/{id}/cancel/` | `{ contract_number, asos, faktura? }` | Operator/Management | ✅ `cancelOrder` |
| POST | `/{id}/create-zakaz/` | `{ contract_number, asos, supplier?, expected_date? }` | Operator/Management | ✅ `createOrderZakaz` |

DELETE yo‘q — bekor qilish `/cancel/` orqali.

### Zakaz (Import) — `/api/v1/orders/zakaz/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | yuqoridagilar + `date_from`, `date_to`, `ordering`, `page` | Auth | ✅ `zakaz` |
| POST | `/` | zakaz body yoki `new_product` inline | Auth | ✅ `create` |
| GET | `/{id}/` | — | Auth | ✅ `retrieve` |
| PATCH | `/{id}/` | status, received_qty, supplier… | Auth; status o‘zgartirish — Management (`order_status_manage`) | ✅ `update` |
| POST | `/bulk/` | bulk zakaz body | Auth | ✅ `zakazBulk` |
| GET | `/{id}/batch/` | — | Auth | ✅ `zakazBatch` |

**`product_name`:** import javobida faqat mahsulot nomi qaytadi (seriya raqamisiz) — «rv (rv)» emas, «rv».

**`import_batch` (UUID, nullable):** har bir manual import qatoriga yoziladi. Yangi bulk yaratishda avtomatik yangi UUID; mavjud guruhga qator qo‘shishda ixtiyoriy yuboriladi (`POST /bulk/` yoki `POST /` body da). Tahrir (`PATCH`) da o‘zgartirilmaydi. Javobda barcha rollar uchun qaytariladi (Operator serializer ham).

**Qisman to‘lov chegarasi:** `payment_status=partial` bo‘lganda `paid_amount` **jami import summasidan** (`unit_price × quantity`) oshmasligi kerak — bulk, single `POST` va `PATCH` da bir xil tekshiriladi (`400`). Narx (`unit_price`) yo‘q importda qisman to‘lov umuman qabul qilinmaydi — summani solishtirib bo‘lmaydi. UI da input `max` bilan cheklangan, jami summa ko‘rsatiladi va saqlashdan oldin xato matni chiqadi.

**Operator to‘lov himoyasi:** Operator `PATCH` da `payment_status` / `paid_amount` yuborsa ham serializer maydonlari cheklangan — DB dagi qiymatlar o‘zgarmaydi (`ZakazOperatorSerializer`). Bulk va single `POST` da backend to‘lov maydonlarini strip qiladi.

**Import → kassadan chiqim (`sync_zakaz_expense`):** faqat `zakaz_type=manual` uchun. Import yaratilganda/yangilanganda backend `Expense` yozuvini yaratadi/yangilaydi (`expenses.Expense.zakaz` FK). Eski xato `Payment(zakaz=…)` yozuvlari o‘chiriladi — import **kirim emas, chiqim**.

| `payment_status` | Chiqim summasi (`Expense.amount`) |
|---|---|
| `paid` | Jami import summasi (`total`) |
| `partial` | `paid_amount` (0 dan katta bo‘lishi shart) |
| `unpaid` | Jami import summasi (`total`) — to‘lanmagan bo‘lsa ham kassadan chiqim sifatida qayd etiladi |

Chiqimlar kassa jurnalida `kind=out`, `source=import` ko‘rinadi. Excel export: `GET /reports/excel/kassa/` (jurnal) yoki `GET /reports/excel/imports/` (zakaz ro‘yxati).

**Narxlar (`unit_price` / `selling_price`):** import qatorida **kelish narxi** (`unit_price`) va **ketish narxi** (`selling_price`) `prices_manage` roli uchun MAJBURIY. Ikkalasi ham ombordagi mahsulotga yoziladi (`purchase_price` / `selling_price`) — mavjud mahsulot tanlansa ham yangilanadi. `vat_percent` qatorda beriladi (bo‘lmasa mahsulotniki olinadi); **QQS har doim kelish narxi asosida** hisoblanadi va javobda `vat_amount`, `total_with_vat` bo‘lib qaytadi.

**Shartnoma raqami (yangilangan — endi umumiy, erkin matn):** `contract_number` yuborilmasa backend **umumiy** ketma-ket raqamni atomar band qiladi (endi kunlik emas — 1, 2, 3, ... hech qachon qayta boshlanmaydi, barcha modullar — buyurtma/zakaz/faktura — bitta hisoblagichdan oladi). `GET /orders/next-contract-number/` faqat ko‘rsatadi (band qilmaydi), shuning uchun forma raqamni oldindan ko‘rsatishi va saqlashda uni yubormasligi kerak (`contract_date` parametri endi natijaga ta'sir qilmaydi — faqat moslik uchun qabul qilinadi). Xodim istasa maydonga istalgan boshqa qiymatni ham qo‘lda yozishi mumkin — format tekshirilmaydi.

**Manual import — `new_product` inline** (POST body, `product` o‘rniga):

```json
{
  "quantity": 10,
  "supplier": "Yetkazuvchi",
  "contract_date": "2026-08-11",
  "expected_date": "2026-08-25",
  "unit_price": "1500000",
  "selling_price": "1900000",
  "vat_percent": "12",
  "payment_status": "partial",
  "paid_amount": "500000",
  "currency": "UZS",
  "new_product": {
    "name": "Yangi tovar",
    "serial_number": "SN-001",
    "barcode": "8600000000001",
    "unit": "piece",
    "vat_percent": "12",
    "purchase_price": "1200000",
    "selling_price": "1900000",
    "delivery_price": "15000000"
  }
}
```

`serial_number` bo‘sh bo‘lsa **avtomatik yaratilmaydi** — mahsulot seriya raqamsiz saqlanadi (`null`). Seriya raqami **noyob**: omborda band raqam yuborilsa `400` qaytadi (`new_product.serial_number` yoki `serial_number` maydonida) — bo‘sh seriya cheklanmaydi. Bitta bulk so‘rov ichida ikki qatorda bir xil seriya bo‘lsa ham `400` (`items` xatosi: «2-qator: … 1-qatorda ham ishlatilgan»). Xuddi shu qoida buyurtma (`/invoices/`) qatorlari uchun ham amal qiladi — ikki qator bir xil (yangi) seriyani boshqa mahsulot nomi bilan ishlatsa `lines` xatosi qaytadi; bir xil nom bilan (bitta mahsulot ikki qatorga bo‘lingan holat) ruxsat etiladi.

`product` va `new_product` **bitta qator** ichida bir vaqtda bo‘lmaydi; lekin ikkalasidan **biri majburiy** — `new_product` yuborilsa `product` talab qilinmaydi. Bir importda bir nechta qator bo‘lsa, qatorlar orasida aralash mumkin: biri `product` (ombordan), boshqasi `new_product` (yangi mahsulot) — `POST /orders/zakaz/bulk/` orqali.

**Serializer javobi:** `ZakazOperatorSerializer` `new_product` maydonini qaytaradi (write-only emas, read uchun).

**Non-management inline import:** `new_product` ichidagi `purchase_price` va `delivery_price` backendda olib tashlanadi — Operator yangi mahsulot yaratishi mumkin, lekin narx maydonlari saqlanmaydi.

### Shartnomalar reestri — `/api/v1/orders/contracts/`

| Method | Path | Query | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `page_size`, `product`, `contract_number`, `source_type`, `order`, `zakaz`, `contract_date`, `search` | Auth | ✅ `contracts` |
| GET | `/{id}/` | — | Auth | ✅ `retrieve` |

Read-only. Yozuvlar tizim avtomatik yaratadi.

### Ombor — `/api/v1/warehouse/`

**Kategoriyalar** `/categories/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `search` | Auth, read | ✅ `categories` |
| POST | `/` | `{ name, parent }` | Operator+ | ✅ `create` |
| GET/PATCH/DELETE | `/{id}/` | — | Operator+ | ✅ `retrieve`/`update`/`remove` |

List faqat root node + `children` daraxti.

**Mahsulotlar** `/products/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `search`, `category` (ost-kategoriyalar bilan), `purchase_price__isnull`, `selling_price__isnull` | Auth | ✅ `products` |
| POST | `/` | product body | Operator+ | ✅ `create` |
| GET/PATCH/DELETE | `/{id}/` | — | Operator+ | ✅ CRUD |
| POST | `/{id}/add-stock/` | `{ quantity, asos, warehouse_location?, contract_number?, faktura? }` | Operator+ | ✅ `addStock` |
| GET | `/{id}/contracts/` | — | Auth | ✅ `productContracts` |

**Holati (`origin`):** `import` — tovar hali kelmagan (buyurtma/import qatoridan yaratilgan), ro‘yxatda «Import» deb ko‘rsatiladi va **buyurtma qatorlarida tanlash uchun chiqmaydi**. Import «Qabul qilindi» bo‘lgach (`Zakaz.receive()`) `origin` avtomatik `warehouse` ga o‘tadi — shundan keyin tovar oddiy ombor mahsuloti bo‘lib, buyurtmada tanlanadi.

**`category` MAJBURIY — har uch yo‘lda:**
- `POST /warehouse/products/` — `category` bo‘lmasa `400`; mahsulot formasi (yaratish va tahrirlash) kategoriya select’ini ko‘rsatadi.
- `POST /orders/zakaz/bulk/` va `POST /orders/zakaz/` — `new_product.category` majburiy; import jadvalida «Kategoriya» ustuni bor.
- `POST/PATCH /invoices/` — qator ombordagi mahsulotga mos kelmasa (yangi mahsulot ochiladi) `lines[].category` majburiy (write-only maydon, faqat mahsulot yaratish uchun); buyurtma jadvalida «Kategoriya» ustuni bor.

Mahsulotlar ro‘yxatida **Kategoriya** (`category_name`) va **Model** ustunlari ko‘rsatiladi. Ro‘yxat **Filtr** panelida kategoriya bo‘yicha saralanadi (`?category=<id>`) — tanlangan kategoriya **va uning barcha ost-kategoriyalari** mahsulotlari chiqadi (MPTT `get_descendants`).

`pending_import_quantity` — hali qabul qilinmagan (yo‘ldagi) import miqdori: faol zakazlar bo‘yicha `quantity − received_qty`. Ombor qoldig‘i (`available_quantity`) faqat import **«Qabul qilindi»** bo‘lgach oshadi, shuning uchun ro‘yxatda qoldiq yonida «+N yo‘lda» ko‘rsatiladi.

`serial_number` — **ixtiyoriy va avtomatik yaratilmaydi**: bo‘sh yuborilsa `null` saqlanadi (unique, lekin bir nechta `null` bo‘lishi mumkin). `origin` — `warehouse` (ombordan yaratilgan, default) yoki `import` (buyurtma/import qatoridan avtomatik qo‘shilgan); `origin_display` inson o‘qiydigan nom.

**Qoldiqlar** `/stocks/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `product`, `warehouse_location`, `category`, `status`, `date_from`, `date_to`, `search` | Auth | ✅ `stocks` |
| POST/PATCH/DELETE | `/`, `/{id}/` | stock body | Operator+ | ✅ CRUD |

`status`: `in_stock` \| `low_stock` \| `out_of_stock`. Bron bor qoldiqni o‘chirib bo‘lmaydi.

### Sotuvlar — `/api/v1/sales/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `page_size`, `product`, `client`, `sold_date`, `search`, `date_from`, `date_to`, `ordering`, `page` | Auth | ✅ `sales` |
| POST | `/` | sale body | Operator+ | ✅ `create` |
| GET/PATCH/DELETE | `/{id}/` | — | Operator+ | ✅ CRUD |
| POST | `/bulk/` | bulk sales body | Operator+ | ✅ `salesBulk` |

FIFO ombordan ayiradi. Operator uchun narx/foyda yashirilishi mumkin.

**Sotuv → kassaga tushum (`sync_sale_payment`):** `POST /sales/` (yagona, bulk, operator) yaratilganda/yangilanganda backend `Payment` + `PaymentTransaction` yozadi — to‘liq sotuv summasi kassaga **tushum** sifatida tushadi. Jurnalda `kind=in`, `source=sale`.

### Kassa — `/api/v1/cash/`

**To‘lovlar** `/payments/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `page_size`, `status`, `include_paid`, `client`, `currency`, `order`, `sale`, `due_date`, `search` | Auth — Operator ham o‘qiydi (summasiz), Accountant/Management to‘liq | ✅ `payments` |
| POST | `/` | payment body | Accountant/Management | ✅ `create` |
| GET/PATCH | `/{id}/` | — | GET: Auth (Operator summasiz); PATCH: Accountant/Management | ✅ `retrieve`/`update` |
| DELETE | `/{id}/` | — | Accountant/Management | ✅ `remove` |
| POST | `/{id}/pay/` | `{ amount, comment }` | Accountant/Management | ✅ `pay` |
| GET | `/summary/` | — | Accountant/Management | ✅ `paymentsSummary` |
| GET | `/ledger/` | `page`, `page_size`, `search`, `source`, `kind` | Accountant/Management (`IsAccountantWithManagementRead`, yozish yo‘q — faqat GET) | ✅ `kassaLedger` |
| POST | `/convert/` | `{ direction: 'uzs_to_usd'\|'usd_to_uzs', amount, rate }` | Accountant/Management | ✅ `cashConvert` |
| POST | `/adjust-balance/` | `{ currency: 'UZS'\|'USD', target_balance, asos }` | **Management** (`IsManagement`) | ✅ `adjustCashBalance` |

**Ro‘yxatda `paid` yashirin** — `?status=paid` yoki `?include_paid=true`.

**Valyuta konvertatsiyasi (`/payments/convert/`)** — kassa balansi (UZS/USD) orasida pul ko'chiradi va DBga (`CashConversion`) yozadi. `amount` — manba valyutadagi summa (kassadan ayiriladi), `rate` — 1 USD necha UZS ekanligi. `uzs_to_usd`: `amount_to = amount / rate` (USD balansga qo'shiladi). `usd_to_uzs`: `amount_to = amount * rate` (UZS balansga qo'shiladi). Manba valyutada balans yetarli bo'lmasa `400` (`{amount: "..."}`). Javob: `{id, direction, amount_from, amount_to, rate, comment, created_by, created_by_name, created_at}`. `GET /payments/summary/` javobidagi `net_balance_uzs`/`net_balance_usd` konvertatsiyalarni ham hisobga oladi.

**Balansni qo'lda tuzatish (`/payments/adjust-balance/`)** — kassa balansi (UZS yoki USD) ko'rsatilgan `target_balance`ga o'zgartiriladi; farq (`target_balance − joriy balans`) backendda hisoblanadi va DBga (`CashBalanceAdjustment`) yoziladi. `asos` **MAJBURIY** (bo'sh/faqat probel — `400`). Faqat **Management** (Accountant ham `403` oladi — pul konvertatsiyasidan farqli). Javob: `{id, currency, amount, asos, created_by, created_by_name, created_at}` (`amount` — hisoblangan farq, manfiy bo'lishi mumkin). Har bir tuzatish `GET /payments/ledger/` jurnalida `source=adjustment` sifatida ko'rinadi (kim/`client_name` = `created_by_name`, izoh = `asos`) — shu orqali "kim, qachon, nima uchun" tarixi saqlanadi. Frontend: `KassaMetric` balans kartalarining qalam (✏️) tugmasi — faqat `session.is_management` bo'lganda ko'rinadi.

**Operator kassani ko‘radi, lekin pul yo‘q:** `GET /cash/payments/` va `/{id}/` Operatorga ham ochiq (`IsAccountantWithManagementRead`), lekin backend `PaymentOperatorSerializer` qaytaradi — javobda `total_amount`, `commission`, `paid_amount`, `remaining` maydonlari **umuman yo‘q**. Frontend bu maydonlar bo‘lmasligiga tayyor bo‘lsin (§21, qoida 7). Yozish (`POST`/`PATCH`/`DELETE`/`pay`) Operatorga hech qachon ochiq emas — `403`.

**Valyuta kursi** `/exchange-rates/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `currency`, `manual_override`, `rate_date` | Auth | ❌ (faqat latest UI da) |
| GET | `/{id}/` | — | Auth | ❌ |
| POST | `/` | `{ mb_rate, buy_rate?, sell_rate?, note? }` | Management | ✅ `create('/cash/exchange-rates/')` |
| PATCH | `/{id}/` | kurs maydonlari | Auth | ❌ |
| GET | `/latest/` | `refresh=true\|false` | Auth | ✅ `exchangeRateLatest` |
| GET | `/settings/` | — | Auth | ✅ `exchangeRateSettings` |
| PATCH | `/settings/` | `{ auto_fetch_enabled?, preferred_rate_source?, preferred_bank_code?, preferred_bank_side? }` | Management | ✅ `updateExchangeRateSettings` |

Celery beat: `refresh_infinbank_usd_rate` har **1 soat** (`root/celery.py`). `auto_fetch_enabled=false` bo‘lsa task o‘tkazib yuboriladi.

### Korxona profili — `/api/v1/company-profile/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | — | Auth | ✅ `companyProfile` |
| PATCH | `/` | `name`, `stir`, `director_jshshr`, `director_fish`, `mfo`, `bank_name`, `oked`, `bank_account`, `address`, `phone`, `email` | Management | ✅ `updateCompanyProfile` |

Singleton (`pk=1`). Buyurtmalar editorida bajaruvchi **«Korxona profili (bizning)»** tanlanganda «Bajaruvchi» bloki uchun ishlatiladi.

**Validatsiya (backend + frontend):** STIR — 9 raqam; JSHSHIR — 14 raqam, 1-raqam 1–6 (checksum yo‘q); MFO — 5; OKED — 5; telefon — `+998…`; bank hisob — 20 raqam. Xatoliklar maydon ostida qizil matn (`FieldError` / `ApiError.fields`); forma validatsiyasida toast ishlatilmaydi. Frontend: `frontend/src/lib/uzValidators.js` → `validateCompanyProfile()` (`CompanyProfileModal`).

**Mijozlar editor validatsiyasi** (`Editor`, title=`Mijozlar`) — `validateClientFields()` (`uzValidators.js`), saqlashdan oldin client-side; backend `ClientSerializer` alohida UZ regex qo‘llamaydi.

| Tur | Maydon | Qoidalar |
|---|---|---|
| Yuridik | `company_name` | Majburiy |
| Yuridik | `phone` | Majburiy, `validateUzPhone` |
| Yuridik | `inn` | Ixtiyoriy; to‘ldirilsa STIR 9 raqam |
| Yuridik | `mfo` | Ixtiyoriy; to‘ldirilsa 5 raqam |
| Yuridik | `director_jshshr` | Ixtiyoriy; to‘ldirilsa JSHSHIR 14 raqam, 1-raqam 1–6 |
| Jismoniy | `full_name` | Majburiy |
| Jismoniy | `pinfl` | Majburiy, JSHSHIR 14 raqam, 1-raqam 1–6 |
| Jismoniy | `passport_number` | Majburiy |
| Jismoniy | `phone` | Majburiy, `validateUzPhone` |
| Ikkala | `email` | Ixtiyoriy; format tekshiruvi |

Buyurtmalar editoridagi **Yangi korxona qo‘shish** (`ClientPickerModal` ichida) shu `Editor` ni ochadi; saqlangach `done(created)` orqali yangi mijoz tanlangan tomonga biriktiriladi (`client` yoki `executor_client`, `POST /clients/`).

### Buyurtmalar (invoices) — `/api/v1/invoices/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `page_size`, `document_type`, `client`, `search`, `ordering` | Auth | ✅ `invoices` |
| POST | `/` | invoice body + `lines[]` | Operator/Management (yozish) | ✅ `createInvoice` |
| GET | `/{uuid}/` | — | Auth | ✅ `invoice` |
| PATCH | `/{uuid}/` | invoice + `lines[]` | Operator/Management | ✅ `updateInvoice` |
| DELETE | `/{uuid}/` | — | Management | ✅ `removeInvoice` |

`document_type`: `contract_sk` \| `invoice` \| `act`.

**Bajaruvchi (executor):**

| Maydon | Turi | Tavsif |
|---|---|---|
| `executor_type` | `company_profile` \| `client` | Default: `company_profile` — korxona profili; `client` — mijozlar reestridan boshqa korxona |
| `executor_client` | UUID \| `null` | `executor_type=client` bo‘lsa majburiy — `clients.Client` FK |
| `executor_name` | string (read-only) | `executor_type=client` va `executor_client` bo‘lsa — mijoz nomi |

Backend validatsiya: `executor_type=client` → `executor_client` majburiy; `company_profile` → `executor_client` saqlashda `null` qilinadi.

**Buyurtmachi (hamkor):** `client` — majburiy FK (`clients.Client`).

Qator (`lines[]`) maydonlari: `product`, `product_name`, `identification_code`, `barcode`, `unit`, `quantity`, `unit_price`, `selling_price`, `delivery_amount`, `vat_percent`, `vat_amount`, `total_amount`.

**Narxlar:** `unit_price` — **kelish narxi** (UI: «Narxi (kelish)»); yetkazish qiymati va QQS aynan shundan hisoblanadi. `selling_price` — **sotuv narxi** (UI: «Sotuv narxi», jadvalda «Jami» dan keyingi ustun), ixtiyoriy (`null` bo‘lishi mumkin), hisobga ta’sir qilmaydi. Ombordan tanlanganda qatorga mahsulotning `purchase_price` va `selling_price` qiymatlari tushadi; yangi mahsulot yaratilganda esa aksincha — qator narxlari mahsulotga yoziladi va shu narxlar bilan import (zakaz) yozuvi ochiladi.

**Hisob qoidasi (`InvoiceLineItem.compute_line`):** NARX ustun — `quantity` × `unit_price` bo‘lsa `delivery_amount` doim shundan, `vat_amount` esa `delivery_amount` dan hisoblanadi, `reverse_calculation=true` bo‘lganda ham. Ya’ni narx yoki QQS % o‘zgarishi bilan QQS miqdori va jami darhol qayta hisoblanadi (frontendda ham — `calcInvoiceLine`), eski qiymatlar qolib ketmaydi. Teskari hisob faqat narx bo‘lmaganda ishlaydi: `total_amount` dan orqaga `delivery_amount` va `vat_amount` chiqariladi (UI da jami/QQS/yetkazish qo‘lda kiritilsa narx ham qayta hisoblanadi).

Operator uchun narx maydonlari (`unit_price`, `delivery_amount`, `vat_amount`, `total_amount`) javobdan olib tashlanadi.

`prices_view` yo‘q foydalanuvchilar uchun invoice darajasidagi `total_delivery`, `total_vat`, `grand_total` ham qaytmaydi (serializer context `can_view_prices=false`).

Mazmun: `content_title`, `content_body` — frontend preview (`DocumentPreviewModal`) bilan ko‘rsatiladi.

**Shartnoma (SK) → kassaga chiqim (`sync_invoice_expense`, yangi):** `document_type=contract_sk` hujjat yaratilganda/tahrirlanganda, **ombordagi (import bo‘lmagan)** mahsulot qatorlari bo‘yicha summa (`delivery_amount + vat_amount` jami) kassadan **chiqim** (`Expense`, `expenses_expense.invoice` FK) sifatida avtomatik yoziladi. Yangi (shu hujjat orqali birinchi marta ochilgan, `origin=import`) mahsulot qatorlari bu yerda hisoblanmaydi — ular alohida import (Zakaz) oqimi orqali kassaga tushadi (`sync_zakaz_expense`, o‘sha zakaz qabul qilinganda/to‘langanda), shu sabab ikki marta hisoblanmaydi. `document_type=invoice`/`act` hujjatlari kassaga umuman yozilmaydi (ular SK’ga qo‘shimcha hujjat, summani takrorlamasin). Hujjat o‘chirilsa (`DELETE`) bog‘liq chiqim ham o‘chadi. Jurnalda (`GET /cash/payments/ledger/?kind=out`) `source=expense` sifatida ko‘rinadi.

### Xarajatlar — `/api/v1/expenses/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/expense-types/` | `search`, `page_size` | Auth | ✅ `expenseTypes` |
| GET | `/expense-types/{id}/` | — | Auth | ❌ |
| GET | `/expense-subtypes/` | `expense_type`, `search` | Auth | ✅ `expenseSubtypes` |
| POST | `/expense-subtypes/` | subtype body | Accountant+ | ❌ |
| GET | `/expense-subtypes/{id}/` | — | Auth | ❌ |
| GET | `/expenses/` | `expense_type`, `sub_type`, `currency`, `responsible`, `date_from`, `date_to`, `search` | Accountant/Management | ✅ `expenses` |
| POST/PATCH/DELETE | `/expenses/`, `/expenses/{id}/` | JSON yoki multipart | Accountant | ✅ `createForm`/`updateForm` |
| GET | `/expenses/summary/` | `date_from`, `date_to`, `currency` | Accountant/Management | ❌ (to‘g‘ridan) |
| GET | `/summary/` | alias yuqoridagi | Accountant/Management | ✅ `expensesSummary` |

### Mijozlar — `/api/v1/clients/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `page_size`, `search` (F.I.Sh, INN, JSHSHIR, passport, kompaniya, email), `is_active`, `date_from`, `date_to`, `ordering`, `page` | `can_view_clients` | ✅ `clients` |
| POST/PATCH/DELETE | `/`, `/{uuid}/` | client body | `can_view_clients` | ✅ CRUD |

Primary key — **UUID**. Maxfiy maydonlar bazada shifrlanadi.

### Hisobotlar — `/api/v1/reports/`

| Method | Path | Query | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/summary/` | dashboard filtrlari | Accountant/Management | ✅ `reports` |
| GET | `/warehouse/` | `date_from`, `date_to` | Accountant/Management | ✅ `reports` (paramsiz) |
| GET | `/cash/` | `date_from`, `date_to`, `client`, `payment_status` | Accountant/Management | ✅ `reports` |
| GET | `/expenses/` | `date_from`, `date_to` | Accountant/Management | ❌ |
| GET | `/top-products/` | `limit`, dashboard filtrlari | Accountant/Management | ✅ `reports` |
| GET | `/monthly-trend/` | `months`, dashboard filtrlari | Accountant/Management | ✅ `monthlyTrend` |
| GET | `/excel/sales/` | `date_from`, `date_to` | Accountant/Management | ✅ `exportSales` / `exportReport('sales')` |
| GET | `/excel/stock/` | — | Accountant/Management | ✅ `exportStock` / `exportReport('stock')` |
| GET | `/excel/expenses/` | `date_from`, `date_to` | Accountant/Management | ✅ `exportExpenses` / `exportReport('expenses')` |
| GET | `/excel/kassa/` | `date_from`, `date_to` | Accountant/Management | ✅ `exportKassa` / `exportReport('kassa')` |
| GET | `/excel/payments/` | `date_from`, `date_to` | Accountant/Management | ✅ `exportPayments` (kassa alias) |
| GET | `/excel/imports/` | `date_from`, `date_to` | Accountant/Management | ✅ `exportImports` / `exportReport('import')` |

### Bildirishnomalar — `/api/v1/notifications/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `page_size`, `is_read` | Auth (o‘ziga) | ✅ `notifications` |
| GET | `/{id}/` | — | Auth | ✅ `retrieve` |
| POST | `/{id}/mark_read/` | — | Auth | ✅ `notificationsMarkRead` |
| POST | `/mark_all_read/` | — | Auth | ✅ `notificationsMarkAllRead` |

Javob `mark_all_read`: `{ "status": "ok", "marked_read": 5 }`.

### Backendda bor, `api.js` da wrapper yo‘q

| Endpoint | Sabab / tavsiya |
|---|---|
| `GET /reports/expenses/` | Hisobotlar moduli; kerak bo‘lsa `api.js` ga qo‘shing |
| `GET /expenses/expenses/summary/` | Alias `/expenses/summary/` ishlatiladi |
| `GET /cash/exchange-rates/` (list) | Hozircha UI da kerak emas |
| `PATCH /cash/exchange-rates/{id}/` | Qo‘lda kurs — faqat POST ishlatiladi |
| `POST /expenses/expense-subtypes/` | Admin/accountant; UI da yo‘q |
| `GET /cash/payments/ledger/?date_from=` | Backend `build_ledger_entries` davrni qo‘llab-quvvatlaydi, lekin ViewSet hozircha query parametr yubormaydi — faqat `search`, `source`, `kind` |

---

## 17a. Buyurtmalar — `/invoices/` (batafsil)

Base:

```http
/api/v1/invoices/
```

Yangi hujjat:

```http
POST /api/v1/invoices/
```

```json
{
  "document_type": "contract_sk",
  "name": "Shartnoma",
  "contract_number": "5/1108",
  "place_signed": "Toshkent shahri",
  "contract_date": "2026-08-11",
  "valid_until": "2026-12-31",
  "client": "<uuid>",
  "executor_type": "company_profile",
  "executor_client": null,
  "reverse_calculation": false,
  "content_title": "1.",
  "content_body": "1.1. Tomonlar shartnoma shartlariga rioya qiladi...",
  "lines": [
    {
      "product": 1,
      "quantity": 2,
      "unit_price": "1500000",
      "selling_price": "1900000",
      "vat_percent": "12"
    },
    {
      "product_name": "Bazada yo‘q tovar",
      "category": 3,
      "quantity": 1,
      "unit_price": "500000",
      "selling_price": "800000",
      "vat_percent": "12"
    }
  ]
}
```

Backend mahsulotdan `product_name`, `barcode`, `identification_code`, `unit`, narx va QQS ni to‘ldiradi; `delivery_amount`, `vat_amount`, `total_amount` hisoblanadi (`unit_price` — **kelish narxi**, QQS shundan).

`contract_number` yuborilmasa o‘sha kunning keyingi raqami avtomatik band qilinadi. Ikkinchi qatordagidek ombordagi mahsulotga mos kelmaydigan tovar uchun `category` majburiy: backend mahsulotni `origin=import` bilan yaratadi va unga import (zakaz) yozuvini ochadi.

**Boshqa korxona bajaruvchi sifatida:**

```json
{
  "executor_type": "client",
  "executor_client": "<uuid>",
  "client": "<uuid>"
}
```

`executor_client` va `client` turli mijozlar bo‘lishi mumkin (masalan, siz vositachi sifatida A korxonasi nomidan B ga shartnoma tuzasiz).

**Narx ko‘rinishi:** `prices_view` yo‘q foydalanuvchilar uchun qator narxlari (`unit_price`, `delivery_amount`, `vat_amount`, `total_amount`) va invoice jami maydonlari (`total_delivery`, `total_vat`, `grand_total`) javobdan olib tashlanadi. Frontend `BuyurtmalarPage` da `can(session, 'prices_view')` bilan jami blokni yashiradi.

### UI oqimlari (`BuyurtmalarPage`)

| Rejim | URL | API chaqiriqlari |
|---|---|---|
| Ro‘yxat | `/buyurtmalar` | `GET /invoices/`, `GET /warehouse/products/`, `GET /company-profile/` (sahifa ochilganda bir marta) |
| Ko‘rish (modal) | Ro‘yxatda qoladi yoki `/buyurtmalar/{uuid}` | `GET /invoices/{uuid}/`, `GET /clients/{uuid}/` (buyurtmachi), kerak bo‘lsa `GET /clients/{uuid}/` (bajaruvchi) — **bir marta** (`viewFetchKeyRef` dublikatni bloklaydi) |
| Yangi | `/buyurtmalar/yangi` | Yuqoridagilar + `GET /orders/next-contract-number/` (sana o‘zgarganda) |
| Tahrir | `/buyurtmalar/{uuid}/tahrir` | `GET /invoices/{uuid}/`, `GET /company-profile/` |

**Layout:** «Bajaruvchi ma’lumotlari» | «Hamkorning ma'lumotlari» yonma-yon (`PartyInfoGrid`).

**Bajaruvchi paneli:**

| Rejim | UI | Manba |
|---|---|---|
| `executor_type=company_profile` (default) | Korxona profili kartasi + «Profilni tahrirlash» hint | `GET /company-profile/` |
| `executor_type=client` | `ClientPickerField` → `ClientPickerModal` — reestrdan qidiruv va qo‘shish | `GET /clients/?search=…`, saqlashda `executor_client` |

**Hamkor paneli:** `ClientPickerField` → `ClientPickerModal` (xuddi shu oqim; saqlashda `client`).

Ko‘rish — `InvoiceContractModal` (jadval + mazmun + «2. Tomonlarni yuridik manzillari va rekvizitlari»). Tahrir/yangi — `DocumentPreviewModal` («Hujjatni ko‘rsatish»). Preview/modalda bajaruvchi: `executorPartyData()` — profil yoki tanlangan `executor_client`.

**Hujjatni yuklab olish («Yuklab olish» tugmasi, ikkala modalda ham):** backendga so‘rov yubormaydi — `downloadInvoiceDocument()` (`App.jsx`) joriy `invoice`/`company`/`client`/`executorClient` ma’lumotlaridan `buildDocumentPrintHtml()` orqali to‘liq standalone HTML hujjat quradi, ko‘rinmas `<iframe>`ga yozadi va uning ichida `print()` chaqiradi (foydalanuvchi «Save as PDF» tanlaydi). `window.open` ishlatilmaydi — popup-bloklagichga qaram emas.

**Validatsiya:** `validateEInvoice()` — xatoliklar input ostida; «Hujjatni ko‘rsatish» / «Saqlash» da toast o‘rniga scroll birinchi qizil maydonga.

**`validateEInvoice()` maydonlari** (`App.jsx`):

| Maydon | Qoidalar |
|---|---|
| `contract_number` | Majburiy (bo'sh bo'lmasin); format erkin — regex tekshiruvi olib tashlandi, xodim istagan qiymatni yozishi mumkin |
| `place_signed` | Majburiy |
| `contract_date` | Majburiy |
| `valid_until` | Majburiy; `>= contract_date` |
| `client` | Majburiy (buyurtmachi / hamkor tanlangan) |
| `executor_type` | `company_profile` yoki `client` |
| `executor_client` | `executor_type=client` bo‘lsa majburiy; `client` bilan bir xil bo‘lmasin |
| `company` | Faqat `executor_type=company_profile` — korxona profilida `name` va `stir` |
| `content_title` | Majburiy |
| `content_body` | Majburiy |
| `lines[].product_name` | Har qator — majburiy |
| `lines[].identification_code` | Har qator — majburiy |
| `lines[].quantity` | Kamida 1 |
| `lines[].unit_price` | Faqat `prices_view` bo‘lsa majburiy — bu **kelish narxi**, QQS shundan hisoblanadi |
| `lines[].selling_price` | Ixtiyoriy («Sotuv narxi» ustuni) |
| `lines[].category` | Qator ombordagi mahsulotga bog‘lanmagan bo‘lsa majburiy (yangi mahsulot ochiladi) |
| `lines` (umumiy) | Kamida bitta to‘liq qator (`product_name` + `quantity` + `identification_code`) |

Xato kalitlari: `contract_number`, `client`, `executor_client`, `company`, `lines.0.product_name` va hokazo. Komponent: `EInvoiceFieldError`.

### Buyurtmalar ro‘yxati (`DataTable`)

`BuyurtmalarPage` — `/buyurtmalar` da `DataTable` ustunlari:

| Ustun | Manba (`row`) | Eslatma |
|---|---|---|
| № | Indeks + 1 | — |
| Mijoz | `client_name` | — |
| Shartnoma | `contract_number` | — |
| Mahsulot | `invoiceProductsLabel(row)` | Birinchi qator nomi yoki «N ta mahsulot» |
| Soni | `invoiceTotalQuantity(row)` | Qatorlar miqdori yig‘indisi |
| Jami summa | `grand_total` | Faqat `prices_view` bo‘lsa |
| Muddat | `contract_date` | `formatDateUz` |
| Turi | `document_type_display` | SK / Hisob-faktura / Dalolatnoma |

Amallar: **ko‘z** (ko‘rish modali), **qalam** (tahrir — `einvoice_manage`). Qator bosilganda ham ko‘rish ochiladi.

**Shartnomalar reestri:** SK (`document_type=contract_sk`) saqlanganda backend `ProductContract` ga `invoice_created` / `invoice_edited` yozuvi qo‘shadi (tovar `product` FK bilan mos bo‘lsa). §10 `source_type` ro‘yxatiga qarang.

Korxona profili (`GET/PATCH /company-profile/`) faqat `executor_type=company_profile` bo‘lganda bajaruvchi bloki uchun ishlatiladi; profil yangilanganda `company-profile-updated` eventi editorlarni yangilaydi.

---

## 5. Auth va user sessiya (batafsil)

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
      "order_status_manage": true,
      "warehouse_view": true,
      "warehouse_create": true,
      "warehouse_manage": true,
      "prices_view": true,
      "prices_manage": true,
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
      "users_manage": true,
      "einvoice_view": true,
      "einvoice_manage": true
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

## 6. Role va UI permission

Frontend menyuni `abilities` bo‘yicha ko‘rsatadi. Ruxsat yo‘q menu UI’da ko‘rinmasligi kerak.

| Ability | Ma’nosi | Kimda |
|---|---|---|
| `dashboard` | bosh sahifa statistikasi | Accountant, Management |
| `orders_view` | eski buyurtmalar API (`/orders/`) — UI da ishlatilmaydi | — |
| `orders_manage` | eski buyurtmalar CRUD — UI da ishlatilmaydi | — |
| `order_status_manage` | import status (`confirmed`/`ordered`/`received`/…) — inline va bulk | Management |
| `warehouse_view` | mahsulotlarni ko‘rish | Operator, Accountant, Management |
| `warehouse_create` | mahsulot qo‘shish (narxsiz) | Operator, Management |
| `warehouse_manage` | mahsulot/kirim boshqarish | Operator, Management |
| `prices_view` | narx/kelish narxi, invoice/order summalari ko‘rish | Accountant, Management |
| `prices_manage` | narx boshqarish | Management |
| `clients_view` | mijozlarni ko‘rish; `api.clients()` dropdown yuklash | `can_view_clients` |
| `clients_manage` | mijoz CRUD | `can_view_clients` |
| `sales_view` | sotuvlarni ko‘rish | Operator, Accountant, Management |
| `sales_manage` | sotuv yaratish/tahrirlash | Operator, Management |
| `cash_view` | kassa ko‘rish | hammaga (summalar Accountant/Management) |
| `cash_manage` | to‘lov qabul qilish | Accountant, Management |
| `expenses_view` | xarajatlarni ko‘rish | hammaga (summalar Accountant/Management) |
| `expenses_manage` | xarajat yaratish/tahrirlash | Accountant, Management |
| `reports_view` | hisobotlar | Accountant, Management |
| `notifications_view` | bildirishnomalar | hammaga |
| `procurement_view` | importlar ko‘rish | Operator, Accountant, Management |
| `procurement_manage` | import yaratish/tahrirlash (status emas!) | Operator, Accountant, Management |
| `contracts_view` | shartnomalar reestri | Operator, Accountant, Management |
| `categories_view` | kategoriyalar | Operator, Management |
| `stocks_view` | qoldiqlar | Operator, Management |
| `einvoice_view` | Buyurtmalar sahifasini ko‘rish | Operator, Accountant, Management |
| `einvoice_manage` | Buyurtma (invoice) yaratish/tahrirlash | Operator, Management |
| `users_view` | userlarni ko‘rish | Management |
| `users_manage` | user boshqarish; FX sozlamalar, kurs manbasi, qo‘lda kurs | Management |

**Muhim farqlar:**

- `procurement_manage` — import **yaratish/tahrirlash**; status o‘zgartirish emas.
- `order_status_manage` — import gridda inline status va bulk status (`confirmed` → `ordered` → `received` …).
- `clients_view` — `SaleEditor`, `BuyurtmalarPage` da `searchClients()` / `fetchClient()` (`clients_view` bo‘lmasa combobox o‘chiriladi).
- `users_manage` — `FxRatePanel` tab almashtirish, qo‘lda saqlash, Infinbank ↻ yangilash.
- `prices_view` — invoice qator narxlari va `total_delivery` / `total_vat` / `grand_total`.

Frontend: `can(session, 'ability')` — `session.user.abilities` dan o‘qiladi.

Operator uchun narx/foyda maydonlari ayrim javoblarda qaytmaydi. Frontend bunday maydonlar yo‘qligiga tayyor bo‘lsin.

### UI gating xaritasi (ability → UI)

| UI element | Ability | Fayl / komponent |
|---|---|---|
| Sidebar / bottom nav sahifa | Har bir nav item `ability` (masalan `einvoice_view`, `procurement_view`) | `App.jsx` — `SIDEBAR_NAV`, `NAV_GROUPS` |
| Grid «Yangi» tugmasi | `manageAbilities[title]` yoki `warehouse_create` (Ombor) | `ResourcePage` — `createAbilities`, `manageAbilities` |
| Grid qator tahriri / o‘chirish | `manageAbilities[title]` | `ResourcePage` — `canEditRows` |
| Import inline status + bulk status | `order_status_manage` (**emas** `procurement_manage`) | `ResourcePage`, `InlineStatusSelect`, `StatusChangeModal` |
| Import yaratish/tahrir formasi | `procurement_manage` | `ResourcePage` — `canManage` |
| Mijoz kartasi URL | `clients_view` | `routes.jsx`, `App.jsx` |
| Global qidiruv — mijozlar | `clients_view` | `GlobalSearch.jsx` |
| Global qidiruv — buyurtmalar | `einvoice_view` | `GlobalSearch.jsx` |
| Hamkor / mijoz tanlash (Buyurtmalar) | `clients_view` | `ClientPickerModal`, `lib/clients.js` |
| Mijoz combobox (Sotuv) | `clients_view` | `SearchableCombobox`, `lib/clients.js` |
| Yangi korxona qo‘shish (Buyurtmalar modal) | `clients_manage` | `Editor` → `POST /clients/` |
| Tovar tanlash (qator) | `einvoice_manage` (editor) | `ProductPickerModal` |
| Editor mijoz combobox | `clients_view` | `SaleEditor` |
| Editor korxona tanlash | `clients_view` | `BuyurtmalarPage` — `ClientPickerModal` |
| Editor mahsulot combobox | (ability shart emas) | `api.products()` doim chaqiriladi |
| Invoice jami / qator narxlari | `prices_view` | `BuyurtmalarPage`, backend serializer |
| FX tab / qo‘lda saqlash / ↻ | `users_manage` | `FxRatePanel` |
| Foydalanuvchilar sahifasi | `users_view` (ko‘rish), `users_manage` (CRUD) | `HIDDEN_PAGES` |
| Hisobotlar → Excel export | `reports_view` | `ReportExportPanel` |
| Kassa jurnali / balans | `cash_view` + `prices_view` (summalar) | `KassaPage` |

`manageAbilities` (`ResourcePage`):

```text
Import      → procurement_manage   (status emas!)
Ombor/…     → warehouse_manage
Mijozlar    → clients_manage
Sotuvlar    → sales_manage
Kassa       → cash_manage
Xarajatlar  → expenses_manage
Foydalanuvchilar → users_manage
```

## 7. Valyuta kursi

Backend Infinbank sahifasidan USD `MB kurs` ni oladi:

```text
https://www.infinbank.com/uz/private/exchange-rates/
```

HTML ichida `rates-table` dan `MB kurs` qatori va `USD` ustuni ajratiladi.

### Oxirgi USD kurs (kengaytirilgan javob)

```http
GET /api/v1/cash/exchange-rates/latest/?refresh=false
GET /api/v1/cash/exchange-rates/latest/?refresh=true
```

`refresh=true` — Infinbankdan majburiy sync (`sync_today_usd_rate`) va [bankxizmatlari.uz](https://bankxizmatlari.uz/uz/rates/) dan bank kurslarini yangilash. Tashqi manba ishlamasa bazadagi oxirgi kurs fallback; yo‘q bo‘lsa `503`.

Qoʻshimcha manba — **bankxizmatlari.uz** (`data-usd-buy-bank` / `data-usd-sale-bank`, filial kursi `BANK`):

```text
https://bankxizmatlari.uz/uz/rates/
```

Ko‘rsatiladigan 6 ta bank (InFinBank + 5 ta mashhur bank): InFinBank, O‘zmilliybank, Kapitalbank, Hamkorbank, Xalq banki, Agrobank.

Javob (faol kurs maydonlari + ikkala manba + bank kurslari):

```json
{
  "infinbank": {
    "currency": "USD",
    "mb_rate": "11934.61",
    "source": "infinbank",
    "manual_override": false,
    "rate_date": "2026-08-11"
  },
  "manual": {
    "currency": "USD",
    "mb_rate": "11950.00",
    "source": "manual",
    "manual_override": true,
    "rate_date": "2026-08-11"
  },
  "active_source": "bank",
  "preferred_rate_source": "bank",
  "preferred_bank_code": "049",
  "preferred_bank_side": "sell",
  "active_bank_code": "049",
  "active_bank_name": "Kapitalbank",
  "active_bank_side": "sell",
  "currency": "USD",
  "mb_rate": "11945.00",
  "rate_date": "2026-08-12",
  "source": "bank",
  "market_rates": {
    "source": "bankxizmatlari",
    "source_url": "https://bankxizmatlari.uz/uz/rates/",
    "fetched_at": "2026-08-12T12:30:00+05:00",
    "banks": [
      {
        "code": "053",
        "name": "InFinBank",
        "buy_rate": "11920.00",
        "sell_rate": "12000.00",
        "updated_at": "Yangilanish vaqti: 12:01, 12.08.2026",
        "source": "bankxizmatlari"
      },
      {
        "code": "002",
        "name": "O'zmilliybank",
        "buy_rate": "11870.00",
        "sell_rate": "11990.00",
        "updated_at": "Yangilanish vaqti: 11:02, 12.08.2026",
        "source": "bankxizmatlari"
      }
    ]
  }
}
```

**Faol kurs (`mb_rate`, `active_source`):** hisob-kitobda ishlatiladi — dashboard, import USD→UZS va hokazo.

| `preferred_rate_source` | Hisob-kitob manbasi |
|---|---|
| `infinbank` | `infinbank.mb_rate` (Infinbank.com MB kurs) |
| `manual` | Bugungi qo‘lda kurs (`manual.mb_rate`) |
| `bank` | `market_rates.banks[]` dan `preferred_bank_code` + `preferred_bank_side` (`buy` = sotib olish, `sell` = sotish) |

`market_rates` — bankxizmatlari.uz dan olingan ro‘yxat (dropdown to‘ldirish uchun). Kurslar 1 soat keshlanadi; `refresh=true` majburiy yangilaydi.

Bank kodlari (doimiy ro‘yxat): `053` InFinBank, `002` O‘zmilliybank, `049` Kapitalbank, `012` Hamkorbank, `006` Xalq banki, `004` Agrobank.

### Frontend: `FxRatePanel` (`App.jsx`)

Komponent: `BankRateDropdown` — `<select>` orqali bank tanlash.

| Rejim | Prop | UI |
|---|---|---|
| Topbar | `header` | Dropdown (bank nomi + kurs) + faol summa + ↻ |
| Import / Xarajat | `compact` | Dropdown + Sotish/Sotib olish select + Qo‘lda tugmasi/input |
| Dashboard | (default) | Dropdown + ↻ + «Qo‘lda kurs» + «Hisobda: …» |

Dropdown variantlari (misol):

- `Infinbank MB — 11 889,95`
- `Kapitalbank — 11 945,00` (tanlangan `preferred_bank_side` bo‘yicha)
- `Qo‘lda — 11 950,00` (saqlangan bo‘lsa)

**Ability gating (`users_manage`):**

- Bank dropdown va Sotish/Sotib olish — faqat `users_manage`
- Qo‘lda kurs saqlash (`POST /cash/exchange-rates/`) — faqat `users_manage`
- ↻ (`?refresh=true`) — Infinbank MB + `market_rates` yangilaydi

`users_manage` bo‘lmagan foydalanuvchi faqat joriy kursni ko‘radi.

Backend ruxsat: `PATCH /cash/exchange-rates/settings/` va `POST /cash/exchange-rates/` — **Management** (`IsManagement()`).

### Qo‘lda kurs saqlash

```http
POST /api/v1/cash/exchange-rates/
```

```json
{
  "mb_rate": "11950.00",
  "buy_rate": "11950.00",
  "sell_rate": "11950.00",
  "manual_override": true,
  "note": "Qo‘lda kiritilgan kurs"
}
```

Backend avtomatik: `currency=USD`, `source=manual`, `rate_date=today`.

### Sozlamalar

```http
GET /api/v1/cash/exchange-rates/settings/
PATCH /api/v1/cash/exchange-rates/settings/
```

Backend ViewSet action nomi: `rate_settings` (`apps/cash/views.py`); URL path: `settings` (REST: `/exchange-rates/settings/`).

GET — barcha autentifikatsiyalangan foydalanuvchilar. PATCH — **Management** (`IsManagement()`).

PATCH body (qisman):

```json
{
  "auto_fetch_enabled": true,
  "preferred_rate_source": "infinbank"
}
```

Bank kursini tanlash:

```json
{
  "preferred_rate_source": "bank",
  "preferred_bank_code": "049",
  "preferred_bank_side": "sell"
}
```

Javob: `{ "auto_fetch_enabled", "preferred_rate_source", "preferred_bank_code", "preferred_bank_side", "updated_at" }`.

Frontend: `api.exchangeRateSettings()`, `api.updateExchangeRateSettings(payload)`.

Celery: `apps.cash.tasks.refresh_infinbank_usd_rate` — har soat Infinbank (`auto_fetch_enabled=true` bo‘lsa).


## 8. Orders API (`/orders/`) — backend, Import bilan bog‘liq

> **Frontend eslatma:** «Buyurtmalar» sahifasi endi `/invoices/` API dan foydalanadi (`BuyurtmalarPage`). Quyidagi `/orders/` endpointlari backendda qoladi — Import, shartnomalar va ichki biznes mantiq uchun.

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

### Keyingi shartnoma raqami

Buyurtma formasi ochilganda frontend avtomatik raqam oladi:

```http
GET /api/v1/orders/next-contract-number/?contract_date=2026-08-11
```

`contract_date` berilmasa backend bugungi Tashkent sanasini ishlatadi.

Javob:

```json
{
  "contract_number": "12/1108",
  "contract_date": "2026-08-11"
}
```

Frontend: `api.nextContractNumber({ contract_date })`.

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

**Operator narxi (`unit_price`) e’tiborga olinmaydi (tuzatilgan bug):** Operator buyurtma yaratsa/tahrirlasa, qatorda yuborgan `unit_price` **e’tiborga olinmaydi** — narx mahsulotning belgilangan `selling_price`sidan avtomatik olinadi (Sotuv bilan bir xil qoida). `prepaid_amount` ham Operator uchun `0`ga majburlanadi. Sabab: narxni faqat Management kirita oladi (`prices_manage`); avval bu qatorlar narxsiz (`unit_price=null`) qolib, `Order.total=None` bo‘lib, buyurtma **kassaga umuman tushmasdi** — endi tuzatilgan. Frontend Operator uchun narx inputini ko‘rsatishi shart emas (baribir e’tiborga olinmaydi); Management/`prices_manage` esa har doimgidek `unit_price`ni to‘g‘ridan-to‘g‘ri kiritadi.

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

## 9. Zakazlar

Base:

```http
/api/v1/orders/zakaz/
```

### Ro‘yxat

```http
GET /api/v1/orders/zakaz/?page_size=30&status=new&zakaz_type=manual&payment_status=unpaid&product=1&order=5&contract_number=12/1108&search=monitor
```

Status oqimi (backend qat’iy ketma-ketlik):

```text
new → confirmed → ordered → received
har qanday faol holat → cancelled
```

| Holat | Keyingi ruxsat etilgan | Majburiy maydonlar |
|-------|----------------------|-------------------|
| `new` | `confirmed`, `cancelled` | `asos` |
| `confirmed` | `ordered`, `cancelled` | `asos`, `contract_number` |
| `ordered` | `received`, `cancelled` | `asos`, shartnoma (zakazda mavjud) |
| `received` / `cancelled` | o‘zgartirish yo‘q | — |

> **`ordered` (`Etkazuvchiga yuborildi`)** — tasdiqlashdan keyin, qabul qilishdan oldin. Reestrga `zakaz_ordered` yozuvi tushadi.

### Yangi zakaz

```http
POST /api/v1/orders/zakaz/
```

```json
{
  "product": 5,
  "quantity": 20,
  "unit_price": "100000.00",
  "selling_price": "150000.00",
  "vat_percent": "12",
  "supplier": "Guangzhou Medical Supply",
  "contract_date": "2026-08-11",
  "expected_date": "2026-08-25",
  "comment": "Yetkazuvchi bilan kelishildi",
  "import_batch": "550e8400-e29b-41d4-a716-446655440000"
}
```

`prices_manage` roli uchun `unit_price` (kelish) va `selling_price` (ketish) **majburiy**; ikkalasi mahsulotning `purchase_price` / `selling_price` maydonlariga yoziladi. `contract_number` yuborilmasa backend o‘sha kunning keyingi raqamini band qiladi.

**Javobda qo‘shimcha maydonlar:** `selling_price`, `delivery_price`, `vat_percent`, `vat_amount` (kelish summasidan hisoblangan QQS), `total_with_vat`, `total`. `product_name` — faqat mahsulot nomi (seriya raqamisiz).

`import_batch` ixtiyoriy — berilmasa backend yangi UUID yaratadi. Mavjud import guruhiga bitta qator qo‘shishda shu UUID yuboriladi (tahrir modalidagi yangi qatorlar).

### Bulk zakaz

```http
POST /api/v1/orders/zakaz/bulk/
```

Bir nechta mahsulot uchun zakaz yaratadi. Har bir `items` qatori mavjud `product` id yoki `new_product` (yangi mahsulot) qabul qiladi — **bitta qator** ichida ikkalasi bir vaqtda emas, lekin **turli qatorlarda aralash** bo‘lishi mumkin (ombordan + yangi mahsulot bir importda).

```json
{
  "supplier": "Xitoy",
  "contract_number": "13/1108",
  "contract_date": "2026-08-13",
  "currency": "UZS",
  "payment_status": "partial",
  "paid_amount": "500000.00",
  "import_batch": "550e8400-e29b-41d4-a716-446655440000",
  "items": [
    {
      "product": 12,
      "quantity": 5,
      "unit_price": "100000.00",
      "selling_price": "140000.00"
    },
    {
      "new_product": {
        "name": "AMD CHIP",
        "category": 3,
        "serial_number": "1234",
        "unit": "piece"
      },
      "quantity": 10,
      "unit_price": "50000.00",
      "selling_price": "70000.00",
      "vat_percent": "12"
    }
  ]
}
```

`payment_status` / `paid_amount` / `currency` bulk so‘rovda umumiy maydon — barcha qatorlarga qo‘llanadi. `partial` bo‘lganda `paid_amount` qatorlar jami summasiga **proporsional** taqsimlanadi; yaxlitlash qoldig‘i **oxirgi qator** `paid_amount` ga qo‘shiladi (yig‘indi doim kiritilgan summa bilan teng). **`paid_amount` jami summadan oshmasligi** va **narx (`unit_price`) bo‘lmasa qisman to‘lov qabul qilinmaydi** (`400`). To‘lov maydonlarini faqat **Management** yoki **Buxgalter** (`prices_manage` / `cash_manage`) yuboradi — Operator API orqali ham yubora olmaydi (backend strip qiladi).

**Bir xil mahsulotga bir nechta faol zakaz — ruxsat etilgan:** avval `product` uchun faol (`new`/`confirmed`/`ordered`) zakaz mavjud bo‘lsa bulk endpoint butunlay rad etardi («bu mahsulot uchun faol zakaz allaqachon mavjud»); bu global taqiq noto‘g‘ri edi (turli buyurtmalar/holatlar bir xil mahsulotni talab qilishi mumkin) — **olib tashlandi**. Endi bir xil `product`ga istalgancha zakaz ochish mumkin. Faqat bitta so‘rov ICHIDA takrorlangan **seriya raqami** (`new_product.serial_number`) hali ham `400` bilan rad etiladi.

**`payment_status=paid` → ombor avtomatik to‘ldiriladi:** zakaz yaratilganda YOKI keyinroq `PATCH /orders/zakaz/{id}/` orqali `payment_status` `paid`ga o‘zgartirilganda — rasmiy qabul (`status=received`) bosqichidan o‘tmagan bo‘lsa ham — `Zakaz.receive()` avtomatik chaqiriladi: mahsulot `origin` (`import` → `warehouse`) o‘zgaradi, `Stock` qatoriga `quantity` (yoki `received_qty`, agar berilgan bo‘lsa) qo‘shiladi. Idempotent (`Zakaz.stock_credited` bayrog‘i) — `status=received` orqali ham, `payment_status=paid` orqali ham faqat **bir marta** kiritiladi.

**`import_batch` (ixtiyoriy):** berilmasa har bir bulk yaratishda yangi UUID — barcha `items` qatorlariga bir xil yoziladi. Mavjud guruhga qator qo‘shishda shu UUID yuboriladi.

### Import guruhi (batch endpoint)

```http
GET /api/v1/orders/zakaz/{id}/batch/
```

Auth talab qilinadi. Javob:

```json
{
  "items": [ /* ZakazSerializer yoki ZakazOperatorSerializer ro‘yxati */ ]
}
```

Sibling qatorlarni topish tartibi:

1. `import_batch` mavjud bo‘lsa — shu UUID bo‘yicha filter
2. Aks holda `contract_number` + `contract_date` + `supplier` (legacy guruhlash)
3. Hech biri yo‘q — faqat `{id}` qatori

**Cheklovlar:** faqat `zakaz_type=manual` va buyurtmaga bog‘lanmagan (`order` yo‘q) yozuvlar guruhdan qidiriladi; `cancelled` statusdagi qatorlar chiqarilmaydi. Backorder yoki buyurtmadan kelgan zakaz uchun javobda faqat bitta element.

Frontend: `api.zakazBatch(id)` — `ZakazEditor` tahrir modali ochilganda sibling qatorlarni yuklaydi.

Mahsulot dropdown formati: `{name} · raqam: {serial_number}` — bu identifikator, import miqdori emas (`quantity` alohida maydonda). `productOptionLabel()` (`App.jsx`).

> **Bulk yaratish:** ko‘p qatorli import har doim `POST /orders/zakaz/bulk/` orqali yuboriladi (1 yoki ko‘p qator). **`payment_status` / `paid_amount` / `currency`** bulk da qo‘llab-quvvatlanadi. Legacy yozuvlar uchun jadval guruhlashi `contract_number` + `contract_date` + `supplier` bo‘yicha ham ishlaydi; yangi yaratishlar doim `import_batch` oladi.

---

### 9a. Import ro‘yxat sahifasi UI (`ResourcePage`, path `/import`)

Komponent: `ResourcePage` (`App.jsx`, `title="Import"`). Grid: `GRID_PAGES`, `page_size=25`.

#### Sahifa sarlavhasi

| Element | Matn / xulq |
|---|---|
| Eyebrow | `MODUL` |
| Sarlavha (H1) | `Import` |
| Asosiy tugma | **`+ Yangi qo‘shish`** — `procurement_manage` bo‘lsa; `ZakazEditor` modali ochiladi (`setEditing({})`) |
| Panel eyebrow | `RO‘YXAT` |
| Panel sarlavha | **`{N} ta import · {M} qator`** — guruhlangan import soni + API qatorlari (`displayRows` / `totalCount`) |
| Qidiruv | placeholder: **`Qidirish`**; submit → `search` query param |

#### Bulk amallar (`BulkActionsBar`, tanlangan qatorlar)

| Tugma | Matn | Ability | API |
|---|---|---|---|
| Eksport | **`Eksport`** + DownloadSimple ikon | — | Frontend CSV (`exportRowsCsv`) |
| Bulk status | **`Status o‘zgartirish`** | `order_status_manage` | Har tanlangan qator uchun ketma-ket `PATCH /orders/zakaz/{id}/` — `StatusChangeModal` |

#### Grid ustunlari (UI label → maydon)

| Ustun | Label | Maydon / render |
|---|---|---|
| ID | `ID` | `id` yoki guruhda `5–6` |
| Mahsulot | `Mahsulot` | `product_name` yoki guruhda **`2 ta mahsulot`** (hover: ro‘yxat) |
| Tur | `Tur` | `zakaz_type`: **`Mustaqil`** / **`Backorder`** |
| Shartnoma | `Shart.` | `contract_number` |
| Miqdor | `Zak.` | `quantity` — guruhda **yig‘indi** |
| Summa | `Summa` | `total` + `currency` — faqat `prices_view`; guruhda jami |
| To‘lov | `To‘lov` | **`To‘lanmagan`** / **`Qisman · {summa}`** / **`To‘langan`** / **`Aralash`** |
| Qabul | `Qabul` | `received_qty` — guruhda yig‘indi |
| Yetkazuvchi | `Etkaz.` | `supplier` |
| Kutilgan sana | `Kutil.` | `expected_date` |
| Holati | `Holati` | inline status; guruhda farq qilsa **`Aralash`** |
| Yaratuvchi | `Yaratdi` | `created_by_name` |

Sort (`GRID_SORT_FIELDS`): `id`, `product`→`created_at`, `created_at`, `status`, `supplier`, `expected_date`.

#### Jadval guruhlash (`groupImportRows`, `importBatchKey`)

API har bir qatorni alohida qaytaradi; frontend gridda bir xil importni bitta qator sifatida ko‘rsatadi.

| Guruh kaliti | Shart |
|---|---|
| `batch:{uuid}` | `import_batch` mavjud (asosiy, yangi yozuvlar) |
| `contract:{raqam}\|{sana}\|{supplier}` | Legacy — `import_batch` yo‘q, lekin shartnoma + sana bor |
| Guruhlanmaydi | Backorder, buyurtmadan kelgan (`order`), yoki kalit yo‘q |

Guruhlangan qator: `_grouped`, `_items`, `_groupIds`; miqdor/qabul/summa/to‘lov yig‘indisi; bir nechta mahsulot nomi — **`{N} ta mahsulot`**; to‘lov/status farq qilsa — **`Aralash`**.

#### Qator amallari (Amallar ustuni)

| Tugma | `aria-label` | Vazifa |
|---|---|---|
| Tarix | **`Tarix`** | `GET /orders/zakaz/{id}/` → **`ImportHistoryModal`** |
| Tahrirlash | **`Tahrirlash`** | `ZakazEditor` (mavjud yozuv) — `procurement_manage` |

#### `ImportHistoryModal`

| Element | Matn |
|---|---|
| Eyebrow | **`IMPORT TARIXI`** |
| Sarlavha | `{product_name}` / guruhda **`{N} ta mahsulot — import tarixi`** |
| Guruh | Har bir mahsulot uchun alohida tarix bloklari (`_batchHistory`) |
| Bo‘sh holat | **`Tarix yozuvlari yo‘q.`** |
| Har yozuv | `action_display`, `{old_status} → {new_status}`, `asos`, sana/vaqt |

#### Inline status (`InlineStatusSelect`, `StatusChangeModal`)

Faqat **`order_status_manage`**. Ruxsat etilgan o‘tishlar: `new → confirmed → ordered → received` (bekor alohida).

Status label matnlari (`StatusChangeModal.jsx`):

| Kod | UI matn |
|---|---|
| `new` | Yangi |
| `confirmed` | Tasdiqlandi |
| `ordered` | Etkazuvchiga yuborildi |
| `received` | Qabul qilindi |
| `cancelled` | Bekor qilindi |

Bulk modal eyebrow: **`STATUS O‘ZGARTIRISH`**. Majburiy maydonlar status bo‘yicha: `asos`; `confirmed`/`ordered`/`received` da shartnoma; `received` da faktura + qabul miqdori.

Filtr paneli (`ListFiltersPanel`): **status**, **sana oralig‘i** (`date_from`, `date_to`).

---

### 9b. Yangi / tahrir import modali — `ZakazEditor`

Komponent: `ZakazEditor` (`App.jsx`). Modal class: `editor import-editor`.

#### Modal sarlavhasi

| Rejim | Eyebrow | H3 |
|---|---|---|
| Yangi | **`YANGI IMPORT`** | **`Yetkazuvchidan import`** |
| Tahrir | **`IMPORT TAHRIRI`** | **`Yetkazuvchidan import`** |
| Yopish | `aria-label`: **`Yopish`** | — |
| Pastki tugmalar | **`Bekor qilish`** / **`Saqlash`** | `Saqlash` — `saving \|\| batchLoading` bo‘lsa **disabled** |

#### Qaysi UI ko‘rinadi? (rejimlar)

| Shart | Ko‘rinish |
|---|---|
| Yangi + `zakaz_type !== backorder` + `order_contract` yo‘q | **Ko‘p qatorli** MAHSULOTLAR bloki (§9b.1) |
| Mavjud mustaqil import + `zakaz_type !== backorder` + `order_contract` yo‘q | **Ko‘p qatorli** — `GET /orders/zakaz/{id}/batch/` yuklanadi; yuklanayotganda **`Mahsulot qatorlari yuklanmoqda…`** |
| Mavjud backorder yoki buyurtmadan kelgan (`order_contract`) | **Bitta mahsulot** qatori (select + miqdor; Management da qabul miqdori) |
| Backorder | Mahsulot select **disabled** (`productLocked`); miqdor faqat Management tahririda |

Ability kalitlari:

| Ability | Ta’sir |
|---|---|
| `prices_manage` | Narx, valyuta, yangi mahsulot narxi (Management) |
| `cash_manage` | To‘lov statusi va qisman summa (Buxgalter) — `showPayment` |
| `prices_view` | Gridda summa ustuni |
| `order_status_manage` | Status select, `received_qty` |
| Operator (`procurement_manage` only) | Import yaratadi/tahrirlaydi; to‘lov maydonlari **ko‘rinmaydi** (hint matn) |

#### 9b.1. MAHSULOTLAR bloki (yangi va mavjud mustaqil import)

| Element | Aniq UI matni |
|---|---|
| Bo‘lim eyebrow | **`MAHSULOT QATORLARI`** |
| Yordamchi matn | **`Tovar nomi ombordagi mahsulot bilan mos kelsa qator avtomatik bog‘lanadi; mos kelmasa yangi mahsulot ombor ro‘yxatiga qo‘shiladi. QQS kelish narxi asosida hisoblanadi.`** |
| Yuklanish holati | **`Mahsulot qatorlari yuklanmoqda…`** — tahrirda `api.zakazBatch(id)` chaqirilganda; shu vaqt **`Saqlash` bloklangan** |
| Qator qo‘shish | Jadval oxiridagi **`+`** tugmasi |
| Qator o‘chirish | **`Qatorni o‘chirish`** (savat ikon) — faqat 2+ qator bo‘lsa; **mavjud API qatorlari** (`zakazId` bor) o‘chirilmaydi |
| Jadval ustidagi boshqaruv | **`Teskari hisob`** katagi + **`MXIK kodlari`** havolasi |
| Ombordan tanlash | Tovar nomi yonidagi **quti** ikonkasi → `ProductPickerModal`; nom/seriya datalist orqali ham |

**Jadval ustunlari:**

| Label | Maydon | Eslatma |
|---|---|---|
| Tovar nomi | `input` + datalist + `ProductPickerModal` (quti ikonkasi) | majburiy; ombordagi nom bilan mos kelsa qator avtomatik bog‘lanadi |
| Kategoriya | `<select>` | yangi mahsulot qatorida **majburiy**; ombordan tanlansa avtomatik |
| Seriya raqami | `input` + datalist | ixtiyoriy — **avtomatik yaratilmaydi** |
| Shtrix kod | `input` | ixtiyoriy |
| O‘lchov birligi | `<select>` | `productUnits` (dona, kg, …) |
| Soni | `number` | min 1 |
| Kelish narxi | `number` | `prices_manage`; majburiy; ombordan tanlansa `purchase_price` |
| Ketish narxi | `number` | `prices_manage`; majburiy; ombordan tanlansa `selling_price` |
| Yetkazish qiymati | read-only (teskari hisobda tahrirlanadi) | `soni × kelish narxi` |
| QQS % | `<select>` | QQS siz / 0% / 6% / 12% / 15% |
| QQS miqdori | read-only (teskari hisobda tahrirlanadi) | kelish qiymatidan |
| Jami | read-only (teskari hisobda tahrirlanadi) | yetkazish + QQS |

Jadval ustida **«Teskari hisob»** katagi va **MXIK kodlari** havolasi; pastda ustunlar bo‘yicha jami satri. Qator qo‘shish/o‘chirish — oxirgi ustundagi `+` / savat tugmalari.

Frontend validatsiya (toast xato):

- `{N}-qator: miqdor kamida 1 bo‘lishi kerak.`
- `{N}-qator: tovar nomi kiritilishi shart.`
- `{N}-qator: yangi mahsulot uchun kategoriya tanlanishi shart.`
- `{N}-qator: kelish narxi kiritilishi shart.`
- `{N}-qator: ketish narxi kiritilishi shart.`
- `Qisman to‘langan summa jami import summasidan ({jami}) oshmasligi kerak.`
- `{N}-qator: narx kiritilishi shart.` (`prices_manage`)
- **`Qisman to'lov uchun summa kiriting.`**
- **`Qisman to'lov uchun avval barcha qatorlarga narx kiritilishi kerak.`** — guruh tahririda `partial` + barcha qator jami (`grandTotal`) 0 bo‘lsa

#### 9b.2. Umumiy maydonlar (barcha rejimlar)

| Label | Maydon | Eslatma |
|---|---|---|
| Valyuta | `<select>` | **`UZS`** / **`USD`** — `showPayment` (`prices_manage` \|\| `cash_manage`) |
| To‘lov statusi | `<select>` | **`To‘lanmagan`** / **`Qisman`** / **`To‘langan`** — `showPayment` |
| Operator hint | **`To‘lov holati (qisman / to‘langan) faqat boshqaruv yoki buxgalter tomonidan belgilanadi.`** | `!showPayment` |
| Qisman to‘langan summa | `number` | faqat `partial`; placeholder: **`Masalan, 500000`** |
| Hint (partial) | **`Kiritilgan summa saqlangach kassadan chiqim (xarajat) sifatida yoziladi.`** | |
| Hint (unpaid) | **`To‘lanmagan import summasi kassadan chiqim sifatida yoziladi.`** | |
| Status | `<select>` | faqat `order_status_manage`: Yangi, Tasdiqlandi, Etkazuvchiga yuborildi, Qabul qilindi, Bekor qilindi — **guruh tahririda barcha sibling qatorlarga** qo‘llanadi |
| Qabul qilingan (asosiy qator) | `number` | faqat ko‘p qatorli tahrir + Management — **`received_qty` faqat ochilgan qator** (`item.id`) uchun PATCH |
| Yetkazuvchi | `input` | |
| Shartnoma raqami | `input` | placeholder: **`12/1108`**; faqat raqam va `/` |
| Shartnoma sanasi | `date` | default bugun |
| Faktura | `input` | |
| Kutilgan sana | `date` | |
| Ombor joyi | `input` | |
| Asos | `textarea` | tahrirda status o‘zgarsa majburiy |
| Izoh | `textarea` | |

USD tanlanganda: **`FxRatePanel`** (`compact`) — Import editor ichida kurs.

#### 9b.3. Saqlash → API mapping

| Holat | Chaqiruv |
|---|---|
| Yangi import (1+ qator, aralash manba) | `POST /orders/zakaz/bulk/` — `items[]` + umumiy maydonlar + ixtiyoriy `payment_status` / `paid_amount` / `currency` |
| Mavjud import (guruh) — yuklash | `GET /orders/zakaz/{id}/batch/` → `importRows[]` + `importBatchId` state |
| Mavjud import (guruh) — saqlash | Har bir **mavjud** qator: `PATCH /orders/zakaz/{zakazId}/`; har bir **yangi** qator: `POST /orders/zakaz/` **`import_batch`** bilan (guruhdan ajralmasligi uchun) |
| Mavjud import (yagona, backorder, order) | `PATCH /orders/zakaz/{id}/` |

**Guruh tahririda qisman to‘lov (`partial`):** frontend `splitPartialPayment(totalPaid, lineTotals)` — proporsional taqsimlash, yaxlitlash qoldig‘i oxirgi qatorga. Har bir PATCH alohida o‘z `paid_amount` ni oladi; umumiy `common` payload dan `paid_amount` / `payment_status` / `currency` olib tashlanadi (dublikatsiya oldini olish).

**Guruh tahririda status:** `status` va `asos` o‘zgarsa — **barcha** sibling qatorlar PATCH payloadiga qo‘shiladi (faqat ochilgan qator emas).

**Yangi qator mavjud guruhda:** `POST /orders/zakaz/` body da `import_batch: importBatchId` (batch yuklangandan keyin saqlangan UUID).

Muvaffaqiyat toast: **`Import yaratildi.`** / **`Import yangilandi.`**

Operator (`prices_manage` yo‘q): payload dan `unit_price`, `currency`, `payment_status`, `paid_amount` olib tashlanadi; `new_product` ichidan `purchase_price`, `delivery_price` olib tashlanadi. Backend ham Operator `PATCH` da to‘lov maydonlarini qabul qilmaydi.

#### 9b.4. Frontend state va helperlar

| Nom | Vazifa |
|---|---|
| `batchLoading` | Tahrirda sibling qatorlar yuklanayotganda `true`; `Saqlash` disabled |
| `importBatchId` | `GET .../batch/` javobidan `import_batch` UUID |
| `importRows[]` | Har qator: `key`, `zakazId?`, `source`, `product`, `quantity`, `unit_price`, `manual` |
| `splitPartialPayment()` | Qisman to‘lovni qatorlar bo‘yicha taqsimlash (oxirgi qatorga qoldiq) |
| `zakazToImportRow()` | API zakaz → modal qator formati |
| `buildImportItem()` / `buildCommonPayload()` | Saqlash payload yig‘ish |
| `applyPaymentPayload()` | `!showPayment` bo‘lsa to‘lov maydonlarini strip |

---

**Frontend (`ZakazEditor`) — qisqa xulosa:**

- Manba dropdowni yo‘q: tovar nomi ombordagi mahsulot bilan mos kelsa qator o‘sha mahsulotga bog‘lanadi, mos kelmasa yangi mahsulot ochiladi — bir importda aralash bo‘lishi mumkin.
- Qator qo‘shish/o‘chirish — jadval oxiridagi `+` / savat tugmalari.
- Yaratish → har doim `POST /orders/zakaz/bulk/` (`items[]` + to‘lov maydonlari).
- Tahrir (qalamcha) → `GET /orders/zakaz/{id}/batch/` orqali guruhdagi **barcha** mahsulot qatorlari; yuklanmaguncha saqlash bloklangan.
- Tahrir saqlash → mavjud qatorlar `PATCH`, yangi qatorlar `POST` + `import_batch`.
- Qisman to‘lov → qatorlar bo‘yicha taqsimlangan `paid_amount`; jami 0 bo‘lsa xato.
- Status o‘zgarishi → barcha sibling qatorlarga; `received_qty` faqat ochilgan qator uchun.
- Ombordan tanlanganda **Narx** avtomatik `purchase_price` (`prices_manage`).
- `serial_number` bo‘sh bo‘lsa `null` saqlanadi — avtomatik raqam **yaratilmaydi**.
- Yangi import shartnoma raqamini `GET /orders/next-contract-number/` dan oldindan ko‘rsatadi; qo‘lda o‘zgartirilmasa saqlashda yubormaydi va backend raqamni band qiladi.

### Status PATCH

```http
PATCH /api/v1/orders/zakaz/{id}/
```

Backend: status o‘zgartirish (`confirmed`, `ordered`, `received`, `cancelled`) — **Management** roli talab qilinadi. Ketma-ketlik buzilsa **400** (`confirmed` → `received` to‘g‘ridan-to‘g‘ri ishlamaydi).

Frontend: Import gridda inline status va bulk status faqat `order_status_manage` ability bo‘lsa ko‘rinadi (`procurement_manage` yetarli emas). Inline o‘tishlar: `new→confirmed→ordered→received`.

Tasdiqlash:

```json
{
  "status": "confirmed",
  "contract_number": "13/1108",
  "asos": "Rahbariyat tasdiqladi"
}
```

Buyurtma berildi (`ordered` — shartnoma tasdiqlashda kiritilgan bo‘lishi kerak):

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

## 10. Shartnomalar reestri

Read-only audit jurnali — buyurtma, zakaz va kirim amallaridan avtomatik yozuvlar.

```http
GET /api/v1/orders/contracts/?page_size=30&product=1&contract_number=12/1108&source_type=order_created&order=5&zakaz=3
GET /api/v1/orders/contracts/{id}/
```

Frontend:

- Ro‘yxat: `api.contracts(params)` — sahifa **Shartnomalar**
- Detail modal: `api.retrieve('/orders/contracts/', id)`

Mahsulot detailidan reestr:

```http
GET /api/v1/warehouse/products/{id}/contracts/
```

Frontend: `api.productContracts(productId)`.

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
invoice_created
invoice_edited
```

**Buyurtma (SK) dan reestr:** `POST` / `PATCH /api/v1/invoices/` (`document_type=contract_sk`, qatorlarda `product` FK mos) — backend `sync_invoice_contract_registry()` orqali `invoice_created` / `invoice_edited` yozuvlarini qo‘shadi (`apps/invoices/services.py`). Filtrlash: `GET /orders/contracts/?source_type=invoice_created`.

## 11. Ombor

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
GET /api/v1/warehouse/products/?page_size=30&search=monitor&category=1&purchase_price__isnull=true&selling_price__isnull=false
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
pending_import_quantity
stock_status
category_name
origin
origin_display
unit_display
```

Operator uchun `purchase_price`, `selling_price` qaytmasligi mumkin.

`category` — **majburiy**; `serial_number` — ixtiyoriy (bo‘sh bo‘lsa `null`, avtomatik yaratilmaydi).

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

**Kassaga chiqim (`record_stock_in_expense`, yangi):** mahsulotning **kelish narxi** (`purchase_price`) belgilangan bo‘lsa, kirim summasi (`narx × miqdor`) kassadan **chiqim** (`Expense`, toifa — Import) sifatida avtomatik yoziladi (har kirim — alohida yozuv). `purchase_price` bo‘lmasa (masalan operator narxsiz mahsulotga kirim qilsa) — hisoblab bo‘lmagani uchun chiqim yozilmaydi, jurnalda ko‘rinmaydi. Xuddi shu qoida `POST /warehouse/products/` da boshlang‘ich `quantity` bilan mahsulot yaratilganda ham ishlaydi.

### Qoldiqlar

```http
GET /api/v1/warehouse/stocks/?page_size=30&product=1&category=2&warehouse_location=A-1&status=low_stock&date_from=2026-08-01&date_to=2026-08-31&search=monitor
POST /api/v1/warehouse/stocks/
GET /api/v1/warehouse/stocks/{id}/
PATCH /api/v1/warehouse/stocks/{id}/
DELETE /api/v1/warehouse/stocks/{id}/
```

`status`: `in_stock` | `low_stock` | `out_of_stock`. `reserved_quantity` read-only. Broni bor qatorni o‘chirib bo‘lmaydi.

## 12. Mijozlar

```http
GET /api/v1/clients/?page_size=30&search=smart
GET /api/v1/clients/?page_size=30&search=310776556
GET /api/v1/clients/?page_size=30&search=31208123456789
GET /api/v1/clients/?page_size=30&search=AA1234567
POST /api/v1/clients/
GET /api/v1/clients/{uuid}/
PATCH /api/v1/clients/{uuid}/
DELETE /api/v1/clients/{uuid}/
```

### Qidiruv (`search`)

Backend: `apps/clients/filters.py` — `ClientSearchFilter`. Shifrlangan maydonlar (Fernet) serverda ochilib qidiriladi; `company_name` va `email` to‘g‘ridan-to‘g‘ri DB filter.

| Qidiruv turi | Maydonlar |
|---|---|
| F.I.Sh | `full_name`, `first_name`, `last_name`, `middle_name`, `director_fish` (yuridik rahbar) |
| INN / STIR | `inn` |
| JSHSHIR | `pinfl` (jismoniy), `director_jshshr` (yuridik rahbar) |
| Passport | `passport_number` |
| Boshqa | `company_name`, `email` |

Qismiy moslik (`icontains`) va raqamlar uchun bo‘shliqsiz solishtirish qo‘llab-quvvatlanadi (masalan `31208123456789`).

### Ro‘yxat javobi (`ClientListSerializer`)

`GET /clients/` maydonlari: `id`, `full_name`, `company_name`, `client_type`, `phone`, `inn`, `pinfl`, `passport_number`, `director_jshshr`, `director_fish`, `is_active`, `created_at`. Jismoniy shaxsda `full_name` familiya + ism + otasidan yig‘iladi.

`can_view_clients` ruxsati kerak.

Frontend: ro‘yxat grid (`/mijozlar`), qator bosilganda `/mijozlar/{uuid}` — tablar §3a jadvalida.

So‘rov:

```json
{
  "client_type": "legal",
  "company_name": "Samarqand Med Texnika MChJ",
  "inn": "310776556",
  "director_jshshr": "31208123456789",
  "director_fish": "Karimov Akmal Alisher o‘g‘li",
  "mfo": "00440",
  "oked": "46900",
  "bank_name": "Kapitalbank",
  "bank_account": "20208000123456789012",
  "phone": "+998901112233",
  "email": "info@example.uz",
  "address": "Samarqand shahri, Universitet xiyoboni 12",
  "comment": "Doimiy mijoz",
  "is_active": true
}
```

Jismoniy shaxs (`client_type: "individual"`):

```json
{
  "client_type": "individual",
  "full_name": "Aliyev Sardor Bahodir o‘g‘li",
  "pinfl": "31208123456789",
  "passport_number": "AA1234567",
  "phone": "+998901112233",
  "email": "sardor@example.uz",
  "address": "Toshkent",
  "is_active": true
}
```

`full_name`, `pinfl`, `inn`, `passport_number`, `phone`, `director_jshshr`, `director_fish`, `bank_account` bazada **Fernet** bilan shifrlanadi (`FERNET_KEY` env). Serializer saqlashda bir marta shifrlaydi, `GET`/`PATCH` javobida `to_representation` orqali **ochiq matn** qaytaradi — frontend hech qachon `gAAAAA...` ko‘rmaydi.

| Qatlam | Ko‘rinish |
|---|---|
| PostgreSQL (bazada) | Shifrlangan (`gAAAAA...`) |
| `GET/PATCH /clients/{uuid}/` JSON | Ochiq matn (`KImdir`, `+998...`) |
| Frontend (`Editor`, `ClientPickerModal`, `PartyInfoGrid`) | API javobidagi ochiq matn |

Shifrlanmaydigan maydonlar: `company_name`, `email`, `address`, `comment`, `mfo`, `oked`, `bank_name`, `client_type`, `is_active`.

`FERNET_KEY` bo‘lmasa va `DEBUG=True` bo‘lsa, ma’lumotlar vaqtincha ochiq saqlanadi (faqat dev). Production (`DEBUG=False`) da kalit **majburiy**.

Hozir Soliq/DIDox kabi external auto-fill endpoint yo‘q. Rejalangan to‘g‘ri arxitektura:

```http
GET /api/v1/clients/lookup/?identifier=310776556
```

Avval local DB, keyin tashqi Soliq provider. Bu hali qo‘shilmagan.

## 13. Sotuvlar

```http
GET /api/v1/sales/?page_size=30&product=1&client=<uuid>&sold_date=2026-08-11
POST /api/v1/sales/
GET /api/v1/sales/{id}/
PATCH /api/v1/sales/{id}/
DELETE /api/v1/sales/{id}/
POST /api/v1/sales/bulk/
```

Sotuv yaratilganda to‘liq summa avtomatik **kassaga tushum** sifatida yoziladi (`Payment` + tranzaksiya, 15% komissiya bilan). Backend: `apps/sales/sale_payment.sync_sale_payment` — `POST` va `PATCH` dan keyin chaqiriladi (`apps/sales/serializers.py`).

**Tahrirda ham kassa qayta sinxronlanadi (tuzatilgan bug):** narx (`sold_price`) yoki miqdor o‘zgarsa, `Payment.total_amount`/`paid_amount` **qayta hisoblanadi** — oshgan farq qo‘shimcha tranzaksiya, kamaygan farq manfiy korrektsiya tranzaksiyasi bo‘lib yoziladi (avval `PATCH` kassani umuman yangilamas edi, eski summada qolib ketardi). Operator `sold_price`ni tahrirlay olmaydi (backend chetlab o‘tadi) — faqat miqdor orqali summa o‘zgarishi mumkin.

**O‘chirishda kassa yozuvi ham tozalanadi:** `DELETE /sales/{id}/` bog‘liq `Payment`ni ham o‘chiradi (aks holda `Payment.sale` FK `PROTECT` bo‘lgani uchun o‘chirish `500` bilan yiqilardi).

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

## 14. Kassa

### Payments

```http
GET /api/v1/cash/payments/?page_size=30&status=partial&order=5&sale=7&client=<uuid>&currency=UZS
POST /api/v1/cash/payments/
GET /api/v1/cash/payments/{id}/
PATCH /api/v1/cash/payments/{id}/
DELETE /api/v1/cash/payments/{id}/
```

**Ro‘yxatda to‘langanlar yashirin.** Standart `GET /cash/payments/` faqat faol to‘lovlarni qaytaradi: `pending`, `partial`, `overdue`. `paid` statusdagi yozuvlar ko‘rinmaydi.

To‘liq to‘langanlarni ko‘rish:

```http
GET /api/v1/cash/payments/?status=paid
GET /api/v1/cash/payments/?include_paid=true
```

| Query | Ma’nosi |
|---|---|
| `status` | `pending`, `partial`, `paid`, `overdue` |
| `include_paid=true` | Barcha statuslar, shu jumladan `paid` |
| `client` | Mijoz UUID |
| `currency` | `UZS` yoki `USD` |
| `order`, `sale` | Bog‘langan buyurtma/sotuv ID |

Frontend Kassa sahifasi: `KassaPage` — `api.kassaLedger()` + `api.paymentsSummary()`. Jadval **tushum** (sotuv/buyurtma tranzaksiyalari) va **chiqim** (import xarajatlari) harakatlarini birlashtirilgan jurnalda ko‘rsatadi.

**Kassa jurnali (`GET /cash/payments/ledger/`):**

| Query | Qiymat |
|---|---|
| `page`, `page_size` | Pagination (default `page_size=25`, max 100) |
| `search` | Izoh, mijoz, shartnoma, mahsulot nomi |
| `source` | `sale` \| `order` \| `import` \| `expense` (yangi) |
| `kind` | `in` \| `out` |

`source=import` — zakaz yoki faktura (SK)ga bog‘langan chiqim (`zakaz_id` bor). `source=expense` (yangi) — boshqa barcha rasxod turlari: ofis, transport, komandirovka, oylik, deklaratsiya, sertifikat, boshqa, **va endi ombor kirimi** (`add-stock`/mahsulot yaratish) ham shu yerda ko‘rinadi. `expense_type` maydoni rasxod toifasi kodini ko‘rsatadi (`office`, `import`, `transport`, …).

Javob (pagination):

```json
{
  "count": 42,
  "results": [
    {
      "id": "in-15",
      "kind": "in",
      "source": "sale",
      "amount": "5200000",
      "currency": "UZS",
      "label": "Sotuv #7",
      "client_name": "Samarqand Med Texnika MChJ",
      "date": "2026-08-11",
      "created_at": "2026-08-11T14:30:00+05:00",
      "payment_id": 12,
      "remaining": "0",
      "status": "paid"
    },
    {
      "id": "out-3",
      "kind": "out",
      "source": "import",
      "expense_type": "import",
      "amount": "15000000",
      "currency": "UZS",
      "label": "Import #5 — Monitor (Guangzhou)",
      "client_name": "Guangzhou Medical Supply",
      "date": "2026-08-10",
      "created_at": "2026-08-10T09:00:00+05:00",
      "zakaz_id": 5
    },
    {
      "id": "out-9",
      "kind": "out",
      "source": "expense",
      "expense_type": "office",
      "amount": "1200000",
      "currency": "UZS",
      "label": "Ofis ijarasi",
      "client_name": null,
      "date": "2026-08-12",
      "created_at": "2026-08-12T10:00:00+05:00",
      "zakaz_id": null
    }
  ]
}
```

**`paymentsSummary` qo‘shimcha maydonlar** (`ledger_totals()`, yangilangan):

```json
{
  "sum_in_uzs": "50000000",
  "sum_in_usd": "0",
  "sum_import_uzs": "20000000",
  "sum_import_usd": "0",
  "sum_out_uzs": "23200000",
  "sum_out_usd": "0",
  "net_balance_uzs": "26800000",
  "net_balance_usd": "0"
}
```

| Maydon | Ma’nosi |
|---|---|
| `sum_import_uzs`/`usd` | **Faqat** import (zakaz/faktura)ga bog‘liq chiqim — eski maydon, moslik uchun saqlangan |
| `sum_out_uzs`/`usd` | **Barcha** chiqim — import + ofis/transport/oylik/... (yangi) |
| `net_balance_uzs`/`usd` | **Kassa balansi** = tushumlar − `sum_out_uzs`/`usd` (**barcha** chiqimlar hisobga olinadi — avval faqat import chiqimi ayrilardi, boshqa rasxodlar balansga kirmasdi) |

**Bug tuzatildi:** avval `net_balance` faqat import chiqimini hisobga olardi — ofis/transport/oylik kabi rasxodlar kiritilgan bo‘lsa ham kassa balansi ularni ko‘rsatmasdi. Frontend `KassaPage` balans metrikasi endi to‘g‘ri qiymat qaytaradi — qo‘shimcha o‘zgartirish talab qilinmaydi (backend hisoblab beradi), lekin agar UI qayerdadir `sum_import_uzs`ni "jami chiqim" sifatida ko‘rsatayotgan bo‘lsa, endi `sum_out_uzs`ga o‘tkazish tavsiya etiladi.

**`KassaPage` UI (`prices_view` bo‘lsa):**

- Metrikalar: Tushum, Import chiqim, Kassa balansi, Komissiya
- Filtrlar: qidiruv, manba (`sale` / `order` / `import` / `expense` — qo‘shildi, `ledgerSourceLabel()` `expense` → «Rasxod» deb ko‘rsatadi)
- Qolgan to‘lov bo‘lsa tushum qatorida **to‘lov qabul qilish** (`api.pay`) — faqat `cash_manage`
- **Yangi to‘lov** modali — qo‘lda `POST /cash/payments/` (sotuvga bog‘lash)
- **Valyuta konvertori** (yangi, `CurrencyConverter` — `KassaPage.jsx` ichida): metrikalar tagida, hammaga ko‘rinadi (rol cheklovi yo‘q). `GET /cash/exchange-rates/latest/` orqali kurslarni (Infinbank MB + bank ro‘yxati) yuklaydi, foydalanuvchi UZS summasini kiritadi + banklardan birini tanlaydi (faqat lokal tanlov — `FxRatePanel`dan farqli, hech qanday sozlamani o‘zgartirmaydi/saqlamaydi), natija darhol `$` da ko‘rsatiladi (`summa / tanlangan_kurs`). Yangi backend endpoint talab qilinmadi — mavjud kurs ma'lumotidan foydalanildi.

**Yangi to‘lov modali** (`cash_manage`):

```json
{
  "sale": 7,
  "client": "<uuid>",
  "paid_amount": "0",
  "currency": "UZS",
  "due_date": "2026-08-20"
}
```

Jami va 15% komissiya backend sotuv asosida avtomatik hisoblanadi.

Payment sotuv yoki orderga bog‘lanadi, ikkalasiga bir vaqtda emas.

Javobda:

```text
source
sale_info
order_info
zakaz
client_name
remaining
transactions
```

`source`: `sale` \| `order` (faqat **tushumlar**). Import chiqimlari `Payment` emas — `Expense(zakaz)` orqali jurnalda `source=import`, `kind=out`.

Sotuv yaratilganda to‘liq summa avtomatik kassaga yoziladi (`sync_sale_payment`, §17c). Import yaratilganda/yangilanganda chiqim yoziladi (`sync_zakaz_expense`).

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

## 15. Xarajatlar

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

## 16. Bildirishnomalar

```http
GET /api/v1/notifications/?page_size=30&is_read=false
GET /api/v1/notifications/{id}/
POST /api/v1/notifications/{id}/mark_read/
POST /api/v1/notifications/mark_all_read/
```

Frontend browser push permission so‘raydi. Polling 30s. Bir xil toast takror chiqmasligi kerak.

## 17. Hisobotlar

Ruxsat: `IsAccountantOrManagement` (Accountant / Management). Operator uchun `403`.

### Dashboard filtrlari (bosh sahifa)

Bosh sahifa `api.reports(params)` va `api.monthlyTrend(6, params)` chaqiradi. Umumiy query parametrlar:

| Param | Tur | Ma’nosi |
|---|---|---|
| `date_from` | `YYYY-MM-DD` | Davr boshlanishi |
| `date_to` | `YYYY-MM-DD` | Davr tugashi |
| `currency` | `UZS` \| `USD` | Valyuta filtri (bo‘sh = hammasi) |
| `category` | int | Kategoriya ID |
| `client` | UUID (frontend) | Mijoz ID — `/clients/` dan; backend summary/trend da `client` query qabul qiladi |
| `supplier` | string | Yetkazuvchi (qisman mos, import/zakaz) |
| `product` | int | Mahsulot ID |
| `payment_status` | string | `pending`, `partial`, `paid`, `overdue` |

Default bosh sahifa filtri: bugungi sana (`date_from` = `date_to` = bugun).

**Dashboard metrik kartalari** (`Dashboard` — `App.jsx`):

| Kartochka | API maydon | Hisoblash | Eslatma |
|---|---|---|---|
| Tushum | `kassa_collected_uzs` / `_usd` | Kassa jurnali `kind=in` (`build_ledger_entries`) — faqat sotuv/buyurtma tranzaksiyalari | Import **kirmaydi** |
| Import chiqim | `import_paid_uzs` / `_usd` | Kassa jurnali `kind=out` (Expense + zakaz) | Kassadan chiqim |
| Kassa balansi | `net_balance_uzs` / `_usd` | `kassa_collected` − `import_paid` (davr bo‘yicha) | Kassa sahifasi bilan bir xil formula |
| Savdo | `sales_revenue_uzs` | `Sale.sold_price × quantity` (`sold_date` bo‘yicha) | Import emas |
| Ombordagi birliklar | `warehouse.total_quantity` | `/reports/warehouse/` | Snapshot |
| Kechikkan to‘lovlar | `overdue_payments_count` | Payment overdue count | |

**Muhim:** Tushum va Import chiqim **alohida** ko‘rsatiladi; bir xil summa bo‘lishi mumkin (bugun 50M sotuv + 50M import), lekin bu turli operatsiyalar. **Balans** kartochkasi (`Tushum − Import`) haqiqiy kassa o‘zgarishini ko‘rsatadi.

**⚠️ Diqqat — ikki xil `net_balance_uzs` doirasi (nomuvofiqlik):** Ushbu bo‘limdagi `import_paid_uzs`/`net_balance_uzs` (`/reports/summary/`, `_import_paid_totals()`) **faqat zakazga bog‘langan** (`Expense.zakaz`) chiqimni hisoblaydi — ombor kirimi (`add-stock`) va faktura (SK) orqali yozilgan yangi chiqimlar (§17c) bu yerga **kirmaydi**. `/cash/payments/summary/` dagi `net_balance_uzs` esa (§14) endi **barcha** `Expense`ni hisobga oladi. Ya’ni shu ikki endpoint bir xil davr uchun **turli** balans qaytarishi mumkin — bosh sahifa balansi torroq (faqat import), Kassa sahifasi balansi to‘liq. Frontend buni hisobga olsin (masalan tooltip/izoh); ikkalasini birlashtirish alohida backend o‘zgarishi talab qiladi (hozircha qilinmagan).

**Frontend UI:** `Dashboard` — `Filtrlar` + `Yangi buyurtma` (`einvoice_manage`). Mobilda (`≤768px`) tugma qator ichida ixcham (`dashboard-toolbar`): filtr chapda kengayadi, tugma o‘ngda `width: auto`; juda tor ekranda (`≤420px`) faqat `+` ikonka (`aria-label="Yangi buyurtma"`).

Misol:

```http
GET /api/v1/reports/summary/?date_from=2026-08-01&date_to=2026-08-31&currency=UZS&category=2&payment_status=partial
```

### Moliyaviy xulosa

```http
GET /api/v1/reports/summary/
```

Dashboard filtrlari qabul qilinadi (yuqoridagi jadval).

Javob (asosiy maydonlar):

```json
{
  "date_from": "2026-08-01",
  "date_to": "2026-08-31",
  "currency": "UZS",
  "category": 2,
  "client": null,
  "supplier": null,
  "product": null,
  "payment_status": null,
  "filtered": true,
  "sales_revenue_total": "45000000",
  "sales_revenue_uzs": "45000000",
  "kassa_collected_uzs": "12000000",
  "kassa_collected_usd": "0",
  "kassa_collected_today_uzs": "500000",
  "kassa_collected_today_usd": "0",
  "import_paid_uzs": "8000000",
  "import_paid_usd": "0",
  "import_paid_today_uzs": "0",
  "import_paid_today_usd": "0",
  "import_out_uzs": "8000000",
  "net_balance_uzs": "4000000",
  "net_balance_usd": "0",
  "mb_rate_today": "11934.61",
  "expenses_uzs": "1200000",
  "expenses_usd": "0",
  "commission_earned": "150000",
  "overdue_payments_count": 3,
  "report_date": "2026-08-11"
}
```

Eslatma:

- `kassa_collected_*` — kassa jurnalidagi **tushumlar** (`PaymentTransaction`, `payment.zakaz` bo‘sh). Import Payment emas.
- `import_paid_*` / `import_out_uzs` — kassa jurnalidagi **import chiqimlari** (`Expense` + `zakaz` FK).
- `net_balance_*` — `kassa_collected − import_paid` (davr bo‘yicha). Backend: `_ledger_in_uzs()` / `_ledger_out_uzs()` (`apps/cash/ledger.py`).
- `sales_revenue_*` — sotuv summasi (`sold_date`); import bilan aralashmaydi.

`client` yoki `payment_status` filtri bo‘lsa ledger override o‘rniga eski `_kassa_collected` / `_import_paid_totals` ishlatiladi.

### Oylik trend

```http
GET /api/v1/reports/monthly-trend/?months=6
```

| Param | Default | Cheklov |
|---|---|---|
| `months` | `6` | 1–24 |

Qabul qilinadigan filtrlari: `currency`, `category`, `client`, `supplier`, `product`, `payment_status`. `date_from`/`date_to` ishlatilmaydi — oxirgi N oy avtomatik hisoblanadi.

Javob — array (eng yangi oy birinchi):

```json
[
  {
    "year": 2026,
    "month": 8,
    "label": "Avgust 2026",
    "date_from": "2026-08-01",
    "date_to": "2026-08-11",
    "kassa_uzs": "12000000",
    "import_uzs": "8000000",
    "import_usd": "0",
    "sales_uzs": "45000000"
  }
]
```

Frontend: `api.monthlyTrend(6, params)`. Jadval ustunlari: **Oy**, **Tushum**, **Import chiqim**, **Balans** (`kassa_uzs − import_uzs`), **Savdo**.

Oylik trend ham kassa jurnalidan hisoblanadi (`_ledger_in_uzs` / `_ledger_out_uzs`) — `client`/`payment_status` filtri bo‘lmasa.

### Ombor hisoboti

```http
GET /api/v1/reports/warehouse/
GET /api/v1/reports/warehouse/?date_from=2026-08-01&date_to=2026-08-31
```

`api.reports()` hozir **warehouse** ga parametr yubormaydi — doim hozirgi ombor holati.

Javob:

```json
{
  "total_product_types": 42,
  "total_quantity": 380,
  "by_category": [{ "product__category__name": "Med texnika", "total_qty": 120 }],
  "low_stock": [{ "product__id": 1, "product__name": "...", "quantity": 2, "product__min_quantity": 5 }],
  "out_of_stock": [{ "product__id": 9, "product__name": "..." }]
}
```

### Kassa hisoboti (reports)

```http
GET /api/v1/reports/cash/?date_from=2026-08-01&date_to=2026-08-31&client=<uuid>&payment_status=overdue
```

`/cash/payments/summary/` dan farqi: bu endpoint davr va filtr bo‘yicha hisobot; `commission_total` nomi bilan komissiya qaytaradi.

Javob:

```json
{
  "total_pending": 3,
  "total_partial": 2,
  "total_paid": 10,
  "total_overdue": 1,
  "sum_paid_uzs": "15000000",
  "sum_paid_usd": "0",
  "commission_total": "150000"
}
```

Davr berilganda `sum_paid_uzs` tranzaksiya sanasi bo‘yicha; davrsiz — `paid_amount` yig‘indisi.

### Eng ko‘p sotilgan mahsulotlar

```http
GET /api/v1/reports/top-products/?limit=10&date_from=2026-08-01&date_to=2026-08-31&category=2&client=<uuid>&product=5
```

Javob — array:

```json
[
  {
    "product": 1,
    "name": "Samsung monitor",
    "serial_number": "SM-G55C",
    "sold_qty": 24,
    "current_stock": 8,
    "min_quantity": 3,
    "is_low": false
  }
]
```

### Xarajat hisoboti

```http
GET /api/v1/reports/expenses/?date_from=2026-08-01&date_to=2026-08-31
```

`api.expensesSummary()` alohida: `GET /expenses/summary/` (xarajatlar moduli).

### Hisobotlar sahifasi vs bosh sahifa

| Sahifa | Chaqiriqlar |
|---|---|
| Bosh sahifa | `api.reports(params)` + `api.monthlyTrend(6, params)` — filtrli |
| Hisobotlar (tablar) | Moliyaviy/Ombor/Sotuvlar/Xarajatlar: `api.reports()` filtrsiz + `api.expensesSummary()` + `api.paymentsSummary()` |
| Hisobotlar → **Excel** | `api.exportReport(type, params)` — `ReportExportPanel` (§17b) |

### Excel export (backend)

Ruxsat: `IsAccountantOrManagement`. Operator uchun `403`.

| Endpoint | Davr | Ma’lumot |
|---|---|---|
| `GET /reports/excel/sales/?date_from=&date_to=` | `sold_date` | Sotuvlar jadvali + meta sarlavha |
| `GET /reports/excel/kassa/?date_from=&date_to=` | tranzaksiya / expense sanasi | Tushum + import chiqim jurnali |
| `GET /reports/excel/payments/` | xuddi `kassa` | Alias (bir xil `PaymentsExportView`) |
| `GET /reports/excel/imports/?date_from=&date_to=` | `created_at` | Mustaqil import (manual zakaz) ro‘yxati |
| `GET /reports/excel/expenses/?date_from=&date_to=` | `date` | Barcha xarajatlar (import chiqimlari ham) |
| `GET /reports/excel/stock/` | — | Joriy qoldiqlar (snapshot) |

Frontend: `api.exportReport(type, params)` yoki alohida `exportSales` / `exportKassa` / … — blob download (`download()` helper).

---

## 17b. Excel export UI — `ReportExportPanel` va kalendari

Joylashuv: **Hisobotlar** → **Excel** tab (`App.jsx` → `ReportsPage` → `ReportExportPanel`).

### Hisobot turlari

| `type` (`exportReport`) | UI yorlig‘i | Davr kerakmi | Sana maydoni |
|---|---|---|---|
| `sales` | Sotuvlar | ✅ | `sold_date` |
| `kassa` | Kassa | ✅ | jurnal `date` |
| `import` | Import | ✅ | zakaz `created_at` |
| `expenses` | Xarajatlar | ✅ | expense `date` |
| `stock` | Ombor holati | ❌ | snapshot |

### Tez tanlov (preset)

| Preset | `resolvePeriod` natijasi |
|---|---|
| Barcha davr | `{}` — parametrsiz so‘rov |
| Joriy oy | `date_from` = oy boshi, `date_to` = oy oxiri |
| O‘tgan oy | Oldingi oy oralig‘i |
| Joriy yil | `YYYY-01-01` … bugun |
| Boshqa davr | Kalendardan tanlangan `date_from` / `date_to` |

Kalendardan sana tanlanganda preset avtomatik **`custom`** ga o‘tadi.

### UI tuzilishi

- **Chap:** hisobot turi kartalari (ikon + yorliq), tez tanlov chip’lari, hint matn
- **O‘ng:** `FilterDateRangeCalendar` — davr oralig‘i (`label="Davr oralig‘i"`)
- **Past:** tanlangan tur + davr xulosasi, **Excel yuklab olish** tugmasi
- **Barcha davr** tanlanganda kalendar `disabled` (vizual o‘chirilgan)

### `FilterDateRangeCalendar`

Fayl: `frontend/src/components/FilterDateRangeCalendar.jsx`.

Ishlatiladi:

- `ReportExportPanel` — export davri
- `App.jsx` — bosh sahifa dashboard davr filtri (`period-filter-menu` → `period-filter-body`)

Props:

| Prop | Turi | Default | Tavsif |
|---|---|---|---|
| `dateFrom` | `YYYY-MM-DD` | — | Oraliq boshi |
| `dateTo` | `YYYY-MM-DD` | — | Oraliq oxiri |
| `onChange` | `({ date_from, date_to }) => void` | — | Sana tanlanganda |
| `label` | string | `'Davr'` | Sarlavha |
| `className` | string | `''` | Qo‘shimcha CSS klass |
| `disabled` | boolean | `false` | `true` bo‘lsa tugmalar o‘chiriladi |

Interaksiya: birinchi bosish — bosh sana; ikkinchi bosish — tugash sana (teskari tartib avtomatik tuzatiladi). Oy/yil navigatsiyasi va yil dropdown mavjud.

CSS: `.filter-calendar-*`, `.filter-date-range-calendar`, export uchun `.report-export-calendar-aside`.

---

## 17c. Kassa jurnali va avtomatik moliyaviy sinxron

Biznes qoida (frontend ko‘rsatish):

| Operatsiya | Yo‘nalish | Backend | Jurnal |
|---|---|---|---|
| **Sotuv** (yaratish/tahrir/o‘chirish) | Kassaga **tushum** | `apps/sales/sale_payment.py` → `sync_sale_payment` | `kind=in`, `source=sale` |
| **Buyurtma** (yaratish/tahrir, oldindan to‘lov) | Kassaga **tushum** | `apps/orders/models.py` → `Order.sync_payment` | `kind=in`, `source=order` |
| **Import (manual zakaz)** | Kassadan **chiqim** | `apps/orders/zakaz_payment.py` → `sync_zakaz_expense` | `kind=out`, `source=import` |
| **Shartnoma (SK) faktura** — ombordagi mahsulot qatorlari *(yangi)* | Kassadan **chiqim** | `apps/invoices/expense_sync.py` → `sync_invoice_expense` | `kind=out`, `source=import` (`expense_type=import`) |
| **Ombor kirimi** (`add-stock`, mahsulot yaratish) — kelish narxi bo‘lsa *(yangi)* | Kassadan **chiqim** | `apps/warehouse/stock_expense.py` → `record_stock_in_expense` | `kind=out`, `source=expense` (`expense_type=import`) |
| **Boshqa rasxod** (ofis, transport, oylik, …) | Kassadan **chiqim** | `apps/expenses/` — qo‘lda kiritiladi | `kind=out`, `source=expense` |

**Kassa balansi** (`/cash/payments/summary/` → `net_balance_uzs`) = barcha tushum tranzaksiyalari − **barcha** `Expense` summalari (`ledger_totals()`, yangilangan — avval faqat import chiqimini hisoblardi). ⚠️ `/reports/summary/` dagi (bosh sahifa) `net_balance_uzs` bundan **farqli**, hali faqat import (zakaz)ni hisoblaydi — yuqoridagi «Diqqat» qutisiga qarang.

**Sotuv o‘chirilsa** bog‘liq kassa yozuvi ham o‘chadi (`PROTECT` xatosining oldi olingan). **Buyurtma bekor qilinsa** (`/cancel/`) — bog‘liq kassa yozuvi hozircha **tegilmaydi** (ochiq savol — refund siyosati aniqlanmagan).

### Import grid ustunlari (`ResourcePage`, title=`Import`)

| Ustun | Maydon | Eslatma |
|---|---|---|
| ID | `id` | |
| Mahsulot | `product_name` | |
| Tur | `zakaz_type` | Mustaqil / Backorder |
| Shart. | `contract_number` | |
| Zak. | `quantity` | |
| Summa | `total` | `prices_view` |
| To‘lov | `payment_status` | `unpaid` / `partial` / `paid` badge |
| Qabul | `received_qty` | |
| Etkaz. | `supplier` | |
| Kutil. | `expected_date` | |
| Holati | `status` | inline — `order_status_manage` |
| Yaratdi | `created_by_name` | |

Tarix tugmasi: zakaz `history` modal.

### Backend fayllar (frontend dasturchi uchun)

| Fayl | Vazifa |
|---|---|
| `apps/cash/ledger.py` | `build_ledger_entries`, `ledger_totals` (endi barcha `Expense`ni hisoblaydi) |
| `apps/reports/excel.py` | Excel generatsiya, meta sarlavhalar, `export_kassa_ledger`, `export_imports` |
| `apps/sales/sale_payment.py` | Sotuv → Payment (yaratish **va tahrir**) |
| `apps/orders/models.py` (`Order.sync_payment`) | Buyurtma → Payment |
| `apps/orders/zakaz_payment.py` | Import (zakaz) → Expense |
| `apps/invoices/expense_sync.py` *(yangi)* | Shartnoma (SK) faktura → Expense |
| `apps/warehouse/stock_expense.py` *(yangi)* | Ombor kirimi (`add-stock`, mahsulot yaratish) → Expense |

---

## 18. Frontendga yangi endpoint qo‘shish

Backend da yangi API paydo bo‘lganda frontend integratsiyasi uchun tartib:

### 1. Backend ni tekshiring

```bash
# Swagger da endpoint oching
open http://127.0.0.1:8000/

# yoki schema
curl http://127.0.0.1:8000/api/schema/ | head
```

Aniqlang: path, method, permission, query params, request body, response shape.

### 2. `frontend/src/api.js` ga metod qo‘shing

Oddiy GET:

```javascript
myFeature: (params = {}) => request(`/my-app/items/${toQuery({ page_size: 30, ...params })}`),
```

POST action:

```javascript
doAction: (id, payload) => request(`/my-app/items/${id}/action/`, {
  method: 'POST',
  body: JSON.stringify(payload),
}),
```

Blob export:

```javascript
exportMyFeature: () => download('/reports/excel/my-feature/', 'my-feature.xlsx'),
```

Generic CRUD yetarli bo‘lsa yangi metod shart emas — `api.create('/path/', body)` ishlating.

### 3. UI komponentini ulang

`App.jsx` dagi `resources` jadvaliga qo‘shish (ro‘yxat sahifasi). Grid kerak bo‘lsa `GRID_PAGES` va `MODULE_FILTER_FEATURES` (`listFilters.js`) ni yangilang:

```javascript
'Yangi modul': { load: api.myFeature, path: '/my-app/items/' },
```

Yoki alohida komponentda `useEffect` + `api.myFeature()`.

### 4. Permission va menu

`apps/users/serializers.py` → `user_abilities()` ga yangi ability qo‘shilsa, `App.jsx` navigation va `can(session, 'ability')` tekshiruvini yangilang.

### 5. Hujjatni yangilang

Ushbu `FRONTEND_API.md` ning **§4 jadvali** va tegishli batafsil bo‘limiga endpoint qo‘shing.

### 6. Tekshirish

```bash
cd frontend && npm run dev    # proxy orqali
# Login → yangi funksiya → Network tab da /api/v1/... so‘rovini ko‘ring
```

---

## 19. Frontend performance va dev/prod

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

## 20. Frontend checklist

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
- Excel exportda `api.exportReport(type, params)` yoki `download()` ishlatilsin; Hisobotlar → Excel — `ReportExportPanel`.
- Kassa sahifasi `KassaPage` — `kassaLedger` + `paymentsSummary`; import chiqim `kind=out`.
- Sotuv/import yaratilganda avtomatik kassa sinxroni (`sync_sale_payment`, `sync_zakaz_expense`) — qo‘lda Payment yaratish shart emas.
- `FilterDateRangeCalendar` — dashboard, export va filtrlarda bir xil oralik tanlash UX.
- Bosh sahifa dashboard filtrlari `api.reports()` va `api.monthlyTrend()` ga uzatilsin.
- Dashboard: Tushum / Import chiqim / Kassa balansi alohida; import tushum sifatida ko‘rsatilmasin (`net_balance_uzs`).
- Kassa ro‘yxatida `paid` default yashirin; kerak bo‘lsa `?status=paid` yoki `?include_paid=true`.
- Buyurtma yaratishda `api.nextContractNumber({ contract_date })` bilan raqam olinadi.
- Yangi backend endpoint qo‘shilganda `api.js` → UI → `FRONTEND_API.md` §4 jadval yangilansin.
- Operator uchun narx/foyda maydonlari yo‘q bo‘lishiga UI tayyor bo‘lsin.
- Mobile’da sidebar emas, bottom navigation ko‘rsatilsin.
- Desktop sidebar collapse holati saqlansin.
- Grid sahifalarda `ListFiltersPanel` filtrlari `buildListQueryParams` orqali API ga uzatilsin.
- Global qidiruv Ctrl+K; kamida 2 belgi.
- Mijoz kartasi URL tablari `CLIENT_TABS` bilan mos bo‘lsin.
- USD kurs: `preferred_rate_source` (`infinbank` \| `manual` \| `bank`), `preferred_bank_code`, `preferred_bank_side`; `latest` javobidagi `mb_rate`, `market_rates`, `infinbank`/`manual`.
- `FxRatePanel`: topbar — `header` (bank dropdown + kurs); editorlar — `compact` (dropdown + Qo‘lda). FX boshqaruv — `users_manage`.
- Import grid status (inline + bulk) — `order_status_manage`, `procurement_manage` emas.
- Import yangi/tahrir modal: **`+ Qator qo‘shish`**, **`Manba`**, bulk **`POST /orders/zakaz/bulk/`**, tahrir **`GET .../batch/`** + **`PATCH`**/**`POST`+`import_batch`** (§9a–9b).
- Import gridda guruhlash: `import_batch` (asosiy) yoki legacy shartnoma kaliti — §9a.
- Qisman to‘lov: backend va frontend proporsional taqsimlash, qoldiq oxirgi qatorga; `grandTotal=0` da xato.
- `batchLoading` paytida `ZakazEditor` **`Saqlash`** disabled.
- Operator to‘lov: frontend strip + backend `ZakazOperatorSerializer` / bulk strip — §4, §9b.
- `import_batch` migratsiyasi: `orders.0007_zakaz_import_batch_*` — deploy da `python manage.py migrate` majburiy (`migrations/` `.gitignore` da — har muhit o‘zi `makemigrations` qiladi).
- `ZakazEditor` / Import grid barcha UI label matnlari §9a–9b da — yangi label qo‘shilsa hujjat yangilansin.
- `SaleEditor`, `BuyurtmalarPage`: `api.products()` doim; mijoz qidiruv — `searchClients()` + `fetchClient()` faqat `clients_view`.
- `DataTable` Amallar ustuni: `.row-actions` flex wrapper; grid da `flex-wrap: nowrap`, tugmalar 36px balandlik.
- Invoice javobida `prices_view` yo‘q bo‘lsa `total_delivery`, `total_vat`, `grand_total` ham yo‘q.
- Buyurtma ko‘rish: bir invoice uchun takroriy `GET /invoices/{id}/` yuborilmasin (`viewFetchKeyRef`).
- Korxona profili / invoice forma validatsiyasi — inline `FieldError`, toast emas.
- `ApiError.fields` — PATCH xatoliklarini maydon bo‘yicha ko‘rsatish.
- `validateClientFields()` — Mijozlar editorida saqlashdan oldin.
- `invoiceNewPath()` / `invoiceEditPath()` — navigatsiya helperlari.

## 21. Rol matritsasi (11 qoida)

Regressiya testlari: `apps/common/tests/test_role_matrix.py`.

| # | Qoida | Natija |
|---|---|---|
| 1 | Mahsulot qo‘shish | Operator ✅, Accountant ❌, Management ✅ |
| 2 | Operator API — narxlar yo‘q | `purchase_price`, `selling_price`, `delivery_price` qaytmaydi |
| 3 | Narx yozish | Faqat Management (`PATCH` ishlaydi) |
| 4 | `min_quantity` | Operator ko‘rmaydi; Management o‘zgartiradi |
| 5 | Sotuv yaratish | Operator ✅, Accountant ❌, Management ✅ |
| 6 | Sotuv summasi | Operator uchun `sold_price`, `total_amount`, `profit` yo‘q |
| 7 | Kassa/xarajat | Operator faqat GET; summalar yashirin |
| 8 | Buyurtma yaratish | Operator ✅, Accountant ❌, Management ✅. Narx (`unit_price`) faqat Management kiritadi — Operator yuborsa e’tiborga olinmaydi, mahsulot `selling_price`sidan avtomatik olinadi |
| 9 | Import yaratish | Barcha rollar ✅ |
| 10 | Import status | Faqat Management (`confirmed`, `ordered`, `received`, …) — frontend: `order_status_manage` |
| 11 | Hisobotlar | Operator ❌, Accountant/Management ✅ |

Frontend `abilities` (`warehouse_create`, `order_status_manage`, `prices_view`, `prices_manage`, `einvoice_view`, …) shu qoidalarga mos menyu va maydonlarni yashiradi.

## 22. Hali backendda yo‘q (kelajak modullar)

Buyurtmalar moduli (`/api/v1/invoices/`) — **mavjud:** mazmun, qatorlar, alohida yangi/tahrir sahifalari, preview/ko‘rish modali, teskari hisob, hamkor/tovar tanlash, inline validatsiya, SK → shartnomalar reestri sinx (`invoice_created` / `invoice_edited`), **SK → kassa (Expense) sinx** (§4, §17c — yangi).

**Hali yo‘q:**

- hamkor STIR/JSHSHIR lookup (tashqi Soliq API);
- MXIK/IKPU katalog lookup (frontend faqat tasnif.soliq.uz havolasi);
- shablon saqlash;
- ERI/imzolash;
- Didox/Soliq real integratsiya;
- mijozlar backend UZ validatsiyasi (`ClientSerializer` — faqat frontend `validateClientFields`).
