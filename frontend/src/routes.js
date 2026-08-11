export const PAGE_PATHS = {
  'Bosh sahifa': '/',
  Buyurtmalar: '/buyurtmalar',
  Import: '/import',
  Shartnomalar: '/shartnomalar',
  Ombor: '/ombor',
  Kategoriyalar: '/ombor/kategoriyalar',
  Qoldiqlar: '/ombor/qoldiqlar',
  Mijozlar: '/mijozlar',
  Sotuvlar: '/sotuvlar',
  Kassa: '/moliya/kassa',
  Xarajatlar: '/moliya/xarajatlar',
  Hisobotlar: '/hisobotlar',
  'Elektron faktura': '/elektron-faktura',
  Bildirishnomalar: '/bildirishnomalar',
  Foydalanuvchilar: '/foydalanuvchilar',
}

const PATH_TO_PAGE = Object.fromEntries(
  Object.entries(PAGE_PATHS).map(([page, path]) => [path, page]),
)

export const CLIENT_TABS = ['umumiy', 'buyurtmalar', 'sotuvlar', 'tolovlar', 'hujjatlar', 'tarix']

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

  const orderMatch = clean.match(/^\/buyurtmalar\/(\d+)$/)
  if (orderMatch) {
    return {
      kind: 'order-detail',
      page: 'Buyurtmalar',
      orderId: Number(orderMatch[1]),
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

export function orderDetailPath(orderId) {
  return `/buyurtmalar/${orderId}`
}

export function crumbFromPath(pathname) {
  const parsed = parseAppPath(pathname)
  if (parsed.kind === 'client-detail') {
    return `Mijozlar / ${parsed.tab}`
  }
  if (parsed.kind === 'order-detail') {
    return `Buyurtmalar / #${parsed.orderId}`
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
