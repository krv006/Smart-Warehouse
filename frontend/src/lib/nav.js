import { NAV_GROUPS } from './constants'
import { can, canNavItem } from './permissions'

export function getSidebarGroupKey(label) {
  if (label === 'Ombor') return 'Ombor'
  if (label === 'Moliya') return 'Moliya'
  return null
}

export function getGroupForPage(page) {
  if (NAV_GROUPS.Ombor.some((item) => item.page === page)) return 'Ombor'
  if (NAV_GROUPS.Moliya.some((item) => item.page === page)) return 'Moliya'
  return null
}

export function isPageInGroup(page, groupKey) {
  return NAV_GROUPS[groupKey]?.some((item) => item.page === page)
}

export function isSidebarActive(sidebarLabel, active) {
  const group = getSidebarGroupKey(sidebarLabel)
  if (group) return isPageInGroup(active, group)
  return sidebarLabel === active
}

export function defaultGroupPage(session, groupKey) {
  return NAV_GROUPS[groupKey]?.find((item) => can(session, item.ability))?.page || null
}

export function getPageDisplayTitle(page) {
  if (page === 'Ombor') return 'Mahsulotlar'
  if (page === 'Moliya') return 'Moliya'
  return page
}

export function editorSectionTitle(title) {
  if (title === 'Ombor') return 'Ombor'
  if (title === 'Kategoriyalar') return 'Kategoriya'
  if (title === 'Qoldiqlar') return 'Qoldiq'
  if (title === 'Mijozlar') return 'Mijoz'
  return title.replace(/lar$/, '')
}
