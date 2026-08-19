import { api } from '../api'

export const resources = {
  Buyurtmalar: { load: api.orders, path: '/orders/' },
  // "Import" sahifasi UIda "Kirim" deb ataladi (backend hali ham
  // zakaz/import atamalarini ichki ishlatadi — bu faqat foydalanuvchiga
  // ko'rinadigan nom). Boshqa joylarda ham shu kalit ('Kirim') bilan
  // qidiriladi (title === 'Kirim', GRID_PAGES, va h.k.).
  Kirim: { load: api.zakaz, path: '/orders/zakaz/' },
  Shartnomalar: { load: api.contracts, path: '/orders/contracts/', readonly: true },
  Ombor: { load: api.products, path: '/warehouse/products/' },
  Kategoriyalar: { load: api.categories, path: '/warehouse/categories/' },
  Qoldiqlar: { load: api.stocks, path: '/warehouse/stocks/' },
  Mijozlar: { load: api.clients, path: '/clients/' },
  Sotuvlar: { load: api.sales, path: '/sales/' },
  Kassa: { load: api.payments, path: '/cash/payments/' },
  Xarajatlar: { load: api.expenses, path: '/expenses/expenses/' },
  Foydalanuvchilar: { load: api.users, path: '/auth/users/' },
  Bildirishnomalar: { load: api.notifications, path: '/notifications/' },
}
