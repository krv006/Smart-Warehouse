# Warehouse Small — Ombor boshqaruv tizimi

Django REST Framework asosida qurilgan ombor boshqaruv API'si.  
Ikki rol: **Operator** (kirim/sotuv) va **Management** (hisobot, export).

---

## Texnologiyalar

| Kutubxona | Versiya | Maqsad |
|-----------|---------|--------|
| Django | ≥ 5.2 | Asosiy framework |
| Django REST Framework | ≥ 3.15 | REST API |
| django-mptt | ≥ 0.16 | Daraxt kategoriya |
| drf-spectacular | ≥ 0.27 | Swagger UI |
| djangorestframework-simplejwt | ≥ 5.3 | JWT autentifikatsiya |
| django-jazzmin | ≥ 3.0 | Admin tema |
| django-filter | ≥ 24.0 | Filtr va qidiruv |
| django-cors-headers | ≥ 4.0 | CORS |
| openpyxl | ≥ 3.1 | Excel export |

---

## O'rnatish

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### .env

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL (bo'lmasa SQLite ishlatiladi)
DB_ENGINE=postgres
DB_NAME=warehouse
DB_USER=postgres
DB_PASSWORD=secret
DB_HOST=localhost
DB_PORT=5432
```

---

## Ma'lumotlar modeli

### Category
| Maydon | Tur | Tavsif |
|--------|-----|--------|
| `id` | int | Avtomatik |
| `name` | string | Kategoriya nomi |
| `parent` | FK → Category | Ota kategoriya (MPTT daraxt) |

### Product
| Maydon | Tur | Tavsif |
|--------|-----|--------|
| `id` | int | Avtomatik |
| `category` | FK → Category | Qaysi kategoriyaga tegishli |
| `name` | string | Mahsulot nomi |
| `model` | string | Model (ixtiyoriy) |
| `serial_number` | string unique | Seriya raqami |
| `purchase_price` | decimal | **Sotib olish narxi** |
| `source` | string | **Qayerdan keldi** — yetkazuvchi/manzil (ixtiyoriy) |
| `quantity_in_stock` | int (read-only) | Ombordagi umumiy miqdor |
| `created_at` | datetime | Qo'shilgan vaqt |

### Stock
| Maydon | Tur | Tavsif |
|--------|-----|--------|
| `id` | int | Avtomatik |
| `product` | FK → Product | Qaysi mahsulot |
| `quantity` | int | Miqdor |
| `warehouse_location` | string | Lokatsiya (masalan: `A-1`, `Shelf-3`) |

### Sale
| Maydon | Tur | Tavsif |
|--------|-----|--------|
| `id` | int | Avtomatik |
| `product` | FK → Product | Sotilgan mahsulot |
| `quantity` | int | Miqdor |
| `sold_price` | decimal | **Birlik uchun sotuv narxi** |
| `total_amount` | decimal (read-only) | `sold_price × quantity` |
| `profit` | decimal (read-only) | `(sold_price − purchase_price) × quantity` |
| `sold_to` | string | Xaridor ismi (ixtiyoriy) |
| `destination` | string | **Qayerga ketdi** — shahar/manzil (ixtiyoriy) |
| `sold_date` | date | Sotuv sanasi |
| `comment` | text | Izoh (ixtiyoriy) |
| `created_at` | datetime | Yozilgan vaqt |

> Sotuv yaratilganda ombor qoldig'i **FIFO** tartibida avtomatik kamayadi.  
> Qoldiqdan ortiq sotishga ruxsat berilmaydi — xato qaytariladi.

---

## Rollar va huquqlar

| Rol | Nima qila oladi |
|-----|-----------------|
| `OPERATOR` | Kategoriya, mahsulot, stock, sotuv — CRUD |
| `MANAGEMENT` | Hamma narsani o'qish + hisobot + Excel yuklab olish |
| `superuser` | Hamma huquq |

> `OPERATOR` uchun `purchase_price` ko'rsatilmaydi (yashirilgan).

---

## API endpointlar

**Bazaviy URL:** `http://localhost:8000/api/v1/`

---

### Auth

| Method | URL | Ruxsat | Tavsif |
|--------|-----|--------|--------|
| POST | `/auth/login/` | Hammaga | Username + parol → JWT token |
| POST | `/auth/token/refresh/` | Hammaga | Refresh token → yangi access |
| POST | `/auth/register-operator/` | Management | Yangi Operator yaratish |

**Login response:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": { "id": 1, "username": "admin", "role": "MANAGEMENT" }
}
```

Token muddati: **access** — 8 soat · **refresh** — 30 kun

---

### Kategoriyalar

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/categories/` | Daraxt ko'rinishida (faqat root, children ichida) |
| POST | `/categories/` | Yangi kategoriya |
| GET | `/categories/{id}/` | Bitta kategoriya |
| PUT/PATCH | `/categories/{id}/` | Tahrirlash |
| DELETE | `/categories/{id}/` | O'chirish |

**Response namunasi:**
```json
[
  {
    "id": 1, "name": "Server", "parent": null,
    "children": [
      {
        "id": 2, "name": "DDR4", "parent": 1,
        "children": [
          {"id": 3, "name": "32gb", "parent": 2, "children": []},
          {"id": 4, "name": "64gb", "parent": 2, "children": []}
        ]
      },
      {
        "id": 5, "name": "DDR5", "parent": 1,
        "children": []
      }
    ]
  },
  {
    "id": 6, "name": "Protsessor", "parent": null,
    "children": [
      {"id": 7, "name": "Intel Xeon Gold 4510", "parent": 6, "children": []}
    ]
  }
]
```

---

### Mahsulotlar

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/products/` | Ro'yxat |
| POST | `/products/` | Yangi mahsulot |
| GET | `/products/{id}/` | Bitta mahsulot |
| PUT/PATCH | `/products/{id}/` | Tahrirlash |
| DELETE | `/products/{id}/` | O'chirish |

Qidiruv: `?search=Intel` — nom, model, seriya bo'yicha  
Saralash: `?ordering=purchase_price` · `?ordering=-created_at`

**POST body namunasi:**
```json
{
  "category": 3,
  "name": "Samsung DDR4",
  "model": "M378A2K43CB1",
  "serial_number": "SN-20240001",
  "purchase_price": "850000.00",
  "source": "Astek Electronics, Toshkent"
}
```

---

### Stock (Ombor qoldiqlari)

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/stocks/` | Barcha qoldiqlar |
| POST | `/stocks/` | Yangi qoldiq yozuvi |
| GET | `/stocks/{id}/` | Bitta yozuv |
| PUT/PATCH | `/stocks/{id}/` | Tahrirlash |
| DELETE | `/stocks/{id}/` | O'chirish |

Filtr: `?product=1` · `?warehouse_location=A-1`

---

### Sotuvlar

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/sales/` | Sotuvlar ro'yxati |
| POST | `/sales/` | Yangi sotuv |
| GET | `/sales/{id}/` | Bitta sotuv |
| PUT/PATCH | `/sales/{id}/` | Tahrirlash |
| DELETE | `/sales/{id}/` | O'chirish |

Filtr: `?product=1` · `?sold_date=2024-06-01`  
Qidiruv: `?search=Samarkand` — xaridor yoki destination bo'yicha

**POST body namunasi:**
```json
{
  "product": 5,
  "quantity": 2,
  "sold_price": "1200000.00",
  "sold_to": "Javlon Toshmatov",
  "destination": "Samarkand, Mirzo ko'chasi 12",
  "sold_date": "2024-06-24",
  "comment": "Naqd to'lov"
}
```

**Response (qo'shimcha maydonlar):**
```json
{
  "total_amount": "2400000.00",
  "profit": "700000.00"
}
```

---

### Hisobot

| Method | URL | Ruxsat | Tavsif |
|--------|-----|--------|--------|
| GET | `/reports/` | Management | Umumiy statistika |

**Response:**
```json
{
  "sales_count": 142,
  "total_revenue": "85000000.00",
  "total_profit": "21500000.00",
  "total_units_sold": 310,
  "total_stock_units": 88,
  "products_count": 47,
  "by_product": [
    {
      "product": 3,
      "product__name": "Intel Xeon Gold",
      "revenue": "12000000.00",
      "profit": "3200000.00",
      "units_sold": 8
    }
  ]
}
```

---

### Excel yuklab olish

| Method | URL | Fayl | Ruxsat |
|--------|-----|------|--------|
| GET | `/export/sales/` | `sotuvlar.xlsx` | Management |
| GET | `/export/stock/` | `ombor_qoldiqlari.xlsx` | Management |

**`sotuvlar.xlsx` ustunlari:**

| # | Mahsulot | Miqdor | Sotuv narxi | Jami summa | Foyda | Xaridor | Qayerga ketdi | Sana | Izoh |
|---|----------|--------|-------------|------------|-------|---------|---------------|------|------|

**`ombor_qoldiqlari.xlsx` ustunlari:**

| # | Mahsulot | Kategoriya | Model | Seriya raqami | Qayerdan keldi | Lokatsiya | Miqdor | Olish narxi |
|---|----------|------------|-------|---------------|----------------|-----------|--------|-------------|

- Sarlavha qatorlari — ko'k fon, oq yozuv
- Miqdori `0` bo'lgan satrlar — qizil rang bilan belgilanadi

---

## CORS

Ruxsat etilgan manzillar:

```
http://localhost:5173
https://warehouse-eosin-six.vercel.app
```

---

## Swagger UI

| URL | Tavsif |
|-----|--------|
| `http://localhost:8000/` | Swagger UI (barcha endpointlar) |
| `http://localhost:8000/api/redoc/` | ReDoc |
| `http://localhost:8000/api/schema/` | OpenAPI JSON |

---

## Admin panel

`http://localhost:8000/admin/` — Jazzmin tema.

| Bo'lim | Imkoniyatlar |
|--------|-------------|
| Kategoriyalar | Drag & drop daraxt ko'rinishi |
| Mahsulotlar | `source` maydoni, stock inline, ombor badge |
| Stock | Rangli miqdor (yashil / sariq / qizil) |
| Sotuvlar | `destination` maydoni, foyda va jami summa |

---

## Kelajakda qo'shish mumkin

- **QR code** — `serial_number` asosida mahsulot QR'i (`GET /products/{id}/qr/`). Hozirgi model o'zgarmaydi, faqat `qrcode` kutubxona qo'shiladi.
