# Warehouse Small — Ombor boshqaruv tizimi

Django REST Framework asosida qurilgan kichik ombor boshqaruv API'si.  
Ikki rol: **Operator** (kirim/sotuv) va **Management** (hisobot).

---

## Texnologiyalar

| Kutubxona | Versiya |
|-----------|---------|
| Django | ≥ 5.2 |
| Django REST Framework | ≥ 3.15 |
| django-mptt | ≥ 0.16 |
| drf-spectacular (Swagger) | ≥ 0.27 |
| djangorestframework-simplejwt | ≥ 5.3 |
| django-jazzmin | ≥ 3.0 |
| django-filter | ≥ 24.0 |

---

## O'rnatish

```bash
# 1. Virtual muhit
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# 2. Paketlar
pip install -r requirements.txt

# 3. .env fayl (quyidagi namunaga qarang)

# 4. Migratsiyalar
python manage.py migrate

# 5. Superuser
python manage.py createsuperuser

# 6. Server
python manage.py runserver
```

### .env namunasi

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL ishlatmoqchi bo'lsangiz:
DB_ENGINE=postgres
DB_NAME=warehouse
DB_USER=postgres
DB_PASSWORD=secret
DB_HOST=localhost
DB_PORT=5432
```

> `DB_ENGINE` ko'rsatilmasa SQLite avtomatik ishlatiladi.

---

## Ma'lumotlar modeli

| Model | Maydonlar |
|-------|-----------|
| `User` | username, role (`OPERATOR` / `MANAGEMENT`) |
| `Category` | name, parent (MPTT daraxt) |
| `Product` | category, name, model, serial_number, purchase_price |
| `Stock` | product, quantity, warehouse_location |
| `Sale` | product, sold_price, quantity, sold_to, sold_date, comment |

Sotuv yaratilganda ombor qoldig'i **FIFO** tartibida avtomatik kamayadi.  
Qoldiqdan ortiq sotishga ruxsat berilmaydi.

---

## Rollar

| Rol | Huquqlar |
|-----|----------|
| `OPERATOR` | Kategoriya, mahsulot, stock, sotuv — CRUD |
| `MANAGEMENT` | O'qish + `/reports/` |
| `superuser` | Hammasi |

---

## API endpointlar

Bazaviy URL: `http://localhost:8000/api/v1/`

### Auth

| Method | URL | Tavsif |
|--------|-----|--------|
| POST | `/auth/login/` | JWT token olish |
| POST | `/auth/token/refresh/` | Access tokenni yangilash |
| POST | `/auth/register-operator/` | Yangi operator (faqat Management) |

### Kategoriyalar (MPTT daraxt)

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/categories/` | Daraxt ko'rinishida root kategoriyalar |
| POST | `/categories/` | Yangi kategoriya |
| GET | `/categories/{id}/` | Bitta kategoriya |
| PUT/PATCH | `/categories/{id}/` | Tahrirlash |
| DELETE | `/categories/{id}/` | O'chirish |

`GET /categories/` response namunasi:
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
      }
    ]
  },
  {
    "id": 7, "name": "Protsessor", "parent": null,
    "children": [
      {"id": 8, "name": "Intel Xeon Gold 4510", "parent": 7, "children": []}
    ]
  }
]
```

### Mahsulotlar

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/products/` | Ro'yxat |
| POST | `/products/` | Yangi mahsulot |
| GET | `/products/{id}/` | Bitta mahsulot |
| PUT/PATCH | `/products/{id}/` | Tahrirlash |
| DELETE | `/products/{id}/` | O'chirish |

Qidiruv: `?search=MacBook` — nom, model, seriya bo'yicha.  
Saralash: `?ordering=purchase_price` yoki `?ordering=-created_at`.

### Stock (Ombor qoldiqlari)

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/stocks/` | Qoldiqlar |
| POST | `/stocks/` | Yangi qoldiq yozuvi |
| PUT/PATCH | `/stocks/{id}/` | Tahrirlash |
| DELETE | `/stocks/{id}/` | O'chirish |

Filtr: `?product=1`, `?warehouse_location=A1`.

### Sotuvlar

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/sales/` | Sotuvlar ro'yxati |
| POST | `/sales/` | Yangi sotuv (FIFO) |
| PUT/PATCH | `/sales/{id}/` | Tahrirlash |
| DELETE | `/sales/{id}/` | O'chirish |

Filtr: `?product=1`, `?sold_date=2024-06-01`.

### Hisobot

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/reports/` | Umumiy daromad, foyda, mahsulot kesimi (faqat Management) |

---

## Autentifikatsiya

JWT Bearer token:

```bash
# Token olish
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'

# So'rovlarda ishlatish
curl http://localhost:8000/api/v1/products/ \
  -H "Authorization: Bearer <access_token>"
```

---

## Swagger UI

| URL | Tavsif |
|-----|--------|
| `http://localhost:8000/` | Swagger UI |
| `http://localhost:8000/api/redoc/` | ReDoc |
| `http://localhost:8000/api/schema/` | OpenAPI JSON sxema |

---

## Admin panel

`http://localhost:8000/admin/` — Jazzmin tema.

- **Kategoriyalar** — drag & drop daraxt (`DraggableMPTTAdmin`)
- **Mahsulotlar** — stock inline, ombor qoldig'i rangli badge
- **Sotuvlar** — foyda va jami summa avtomatik hisoblanadi

---

## Testlar

```bash
python manage.py test
```
