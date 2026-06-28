# Mahsulot, Ombor va Notification — o'zgarishlar

## 1. `Product.purchase_price` ixtiyoriy bo'ldi
`apps/warehouse/models.py` — `null=True, blank=True`.
Operator mahsulot qo'shganda narx kiritmasligi mumkin.

## 2. Mahsulot qo'shilganda Stock avtomatik yaratiladi

`apps/warehouse/serializers.py` — `ProductSerializer` va `ProductOperatorSerializer`
ikkisida ham bir xil ishlaydi (bir xil backend, faqat `purchase_price`
ko'rinishi farq qiladi).

`POST /api/v1/warehouse/products/` ga ixtiyoriy ikkita maydon qo'shildi:

| Maydon | Majburiy? | Tavsif |
|--------|-----------|--------|
| `quantity` | yo'q | Boshlang'ich miqdor |
| `warehouse_location` | `quantity` berilsa — ha | Lokatsiya (masalan `A-1`) |

- Ikkisi ham berilsa → mahsulot bilan birga `Stock` yozuvi avtomatik yaratiladi.
- `quantity` berilib, `warehouse_location` berilmasa → validatsiya xatosi qaytadi.
- Ikkisi ham berilmasa → eski xulq: faqat `Product` yaratiladi, stock yo'q.

**Misol so'rov:**
```json
POST /api/v1/warehouse/products/
{
  "name": "Samsung DDR4",
  "serial_number": "SN-001",
  "quantity": 10,
  "warehouse_location": "A-1"
}
```
Operator uchun `purchase_price` baribir yuborilmaydi/ko'rinmaydi.

## 3. Telegram olib tashlandi — saytda (in-app) Notification

Bildirishnoma faqat DB orqali saytda ko'rsatiladi, tashqi servis yo'q.

### `Notification` modeli — `apps/notifications/models.py`

| Maydon | Tavsif |
|--------|--------|
| `recipient` | FK → User (qaysi Management foydalanuvchiga) |
| `product` | FK → Product (qaysi mahsulot haqida, `null=True`) |
| `title`, `message` | Matn |
| `is_read` | O'qilgan/o'qilmagan |
| `created_at` | Yaratilgan vaqt |

**Classmethod'lar (asosiy logika shu yerda):**
- `notify_missing_price(product)` — mahsulot narxsiz bo'lsa, har bir
  `role=MANAGEMENT, is_active=True` userga **bitta** o'qilmagan notification
  borligini ta'minlaydi (qayta-qayta chaqirilsa ham dublikat yaratmaydi).
- `sync_missing_price_for_user(user)` — **login paytida** chaqiriladi: hozircha
  narxi kiritilmagan **barcha** mahsulotlar bo'yicha shu userda notification
  yo'q bo'lganlarini yaratadi. Shu sababli narx hali kiritilmagan bo'lsa,
  manager har safar login qilganda eslatma ko'radi.
- `resolve_price_notifications(product)` — narx kiritilganda, shu mahsulotga
  oid barcha o'qilmagan notification'larni avtomatik "o'qilgan" qiladi.

### Trigger nuqtalari

| Joy | Nima qiladi |
|-----|-------------|
| `ProductOperatorSerializer.create()` | Operator narxsiz mahsulot qo'shganda `notify_missing_price()` |
| `ProductSerializer.update()` | Management narx kiritib saqlaganda `resolve_price_notifications()` — eslatma yopiladi |
| `apps/users/views.py` → `login()` | Management har login qilganda `sync_missing_price_for_user()` — hamon narxsiz mahsulotlar qaytadan eslatiladi |

### API — `apps/notifications/views.py`, `urls.py`

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/api/v1/notifications/` | O'z notification'larim (eng yangisi birinchi) |
| GET | `/api/v1/notifications/{id}/` | Bitta notification |
| POST | `/api/v1/notifications/{id}/mark_read/` | Bitta notification'ni o'qilgan qilish |
| POST | `/api/v1/notifications/mark_all_read/` | Hammasini birdan o'qilgan qilish (javobda `marked_read: <son>`) |

Filtr: `?is_read=false` — faqat o'qilmaganlar.

## 4. Management uchun narxi yo'q mahsulotlarni ajratish

`apps/warehouse/views.py` — `GET /api/v1/warehouse/products/?purchase_price__isnull=true`

## 5. Admin panel xatosi tuzatildi

`format_html('{:,.0f}', ...)` — bu sintaksis ishlamaydi (`format_html` Python
format mini-language'ni tushunmaydi). Avval son `f'{value:,.0f}'` bilan
formatlanadi, keyin `format_html`ga uzatiladi. Tuzatilgan joylar:
`apps/expenses/admin.py`, `apps/cash/admin.py`, `apps/sales/admin.py`,
`apps/warehouse/admin.py`. Shu bilan birga narxi `None` bo'lgan mahsulotlar
uchun "narx kiritilmagan" deb ko'rsatish qo'shildi (xato bermay).

## 6. `/stocks/` javobiga `product_model` qo'shildi

`apps/warehouse/serializers.py` → `StockSerializer` — `Product.model` maydoni
endi `product_model` nomi bilan qaytadi, qo'shimcha so'rov kerak emas
(`select_related` allaqachon bor).

## Oqim (misol)

1. Operator `POST /api/v1/warehouse/products/` — narx yubormaydi, lekin
   `quantity` + `warehouse_location` yuborsa, Stock ham birga yaratiladi.
2. Management'ga avtomatik notification yoziladi: *"'X' mahsuloti uchun summasini
   (kelish narxini) kiritmagansiz! Iltimos, kiriting."*
3. Manager `POST /api/v1/auth/login/` qiladi — agar shu mahsulot (yoki boshqa
   narxsiz mahsulotlar) bo'yicha hali o'qilmagan eslatma yo'q bo'lsa, yangidan yaratiladi.
4. Manager `/api/v1/notifications/?is_read=false` orqali eslatmalarni ko'radi.
5. Manager `PATCH /api/v1/warehouse/products/{id}/` orqali narx kiritadi →
   tegishli notification avtomatik `is_read=True` bo'ladi, qaytib chiqmaydi
   (narx o'chirilmasa).

## Migratsiyalar

```
apps/warehouse/migrations/0002_alter_product_purchase_price.py
apps/notifications/migrations/0002_notification.py
apps/notifications/migrations/0003_notification_product.py
```
Barchasi local'da qo'llanildi (`migrate` ishlatildi). Eslatma: `migrations/`
papkalar `.gitignore`da — har bir muhit (local/server) o'z migratsiyasini
`makemigrations` orqali generatsiya qiladi, shuning uchun serverda ham
`make migrations && make migrate` (yoki shunga teng) ishga tushirish kerak.

## Frontend uchun

- Mahsulot qo'shish formasida ixtiyoriy `quantity` / `warehouse_location`
  maydonlarini qo'shish mumkin — to'ldirilsa, alohida `/stocks/` so'rovi
  yuborish shart emas.
- Mahsulotlar jadvalida `purchase_price: null` bo'lgan qatorlarni qizil/ajratilgan
  rangda ko'rsatish (`?purchase_price__isnull=true` filtridan foydalanish mumkin).
- Login muvaffaqiyatli bo'lgandan keyin (agar `role: MANAGEMENT`)
  `/api/v1/notifications/?is_read=false` ni chaqirib, qo'ng'iroq belgisida
  son va ro'yxatni ko'rsatish kerak.
- Hozircha WebSocket/push yo'q — oddiy REST orqali, login va sahifa
  yangilanishlarida so'rov yuboriladi.
