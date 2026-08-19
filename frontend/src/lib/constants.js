import {
  ChartLineUp, ClipboardText, CurrencyCircleDollar, FileText, House, Package, TrendUp, Truck, Users,
} from '@phosphor-icons/react'

export const AUTO_REFRESH_MS = 30000
export const workspace = 'Asosiy ombor'

export const NAV_GROUPS = {
  Ombor: [
    { page: 'Ombor', label: 'Mahsulotlar', ability: 'warehouse_view' },
    // Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
    // { page: 'Kategoriyalar', label: 'Kategoriyalar', ability: 'categories_view' },
    { page: 'Qoldiqlar', label: 'Qoldiqlar', ability: 'stocks_view' },
  ],
  Moliya: [
    { page: 'Kassa', label: 'Kassa', ability: 'cash_view' },
    { page: 'Xarajatlar', label: 'Xarajatlar', ability: 'expenses_view' },
  ],
}

export const SIDEBAR_NAV = [
  ['Bosh sahifa', House, 'dashboard'],
  ['Buyurtmalar', FileText, 'orders_view'],
  ['Import', Truck, 'procurement_view'],
  ['Shartnomalar', ClipboardText, 'contracts_view'],
  ['Ombor', Package, '__group_ombor__'],
  ['Mijozlar', Users, 'clients_view'],
  ['Sotuvlar', TrendUp, 'sales_view'],
  ['Moliya', CurrencyCircleDollar, '__group_moliya__'],
  ['Hisobotlar', ChartLineUp, 'reports_view'],
  ['Elektron faktura', FileText, 'einvoice_view'],
]

export const HIDDEN_PAGES = {
  Bildirishnomalar: 'notifications_view',
  Foydalanuvchilar: 'users_view',
}

export const productUnits = [
  ['piece', 'dona'], ['kg', 'kg'], ['liter', 'l'], ['meter', 'm'], ['sqm', 'm²'], ['cbm', 'm³'],
  ['barrel', 'bochka'], ['ton', 'tonna'], ['set', 'komplekt'], ['gram', 'gram'], ['cm', 'sm'],
  ['mm', 'mm'], ['ml', 'ml'], ['box', 'quti'], ['pack', 'pachka'], ['pair', 'juft'],
  ['roll', 'rulon'], ['bag', 'qop'], ['sheet', 'list'],
]

export const eInvoiceUnits = productUnits.filter(([key]) => (
  ['piece', 'kg', 'liter', 'meter', 'sqm', 'cbm', 'barrel', 'ton', 'set'].includes(key)
))

export const vatOptions = [
  ['none', 'QQS siz'], ['0', '0%'], ['6', '6%'], ['12', '12%'], ['15', '15%'],
]

export const documentTypeLabels = {
  invoice: 'Hisob-faktura',
  act: 'Dalolatnoma',
  contract: 'Shartnoma',
}

export const GRID_PAGES = new Set(['Mijozlar', 'Buyurtmalar', 'Sotuvlar', 'Import', 'Ombor', 'Kassa', 'Xarajatlar'])

export const ORDER_STATUS_BADGES = {
  pending: { label: 'Kutilmoqda', tone: 'warning' },
  partial: { label: 'Qisman', tone: 'warning' },
  reserved: { label: 'Bron', tone: 'info' },
  fulfilled: { label: 'Yetkazildi', tone: 'success' },
  cancelled: { label: 'Bekor', tone: 'danger' },
  new: { label: 'Yangi', tone: 'info' },
  confirmed: { label: 'Tasdiqlandi', tone: 'info' },
  ordered: { label: 'Etkazuvchiga yuborildi', tone: 'info' },
  received: { label: 'Qabul qilindi', tone: 'success' },
  paid: { label: 'To‘langan', tone: 'success' },
  overdue: { label: 'Muddati o‘tgan', tone: 'danger' },
}
