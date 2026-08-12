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

export function allowedSidebar(session) {
  return SIDEBAR_NAV.filter(([, , ability]) => canNavItem(session, ability))
}

export function isAccessiblePage(session, page) {
  const sidebar = SIDEBAR_NAV.find(([label]) => label === page)
  if (sidebar) return canNavItem(session, sidebar[2])
  const hidden = HIDDEN_PAGES[page]
  return hidden ? can(session, hidden) : false
}
