export const money = (value) => new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 0 }).format(Number(value || 0))

export const moneyDecimal = (value) => new Intl.NumberFormat('uz-UZ', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0))

export const list = (data) => Array.isArray(data) ? data : data?.results || []

export const asText = (value, fallback = '—') => value === undefined || value === null || value === '' ? fallback : value

export const todayValue = () => new Date().toISOString().slice(0, 10)

export const currentYearEndValue = () => `${new Date().getFullYear()}-12-31`

export const formatDateUz = (iso) => {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export const formatDateTimeUz = (iso) => {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('uz-UZ', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export const formatError = (message) => {
  if (!message) return 'Xatolik yuz berdi.'
  if (typeof message === 'string') return message
  return 'Xatolik yuz berdi.'
}

export const userInitials = (name) => {
  const parts = String(name || 'U').trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return (parts[0]?.[0] || 'U').toUpperCase()
}

// Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
// export function flattenCategories(nodes, depth = 0, result = []) {
//   for (const node of nodes) {
//     result.push({ id: node.id, name: node.name, depth })
//     if (node.children?.length) flattenCategories(node.children, depth + 1, result)
//   }
//   return result
// }
//
// export function findCategoryNode(nodes, id) {
//   for (const node of nodes) {
//     if (node.id === id) return node
//     const found = findCategoryNode(node.children || [], id)
//     if (found) return found
//   }
//   return null
// }

export function collectDescendantIds(node) {
  const ids = []
  for (const child of node?.children || []) {
    ids.push(child.id)
    ids.push(...collectDescendantIds(child))
  }
  return ids
}
