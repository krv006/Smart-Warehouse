export const PAGE_PATHS = {
  'Bosh sahifa': '/',
  Buyurtmalar: '/buyurtmalar',
  Kirim: '/import',
  Shartnomalar: '/shartnomalar',
  Ombor: '/ombor',
  Kategoriyalar: '/ombor/kategoriyalar',
  Qoldiqlar: '/ombor/qoldiqlar',
  Mijozlar: '/mijozlar',
  Sotuvlar: '/sotuvlar',
  Kassa: '/moliya/kassa',
  Xarajatlar: '/moliya/xarajatlar',
  Hisobotlar: '/hisobotlar',
  Bildirishnomalar: '/bildirishnomalar',
  Foydalanuvchilar: '/foydalanuvchilar',
}

const PATH_TO_PAGE = Object.fromEntries(
  Object.entries(PAGE_PATHS).map(([page, path]) => [path, page]),
)

export const CLIENT_TABS = ['umumiy', 'buyurtmalar', 'sotuvlar', 'tolovlar']

export function pathForPage(page) {
  return PAGE_PATHS[page] || '/'
}

export function parseAppPath(pathname) {
  const clean = pathname.replace(/\/+$/, '') || '/'

  const clientMatch = clean.match(/^\/mijozlar\/([^/]+)(?:\/([^/]+))?$/)
  if (clientMatch) {
    const tab = clientMatch[2] && CLIENT_TABS.includes(clientMatch[2]) ? clientMatch[2] : 'umumiy'
    return {
      kind: 'client-detail',
      page: 'Mijozlar',
      clientId: clientMatch[1],
      tab,
      path: clean,
    }
  }

  if (clean === '/import/yangi') {
    return { kind: 'import-new', page: 'Kirim', path: clean }
  }

  const importEditMatch = clean.match(/^\/import\/(\d+)\/tahrir$/)
  if (importEditMatch) {
    return {
      kind: 'import-edit',
      page: 'Kirim',
      zakazId: Number(importEditMatch[1]),
      path: clean,
    }
  }

  const invoiceNewMatch = clean === '/buyurtmalar/yangi'
  if (invoiceNewMatch) {
    return { kind: 'invoice-new', page: 'Buyurtmalar', path: clean }
  }

  const invoiceEditMatch = clean.match(/^\/buyurtmalar\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/tahrir$/i)
  if (invoiceEditMatch) {
    return {
      kind: 'invoice-edit',
      page: 'Buyurtmalar',
      invoiceId: invoiceEditMatch[1],
      path: clean,
    }
  }

  const invoiceMatch = clean.match(/^\/buyurtmalar\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i)
  if (invoiceMatch) {
    return {
      kind: 'invoice-detail',
      page: 'Buyurtmalar',
      invoiceId: invoiceMatch[1],
      path: clean,
    }
  }

  const page = PATH_TO_PAGE[clean]
  if (page) {
    return { kind: 'page', page, path: clean }
  }

  return { kind: 'unknown', path: clean }
}

export function pageFromPath(pathname) {
  return parseAppPath(pathname).page || null
}

export function clientDetailPath(clientId, tab = 'umumiy') {
  return tab === 'umumiy' ? `/mijozlar/${clientId}` : `/mijozlar/${clientId}/${tab}`
}

export function invoiceDetailPath(invoiceId) {
  return `/buyurtmalar/${invoiceId}`
}

export function invoiceNewPath() {
  return '/buyurtmalar/yangi'
}

export function invoiceEditPath(invoiceId) {
  return `/buyurtmalar/${invoiceId}/tahrir`
}

export function importNewPath() {
  return '/import/yangi'
}

export function importEditPath(zakazId) {
  return `/import/${zakazId}/tahrir`
}

/** @deprecated use invoiceDetailPath */
export function orderDetailPath(id) {
  return invoiceDetailPath(id)
}

export function crumbFromPath(pathname) {
  const parsed = parseAppPath(pathname)
  if (parsed.kind === 'client-detail') {
    return `Mijozlar / ${parsed.tab}`
  }
  if (parsed.kind === 'invoice-detail') {
    return `Buyurtmalar / ${parsed.invoiceId.slice(0, 8)}…`
  }
  if (parsed.kind === 'invoice-new') {
    return 'Buyurtmalar / Yangi'
  }
  if (parsed.kind === 'invoice-edit') {
    return `Buyurtmalar / Tahrir / ${parsed.invoiceId.slice(0, 8)}…`
  }
  if (parsed.kind === 'import-new') {
    return 'Kirim / Yangi'
  }
  if (parsed.kind === 'import-edit') {
    return `Kirim / Tahrir / #${parsed.zakazId}`
  }
  if (parsed.page === 'Ombor' || parsed.page === 'Kategoriyalar' || parsed.page === 'Qoldiqlar') {
    if (parsed.page === 'Ombor') return 'Ombor / Mahsulotlar'
    if (parsed.page === 'Kategoriyalar') return 'Ombor / Kategoriyalar'
    if (parsed.page === 'Qoldiqlar') return 'Ombor / Qoldiqlar'
  }
  if (parsed.page === 'Kassa' || parsed.page === 'Xarajatlar') {
    if (parsed.page === 'Kassa') return 'Moliya / Kassa'
    return 'Moliya / Xarajatlar'
  }
  return parsed.page || 'Bosh sahifa'
}
