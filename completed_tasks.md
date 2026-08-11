# Tugallangan ishlar va tafsilotlar

## Umumiy maqsad
Ushbu loyiha bo‘yicha avvalgi bosqichlarda boshlangan biznes jarayonlar davom ettirildi. Asosiy e’tibor mijozlar, buyurtmalar, shartnomalar, ombor, kassa, xarajatlar, xabarnomalar, valyuta kursi va foydalanuvchi interfeysi bo‘yicha ishlashga qaratildi.

## 1. Loyiha asosiy biznes workflowini qurish

### Qaysi fayllar?
- [apps/orders/models.py](apps/orders/models.py)
- [apps/orders/serializers.py](apps/orders/serializers.py)
- [apps/orders/views.py](apps/orders/views.py)
- [apps/warehouse/models.py](apps/warehouse/models.py)
- [apps/warehouse/views.py](apps/warehouse/views.py)

### Nima qilindi?
- Buyurtma, shartnoma va ombor jarayonlari uchun asosiy modeli va biznes qoidalar yo‘lga qo‘yildi.
- Buyurtma va shartnoma bilan ishlash mexanizmi ishlab chiqildi.
- Ombor bo‘yicha asosiy operatsiyalar tizimga kiritildi.

## 2. Mijozlar va identifikatsiya boshqaruvi

### Qaysi fayllar?
- [apps/clients/models.py](apps/clients/models.py)
- [apps/clients/serializers.py](apps/clients/serializers.py)
- [apps/clients/views.py](apps/clients/views.py)
- [frontend/src/App.jsx](frontend/src/App.jsx)

### Nima qilindi?
- Yuridik shaxs va jismoniy shaxs uchun alohida ma’lumotlar modeli qo‘llab-quvvatlandi.
- Jismoniy shaxs uchun ism, familiya, otasining ismi, PINFL, passport raqami va telefon maydonlari qo‘shildi.
- Mijoz ma’lumotlari shifrlangan holda saqlanadi.
- Mijozlar ro‘yxatida korxona nomi yoki shaxsning F.I.Sh. ko‘rinishi ishlaydi.

## 3. Buyurtma, shartnoma va fayl yuklash funksiyalari

### Qaysi fayllar?
- [apps/orders/models.py](apps/orders/models.py)
- [apps/orders/serializers.py](apps/orders/serializers.py)
- [apps/orders/views.py](apps/orders/views.py)
- [frontend/src/App.jsx](frontend/src/App.jsx)

### Nima qilindi?
- Buyurtma yaratish jarayoni kengaytirildi.
- Shartnoma raqami avtomatik yaratilishi ishladi.
- Shartnoma sanasi va shartnoma fayli kiritilishi mumkin bo‘ldi.
- Buyurtma yaratishda fayl yuklash ham qo‘llab-quvvatlandi.

## 4. Import / Zakaz va ichki xabarnomalar

### Qaysi fayllar?
- [apps/notifications/models.py](apps/notifications/models.py)
- [apps/notifications/tasks.py](apps/notifications/tasks.py)
- [apps/notifications/views.py](apps/notifications/views.py)

### Nima qilindi?
- Muhim voqealar uchun ichki bildirishnomalar ishlab chiqildi.
- Import/zakaz bilan bog‘liq kechiktirilgan xabarnomalar barcha faol foydalanuvchilarga yetkazilishi ta’minlandi.
- Bildirishnomalar orqali foydalanuvchilar muhim o‘zgarishlar haqida xabardor bo‘lishi mumkin bo‘ldi.

## 5. Kassa, xarajatlar va pul oqimlari

### Qaysi fayllar?
- [apps/cash/models.py](apps/cash/models.py)
- [apps/cash/serializers.py](apps/cash/serializers.py)
- [apps/cash/views.py](apps/cash/views.py)
- [apps/expenses/models.py](apps/expenses/models.py)
- [apps/expenses/serializers.py](apps/expenses/serializers.py)
- [apps/expenses/views.py](apps/expenses/views.py)

### Nima qilindi?
- Kassa va xarajatlar uchun asosiy biznes qoidalar qo‘shildi.
- Kirim/chiqim ma’lumotlari tizimda boshqarila boshladi.
- Xarajatlarni ro‘yxatga olish va ko‘rish imkoniyati yaxshilandi.

## 6. Valyuta kursi va qo‘lda kiritish imkoniyati

### Qaysi fayllar?
- [apps/cash/models.py](apps/cash/models.py)
- [apps/cash/views.py](apps/cash/views.py)
- [frontend/src/App.jsx](frontend/src/App.jsx)

### Nima qilindi?
- USD kursi uchun alohida model va endpoint qo‘shildi.
- Kursni qo‘lda kiritish yoki o‘zgartirish imkoniyati ta’minlandi.
- Frontenddan kursni kiritish mumkin bo‘ldi.

## 7. Brauzer bildirishnomalari

### Qaysi fayllar?
- [frontend/src/App.jsx](frontend/src/App.jsx)
- [frontend/src/api.js](frontend/src/api.js)

### Nima qilindi?
- Foydalanuvchi uchun brauzer bildirishnomalari ruxsatini so‘rash mexanizmi qo‘shildi.
- Bildirishnomalar ishlashi uchun frontend va backend integratsiyasi amalga oshirildi.

## 8. Frontend interfeysi va umumiy foydalanuvchi tajribasi

### Qaysi fayllar?
- [frontend/src/App.jsx](frontend/src/App.jsx)
- [frontend/src/styles.css](frontend/src/styles.css)
- [frontend/src/api.js](frontend/src/api.js)

### Nima qilindi?
- Asosiy CRUD formalar va modal oynalar yangilandi.
- Mijozlar, buyurtmalar, kassa, xarajatlar va bildirishnomalar bo‘yicha interfeys birlashtirildi.
- Foydalanuvchi uchun ko‘proq tushunarli va maqsadga yo‘naltirilgan UI taqdim etildi.

## 9. Tekshiruvlar va sinov natijalari

### Nima qilindi?
- Django tizim tekshiruvi o‘tdi.
- Frontend build muvaffaqiyatli yakunlandi.

### Tekshiruv natijalari
- python manage.py check → “System check identified no issues (0 silenced).”
- npm run build → Vite build muvaffaqiyatli yakunlandi.

## 9. Siz aytgan talablar bo‘yicha bajarilgan ishlar

### Mijoz ma’lumotlari
- Klientlar uchun yuridik shaxs va jismoniy shaxs turi bo‘lib, ularni ajratish mumkin bo‘ldi.
- Jismoniy shaxs uchun passport raqami kiritish funksiyasi qo‘shildi.
- Agar faqat telefon raqami kerak bo‘lsa, boshqa ma’lumotlar ixtiyoriy bo‘lishi uchun form mantiqiy jihatdan moslashtirildi.

### Buyurtmalar va shartnomalar
- Shartnoma raqami formati `1/0608` kabi avtomatik yaratilishi taminlandi.
- Shartnoma raqami avtomatik hosil qilinadi.
- Shartnoma sanasi o‘zgartirilishi mumkin bo‘ldi.
- Shartnoma faylini yuklash imkoniyati qo‘shildi.
- Yetkazish muddati (deadline) doim ko‘rinadigan qilib tashkil etildi.

### Zakaz / import bo‘limi
- Import qilinayotgan mahsulot kechikkan bo‘lsa, bildirishnoma chiqarilishi ishladi.
- Import qilinganda mahsulot summasi kassa / xarajat sifatida hisobga olinishi uchun asosiy biznes logic yo‘lga qo‘yildi.

### Kassa / xarajatlar bo‘limi
- Balans ko‘rinishi ta’minlandi.
- Harakatlar summali ko‘rinishi uchun asosiy hisoblash mexanizmi qo‘shildi.
- Valyuta kursini yozish bo‘limi ishladi.
- Valyuta almashinuvi / konvertatsiya bo‘yicha asosiy imkoniyatlar yaratildi.

### Qo‘shimcha talablar
- “Buyurtma → shartnoma” ichida bitta umumiy punkt sifatida ko‘rsatish yo‘li tashkil etildi.
- Word fayl yuklash funksiyasi qo‘shildi.

## 10. Xulosa
Bu ishlar orqali loyiha oldingi oddiy funksionallikdan chiqib, buyurtma, shartnoma, ombor, mijoz, kassa, xarajat va bildirishnoma jarayonlarini qamrab oluvchi yanada to‘liq va amaliy biznes tizimga yaqinlashdi.

## 11. Frontend ruxsatlar, sidebar va admin panel

### Qaysi fayllar?
- [apps/users/serializers.py](apps/users/serializers.py)
- [apps/users/views.py](apps/users/views.py)
- [apps/users/urls.py](apps/users/urls.py)
- [apps/users/admin.py](apps/users/admin.py)
- [frontend/src/api.js](frontend/src/api.js)
- [frontend/src/App.jsx](frontend/src/App.jsx)
- [completed_tasks.md](completed_tasks.md)

### Nima qilindi?
- Login javobiga foydalanuvchi `abilities` ma’lumotlari qo‘shildi.
- `GET /api/v1/auth/me/` endpointi qo‘shildi; frontend sessiya ochilganda user ruxsatlarini yangilab oladi.
- Sidebar menyulari user bajarishi mumkin bo‘lgan bo‘limlargagina moslab ko‘rsatiladigan qilindi.
- Report ruxsati bo‘lmagan user uchun dashboard avtomatik yuklanmaydi, shu sababli login paytida ortiqcha 403 xatolik chiqmaydi.
- Mijozlar, ombor, buyurtma, sotuv, kassa va xarajat tugmalari role/ability bo‘yicha yashiriladi.
- Bir xil xatolik ketma-ket kelsa, toast 2 soniya ichida takror chiqmaydigan dedupe logikasi qo‘shildi.
- Admin panelda foydalanuvchi rolini va mijozlar bo‘limi ruxsatini tez boshqarish uchun actionlar qo‘shildi.
- Admin user ro‘yxatida qaysi user qaysi modullarga kira olishi qisqa ko‘rinadigan bo‘ldi.

### Tekshiruv natijalari
- `.venv/bin/python manage.py check` → muvaffaqiyatli.
- `npm run build` → muvaffaqiyatli.

## 12. Backend endpointlarini frontendga ulash va mobil UI

### Qaysi fayllar?
- [frontend/src/api.js](frontend/src/api.js)
- [frontend/src/App.jsx](frontend/src/App.jsx)
- [frontend/src/styles.css](frontend/src/styles.css)
- [apps/users/serializers.py](apps/users/serializers.py)
- [completed_tasks.md](completed_tasks.md)

### Nima qilindi?
- Backendda bor bo‘lgan qo‘shimcha endpointlar frontend API qatlamiga qo‘shildi: zakazlar, shartnomalar reestri, kategoriyalar, qoldiqlar, bulk sotuv, xarajat/payment summary va Excel exportlar.
- Sidebar menyusi yangi modullar bilan kengaytirildi: Zakazlar, Shartnomalar, Kategoriyalar, Qoldiqlar, Foydalanuvchilar.
- Hisobotlar sahifasiga xarajat summary, payment summary va Excel export tugmalari qo‘shildi.
- Buyurtma va sotuv formalarida ko‘p qatorli mahsulot kiritish imkoniyati qo‘shildi.
- User management uchun frontenddagi oddiy boshqaruv formasi qo‘shildi.
- Mobile ekranlarda sidebar yashirilib, pastki bottom navigation qo‘shildi.
- Mobile navigation 4 ta asosiy menyu va qolgan bo‘limlar uchun “Ko‘proq” paneli bilan ishlaydigan qilindi.
- Mobile’da forma, modal, qidiruv, ro‘yxat qatorlari va jadval ko‘rinishlari kichik ekranga moslashtirildi.
- Tugmalar mobile touch uchun kamida 44px atrofida bosiladigan qilib moslashtirildi.

### Tekshiruv natijalari
- `npm run build` → muvaffaqiyatli.

## 16. FRONTEND_API.md backend kontrakt bo‘yicha yangilandi

### Qaysi fayllar?
- [FRONTEND_API.md](FRONTEND_API.md)
- [completed_tasks.md](completed_tasks.md)

### Nima qilindi?
- Frontend uchun API kontrakt to‘liq qayta yozildi.
- Auth, refresh token, `abilities`, permission-based UI qoidalari hujjatlashtirildi.
- Buyurtma, zakaz, shartnoma reestri, ombor, mijoz, sotuv, kassa, xarajat, bildirishnoma, hisobot va Excel export endpointlari yozildi.
- Valyuta kursi Infinbankdan olinishi va qo‘lda kurs saqlash kontrakti yozildi.
- Request/response misollari, majburiy maydonlar, status oqimlari, edge-case va frontend checklist qo‘shildi.
- Didox/Soliq invoice moduli backendda hali yo‘qligi alohida ko‘rsatildi.

## 15. Sidebar ochilib-yopilishi va chiqish tugmasi

### Qaysi fayllar?
- [frontend/src/App.jsx](frontend/src/App.jsx)
- [frontend/src/styles.css](frontend/src/styles.css)
- [completed_tasks.md](completed_tasks.md)

### Nima qilindi?
- Desktop sidebar uchun ochish/yopish tugmasi qo‘shildi.
- Sidebar holati `localStorage` da saqlanadi.
- Sidebar yopilganda faqat ikonlar qoladi.
- Sidebar ichidagi menyu scroll bo‘ladigan qilindi.
- `Chiqish` tugmasi pastda kesilib qolmasligi uchun sidebar layout tuzatildi.

### Tekshiruv natijalari
- `npm run build` → muvaffaqiyatli.

## 14. Global tunnel/loading optimizatsiyasi

### Qaysi fayllar?
- [frontend/src/api.js](frontend/src/api.js)
- [frontend/src/App.jsx](frontend/src/App.jsx)
- [frontend/vite.config.js](frontend/vite.config.js)
- [completed_tasks.md](completed_tasks.md)

### Nima qilindi?
- API so‘rovlariga `8s` timeout qo‘shildi; backend o‘chiq bo‘lsa sahifa uzoq loadingda qolmaydi.
- Backend ulanmasa foydalanuvchiga aniq xabar chiqadigan qilindi.
- Auto-refresh `4s` dan `30s` ga o‘zgartirildi.
- Notification polling `12s` dan `30s` ga o‘zgartirildi.
- Ro‘yxat endpointlarida `page_size` kamaytirildi: userlar `20`, asosiy ro‘yxatlar `30`.
- Vite proxy uchun `timeout` va `proxyTimeout` `8000ms` qilindi.

### Tekshiruv natijalari
- `npm run build` → muvaffaqiyatli.

## 13. Popup formalar va file input UI yaxshilandi

### Qaysi fayllar?
- [frontend/src/App.jsx](frontend/src/App.jsx)
- [frontend/src/styles.css](frontend/src/styles.css)
- [completed_tasks.md](completed_tasks.md)

### Nima qilindi?
- Popup oynalar eni `640px` dan `980px` gacha kengaytirildi.
- Buyurtma va sotuv formalaridagi `+ Qator` tugmasi `Mahsulot qo‘shish` deb o‘zgartirildi.
- `Mahsulot qo‘shish` tugmasi mahsulot qatorlari ostiga ko‘chirildi.
- Rasxod formadagi oddiy browser file input chiroyli custom file-picker ko‘rinishiga o‘tkazildi.
- Checkbox maydonlari ixchamroq va tartibliroq ko‘rinadigan qilindi.

### Tekshiruv natijalari
- `npm run build` → muvaffaqiyatli.
