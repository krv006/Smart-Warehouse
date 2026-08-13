export const MODULE_STATUS_OPTIONS = {
  Mijozlar: [
    { value: 'true', label: 'Faol' },
    { value: 'false', label: 'Nofaol' },
  ],
  Import: [
    { value: 'new', label: 'Yangi' },
    { value: 'confirmed', label: 'Tasdiqlandi' },
    { value: 'ordered', label: 'Etkazuvchiga yuborildi' },
    { value: 'received', label: 'Qabul qilindi' },
    { value: 'cancelled', label: 'Bekor qilindi' },
  ],
  Kassa: [
    { value: 'pending', label: 'Kutilmoqda' },
    { value: 'partial', label: 'Qisman' },
    { value: 'paid', label: 'To‘langan' },
    { value: 'overdue', label: 'Muddati o‘tgan' },
  ],
}

export const MODULE_FILTER_FEATURES = {
  Mijozlar: { status: true, client: false, date: true },
  Sotuvlar: { status: false, client: true, date: true },
  Import: { status: true, client: false, date: true },
  Ombor: { status: false, client: false, date: false },
  Kassa: { status: true, client: true, date: true },
  Xarajatlar: { status: false, client: false, date: true },
}

export function buildListQueryParams(title, filters = {}) {
  const params = {}
  if (filters.status) {
    if (title === 'Mijozlar') params.is_active = filters.status
    else params.status = filters.status
  }
  if (filters.client) params.client = filters.client
  if (filters.date_from) params.date_from = filters.date_from
  if (filters.date_to) params.date_to = filters.date_to
  return params
}

export function hasActiveListFilters(filters = {}) {
  return Boolean(filters.status || filters.client || filters.date_from || filters.date_to)
}

export function emptyStateConfig(title) {
  const map = {
    Mijozlar: { label: 'Hali mijoz yo‘q', cta: 'Birinchi mijozni qo‘shish' },
    Sotuvlar: { label: 'Hali sotuv yo‘q', cta: 'Birinchi sotuvni qo‘shish' },
    Import: { label: 'Hali import yozuvi yo‘q', cta: 'Import qo‘shish' },
    Ombor: { label: 'Hali mahsulot yo‘q', cta: 'Birinchi mahsulotni qo‘shish' },
    Kassa: { label: 'To‘lov yozuvi topilmadi', cta: null },
    Xarajatlar: { label: 'Hali xarajat yo‘q', cta: 'Xarajat qo‘shish' },
  }
  return map[title] || { label: 'Yozuv topilmadi', cta: null }
}

export function exportRowsCsv(filename, columns, rows) {
  const escape = (value) => {
    const text = String(value ?? '').replace(/"/g, '""')
    return `"${text}"`
  }
  const header = columns.map((col) => escape(col.label)).join(',')
  const body = rows.map((row) => columns.map((col) => {
    if (col.exportValue) return escape(col.exportValue(row))
    const raw = col.render ? col.render(row) : row[col.key]
    if (typeof raw === 'object' && raw !== null) return escape('')
    return escape(raw)
  }).join(',')).join('\n')
  const blob = new Blob([`${header}\n${body}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
