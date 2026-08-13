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
| 17 | Hisobotlar |
| 17a | Buyurtmalar — `/invoices/` (batafsil) |
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
| `download(path, filename)` | Blob yuklab olish (Excel export) |

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
| `zakazBulk(payload)` | POST | `/orders/zakaz/bulk/` | bulk zakaz body |
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
| `pay(id, payload)` | POST | `/cash/payments/{id}/pay/` | `{ amount, comment }` |
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
| `exportSales()` | GET | `/reports/excel/sales/` | blob → `sales.xlsx` |
| `exportStock()` | GET | `/reports/excel/stock/` | blob → `stock.xlsx` |
| `exportExpenses()` | GET | `/reports/excel/expenses/` | blob → `expenses.xlsx` |
| `exportPayments()` | GET | `/reports/excel/payments/` | blob → `payments.xlsx` |
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

`list()` helperi (`App.jsx`) pagination `results` yoki oddiy arrayni qaytaradi.

---

## 3. Frontend ↔ Backend xaritasi (sahifalar va API)

| UI sahifa | `api.js` | Backend path | Eslatma |
|---|---|---|---|
| Bosh sahifa | `reports`, `monthlyTrend` | `/reports/*` | Filtrli |
| Hisobotlar | `reports`, `expensesSummary`, `paymentsSummary`, `export*` | `/reports/*`, `/expenses/summary/`, `/cash/payments/summary/` | Filtrsiz reports |
| Buyurtmalar | `invoices`, `invoice`, `createInvoice`, `updateInvoice`, `removeInvoice`, `nextContractNumber`, `companyProfile`, `clients` (qidiruv/qo‘shish) | `/invoices/`, `/company-profile/`, `/clients/` | `BuyurtmalarPage` — ro‘yxat, ko‘rish modali, alohida editor sahifalari (§17a) |
| Import | `zakaz`, `create`, `update` | `/orders/zakaz/` | `new_product` inline (manual import); inline/bulk status — faqat `order_status_manage` |
| Shartnomalar | `contracts`, `retrieve` | `/orders/contracts/` | Read-only |
| Korxona profili | `companyProfile`, `updateCompanyProfile` | `/company-profile/` | Profil dropdown |
| Ombor | `products`, `create`, `update`, `addStock`, `productContracts` | `/warehouse/products/` | `warehouse_create` ability |
| Kategoriyalar | `categories`, `create`, `update`, `remove` | `/warehouse/categories/` | |
| Qoldiqlar | `stocks` | `/warehouse/stocks/` | |
| Mijozlar (ro‘yxat) | `clients`, `create`, `update`, `remove` | `/clients/` | Grid + filtr; qator → mijoz kartasi |
| Mijoz kartasi | `retrieve`, `orders`, `sales`, `payments`, `invoices` | `/clients/{uuid}/`, `/orders/`, … | URL: `/mijozlar/{id}[/{tab}]` — `ClientDetailPage` |
| Sotuvlar | `sales`, `salesBulk`, `create`, `update` | `/sales/` | |
| Kassa | `payments`, `pay` | `/cash/payments/` | Paid yashirin |
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

**Grid sahifalar** (`GRID_PAGES` — `App.jsx`): Mijozlar, Sotuvlar, Import, Ombor, Kassa, Xarajatlar. **Buyurtmalar** alohida `BuyurtmalarPage` (`/invoices/`).

| Parametr | Qiymat |
|---|---|
| `page_size` | 25 (grid); `api.js` defaultlari 20/30 — grid override qiladi) |
| `page`, `ordering` | Server-side sort (`GRID_SORT_FIELDS` mapping) |
| Qidiruv | Form submit → query param `search` |

Filtr paneli: `ListFiltersPanel` + `frontend/src/listFilters.js`.

| Modul | Status | Mijoz | Sana |
|---|---|---|---|
| Mijozlar | `is_active` | — | ✅ |
| Sotuvlar | — | ✅ | ✅ |
| Import | `status` | — | ✅ |
| Ombor | — | — | — |
| Kassa | `status` | ✅ | ✅ (UI) |
| Xarajatlar | — | — | ✅ |

`buildListQueryParams(title, filters)` → API query: `status` yoki `is_active`, `client`, `date_from`, `date_to`.

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

**Buyurtma qatorlari — tovar tanlash:** «Tovar nomi» maydoni qo‘lda yoki datalist orqali; yonidagi **quti** ikonkasi `ProductPickerModal` ochadi (`products` ro‘yxatidan qidiruv). Tanlanganda `product`, `identification_code`, `barcode`, `unit`, narx maydonlari to‘ldiriladi.

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

Jami **~91** HTTP endpoint (custom actionlar bilan). ✅ = `api.js` da wrapper bor.

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

`zakaz_type`: `auto` (buyurtmadan / backorder) \| `manual`. `payment_status`: `unpaid` \| `partial` \| `paid`.

**Manual import — `new_product` inline** (POST body, `product` o‘rniga):

```json
{
  "quantity": 10,
  "supplier": "Yetkazuvchi",
  "contract_number": "3/1108",
  "contract_date": "2026-08-11",
  "expected_date": "2026-08-25",
  "unit_price": "1500000",
  "new_product": {
    "name": "Yangi tovar",
    "serial_number": "SN-001",
    "barcode": "8600000000001",
    "unit": "piece",
    "vat_percent": "12",
    "purchase_price": "1200000",
    "delivery_price": "15000000"
  }
}
```

`product` va `new_product` bir vaqtda bo‘lmaydi. `unit_price` faqat Management uchun majburiy (mustaqil import).

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
| GET | `/` | `search`, `category`, `purchase_price__isnull`, `selling_price__isnull` | Auth | ✅ `products` |
| POST | `/` | product body | Operator+ | ✅ `create` |
| GET/PATCH/DELETE | `/{id}/` | — | Operator+ | ✅ CRUD |
| POST | `/{id}/add-stock/` | `{ quantity, asos, warehouse_location?, contract_number?, faktura? }` | Operator+ | ✅ `addStock` |
| GET | `/{id}/contracts/` | — | Auth | ✅ `productContracts` |

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

### Kassa — `/api/v1/cash/`

**To‘lovlar** `/payments/`

| Method | Path | Query / body | Ruxsat | api.js |
|---|---|---|---|---|
| GET | `/` | `page_size`, `status`, `include_paid`, `client`, `currency`, `order`, `sale`, `due_date`, `search` | Accountant/Management read | ✅ `payments` |
| POST | `/` | payment body | Accountant | ✅ `create` |
| GET/PATCH | `/{id}/` | — | Accountant/Management | ✅ `retrieve`/`update` |
| DELETE | `/{id}/` | — | Management | ✅ `remove` |
| POST | `/{id}/pay/` | `{ amount, comment }` | Accountant/Management | ✅ `pay` |
| GET | `/summary/` | — | Accountant/Management | ✅ `paymentsSummary` |

**Ro‘yxatda `paid` yashirin** — `?status=paid` yoki `?include_paid=true`.

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

**Validatsiya (backend + frontend):** STIR — 9 raqam; JSHSHIR — 14; MFO — 5; OKED — 5; telefon — `+998…`; bank hisob — 20 raqam. Xatoliklar maydon ostida qizil matn (`FieldError` / `ApiError.fields`); forma validatsiyasida toast ishlatilmaydi. Frontend: `frontend/src/lib/uzValidators.js` → `validateCompanyProfile()` (`CompanyProfileModal`).

**Mijozlar editor validatsiyasi** (`Editor`, title=`Mijozlar`) — `validateClientFields()` (`uzValidators.js`), saqlashdan oldin client-side; backend `ClientSerializer` alohida UZ regex qo‘llamaydi.

| Tur | Maydon | Qoidalar |
|---|---|---|
| Yuridik | `company_name` | Majburiy |
| Yuridik | `phone` | Majburiy, `validateUzPhone` |
| Yuridik | `inn` | Ixtiyoriy; to‘ldirilsa STIR 9 raqam |
| Yuridik | `mfo` | Ixtiyoriy; to‘ldirilsa 5 raqam |
| Jismoniy | `full_name` | Majburiy |
| Jismoniy | `pinfl` | Majburiy, JSHSHIR 14 raqam + kontrol |
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

Qator (`lines[]`) maydonlari: `product`, `product_name`, `identification_code`, `barcode`, `unit`, `quantity`, `unit_price`, `delivery_amount`, `vat_percent`, `vat_amount`, `total_amount`. Backend `reverse_calculation=true` bo‘lsa teskari hisoblaydi.

Operator uchun narx maydonlari (`unit_price`, `delivery_amount`, `vat_amount`, `total_amount`) javobdan olib tashlanadi.

`prices_view` yo‘q foydalanuvchilar uchun invoice darajasidagi `total_delivery`, `total_vat`, `grand_total` ham qaytmaydi (serializer context `can_view_prices=false`).

Mazmun: `content_title`, `content_body` — frontend preview (`DocumentPreviewModal`) bilan ko‘rsatiladi.

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
| GET | `/excel/sales/` | `date_from`, `date_to` | Accountant/Management | ✅ `exportSales` |
| GET | `/excel/stock/` | — | Accountant/Management | ✅ `exportStock` |
| GET | `/excel/expenses/` | `date_from`, `date_to` | Accountant/Management | ✅ `exportExpenses` |
| GET | `/excel/payments/` | — | Accountant/Management | ✅ `exportPayments` |

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
      "vat_percent": "12"
    }
  ]
}
```

Backend mahsulotdan `product_name`, `barcode`, `identification_code`, `unit`, narx va QQS ni to‘ldiradi; `delivery_amount`, `vat_amount`, `total_amount` hisoblanadi.

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

**Validatsiya:** `validateEInvoice()` — xatoliklar input ostida; «Hujjatni ko‘rsatish» / «Saqlash» da toast o‘rniga scroll birinchi qizil maydonga.

**`validateEInvoice()` maydonlari** (`App.jsx`):

| Maydon | Qoidalar |
|---|---|
| `contract_number` | Majburiy; regex `^\d+/\d{4}$` (masalan `12/1108`) |
| `place_signed` | Majburiy |
| `contract_date` | Majburiy |
| `valid_until` | Majburiy; `>= contract_date` |
| `client` | Majburiy (buyurtmachi / hamkor tanlangan) |
| `executor_type` | `company_profile` yoki `client` |
| `executor_client` | `executor_type=client` bo‘lsa majburiy |
| `company` | Faqat `executor_type=company_profile` — korxona profilida `name` va `stir` |
| `content_title` | Majburiy |
| `content_body` | Majburiy |
| `lines[].product_name` | Har qator — majburiy |
| `lines[].identification_code` | Har qator — majburiy |
| `lines[].quantity` | Kamida 1 |
| `lines[].unit_price` | Faqat `prices_view` + `reverse_calculation=false` bo‘lsa majburiy |
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
| `order_status_manage` | import status (`confirmed`/`received`/…) — inline va bulk | Management |
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
- `order_status_manage` — import gridda inline status va bulk status (`confirmed` → `received` …).
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

Backend: status o‘zgartirish (`confirmed`, `ordered`, `received`, `cancelled`) — **Management** roli talab qilinadi.

Frontend: Import gridda inline status va bulk status faqat `order_status_manage` ability bo‘lsa ko‘rinadi (`procurement_manage` yetarli emas).

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

`full_name`, `pinfl`, `inn`, `passport_number`, `phone`, `director_jshshr`, `director_fish`, `bank_account` bazada shifrlanadi. Javobda ochiq matn qaytadi.

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

Frontend Kassa sahifasi: `api.payments()` — default holatda faol to‘lovlar.

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
  "mb_rate_today": "11934.61",
  "expenses_uzs": "1200000",
  "expenses_usd": "0",
  "commission_earned": "150000",
  "overdue_payments_count": 3,
  "report_date": "2026-08-11"
}
```

Eslatma: `import_paid_*` — to‘langan MANUAL zakazlar (yetkazuvchi to‘lovi). `kassa_collected_*` — mijoz to‘lov tranzaksiyalari.

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

Frontend: `api.monthlyTrend(6, params)`.

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
| Hisobotlar | `api.reports()` filtrsiz + `api.expensesSummary()` + `api.paymentsSummary()` |

Excel export:

```http
GET /api/v1/reports/excel/sales/?date_from=2026-08-01&date_to=2026-08-31
GET /api/v1/reports/excel/stock/
GET /api/v1/reports/excel/expenses/?date_from=2026-08-01&date_to=2026-08-31
GET /api/v1/reports/excel/payments/
```

Frontend: `api.exportSales()`, `api.exportStock()`, `api.exportExpenses()`, `api.exportPayments()` — blob download. Operator uchun `403`.

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
- Excel exportda blob download ishlatilsin.
- Bosh sahifa dashboard filtrlari `api.reports()` va `api.monthlyTrend()` ga uzatilsin.
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
| 8 | Buyurtma yaratish | Operator ✅, Accountant ❌, Management ✅ |
| 9 | Import yaratish | Barcha rollar ✅ |
| 10 | Import status | Faqat Management (`confirmed`, `received`, …) — frontend: `order_status_manage` |
| 11 | Hisobotlar | Operator ❌, Accountant/Management ✅ |

Frontend `abilities` (`warehouse_create`, `order_status_manage`, `prices_view`, `prices_manage`, `einvoice_view`, …) shu qoidalarga mos menyu va maydonlarni yashiradi.

## 22. Hali backendda yo‘q (kelajak modullar)

Buyurtmalar moduli (`/api/v1/invoices/`) — **mavjud:** mazmun, qatorlar, alohida yangi/tahrir sahifalari, preview/ko‘rish modali, teskari hisob, hamkor/tovar tanlash, inline validatsiya, SK → shartnomalar reestri sinx (`invoice_created` / `invoice_edited`).

**Hali yo‘q:**

- hamkor STIR/JSHSHIR lookup (tashqi Soliq API);
- MXIK/IKPU katalog lookup (frontend faqat tasnif.soliq.uz havolasi);
- shablon saqlash;
- ERI/imzolash;
- Didox/Soliq real integratsiya;
- mijozlar backend UZ validatsiyasi (`ClientSerializer` — faqat frontend `validateClientFields`).
