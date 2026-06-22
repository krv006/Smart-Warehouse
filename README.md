# Smart Warehouse (Sklad & Savdo API)

Tovarlarni hisobga olish, ombor (sklad) boshqaruvi va sotuv jarayonlarini
nazorat qilish uchun Django + Django REST Framework asosidagi backend API.

## Rollar (TZ bo'yicha)

- **Operator (Ishchi)** — tovar kirimi, qoldiq (stock) va sotuvlarni kiritadi.
- **Management (Boshqaruv)** — kirim/chiqim, foyda va analitikani (hisobotlar) ko'radi.

## Ma'lumotlar modeli

| Model | Maydonlar |
|-------|-----------|
| `User` | username, role (`OPERATOR` / `MANAGEMENT`) |
| `Product` | name, model, serial_number, purchase_price, created_at |
| `Stock` | product, quantity, warehouse_location |
| `Sale` | product, sold_price, quantity, sold_to, sold_date, comment |

Sotuv yaratilganda ombor qoldig'i avtomatik kamayadi va qoldiqdan ortiq
sotishga ruxsat berilmaydi.

## API endpointlari (`/api/v1/`)

| Endpoint | Ruxsat |
|----------|--------|
| `products/` | o'qish — barcha; yozish — Operator |
| `stocks/` | o'qish — barcha; yozish — Operator |
| `sales/` | o'qish — barcha; yozish — Operator |
| `reports/` | faqat Management (foyda, sotuv monitoringi) |

Qidiruv (`?search=`), filtr (`?product=`, `?warehouse_location=`) va
saralash (`?ordering=`) qo'llab-quvvatlanadi.

## Ishga tushirish

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### PostgreSQL (TZ talab qilgan SQL DB)

```bash
export DB_ENGINE=postgres DB_NAME=warehouse DB_USER=postgres DB_PASSWORD=...
```

## Testlar

```bash
python manage.py test
```
