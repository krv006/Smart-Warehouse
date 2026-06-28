# Narxsiz mahsulot — In-App Notification

## Nima o'zgardi

1. **`Product.purchase_price` ixtiyoriy bo'ldi** — `apps/warehouse/models.py`
   Operator mahsulot qo'shganda narx kiritmasligi mumkin (`null=True, blank=True`).

2. **Telegram notification olib tashlandi.**
   `apps/notifications/tasks.py` dagi `notify_missing_price` Telegram task butunlay o'chirildi.
   (`check_overdue_payments` va `send_backup_notification` — eski, bog'liq bo'lmagan tasklar, tegilmadi.)

3. **Saytda (in-app) notification tizimi qo'shildi** — `apps/notifications/`
   - **Model** (`models.py`): `Notification(recipient, title, message, is_read, created_at)`
   - **Trigger** (`apps/warehouse/serializers.py` → `ProductOperatorSerializer.create()`):
     Operator narxsiz mahsulot qo'shganda, barcha `role=MANAGEMENT, is_active=True`
     foydalanuvchilarga bevosita `Notification` yozuvi yaratiladi (DB orqali, Celery/Telegram shart emas).
   - **API** (`apps/notifications/views.py`, `urls.py`):

     | Method | URL | Tavsif |
     |--------|-----|--------|
     | GET | `/api/v1/notifications/` | O'z notification'larim (eng yangisi birinchi) |
     | GET | `/api/v1/notifications/{id}/` | Bitta notification |
     | POST | `/api/v1/notifications/{id}/mark_read/` | O'qilgan deb belgilash |
     | POST | `/api/v1/notifications/mark_all_read/` | Hammasini o'qilgan qilish |

     Filtr: `?is_read=false` — faqat o'qilmaganlar.

4. **Management uchun narxi yo'q mahsulotlarni ajratish** — `apps/warehouse/views.py`
   `GET /api/v1/warehouse/products/?purchase_price__isnull=true`

## Migratsiyalar

```
apps/warehouse/migrations/0002_alter_product_purchase_price.py
apps/notifications/migrations/0002_notification.py
```
Ikkisi ham qo'llanildi (`migrate` ishlatildi).

## Frontend uchun

- Mahsulotlar jadvalida `purchase_price: null` bo'lgan qatorlarni qizil/ajratilgan rangda ko'rsatish kerak.
- Management login qilganda `/api/v1/notifications/?is_read=false` ni poll qilib, qo'ng'iroq belgisida son ko'rsatish mumkin (hozircha WebSocket yo'q, oddiy REST polling).
