# Narxsiz mahsulot — In-App Notification tizimi

## Nima o'zgardi

1. **`Product.purchase_price` ixtiyoriy bo'ldi** — `apps/warehouse/models.py`
   Operator mahsulot qo'shganda narx kiritmasligi mumkin (`null=True, blank=True`).

2. **Telegram bog'liqligi yo'q.** Bildirishnoma faqat saytda (DB orqali) ko'rsatiladi,
   tashqi servis (Telegram, email va h.k.) ishlatilmaydi.

3. **`Notification` modeli** — `apps/notifications/models.py`

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

4. **Trigger nuqtalari:**
   - `apps/warehouse/serializers.py` → `ProductOperatorSerializer.create()`:
     operator narxsiz mahsulot qo'shganda `notify_missing_price()` chaqiriladi.
   - `apps/warehouse/serializers.py` → `ProductSerializer.update()`:
     Management mahsulotga narx kiritib saqlaganda `resolve_price_notifications()`
     chaqiriladi — eslatma avtomatik yopiladi.
   - `apps/users/views.py` → `login()`:
     Management foydalanuvchi har safar login qilganda `sync_missing_price_for_user()`
     ishlaydi — narxi hamon kiritilmagan mahsulotlar bo'yicha eslatma qayta chiqadi.

5. **API** — `apps/notifications/views.py`, `urls.py`

   | Method | URL | Tavsif |
   |--------|-----|--------|
   | GET | `/api/v1/notifications/` | O'z notification'larim (eng yangisi birinchi) |
   | GET | `/api/v1/notifications/{id}/` | Bitta notification |
   | POST | `/api/v1/notifications/{id}/mark_read/` | Bitta notification'ni o'qilgan qilish |
   | POST | `/api/v1/notifications/mark_all_read/` | Hammasini birdan o'qilgan qilish (javobda `marked_read: <son>`) |

   Filtr: `?is_read=false` — faqat o'qilmaganlar.

6. **Management uchun narxi yo'q mahsulotlarni ajratish** — `apps/warehouse/views.py`
   `GET /api/v1/warehouse/products/?purchase_price__isnull=true`

## Oqim (misol)

1. Operator `POST /api/v1/warehouse/products/` — narx maydonini umuman yubormaydi.
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
Barchasi qo'llanildi (`migrate` ishlatildi). Eslatma: `migrations/` papkalar
`.gitignore`da — har bir muhit (local/server) o'z migratsiyasini
`makemigrations` orqali generatsiya qiladi.

## Frontend uchun

- Mahsulotlar jadvalida `purchase_price: null` bo'lgan qatorlarni qizil/ajratilgan
  rangda ko'rsatish (`?purchase_price__isnull=true` filtridan foydalanish mumkin).
- Login muvaffaqiyatli bo'lgandan keyin (agar `role: MANAGEMENT`)
  `/api/v1/notifications/?is_read=false` ni chaqirib, qo'ng'iroq belgisida
  son va ro'yxatni ko'rsatish kerak.
- Hozircha WebSocket/push yo'q — oddiy REST orqali, login va sahifa
  yangilanishlarida so'rov yuboriladi.
