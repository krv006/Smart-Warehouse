import { HIDDEN_PAGES, NAV_GROUPS, SIDEBAR_NAV } from './constants'

export function can(session, ability) {
  if (!session) return false
  if (session.is_superuser) return true
  return Boolean(session.abilities?.[ability])
}

export function canNavItem(session, ability) {
  if (ability === '__group_ombor__') return NAV_GROUPS.Ombor.some((item) => can(session, item.ability))
  if (ability === '__group_moliya__') return NAV_GROUPS.Moliya.some((item) => can(session, item.ability))
  return can(session, ability)
}

// Admin (Management) uchun soddalashtirilgan navigatsiya — App.jsx'dagi bilan
// bir xil (backend cheklanmaydi, faqat sidebar diqqatni jamlaydi).
const MANAGEMENT_SIMPLIFIED_PAGES = new Set(['Bosh sahifa', 'Buyurtmalar', 'Bron', 'Tasdiqlash', 'Hisobotlar'])

export function allowedSidebar(session) {
  const items = SIDEBAR_NAV.filter(([, , ability]) => canNavItem(session, ability))
  if (session?.role === 'MANAGEMENT' && !session?.is_superuser) {
    return items.filter(([label]) => MANAGEMENT_SIMPLIFIED_PAGES.has(label))
  }
  return items
}

export function isAccessiblePage(session, page) {
  const sidebar = SIDEBAR_NAV.find(([label]) => label === page)
  if (sidebar) return canNavItem(session, sidebar[2])
  const hidden = HIDDEN_PAGES[page]
  return hidden ? can(session, hidden) : false
}
