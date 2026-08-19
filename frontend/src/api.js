const API_ROOT = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const ACCESS_KEY = 'warehouse_access'
const REFRESH_KEY = 'warehouse_refresh'
const REQUEST_TIMEOUT_MS = 8000

let refreshPromise = null
let authFailureHandler = null

export class ApiError extends Error {
  constructor(message, status, fields = null) {
    super(message)
    this.status = status
    this.fields = fields
  }
}

function fieldErrors(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data) || data.detail) return {}
  const errors = {}
  Object.entries(data).forEach(([key, value]) => {
    if (key === 'non_field_errors') return
    const flat = Array.isArray(value) ? value.flat(Infinity).filter(Boolean) : [value]
    const message = flat.find((item) => typeof item === 'string')
    if (message) errors[key] = message
  })
  return errors
}

// Ichma-ich joylashgan DRF xatolarini ({items: {0: {new_product: {...}}}})
// o'qiladigan matnga aylantiradi
function collectMessages(value, path = []) {
  if (typeof value === 'string') return [{ path, message: value }]
  if (Array.isArray(value)) return value.flatMap((item) => collectMessages(item, path))
  if (value && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, item]) => collectMessages(item, [...path, key]))
  }
  return []
}

const ROW_KEYS = { items: 'qator', lines: 'qator' }

function formatMessage({ path, message }) {
  const rowKeyIndex = path.findIndex((key) => ROW_KEYS[key] !== undefined)
  if (rowKeyIndex !== -1) {
    const index = Number(path[rowKeyIndex + 1])
    if (Number.isFinite(index)) {
      return `${index + 1}-${ROW_KEYS[path[rowKeyIndex]]}: ${message}`
    }
  }
  return message
}

function errorMessage(data) {
  if (!data || typeof data !== 'object') return 'So‘rovni bajarib bo‘lmadi.'
  if (data.detail) {
    const detail = String(data.detail)
    if (/throttled/i.test(detail)) {
      const match = detail.match(/(\d+)\s+seconds?/i)
      return match
        ? `Juda ko‘p so‘rov yuborildi. ${match[1]} soniyadan keyin qayta urinib ko‘ring.`
        : 'Juda ko‘p so‘rov yuborildi. Biroz kutib qayta urinib ko‘ring.'
    }
    return detail
  }
  const messages = [...new Set(collectMessages(data).map(formatMessage))]
  return messages.join(' ') || 'So‘rovni bajarib bo‘lmadi.'
}

function retryAfterSeconds(response, data) {
  const header = response.headers.get('Retry-After')
  if (header) {
    const parsed = Number.parseInt(header, 10)
    if (Number.isFinite(parsed) && parsed > 0) return parsed
  }
  const detail = typeof data?.detail === 'string' ? data.detail : ''
  const match = detail.match(/(\d+)\s+seconds?/i)
  if (match) return Number.parseInt(match[1], 10)
  return 2
}

function wait(ms) {
  return new Promise((resolve) => { window.setTimeout(resolve, ms) })
}

async function readResponse(response) {
  const contentType = response.headers.get('content-type') || ''
  if (response.status === 204) return null
  if (contentType.includes('application/json')) {
    return response.json().catch(() => ({}))
  }
  const text = await response.text().catch(() => '')
  const isHtml = /^\s*</.test(text)
  return {
    detail: isHtml
      ? 'Backend API JSON o‘rniga HTML qaytardi. Django backend ishlayotganini va Vite proxy /api -> http://127.0.0.1:8000 ekanini tekshiring.'
      : text || 'Serverdan noto‘g‘ri formatdagi javob keldi.',
  }
}

function clearSession() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem('warehouse_user')
}

function toQuery(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}

function notifyAuthFailure() {
  clearSession()
  authFailureHandler?.()
}

export function setAuthFailureHandler(handler) {
  authFailureHandler = handler
}

export function saveSession({ access, refresh, user }) {
  if (access) localStorage.setItem(ACCESS_KEY, access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  if (user) localStorage.setItem('warehouse_user', JSON.stringify(user))
}

export function clearStoredSession() {
  clearSession()
}

export function tokenExpiresAt(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return Number(payload.exp || 0) * 1000
  } catch {
    return 0
  }
}

export async function refreshAccessToken() {
  const refresh = localStorage.getItem(REFRESH_KEY)
  if (!refresh) throw new ApiError('Sessiya muddati tugagan. Qayta kiring.', 401)
  if (refreshPromise) return refreshPromise

  refreshPromise = fetch(`${API_ROOT}/auth/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })
    .then(async (response) => {
      const data = await readResponse(response)
      if (!response.ok || !data.access) throw new ApiError(errorMessage(data), response.status)
      localStorage.setItem(ACCESS_KEY, data.access)
      return data.access
    })
    .catch((error) => {
      notifyAuthFailure()
      throw error
    })
    .finally(() => { refreshPromise = null })

  return refreshPromise
}

async function fetchRequest(path, options, token) {
  const headers = new Headers(options.headers || {})
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  try {
    return await fetch(`${API_ROOT}${path}`, { ...options, headers, signal: controller.signal })
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new ApiError('Backend javobi kechikdi. Django server ishlayotganini tekshiring.', 504)
    }
    throw new ApiError('Backendga ulanib bo‘lmadi. Django server 127.0.0.1:8000 da ishlashi kerak.', 503)
  } finally {
    window.clearTimeout(timeout)
  }
}

export async function download(path, filename = 'export.xlsx') {
  const token = localStorage.getItem(ACCESS_KEY)
  const response = await fetchRequest(path, {}, token)
  if (!response.ok) {
    const data = await readResponse(response)
    throw new ApiError(errorMessage(data), response.status)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export async function request(path, options = {}) {
  const { skipAuth = false, retry = true, throttleRetry = true, ...fetchOptions } = options
  let token = skipAuth ? null : localStorage.getItem(ACCESS_KEY)
  let response = await fetchRequest(path, fetchOptions, token)

  // A refresh is shared between concurrent failed requests, then every request
  // retries once with the fresh access token. This prevents refresh storms.
  if (response.status === 401 && !skipAuth && retry && localStorage.getItem(REFRESH_KEY)) {
    try {
      token = await refreshAccessToken()
      response = await fetchRequest(path, fetchOptions, token)
    } catch (error) {
      throw error instanceof ApiError ? error : new ApiError('Sessiyani yangilab bo‘lmadi. Qayta kiring.', 401)
    }
  }

  let data = await readResponse(response)

  if (response.status === 429 && throttleRetry) {
    const delaySec = retryAfterSeconds(response, data)
    await wait(Math.min(delaySec, 5) * 1000)
    return request(path, { skipAuth, retry, throttleRetry: false, ...fetchOptions })
  }

  if (response.status === 401 && !skipAuth) notifyAuthFailure()
  if (!response.ok) {
    throw new ApiError(errorMessage(data), response.status, fieldErrors(data))
  }
  return data
}

export const api = {
  login: (username, password) => request('/auth/login/', { method: 'POST', skipAuth: true, body: JSON.stringify({ username, password }) }),
  me: () => request('/auth/me/'),
  reports: (params = {}) => {
    const q = toQuery(params)
    return Promise.all([
      request(`/reports/summary/${q}`),
      request('/reports/warehouse/'),
      request(`/reports/cash/${q}`),
      request(`/reports/top-products/${toQuery({ limit: 10, ...params })}`),
    ])
  },
  monthlyTrend: (months = 6, params = {}) => request(`/reports/monthly-trend/${toQuery({ months, ...params })}`),
  orders: (params = {}) => request(`/orders/${toQuery({ page_size: 20, ...params })}`),
  nextContractNumber: (params = {}) => request(`/orders/next-contract-number/${toQuery(params)}`),
  ordersBulk: (payload) => request('/orders/bulk/', { method: 'POST', body: JSON.stringify(payload) }),
  order: (id) => request(`/orders/${id}/`),
  zakaz: (params = {}) => request(`/orders/zakaz/${toQuery({ page_size: 30, ...params })}`),
  zakazBulk: (payload) => request('/orders/zakaz/bulk/', { method: 'POST', body: JSON.stringify(payload) }),
  zakazBatch: (id) => request(`/orders/zakaz/${id}/batch/`),
  contracts: (params = {}) => request(`/orders/contracts/${toQuery({ page_size: 30, ...params })}`),
  productContracts: (id) => request(`/warehouse/products/${id}/contracts/`),
  // Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
  // categories: (params = {}) => request(`/warehouse/categories/${toQuery({ page_size: 30, ...params })}`),
  stocks: (params = {}) => request(`/warehouse/stocks/${toQuery({ page_size: 30, ...params })}`),
  products: (params = {}) => request(`/warehouse/products/${toQuery({ page_size: 30, ...params })}`),
  clients: (params = {}) => request(`/clients/${toQuery({ page_size: 30, ...params })}`),
  users: (params = {}) => request(`/auth/users/${toQuery({ page_size: 20, ...params })}`),
  registerUser: (payload) => request('/auth/register/', { method: 'POST', body: JSON.stringify(payload) }),
  notifications: (params = {}) => request(`/notifications/${toQuery({ page_size: 30, ...params })}`),
  notificationsMarkRead: (id) => request(`/notifications/${id}/mark_read/`, { method: 'POST' }),
  notificationsMarkAllRead: () => request('/notifications/mark_all_read/', { method: 'POST' }),
  payments: (params = {}) => request(`/cash/payments/${toQuery({ page_size: 30, ...params })}`),
  paymentsSummary: () => request('/cash/payments/summary/'),
  kassaLedger: (params = {}) => request(`/cash/payments/ledger/${toQuery({ page_size: 25, ...params })}`),
  sales: (params = {}) => request(`/sales/${toQuery({ page_size: 30, ...params })}`),
  salesBulk: (payload) => request('/sales/bulk/', { method: 'POST', body: JSON.stringify(payload) }),
  expenses: (params = {}) => request(`/expenses/expenses/${toQuery({ page_size: 30, ...params })}`),
  expensesSummary: () => request('/expenses/summary/'),
  expenseTypes: () => request('/expenses/expense-types/?page_size=50'),
  expenseSubtypes: () => request('/expenses/expense-subtypes/?page_size=100'),
  exchangeRateLatest: (refresh = false) => request(`/cash/exchange-rates/latest/?refresh=${refresh ? 'true' : 'false'}`),
  exchangeRateSettings: () => request('/cash/exchange-rates/settings/'),
  updateExchangeRateSettings: (payload) => request('/cash/exchange-rates/settings/', { method: 'PATCH', body: JSON.stringify(payload) }),
  companyProfile: () => request('/company-profile/'),
  updateCompanyProfile: (payload) => request('/company-profile/', { method: 'PATCH', body: JSON.stringify(payload) }),
  invoices: (params = {}) => request(`/invoices/${toQuery({ page_size: 30, ...params })}`),
  invoice: (id) => request(`/invoices/${id}/`),
  createInvoice: (payload) => request('/invoices/', { method: 'POST', body: JSON.stringify(payload) }),
  updateInvoice: (id, payload) => request(`/invoices/${id}/`, { method: 'PATCH', body: JSON.stringify(payload) }),
  removeInvoice: (id) => request(`/invoices/${id}/`, { method: 'DELETE' }),
  retrieve: (path, id) => request(`${path}${id}/`),
  create: (path, payload) => request(path, { method: 'POST', body: JSON.stringify(payload) }),
  createForm: (path, payload) => request(path, { method: 'POST', body: payload instanceof FormData ? payload : JSON.stringify(payload) }),
  update: (path, id, payload) => request(`${path}${id}/`, { method: 'PATCH', body: JSON.stringify(payload) }),
  updateForm: (path, id, payload) => request(`${path}${id}/`, { method: 'PATCH', body: payload instanceof FormData ? payload : JSON.stringify(payload) }),
  remove: (path, id) => request(`${path}${id}/`, { method: 'DELETE' }),
  pay: (id, payload) => request(`/cash/payments/${id}/pay/`, { method: 'POST', body: JSON.stringify(payload) }),
  cashConvert: (payload) => request('/cash/payments/convert/', { method: 'POST', body: JSON.stringify(payload) }),
  adjustCashBalance: (payload) => request('/cash/payments/adjust-balance/', { method: 'POST', body: JSON.stringify(payload) }),
  fulfillOrder: (id, payload) => request(`/orders/${id}/fulfill/`, { method: 'POST', body: JSON.stringify(payload) }),
  cancelOrder: (id, payload) => request(`/orders/${id}/cancel/`, { method: 'POST', body: JSON.stringify(payload) }),
  createOrderZakaz: (id, payload) => request(`/orders/${id}/create-zakaz/`, { method: 'POST', body: JSON.stringify(payload) }),
  addStock: (id, payload) => request(`/warehouse/products/${id}/add-stock/`, { method: 'POST', body: JSON.stringify(payload) }),
  exportSales: (params = {}) => download(`/reports/excel/sales/${toQuery(params)}`, 'sotuvlar.xlsx'),
  exportStock: (params = {}) => download(`/reports/excel/stock/${toQuery(params)}`, 'ombor.xlsx'),
  exportExpenses: (params = {}) => download(`/reports/excel/expenses/${toQuery(params)}`, 'xarajatlar.xlsx'),
  exportPayments: (params = {}) => download(`/reports/excel/payments/${toQuery(params)}`, 'kassa.xlsx'),
  exportKassa: (params = {}) => download(`/reports/excel/kassa/${toQuery(params)}`, 'kassa.xlsx'),
  exportImports: (params = {}) => download(`/reports/excel/imports/${toQuery(params)}`, 'import.xlsx'),
  exportReport: (type, params = {}) => {
    const routes = {
      sales: ['/reports/excel/sales/', 'sotuvlar'],
      stock: ['/reports/excel/stock/', 'ombor'],
      expenses: ['/reports/excel/expenses/', 'xarajatlar'],
      kassa: ['/reports/excel/kassa/', 'kassa'],
      payments: ['/reports/excel/payments/', 'kassa'],
      import: ['/reports/excel/imports/', 'import'],
    }
    const [path, prefix] = routes[type] || routes.sales
    const q = toQuery(params)
    const suffix = params.date_from || params.date_to || new Date().toISOString().slice(0, 10)
    return download(`${path}${q}`, `${prefix}_${suffix}.xlsx`)
  },
}
