import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Warehouse, Bell, Buildings, CaretDown, ChartLineUp,
  ClipboardText, CurrencyCircleDollar, DownloadSimple, Eye, FileText, Funnel, House, MagnifyingGlass,
  Package, PencilSimple, Plus, SignOut, SpinnerGap, Stack, Tag, TrendDown, TrendUp, Truck, UserGear, Users, WarningCircle, X, XCircle, DotsThree, CaretLeft, CaretRight, CheckCircle,
} from '@phosphor-icons/react'
import { api, clearStoredSession, refreshAccessToken, saveSession, setAuthFailureHandler, tokenExpiresAt } from './api'

const navigation = [
  ['Bosh sahifa', House, 'dashboard'],
  ['Buyurtmalar', FileText, 'orders_view'],
  ['Import', Truck, 'procurement_view'],
  ['Shartnomalar', ClipboardText, 'contracts_view'],
  ['Ombor', Package, 'warehouse_view'],
  ['Kategoriyalar', Tag, 'categories_view'],
  ['Qoldiqlar', Stack, 'stocks_view'],
  ['Mijozlar', Users, 'clients_view'],
  ['Sotuvlar', TrendUp, 'sales_view'],
  ['Kassa', CurrencyCircleDollar, 'cash_view'],
  ['Xarajatlar', ClipboardText, 'expenses_view'],
  ['Hisobotlar', ChartLineUp, 'reports_view'],
  ['Foydalanuvchilar', UserGear, 'users_view'],
  ['Bildirishnomalar', Bell, 'notifications_view'],
]

const money = (value) => new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 0 }).format(Number(value || 0))
const list = (data) => Array.isArray(data) ? data : data?.results || []

function flattenCategories(nodes, depth = 0, result = []) {
  for (const node of nodes) {
    result.push({ id: node.id, name: node.name, depth })
    if (node.children?.length) flattenCategories(node.children, depth + 1, result)
  }
  return result
}

function findCategoryNode(nodes, id) {
  for (const node of nodes) {
    if (node.id === id) return node
    const found = findCategoryNode(node.children || [], id)
    if (found) return found
  }
  return null
}

function collectDescendantIds(node) {
  const ids = []
  for (const child of node?.children || []) {
    ids.push(child.id)
    ids.push(...collectDescendantIds(child))
  }
  return ids
}
const AUTO_REFRESH_MS = 30000
const workspace = 'Asosiy ombor'
const productUnits = [
  ['piece', 'dona'],
  ['kg', 'kg'],
  ['gram', 'gram'],
  ['ton', 'tonna'],
  ['meter', 'metr'],
  ['cm', 'sm'],
  ['mm', 'mm'],
  ['liter', 'litr'],
  ['ml', 'ml'],
  ['box', 'quti'],
  ['pack', 'pachka'],
  ['set', 'komplekt'],
  ['pair', 'juft'],
  ['roll', 'rulon'],
  ['bag', 'qop'],
  ['sheet', 'list'],
]
const unitLabel = (value) => productUnits.find(([key]) => key === value)?.[1] || value || 'dona'
const quantityWithUnit = (value, row = {}) => `${money(value)} ${row.unit_display || unitLabel(row.unit)}`

function useClickOutside(ref, onClose, active) {
  useEffect(() => {
    if (!active) return undefined
    const handler = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [ref, onClose, active])
}

function useAutoRefresh(callback, enabled = true) {
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  useEffect(() => {
    if (!enabled) return undefined
    const id = setInterval(() => callbackRef.current(true), AUTO_REFRESH_MS)
    return () => clearInterval(id)
  }, [enabled])
}

function useTokenRefresh(enabled) {
  useEffect(() => {
    if (!enabled) return undefined
    let timer
    let disposed = false
    const schedule = async () => {
      const expiresAt = tokenExpiresAt(localStorage.getItem('warehouse_access') || '')
      // Refresh two minutes before expiry; an invalid/missing expiry is refreshed now.
      const delay = Math.max(15_000, expiresAt ? expiresAt - Date.now() - 120_000 : 0)
      timer = window.setTimeout(async () => {
        try {
          await refreshAccessToken()
          if (!disposed) schedule()
        } catch {
          // refreshAccessToken clears the stored session and informs App.
        }
      }, delay)
    }
    schedule()
    return () => { disposed = true; window.clearTimeout(timer) }
  }, [enabled])
}

function formatError(message) {
  if (!message) return 'So‘rovni bajarib bo‘lmadi.'
  if (/permission|forbidden|403/i.test(message)) return 'Bu amalni bajarish uchun ruxsatingiz yo‘q.'
  return message
}

const asText = (value, fallback = '—') => value === undefined || value === null || value === '' ? fallback : value
const todayValue = () => new Date().toISOString().slice(0, 10)
const currentYearEndValue = () => `${new Date().getFullYear()}-12-31`

function monthStartValue(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`
}

function monthEndValue(date = new Date()) {
  const y = date.getFullYear()
  const m = date.getMonth()
  const last = new Date(y, m + 1, 0).getDate()
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(last).padStart(2, '0')}`
}

function prevMonthRangeValue() {
  const d = new Date()
  d.setDate(1)
  d.setMonth(d.getMonth() - 1)
  return { date_from: monthStartValue(d), date_to: monthEndValue(d) }
}

function yearStartValue() {
  return `${new Date().getFullYear()}-01-01`
}

function formatPeriodRange(period) {
  if (!period?.date_from && !period?.date_to) return 'barcha davr'
  if (period.date_from === period.date_to) return period.date_from
  return `${period.date_from || '…'} — ${period.date_to || '…'}`
}

const CALENDAR_WEEKDAYS = ['Du', 'Se', 'Cho', 'Pa', 'Ju', 'Sha', 'Ya']
const UZBEK_MONTHS = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr']
const CALENDAR_YEAR_SPAN = 10

function calendarYearOptions(centerYear = new Date().getFullYear()) {
  const years = []
  for (let year = centerYear - CALENDAR_YEAR_SPAN; year <= centerYear + CALENDAR_YEAR_SPAN; year += 1) {
    years.push(year)
  }
  return years
}

function parseIsoDate(value) {
  if (!value) return null
  const [y, m, d] = value.split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

function toIsoDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function buildMonthGrid(viewYear, viewMonth) {
  const startOffset = (new Date(viewYear, viewMonth, 1).getDay() + 6) % 7
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()
  const cells = []
  for (let i = 0; i < startOffset; i += 1) {
    const d = new Date(viewYear, viewMonth, i - startOffset + 1)
    cells.push({ date: d, inMonth: false, iso: toIsoDate(d) })
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    const d = new Date(viewYear, viewMonth, day)
    cells.push({ date: d, inMonth: true, iso: toIsoDate(d) })
  }
  while (cells.length % 7 !== 0) {
    const d = new Date(cells[cells.length - 1].date)
    d.setDate(d.getDate() + 1)
    cells.push({ date: d, inMonth: false, iso: toIsoDate(d) })
  }
  return cells
}

function FilterDateRangeCalendar({ dateFrom, dateTo, onChange }) {
  const [viewDate, setViewDate] = useState(() => parseIsoDate(dateFrom) || new Date())
  const [pickPhase, setPickPhase] = useState('start')
  const [anchor, setAnchor] = useState(null)
  const [yearDropdownOpen, setYearDropdownOpen] = useState(false)
  const yearDropdownRef = useRef(null)

  useEffect(() => {
    const parsed = parseIsoDate(dateFrom)
    if (parsed) setViewDate(parsed)
  }, [dateFrom])

  useEffect(() => {
    if (!yearDropdownOpen) return undefined
    const handleClickOutside = (event) => {
      if (yearDropdownRef.current && !yearDropdownRef.current.contains(event.target)) {
        setYearDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [yearDropdownOpen])

  const viewYear = viewDate.getFullYear()
  const viewMonth = viewDate.getMonth()
  const yearOptions = useMemo(() => calendarYearOptions(new Date().getFullYear()), [])
  const cells = useMemo(() => buildMonthGrid(viewYear, viewMonth), [viewYear, viewMonth])
  const todayIso = todayValue()

  const highlightFrom = dateFrom
  const highlightTo = dateTo
  const rangeLabel = dateFrom && dateTo
    ? (dateFrom === dateTo ? dateFrom : `${dateFrom} — ${dateTo}`)
    : 'Sanani tanlang'

  const handleDayClick = (iso) => {
    if (pickPhase === 'start') {
      setAnchor(iso)
      setPickPhase('end')
      onChange({ date_from: iso, date_to: iso })
      return
    }
    let from = anchor || dateFrom
    let to = iso
    if (from > to) [from, to] = [to, from]
    setPickPhase('start')
    setAnchor(null)
    onChange({ date_from: from, date_to: to })
  }

  return (
    <div className="filter-calendar filter-date-range-calendar" role="group" aria-label="Davr">
      <div className="filter-calendar-header">
        <span className="filter-calendar-label">Davr</span>
        <span className="filter-calendar-value">{rangeLabel}</span>
      </div>
      <div className="filter-calendar-widget">
        <div className="filter-calendar-nav">
          <button type="button" className="filter-calendar-nav-btn" onClick={() => setViewDate(new Date(viewYear, viewMonth - 1, 1))} aria-label="Oldingi oy">
            <CaretLeft size={16} />
          </button>
          <div className="filter-calendar-nav-title">
            <span className="filter-calendar-month-name">{UZBEK_MONTHS[viewMonth]}</span>
            <div className="filter-calendar-year-wrap" ref={yearDropdownRef}>
              <button
                type="button"
                className="filter-calendar-year-btn"
                onClick={() => setYearDropdownOpen((open) => !open)}
                aria-expanded={yearDropdownOpen}
                aria-haspopup="listbox"
                aria-label={`Yil: ${viewYear}`}
              >
                {viewYear}
                <CaretDown size={12} aria-hidden="true" />
              </button>
              {yearDropdownOpen && (
                <ul className="filter-calendar-year-dropdown" role="listbox" aria-label="Yilni tanlang">
                  {yearOptions.map((year) => (
                    <li key={year}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={year === viewYear}
                        className={year === viewYear ? 'is-active' : undefined}
                        onClick={() => {
                          setViewDate(new Date(year, viewMonth, 1))
                          setYearDropdownOpen(false)
                        }}
                      >
                        {year}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <button type="button" className="filter-calendar-nav-btn" onClick={() => setViewDate(new Date(viewYear, viewMonth + 1, 1))} aria-label="Keyingi oy">
            <CaretRight size={16} />
          </button>
        </div>
        <div className="filter-calendar-weekdays" aria-hidden="true">
          {CALENDAR_WEEKDAYS.map((day) => (
            <span key={day} className="filter-calendar-weekday">{day}</span>
          ))}
        </div>
        <div className="filter-calendar-days" role="grid">
          {cells.map((cell) => {
            const isStart = highlightFrom === cell.iso
            const isEnd = highlightTo === cell.iso
            const isInRange = highlightFrom && highlightTo
              && cell.iso > highlightFrom && cell.iso < highlightTo
            const isToday = cell.iso === todayIso
            return (
              <button
                key={cell.iso}
                type="button"
                role="gridcell"
                className={[
                  'filter-calendar-day',
                  !cell.inMonth && 'is-outside',
                  isInRange && 'is-in-range',
                  isStart && 'is-range-start',
                  isEnd && 'is-range-end',
                  (isStart || isEnd) && 'is-selected',
                  isToday && 'is-today',
                ].filter(Boolean).join(' ')}
                onClick={() => handleDayClick(cell.iso)}
                aria-label={cell.iso}
                aria-selected={isStart || isEnd}
              >
                {cell.date.getDate()}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function periodMetricNote(base, period) {
  if (period.date_from === todayValue() && period.date_to === todayValue()) return `${base} (bugun)`
  if (!period.date_from && !period.date_to) return `${base} (barcha davr)`
  return `${base} (${formatPeriodRange(period)})`
}

function buildDashboardFilterParams(filters) {
  const params = {}
  if (filters?.date_from) params.date_from = filters.date_from
  if (filters?.date_to) params.date_to = filters.date_to
  if (filters?.currency) params.currency = filters.currency
  if (filters?.category) params.category = filters.category
  if (filters?.client) params.client = filters.client
  if (filters?.supplier?.trim()) params.supplier = filters.supplier.trim()
  if (filters?.product) params.product = filters.product
  if (filters?.payment_status) params.payment_status = filters.payment_status
  return params
}

const DEFAULT_DASHBOARD_FILTERS = () => ({
  preset: 'custom',
  date_from: todayValue(),
  date_to: todayValue(),
  currency: '',
  category: '',
  client: '',
  supplier: '',
  product: '',
  payment_status: '',
})

const CURRENCY_FILTERS = [
  { id: '', label: 'Hammasi' },
  { id: 'UZS', label: 'UZS' },
  { id: 'USD', label: 'USD' },
]

const PAYMENT_STATUS_FILTERS = [
  { id: '', label: 'Hammasi' },
  { id: 'pending', label: 'Kutilmoqda' },
  { id: 'partial', label: 'Qisman' },
  { id: 'paid', label: 'To‘langan' },
  { id: 'overdue', label: 'Kechikkan' },
]

const TOAST_DURATION = { error: 16000, warning: 12000, success: 7000 }

function ToastStack({ toasts, dismiss, pauseToast, resumeToast }) {
  const icons = { error: XCircle, success: CheckCircle, warning: WarningCircle }
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => {
        const Icon = icons[toast.type] || WarningCircle
        return (
          <div
            key={toast.id}
            className={`toast toast-${toast.type}`}
            role="alert"
            onMouseEnter={() => pauseToast(toast.id)}
            onMouseLeave={() => resumeToast(toast.id)}
            onFocus={() => pauseToast(toast.id)}
            onBlur={() => resumeToast(toast.id)}
          >
            <span className="toast-icon"><Icon size={22} weight="fill" /></span>
            <div className="toast-body">
              <b>{toast.type === 'error' ? 'Xatolik' : toast.type === 'success' ? 'Muvaffaqiyatli' : 'Ogohlantirish'}</b>
              <span>{toast.message}</span>
            </div>
            <button type="button" className="toast-close" onClick={() => dismiss(toast.id)} aria-label="Yopish">
              <X size={18} />
            </button>
            <span
              className="toast-progress"
              style={{ animationDuration: `${toast.durationMs}ms`, animationPlayState: toast.paused ? 'paused' : 'running' }}
              aria-hidden="true"
            />
          </div>
        )
      })}
    </div>
  )
}

function useNotify() {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())
  const recent = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) { clearTimeout(timer); timers.current.delete(id) }
  }, [])

  const scheduleDismiss = useCallback((id, delayMs) => {
    const timer = setTimeout(() => dismiss(id), delayMs)
    timers.current.set(id, timer)
    return timer
  }, [dismiss])

  const pauseToast = useCallback((id) => {
    const timer = timers.current.get(id)
    if (!timer) return
    clearTimeout(timer)
    timers.current.delete(id)
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, paused: true } : t)))
  }, [])

  const resumeToast = useCallback((id) => {
    setToasts((prev) => {
      const toast = prev.find((t) => t.id === id)
      if (!toast?.paused) return prev
      scheduleDismiss(id, 6000)
      return prev.map((t) => (t.id === id ? { ...t, paused: false } : t))
    })
  }, [scheduleDismiss])

  const notify = useCallback((message, type = 'error') => {
    const formatted = formatError(message)
    const key = `${type}:${formatted}`
    const now = Date.now()
    const lastSeen = recent.current.get(key) || 0
    if (now - lastSeen < 1500) return
    recent.current.set(key, now)
    const id = Date.now() + Math.random()
    const durationMs = TOAST_DURATION[type] || TOAST_DURATION.error
    setToasts((prev) => [...prev, { id, message: formatted, type, durationMs, paused: false }])
    scheduleDismiss(id, durationMs)
  }, [scheduleDismiss])

  return { toasts, notify, dismiss, pauseToast, resumeToast }
}

function formatRelativeTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const diffMs = Date.now() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Hozir'
  if (diffMin < 60) return `${diffMin} daqiqa oldin`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} soat oldin`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay} kun oldin`
  return date.toLocaleDateString('uz-UZ')
}

function NotificationDropdown({ onViewAll, notify, onRequestPermission, browserPermission }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const ref = useRef(null)
  useClickOutside(ref, () => setOpen(false), open)

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      setItems(list(await api.notifications({ page_size: 12 })))
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [notify])

  useEffect(() => {
    load(true)
    const timer = setInterval(() => load(true), AUTO_REFRESH_MS)
    return () => clearInterval(timer)
  }, [load])

  useEffect(() => {
    if (open) load()
  }, [open, load])

  const unreadCount = items.filter((item) => !item.is_read).length

  const toggle = () => {
    setOpen((value) => !value)
    if (browserPermission !== 'granted') onRequestPermission()
  }

  const markRead = async (id) => {
    try {
      await api.notificationsMarkRead(id)
      await load(true)
    } catch (err) {
      notify(err.message)
    }
  }

  const markAllRead = async () => {
    try {
      await api.notificationsMarkAllRead()
      await load(true)
      notify('Hammasi o‘qilgan deb belgilandi.', 'success')
    } catch (err) {
      notify(err.message)
    }
  }

  return (
    <div className="dropdown notification-dropdown" ref={ref}>
      <button
        type="button"
        className="icon-button notification"
        aria-label="Bildirishnomalar"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={toggle}
      >
        <Bell size={20} />
        {unreadCount > 0 && <i aria-hidden="true" />}
      </button>
      {open && (
        <div className="dropdown-menu notification-menu" role="menu">
          <div className="notification-menu-head">
            <div>
              <b>Bildirishnomalar</b>
              {unreadCount > 0 && <small>{unreadCount} ta yangi</small>}
            </div>
            {unreadCount > 0 && (
              <button type="button" className="text-button" onClick={markAllRead}>Hammasini o‘qilgan</button>
            )}
          </div>
          <div className="notification-menu-body">
            {loading && !items.length ? (
              <div className="notification-empty"><SpinnerGap size={22} className="spin" />Yuklanmoqda…</div>
            ) : items.length ? items.map((item) => (
              <button
                type="button"
                key={item.id}
                className={item.is_read ? 'notification-item is-read' : 'notification-item'}
                onClick={() => { if (!item.is_read) markRead(item.id) }}
              >
                <span className="notification-item-icon"><Bell size={16} weight={item.is_read ? 'regular' : 'fill'} /></span>
                <span className="notification-item-body">
                  <b>{item.title}</b>
                  <span>{item.message}</span>
                  <small>{formatRelativeTime(item.created_at)}</small>
                </span>
                {!item.is_read && <span className="notification-dot" aria-hidden="true" />}
              </button>
            )) : (
              <div className="notification-empty">Bildirishnoma yo‘q</div>
            )}
          </div>
          <div className="notification-menu-foot">
            <button type="button" className="secondary-button" onClick={() => { onViewAll(); setOpen(false) }}>
              Barchasini ko‘rish
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function ProfileDropdown({ session, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useClickOutside(ref, () => setOpen(false), open)

  return (
    <div className="dropdown profile-dropdown" ref={ref}>
      <button type="button" className="profile dropdown-trigger" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="menu">
        <span>{session.username.slice(0, 1).toUpperCase()}</span>
        <div><b>{session.username}</b><small>{session.role}</small></div>
        <CaretDown size={15} className={open ? 'caret-open' : ''} />
      </button>
      {open && (
        <ul className="dropdown-menu profile-menu" role="menu">
          <li className="dropdown-meta">
            <b>{session.username}</b>
            <small>{session.role}</small>
          </li>
          <li><button type="button" role="menuitem" onClick={() => { onLogout(); setOpen(false) }}><SignOut size={17} />Chiqish</button></li>
        </ul>
      )}
    </div>
  )
}

function can(session, ability) {
  if (!ability) return true
  if (session?.is_superuser) return true
  return Boolean(session?.abilities?.[ability])
}

function allowedNavigation(session) {
  return navigation.filter(([, , ability]) => can(session, ability))
}

function App() {
  const [session, setSession] = useState(() => JSON.parse(localStorage.getItem('warehouse_user') || 'null'))
  const [active, setActive] = useState('Bosh sahifa')
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(false)
  const [fxRate, setFxRate] = useState(null)
  const [fxDraft, setFxDraft] = useState('')
  const [fxSaving, setFxSaving] = useState(false)
  const [notificationPermission, setNotificationPermission] = useState(() => (typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'default'))
  const [orderModalOpen, setOrderModalOpen] = useState(false)
  const [resourceReloadKey, setResourceReloadKey] = useState(0)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('warehouse_sidebar_collapsed') === '1')
  const [dashboardFilters, setDashboardFilters] = useState(() => DEFAULT_DASHBOARD_FILTERS())
  const { toasts, notify, dismiss, pauseToast, resumeToast } = useNotify()
  const seenNotifications = useRef(new Set())
  const navItems = allowedNavigation(session)
  const primaryMobileNav = navItems.slice(0, 4)
  const secondaryMobileNav = navItems.slice(4)
  const navigate = (label) => {
    setActive(label)
    setMobileMenuOpen(false)
  }
  const toggleSidebar = () => {
    setSidebarCollapsed((value) => {
      localStorage.setItem('warehouse_sidebar_collapsed', value ? '0' : '1')
      return !value
    })
  }

  useEffect(() => {
    setAuthFailureHandler(() => setSession(null))
    return () => setAuthFailureHandler(null)
  }, [])
  useTokenRefresh(Boolean(session))

  const loadDashboard = useCallback(async (silent = false, filters = dashboardFilters) => {
    if (!silent) setLoading(true)
    try {
      const params = buildDashboardFilterParams(filters)
      const [[summary, warehouse, cash, topProducts], monthly] = await Promise.all([
        api.reports(params),
        api.monthlyTrend(6, params),
      ])
      setDashboard({ summary, warehouse, cash, topProducts, monthly })
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [notify, dashboardFilters])

  const changeDashboardFilters = useCallback((nextFilters) => {
    setDashboardFilters((current) => ({ ...current, ...nextFilters }))
  }, [])

  useEffect(() => {
    if (session && can(session, 'dashboard')) loadDashboard()
  }, [session, loadDashboard, dashboardFilters])
  useAutoRefresh(() => { if (session && can(session, 'dashboard') && active === 'Bosh sahifa') loadDashboard(true) }, Boolean(session))

  useEffect(() => {
    if (!session) return undefined
    let cancelled = false
    api.me()
      .then((user) => {
        if (!cancelled) {
          saveSession({ user })
          setSession(user)
        }
      })
      .catch((err) => {
        if (!cancelled && err.status !== 401) notify(err.message)
      })
    return () => { cancelled = true }
  }, [session?.id, notify])

  useEffect(() => {
    if (!session || navItems.some(([label]) => label === active)) return
    setActive(navItems[0]?.[0] || 'Bosh sahifa')
  }, [active, navItems, session])

  useEffect(() => {
    if (!session) return undefined
    let cancelled = false
    const syncNotifications = async () => {
      if (typeof window === 'undefined' || !('Notification' in window) || Notification.permission !== 'granted') return
      try {
        const payload = list(await api.notifications())
        const unread = payload.filter((item) => !item.is_read && !seenNotifications.current.has(item.id))
        if (!cancelled && unread.length) {
          unread.forEach((item) => {
            new Notification(item.title, { body: item.message, icon: '/vite.svg' })
            seenNotifications.current.add(item.id)
          })
        }
      } catch (err) {
        if (!cancelled) console.error(err)
      }
    }
    syncNotifications()
    const timer = setInterval(syncNotifications, 30000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [session])

  useEffect(() => {
    if (!session) return undefined
    let cancelled = false
    const loadRate = async () => {
      try {
        const rate = await api.exchangeRateLatest()
        if (!cancelled) {
          setFxRate(rate)
          setFxDraft(rate?.mb_rate ?? '')
        }
      } catch (err) {
        if (!cancelled) notify(err.message)
      }
    }
    loadRate()
    return () => { cancelled = true }
  }, [session, notify])

  const requestNotifications = useCallback(async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      notify('Brauzer bildirishnomalarini qo‘llab-quvvatlamaydi.', 'warning')
      return
    }
    if (Notification.permission === 'granted') {
      setNotificationPermission('granted')
      notify('Bildirishnomalar allaqachon yoqilgan.', 'success')
      return
    }
    const result = await Notification.requestPermission()
    setNotificationPermission(result)
    if (result === 'granted') {
      notify('Bildirishnomalar ruxsat berildi.', 'success')
    } else {
      notify('Bildirishnomalar uchun ruxsat berilmadi.', 'warning')
    }
  }, [notify])

  const saveFxRate = async (event) => {
    event.preventDefault()
    if (!fxDraft) return
    setFxSaving(true)
    try {
      const rate = await api.create('/cash/exchange-rates/', {
        currency: 'USD',
        mb_rate: fxDraft,
        buy_rate: fxDraft,
        sell_rate: fxDraft,
        manual_override: true,
        note: 'Qo‘lda kiritilgan kurs',
      })
      setFxRate(rate)
      notify('Kurs saqlandi.', 'success')
    } catch (err) {
      notify(err.message)
    } finally {
      setFxSaving(false)
    }
  }

  const logout = () => {
    clearStoredSession()
    setSession(null)
  }

  const openOrderEditor = () => {
    if (!can(session, 'orders_manage')) return notify('Bu amalni bajarish uchun ruxsatingiz yo‘q.')
    setActive('Buyurtmalar')
    setOrderModalOpen(true)
  }

  if (!session) return <Login onSuccess={setSession} />
  return (
    <main className={sidebarCollapsed ? 'app-shell sidebar-collapsed' : 'app-shell'}>
      <ToastStack toasts={toasts} dismiss={dismiss} pauseToast={pauseToast} resumeToast={resumeToast} />
      <aside className={sidebarCollapsed ? 'sidebar is-collapsed' : 'sidebar'}>
        <div className="brand">
          <span className="brand-mark"><Warehouse size={22} weight="fill" /></span>
          <span>smart.<b>ombor</b></span>
          <button className="sidebar-toggle" type="button" onClick={toggleSidebar} aria-label={sidebarCollapsed ? 'Sidebar ochish' : 'Sidebar yopish'}>
            {sidebarCollapsed ? <CaretRight size={17} /> : <CaretLeft size={17} />}
          </button>
        </div>
        <div className="workspace">
          <span>ISH MAYDONI</span>
          <b className="workspace-name">{workspace}</b>
        </div>
        <nav>{navItems.map(([label, Icon]) => (
          <button key={label} onClick={() => navigate(label)} className={active === label ? 'nav-item is-active' : 'nav-item'} title={label}>
            <span className="nav-icon"><Icon size={20} weight={active === label ? 'fill' : 'regular'} /></span>
            <span className="nav-label">{label}</span>
          </button>
        ))}</nav>
        <div className="sidebar-bottom"><button className="nav-item" onClick={logout} title="Chiqish"><span className="nav-icon"><SignOut size={20} /></span><span className="nav-label">Chiqish</span></button></div>
      </aside>
      <section className="content">
        <header className="topbar">
          <div className="crumb"><span>Smart ombor</span><span>/</span><b>{active}</b></div>
          <div className="top-actions">
            <form className="fx-card" onSubmit={saveFxRate}>
              <span>USD MB kurs</span>
              <div>
                <input type="number" min="0" step="0.01" value={fxDraft} onChange={(event) => setFxDraft(event.target.value)} />
                <button type="submit" disabled={fxSaving}>{fxSaving ? '…' : 'Saqlash'}</button>
              </div>
            </form>
            <button className="icon-button" aria-label="Qidiruv" title="Buyurtmalarni qidirish" onClick={() => navigate('Buyurtmalar')}><MagnifyingGlass size={20} /></button>
            <NotificationDropdown
              browserPermission={notificationPermission}
              onRequestPermission={requestNotifications}
              onViewAll={() => { if (can(session, 'notifications_view')) navigate('Bildirishnomalar') }}
              notify={notify}
            />
            <ProfileDropdown session={session} onLogout={logout} />
          </div>
        </header>
        {active === 'Bosh sahifa' && can(session, 'dashboard') && (
          <Dashboard
            data={dashboard}
            loading={loading && !dashboard}
            period={dashboardFilters}
            onPeriodChange={changeDashboardFilters}
            onCreateOrder={openOrderEditor}
            onNavigate={navigate}
            session={session}
          />
        )}
        {active === 'Hisobotlar' && <ReportsPage notify={notify} />}
        {active !== 'Bosh sahifa' && active !== 'Hisobotlar' && <ResourcePage title={active} notify={notify} reloadKey={resourceReloadKey} session={session} onDataChange={() => loadDashboard(true)} onNavigate={navigate} />}
        {orderModalOpen && (
          <OrderEditor
            close={() => setOrderModalOpen(false)}
            done={() => {
              setOrderModalOpen(false)
              setResourceReloadKey((value) => value + 1)
              loadDashboard(true)
            }}
            notify={notify}
            session={session}
          />
        )}
      </section>
      {mobileMenuOpen && secondaryMobileNav.length > 0 && (
        <div className="mobile-menu-panel" role="dialog" aria-label="Barcha bo‘limlar">
          {secondaryMobileNav.map(([label, Icon]) => (
            <button key={label} onClick={() => navigate(label)} className={active === label ? 'mobile-menu-item is-active' : 'mobile-menu-item'}>
              <Icon size={20} weight={active === label ? 'fill' : 'regular'} />{label}
            </button>
          ))}
          <button className="mobile-menu-item danger" onClick={logout}><SignOut size={20} />Chiqish</button>
        </div>
      )}
      <nav className="bottom-nav" aria-label="Mobil menyu">
        {primaryMobileNav.map(([label, Icon]) => (
          <button key={label} onClick={() => navigate(label)} className={active === label ? 'bottom-nav-item is-active' : 'bottom-nav-item'} title={label}>
            <Icon size={22} weight={active === label ? 'fill' : 'regular'} />
            <span>{label}</span>
          </button>
        ))}
        {secondaryMobileNav.length > 0 && (
          <button onClick={() => setMobileMenuOpen((value) => !value)} className={mobileMenuOpen ? 'bottom-nav-item is-active' : 'bottom-nav-item'} aria-label="Ko‘proq bo‘limlar" title="Ko‘proq">
            <DotsThree size={22} weight="bold" />
            <span>Ko‘proq</span>
          </button>
        )}
      </nav>
    </main>
  )
}

function Login({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { toasts, notify, dismiss, pauseToast, resumeToast } = useNotify()

  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    try {
      const data = await api.login(username, password)
      saveSession(data)
      onSuccess(data.user)
    } catch (err) {
      notify(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <ToastStack toasts={toasts} dismiss={dismiss} pauseToast={pauseToast} resumeToast={resumeToast} />
      <section className="login-aside">
        <div className="brand"><span className="brand-mark"><Warehouse size={22} weight="fill" /></span><span>smart.<b>ombor</b></span></div>
        <div className="login-copy">
          <p className="eyebrow">BIR TIZIM, TO‘LIQ NAZORAT</p>
          <h1>Ombor, hujjat va hisoblar bir joyda.</h1>
          <p>Har bir buyurtma, qoldiq va to‘lovning holatini real vaqtda kuzating.</p>
        </div>
        <div className="aside-footer"><span className="live-dot" />Tizim ishlayapti</div>
      </section>
      <section className="login-form-wrap">
        <form className="login-form" onSubmit={submit}>
          <p className="eyebrow">XUSH KELIBSIZ</p>
          <h2>Hisobingizga kiring</h2>
          <p className="muted">Davom etish uchun login ma’lumotlaringizni kiriting.</p>
          <label>Login<input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required /></label>
          <label>Parol<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /></label>
          <button className="primary-button" disabled={loading}>{loading ? <SpinnerGap size={19} className="spin" /> : 'Tizimga kirish'}</button>
          <p className="form-footnote">Kirish huquqi administrator tomonidan beriladi.</p>
        </form>
      </section>
    </main>
  )
}

function importPeriodLabel(summary) {
  const uzs = Number(summary.import_paid_uzs || summary.import_paid_today_uzs || 0)
  const usd = Number(summary.import_paid_usd || summary.import_paid_today_usd || 0)
  if (uzs > 0) return `${money(uzs)} so‘m`
  if (usd > 0) return `$${money(usd)}`
  return '0 so‘m'
}

function importPeriodNote(summary) {
  const usd = Number(summary.import_paid_usd || summary.import_paid_today_usd || 0)
  const rate = Number(summary.mb_rate_today || 0)
  if (usd > 0 && rate > 0) return `$${money(usd)} · MB kurs ${money(rate)}`
  return 'Yetkazuvchi to‘lovi (MB kursida)'
}

function filterContextNote(filters, lookup = {}) {
  const extras = []
  if (filters.category) {
    const cat = lookup.categories?.find((item) => String(item.id) === String(filters.category))
    if (cat?.name) extras.push(cat.name)
  }
  if (filters.client) {
    const client = lookup.clients?.find((item) => String(item.id) === String(filters.client))
    if (client?.full_name || client?.company_name) extras.push(client.full_name || client.company_name)
  }
  if (filters.supplier?.trim()) extras.push(filters.supplier.trim())
  if (filters.product) {
    const product = lookup.products?.find((item) => String(item.id) === String(filters.product))
    if (product?.name) extras.push(product.name)
  }
  if (filters.payment_status) {
    const payment = PAYMENT_STATUS_FILTERS.find((item) => item.id === filters.payment_status)
    if (payment?.label) extras.push(payment.label)
  }
  return extras.length ? ` · ${extras.join(', ')}` : ''
}

function isDefaultDashboardPeriod(filters) {
  return filters.date_from === todayValue() && filters.date_to === todayValue()
}

function buildDashboardFilterChips(filters, lookup = {}) {
  const chips = []
  if (!isDefaultDashboardPeriod(filters)) {
    chips.push({
      key: 'period',
      label: formatPeriodRange(filters),
      patch: { preset: 'custom', date_from: todayValue(), date_to: todayValue() },
    })
  }
  if (filters.currency) {
    const currency = CURRENCY_FILTERS.find((item) => item.id === filters.currency)
    chips.push({ key: 'currency', label: currency?.label || filters.currency, patch: { currency: '' } })
  }
  if (filters.category) {
    const cat = lookup.categories?.find((item) => String(item.id) === String(filters.category))
    chips.push({ key: 'category', label: cat?.name || 'Kategoriya', patch: { category: '' } })
  }
  if (filters.client) {
    const client = lookup.clients?.find((item) => String(item.id) === String(filters.client))
    chips.push({
      key: 'client',
      label: client?.full_name || client?.company_name || 'Mijoz',
      patch: { client: '' },
    })
  }
  if (filters.product) {
    const product = lookup.products?.find((item) => String(item.id) === String(filters.product))
    chips.push({ key: 'product', label: product?.name || 'Mahsulot', patch: { product: '' } })
  }
  if (filters.supplier?.trim()) {
    chips.push({ key: 'supplier', label: `Yetkazuvchi: ${filters.supplier.trim()}`, patch: { supplier: '' } })
  }
  if (filters.payment_status) {
    const payment = PAYMENT_STATUS_FILTERS.find((item) => item.id === filters.payment_status)
    chips.push({ key: 'payment_status', label: payment?.label || filters.payment_status, patch: { payment_status: '' } })
  }
  return chips
}

function FilterSearchSelect({
  id,
  label,
  value,
  onChange,
  options,
  loading,
  getLabel,
  getValue = (item) => item.id,
  emptyLabel = 'Hammasi',
}) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return options
    return options.filter((item) => getLabel(item).toLowerCase().includes(needle))
  }, [options, query, getLabel])

  useEffect(() => {
    if (!value) setQuery('')
  }, [value])

  return (
    <div className="filter-field">
      <label className="filter-field-label" htmlFor={id}>{label}</label>
      {options.length > 8 && (
        <div className="filter-search-wrap">
          <MagnifyingGlass size={16} aria-hidden="true" />
          <input
            type="search"
            className="filter-search-input"
            placeholder="Qidirish..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label={`${label} bo‘yicha qidirish`}
          />
        </div>
      )}
      <select
        id={id}
        className="filter-select"
        value={value || ''}
        disabled={loading}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{emptyLabel}</option>
        {filtered.map((item) => (
          <option key={getValue(item)} value={getValue(item)}>{getLabel(item)}</option>
        ))}
      </select>
    </div>
  )
}

function DashboardFiltersMenu({ filters, onChange }) {
  const [open, setOpen] = useState(false)
  const [customFrom, setCustomFrom] = useState(filters.date_from || todayValue())
  const [customTo, setCustomTo] = useState(filters.date_to || todayValue())
  const [supplierDraft, setSupplierDraft] = useState(filters.supplier || '')
  const [options, setOptions] = useState({ categories: [], clients: [], products: [], loading: false })
  const ref = useRef(null)
  const menuRef = useRef(null)
  const optionsLoaded = useRef(false)
  const closeMenu = useCallback(() => setOpen(false), [])
  useClickOutside(ref, closeMenu, open)

  const loadOptions = useCallback(() => {
    if (optionsLoaded.current) return
    optionsLoaded.current = true
    setOptions((prev) => ({ ...prev, loading: true }))
    Promise.all([
      api.categories({ page_size: 100 }),
      api.clients({ page_size: 100 }),
      api.products({ page_size: 200 }),
    ]).then(([categories, clients, products]) => {
      setOptions({
        categories: list(categories),
        clients: list(clients),
        products: list(products),
        loading: false,
      })
    }).catch(() => {
      optionsLoaded.current = false
      setOptions((prev) => ({ ...prev, loading: false }))
    })
  }, [])

  useEffect(() => { loadOptions() }, [loadOptions])

  useEffect(() => {
    setCustomFrom(filters.date_from || todayValue())
    setCustomTo(filters.date_to || todayValue())
    setSupplierDraft(filters.supplier || '')
  }, [filters.date_from, filters.date_to, filters.supplier])

  useEffect(() => {
    if (!open) return undefined
    loadOptions()
    return undefined
  }, [open, loadOptions])

  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeMenu()
      }
      if (event.key === 'Tab' && menuRef.current) {
        const focusables = menuRef.current.querySelectorAll(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )
        if (!focusables.length) return
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, closeMenu])

  useEffect(() => {
    if (!open || !menuRef.current) return undefined
    const timer = window.setTimeout(() => {
      const first = menuRef.current?.querySelector('button, input, select')
      first?.focus()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [open])

  const applyDateRange = useCallback((from, to) => {
    let date_from = from
    let date_to = to
    if (date_from && date_to && date_from > date_to) {
      [date_from, date_to] = [date_to, date_from]
    }
    onChange({ preset: 'custom', date_from, date_to })
  }, [onChange])

  const handleRangeChange = useCallback(({ date_from, date_to }) => {
    setCustomFrom(date_from)
    setCustomTo(date_to)
    applyDateRange(date_from, date_to)
  }, [applyDateRange])

  const applyCurrency = (currency) => onChange({ currency })

  const applyPaymentStatus = (payment_status) => onChange({ payment_status })

  const applySupplier = (event) => {
    event.preventDefault()
    onChange({ supplier: supplierDraft.trim() })
  }

  const clearSupplierDraft = () => {
    setSupplierDraft('')
    onChange({ supplier: '' })
  }

  const resetFilters = () => {
    onChange(DEFAULT_DASHBOARD_FILTERS())
    closeMenu()
  }

  const removeChip = (patch) => {
    onChange(patch)
    if (patch.supplier === '') setSupplierDraft('')
    if (patch.date_from === todayValue() && patch.date_to === todayValue()) {
      setCustomFrom(todayValue())
      setCustomTo(todayValue())
    }
  }

  const chips = buildDashboardFilterChips(filters, options)
  const extraChipCount = chips.filter((chip) => chip.key !== 'period').length
  const triggerPeriodLabel = formatPeriodRange(filters)

  return (
    <div className="period-filter-wrap">
      <div className="period-filter dropdown" ref={ref}>
        <button
          type="button"
          className="secondary-button period-filter-trigger"
          aria-expanded={open}
          aria-haspopup="dialog"
          aria-controls="dashboard-filters-menu"
          onClick={() => setOpen((value) => !value)}
        >
          <Funnel size={18} />
          Filtrlar
          <span className="period-filter-current">{triggerPeriodLabel}</span>
          {extraChipCount > 0 && (
            <span className="filter-count-badge" aria-label={`${extraChipCount} ta qo‘shimcha filtr`}>
              +{extraChipCount}
            </span>
          )}
        </button>
        {open && (
          <div
            id="dashboard-filters-menu"
            ref={menuRef}
            className="period-filter-menu"
            role="dialog"
            aria-modal="true"
            aria-label="Filtrlar"
          >
            <div className="period-filter-head">
              <div className="period-filter-head-row">
                <div className="period-filter-head-copy">
                  <b className="period-filter-head-label">Filtrlar</b>
                  <p className="period-filter-head-note">O‘zgarishlar darhol qo‘llanadi</p>
                </div>
                <button
                  type="button"
                  className="icon-button period-filter-close"
                  onClick={closeMenu}
                  aria-label="Filtrlarni yopish"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            <div className="period-filter-body">
              <div className="filter-panel">
                <div className="filter-panel-dates" aria-labelledby="filter-davr">
                  <span className="visually-hidden" id="filter-davr">Davr</span>
                  <FilterDateRangeCalendar
                    dateFrom={customFrom}
                    dateTo={customTo}
                    onChange={handleRangeChange}
                  />
                </div>

                <div className="filter-panel-meta">
                  <div className="filter-panel-meta-block">
                    <span className="filter-section-title" id="filter-currency">Valyuta</span>
                    <div className="period-tabs period-tabs--compact" role="tablist" aria-labelledby="filter-currency">
                      {CURRENCY_FILTERS.map((item) => (
                        <button
                          key={item.id || 'all'}
                          type="button"
                          role="tab"
                          aria-selected={filters.currency === item.id}
                          className={filters.currency === item.id ? 'period-tab is-active' : 'period-tab'}
                          onClick={() => applyCurrency(item.id)}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="filter-panel-meta-block">
                    <span className="filter-section-title" id="filter-payment">To‘lov holati</span>
                    <div className="period-tabs period-tabs--compact" role="tablist" aria-labelledby="filter-payment">
                      {PAYMENT_STATUS_FILTERS.map((item) => (
                        <button
                          key={item.id || 'all'}
                          type="button"
                          role="tab"
                          aria-selected={filters.payment_status === item.id}
                          className={filters.payment_status === item.id ? 'period-tab is-active' : 'period-tab'}
                          onClick={() => applyPaymentStatus(item.id)}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="filter-panel-fields">
                  <FilterSearchSelect
                    id="filter-category"
                    label="Kategoriya"
                    value={filters.category}
                    loading={options.loading}
                    options={options.categories}
                    getLabel={(item) => item.name}
                    onChange={(category) => onChange({ category })}
                  />
                  <FilterSearchSelect
                    id="filter-client"
                    label="Mijoz"
                    value={filters.client}
                    loading={options.loading}
                    options={options.clients}
                    getLabel={(item) => item.full_name || item.company_name || `#${item.id}`}
                    onChange={(client) => onChange({ client })}
                  />
                  <FilterSearchSelect
                    id="filter-product"
                    label="Mahsulot"
                    value={filters.product}
                    loading={options.loading}
                    options={options.products}
                    getLabel={(item) => `${item.name}${item.serial_number ? ` (${item.serial_number})` : ''}`}
                    onChange={(product) => onChange({ product })}
                  />
                  <div className="filter-field">
                    <span className="filter-field-label" id="filter-supplier">Yetkazuvchi</span>
                    <form className="filter-supplier-form" onSubmit={applySupplier}>
                      <input
                        type="text"
                        className="filter-text-input"
                        placeholder="Yetkazuvchi nomi"
                        value={supplierDraft}
                        aria-labelledby="filter-supplier"
                        onChange={(event) => setSupplierDraft(event.target.value)}
                      />
                      <button type="submit" className="secondary-button">Qo‘llash</button>
                    </form>
                    {filters.supplier?.trim() && (
                      <button type="button" className="text-button filter-clear-inline" onClick={clearSupplierDraft}>
                        Tozalash
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="period-filter-footer">
              {chips.length > 0 ? (
                <div className="filter-chips" aria-label="Faol filtrlar">
                  {chips.map((chip) => (
                    <button
                      key={chip.key}
                      type="button"
                      className="filter-chip"
                      onClick={() => removeChip(chip.patch)}
                      aria-label={`${chip.label} filtrini olib tashlash`}
                    >
                      <span>{chip.label}</span>
                      <X size={14} weight="bold" />
                    </button>
                  ))}
                </div>
              ) : (
                <span className="period-filter-footer-note">Qo‘shimcha filtr tanlanmagan</span>
              )}
              <div className="period-filter-footer-actions">
                {chips.length > 0 && (
                  <button type="button" className="text-button filter-reset" onClick={resetFilters}>
                    Barchasini tozalash
                  </button>
                )}
                <button type="button" className="primary-button period-filter-done" onClick={closeMenu}>
                  Tayyor
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
      {!open && chips.length > 0 && (
        <div className="filter-chips filter-chips--bar" aria-label="Faol filtrlar">
          {chips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              className="filter-chip"
              onClick={() => removeChip(chip.patch)}
              aria-label={`${chip.label} filtrini olib tashlash`}
            >
              <span>{chip.label}</span>
              <X size={14} weight="bold" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function Dashboard({ data, loading, period, onPeriodChange, onCreateOrder, onNavigate, session }) {
  const summary = data?.summary || {}
  const warehouse = data?.warehouse || {}
  const products = data?.topProducts || []
  const monthly = data?.monthly || []
  const filterSuffix = filterContextNote(period)

  const kassaValue = period.currency === 'USD'
    ? `$${money(summary.kassa_collected_usd || 0)}`
    : `${money(summary.kassa_collected_uzs || summary.kassa_collected_today_uzs || 0)} so‘m`
  const salesValue = money(summary.sales_revenue_uzs || summary.sales_revenue_total || 0)
  const kassaNote = (period.currency === 'USD'
    ? periodMetricNote('Mijoz to‘lovlari (USD)', period)
    : periodMetricNote('Mijoz to‘lovlari', period)) + filterSuffix
  const salesNote = periodMetricNote('Faqat sotuvlar (import emas)', period) + filterSuffix
  const importNote = importPeriodNote(summary) + filterSuffix
  const overdueNote = (period.payment_status ? 'Filtrlangan to‘lovlar' : 'Hozirgi holat') + filterSuffix

  return (
    <div className="page">
      <div className="page-heading page-heading-compact">
        <div className="heading-actions">
          <DashboardFiltersMenu filters={period} onChange={onPeriodChange} />
          {can(session, 'orders_manage') && <button className="primary-button" onClick={onCreateOrder}><Plus size={20} />Yangi buyurtma</button>}
        </div>
      </div>

      <section className="metric-grid">
        <Metric icon={CurrencyCircleDollar} label="Tushum" value={kassaValue} note={kassaNote} trend="up" />
        <Metric icon={Truck} label="Import" value={importPeriodLabel(summary)} note={importNote} trend="neutral" />
        <Metric icon={ClipboardText} label="Savdo" value={`${salesValue} so‘m`} note={salesNote} trend="up" />
        <Metric icon={Package} label="Ombordagi birliklar" value={money(warehouse.total_quantity)} note={`${warehouse.total_product_types || 0} turdagi mahsulot · hozirgi holat`} trend="neutral" />
        <Metric icon={FileText} label="Kechikkan to‘lovlar" value={summary.overdue_payments_count || 0} note={overdueNote} trend="down" />
      </section>
      <section className="dashboard-grid dashboard-grid-single">
        <div className="data-panel products-panel">
          <div className="panel-head">
            <div><p className="eyebrow">SOTUVLAR TAHLILI</p><h3>Eng faol mahsulotlar</h3></div>
            {can(session, 'sales_view') && <button className="text-button" onClick={() => onNavigate('Sotuvlar')}>Barchasi <span>→</span></button>}
          </div>
          <div className="product-list">
            {loading ? <SkeletonRows /> : products.length ? products.slice(0, 5).map((product, i) => (
              <div className="product-row" key={product.product || i}>
                <span className="rank">0{i + 1}</span>
                <div className="product-name"><b>{product.name}</b><small>{product.serial_number || 'Kodsiz mahsulot'}</small></div>
                <div className="bar"><i style={{ width: `${Math.min(100, Math.max(12, Number(product.sold_qty || 0) * 8))}%` }} /></div>
                <b>{product.sold_qty} dona</b>
              </div>
            )) : <Empty label="Sotuv ma’lumotlari hali yo‘q" />}
          </div>
        </div>
      </section>
      <section className="data-panel monthly-panel">
        <div className="panel-head">
          <div><p className="eyebrow">OYMA-OY</p><h3>Oylik moliyaviy ko‘rinish</h3></div>
        </div>
        {loading && !monthly.length ? <SkeletonRows /> : monthly.length ? (
          <table className="report-table monthly-table">
            <thead>
              <tr>
                <th>Oy</th>
                <th>Tushum</th>
                <th>Import</th>
                <th>Savdo</th>
              </tr>
            </thead>
            <tbody>
              {monthly.map((row) => (
                <tr key={`${row.year}-${row.month}`}>
                  <td><b>{row.label}</b></td>
                  <td>{money(row.kassa_uzs)} so‘m</td>
                  <td>
                    {Number(row.import_uzs) > 0
                      ? `${money(row.import_uzs)} so‘m`
                      : Number(row.import_usd) > 0
                        ? `$${money(row.import_usd)}`
                        : '—'}
                  </td>
                  <td>{money(row.sales_uzs)} so‘m</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty label="Oylik ma’lumotlar hali yo‘q" />}
      </section>
      <section className="lower-grid lower-grid-single">
        <div className="data-panel stock-panel">
          <div className="panel-head">
            <div><p className="eyebrow">OMBOR HOLATI</p><h3>Diqqat talab qiluvchi qoldiqlar</h3></div>
            {can(session, 'warehouse_view') && <button className="icon-button" aria-label="Omborga o‘tish" onClick={() => onNavigate('Ombor')}><Funnel size={19} /></button>}
          </div>
          {loading ? <SkeletonRows /> : list(warehouse.low_stock).length ? list(warehouse.low_stock).slice(0, 4).map((item) => (
            <div className="stock-row" key={item.product__id}>
              <span className="stock-icon"><Package size={18} /></span>
              <div><b>{item.product__name}</b><small>{item.product__serial_number}</small></div>
              <span className="warning-tag">{item.quantity} / min {item.product__min_quantity}</span>
            </div>
          )) : <Empty label="Kritik qoldiq aniqlanmadi" />}
        </div>
      </section>
    </div>
  )
}

function ReportsPage({ notify }) {
  const [tab, setTab] = useState('moliyaviy')
  const [data, setData] = useState(null)
  const [extra, setExtra] = useState(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState('')

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const [[summary, warehouse, cash, topProducts], expensesSummary, paymentsSummary] = await Promise.all([
        api.reports(),
        api.expensesSummary(),
        api.paymentsSummary(),
      ])
      setData({ summary, warehouse, cash, topProducts })
      setExtra({ expensesSummary, paymentsSummary })
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [notify])

  useEffect(() => { load() }, [load])
  useAutoRefresh(() => load(true))

  const summary = data?.summary || {}
  const warehouse = data?.warehouse || {}
  const cash = data?.cash || {}
  const products = data?.topProducts || []
  const expensesSummary = extra?.expensesSummary || {}
  const paymentsSummary = extra?.paymentsSummary || {}

  const tabs = [
    ['moliyaviy', 'Moliyaviy', CurrencyCircleDollar],
    ['ombor', 'Ombor', Package],
    ['sotuv', 'Sotuvlar', TrendUp],
    ['xarajat', 'Xarajatlar', ClipboardText],
    ['export', 'Excel', DownloadSimple],
  ]

  const exportFile = async (key, fn) => {
    setExporting(key)
    try {
      await fn()
      notify('Excel fayl yuklandi.', 'success')
    } catch (err) {
      notify(err.message)
    } finally {
      setExporting('')
    }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">TAHLILIY HISOBOT</p>
          <h1>Hisobotlar va statistika</h1>
        </div>
      </div>

      <div className="report-tabs">
        {tabs.map(([key, label, Icon]) => (
          <button key={key} className={tab === key ? 'tab-button is-active' : 'tab-button'} onClick={() => setTab(key)}>
            <Icon size={17} />{label}
          </button>
        ))}
      </div>

      {tab === 'moliyaviy' && (
        <>
          <div className="report-grid">
            <div className="report-stat"><span>Jami savdo daromadi</span><b>{money(summary.sales_revenue_total)} so‘m</b></div>
            <div className="report-stat"><span>Kassaga tushgan</span><b>{money(cash.sum_paid_uzs)} so‘m</b></div>
            <div className="report-stat"><span>Payment summary</span><b>{money(paymentsSummary.sum_paid_uzs)} so‘m</b></div>
            <div className="report-stat"><span>Kechikkan to‘lovlar</span><b>{summary.overdue_payments_count || 0} ta</b></div>
          </div>
          <section className="data-panel">
            <div className="panel-head"><div><p className="eyebrow">TO‘LOVLAR</p><h3>To‘lovlar bo‘yicha tafsilot</h3></div></div>
            {loading && !data ? <SkeletonRows /> : (
              <table className="report-table">
                <thead><tr><th>Holat</th><th>Soni</th><th>Ulushi</th></tr></thead>
                <tbody>
                  {[
                    ['To‘langan', cash.total_paid || 0, '#34d399'],
                    ['Qisman to‘langan', cash.total_partial || 0, '#fbbf24'],
                    ['Kechikkan', cash.total_overdue || 0, '#f87171'],
                  ].map(([label, count, color]) => {
                    const total = (cash.total_paid || 0) + (cash.total_partial || 0) + (cash.total_overdue || 0) || 1
                    const pct = Math.round((Number(count) / total) * 100)
                    return (
                      <tr key={label}>
                        <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><i className="status" style={{ background: color }} />{label}</span></td>
                        <td>{count}</td>
                        <td>{pct}%</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}

      {tab === 'xarajat' && (
        <>
          <div className="report-grid">
            <div className="report-stat"><span>Jami UZS xarajat</span><b>{money(expensesSummary.total_uzs)} so‘m</b></div>
            <div className="report-stat"><span>Jami USD xarajat</span><b>{money(expensesSummary.total_usd)} USD</b></div>
            <div className="report-stat"><span>Yozuvlar soni</span><b>{expensesSummary.count || 0}</b></div>
          </div>
          <section className="data-panel">
            <div className="panel-head"><div><p className="eyebrow">XARAJATLAR</p><h3>Toifalar bo‘yicha</h3></div></div>
            {list(expensesSummary.by_type).length ? (
              <table className="report-table">
                <thead><tr><th>Toifa</th><th>UZS</th><th>USD</th></tr></thead>
                <tbody>{list(expensesSummary.by_type).map((item) => (
                  <tr key={item.expense_type}><td>{item.name}</td><td>{money(item.total_uzs)} so‘m</td><td>{money(item.total_usd)} USD</td></tr>
                ))}</tbody>
              </table>
            ) : <Empty label="Xarajat summary ma’lumotlari yo‘q" />}
          </section>
        </>
      )}

      {tab === 'export' && (
        <section className="data-panel">
          <div className="panel-head"><div><p className="eyebrow">EXCEL EXPORT</p><h3>Hisobot fayllari</h3></div></div>
          <div className="export-grid">
            <button className="secondary-button" disabled={exporting === 'sales'} onClick={() => exportFile('sales', api.exportSales)}><DownloadSimple size={18} />Sotuvlar</button>
            <button className="secondary-button" disabled={exporting === 'stock'} onClick={() => exportFile('stock', api.exportStock)}><DownloadSimple size={18} />Ombor</button>
            <button className="secondary-button" disabled={exporting === 'expenses'} onClick={() => exportFile('expenses', api.exportExpenses)}><DownloadSimple size={18} />Xarajatlar</button>
            <button className="secondary-button" disabled={exporting === 'payments'} onClick={() => exportFile('payments', api.exportPayments)}><DownloadSimple size={18} />To‘lovlar</button>
          </div>
        </section>
      )}

      {tab === 'ombor' && (
        <>
          <div className="report-grid">
            <div className="report-stat"><span>Jami birliklar</span><b>{money(warehouse.total_quantity)}</b></div>
            <div className="report-stat"><span>Mahsulot turlari</span><b>{warehouse.total_product_types || 0}</b></div>
            <div className="report-stat"><span>Kritik qoldiqlar</span><b>{list(warehouse.low_stock).length}</b></div>
          </div>
          <section className="data-panel">
            <div className="panel-head"><div><p className="eyebrow">QOLDIQLAR</p><h3>Minimal qoldiqdan past mahsulotlar</h3></div></div>
            {loading && !data ? <SkeletonRows /> : list(warehouse.low_stock).length ? (
              <table className="report-table">
                <thead><tr><th>Mahsulot</th><th>Seriya</th><th>Qoldiq</th><th>Minimum</th></tr></thead>
                <tbody>
                  {list(warehouse.low_stock).map((item) => (
                    <tr key={item.product__id}>
                      <td>{item.product__name}</td>
                      <td>{item.product__serial_number || '—'}</td>
                      <td>{item.quantity}</td>
                      <td>{item.product__min_quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Empty label="Kritik qoldiq topilmadi" />}
          </section>
        </>
      )}

      {tab === 'sotuv' && (
        <>
          <div className="report-grid">
            <div className="report-stat"><span>Eng ko‘p sotilgan</span><b>{products[0]?.name || '—'}</b></div>
            <div className="report-stat"><span>Faol mahsulotlar</span><b>{products.length}</b></div>
            <div className="report-stat"><span>Jami sotilgan dona</span><b>{products.reduce((s, p) => s + Number(p.sold_qty || 0), 0)}</b></div>
          </div>
          <section className="data-panel">
            <div className="panel-head"><div><p className="eyebrow">REYTING</p><h3>Mahsulotlar bo‘yicha sotuvlar</h3></div></div>
            {loading && !data ? <SkeletonRows /> : products.length ? (
              <table className="report-table">
                <thead><tr><th>#</th><th>Mahsulot</th><th>Seriya</th><th>Sotilgan</th></tr></thead>
                <tbody>
                  {products.map((product, i) => (
                    <tr key={product.product || i}>
                      <td>{String(i + 1).padStart(2, '0')}</td>
                      <td>{product.name}</td>
                      <td>{product.serial_number || '—'}</td>
                      <td>{product.sold_qty} dona</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Empty label="Sotuv ma’lumotlari yo‘q" />}
          </section>
        </>
      )}
    </div>
  )
}

function Metric({ icon: Icon, label, value, note, trend }) {
  return (
    <article className="metric">
      <span className={`metric-icon ${trend}`}><Icon size={22} weight="duotone" /></span>
      <div>
        <p>{label}</p>
        <h2>{value}</h2>
        <small>{trend === 'up' ? <TrendUp size={14} /> : trend === 'down' ? <TrendDown size={14} /> : <Buildings size={14} />} {note}</small>
      </div>
    </article>
  )
}

function SkeletonRows() {
  return <div className="skeleton-wrap"><i /><i /><i /><i /></div>
}

function Empty({ label }) {
  return <div className="empty"><Package size={24} weight="thin" /><span>{label}</span></div>
}

const resources = {
  'Buyurtmalar': { load: api.orders, path: '/orders/' },
  'Import': { load: api.zakaz, path: '/orders/zakaz/' },
  'Shartnomalar': { load: api.contracts, path: '/orders/contracts/', readonly: true },
  'Ombor': { load: api.products, path: '/warehouse/products/' },
  'Kategoriyalar': { load: api.categories, path: '/warehouse/categories/' },
  'Qoldiqlar': { load: api.stocks, path: '/warehouse/stocks/' },
  'Mijozlar': { load: api.clients, path: '/clients/' },
  'Sotuvlar': { load: api.sales, path: '/sales/' },
  'Kassa': { load: api.payments, path: '/cash/payments/' },
  'Xarajatlar': { load: api.expenses, path: '/expenses/expenses/' },
  'Foydalanuvchilar': { load: api.users, path: '/auth/users/' },
  'Bildirishnomalar': { load: api.notifications, path: '/notifications/' },
}

function rowTitle(title, row) {
  if (title === 'Shartnomalar') return row.contract_number || `Reestr #${row.id}`
  if (title === 'Import') return row.product_name || `Import #${row.id}`
  if (title === 'Qoldiqlar') return row.product_name || row.product || `Qoldiq #${row.id}`
  if (title === 'Foydalanuvchilar') return row.username
  return row.company_name || row.full_name || row.client_name || row.name || `Hujjat #${row.id}`
}

function rowMeta(title, row) {
  if (title === 'Shartnomalar') {
    const parts = [row.product_name, row.source_type_display]
    if (row.asos && row.asos !== row.source_type_display) parts.push(row.asos)
    return parts.filter(Boolean).join(' • ') || row.created_at || '—'
  }
  if (title === 'Import') return [row.status_display || row.status, row.supplier, row.expected_date].filter(Boolean).join(' • ') || '—'
  if (title === 'Qoldiqlar') return [row.warehouse_location, `bron: ${row.reserved_quantity || 0}`].filter(Boolean).join(' • ')
  if (title === 'Foydalanuvchilar') return [row.role, row.is_active ? 'faol' : 'bloklangan'].filter(Boolean).join(' • ')
  if (title === 'Mijozlar') return [row.phone, row.passport_number, row.inn].filter(Boolean).join(' • ') || row.created_at || '—'
  return row.serial_number || row.status || row.phone || row.created_at || '—'
}

function rowValue(title, row, session) {
  const showPrices = can(session, 'prices_view')
  if (title === 'Import') {
    if (!showPrices || !row.total) return `${row.quantity || 0} dona`
    return `${money(row.total)} ${row.currency || ''}`
  }
  if (title === 'Buyurtmalar') {
    if (!showPrices) return `${row.total_quantity || 0} dona`
    return row.total ? `${money(row.total)} so‘m` : `${row.total_quantity || 0} dona`
  }
  if (title === 'Qoldiqlar') return quantityWithUnit(row.quantity || 0, row)
  if (title === 'Ombor') return quantityWithUnit(row.available_quantity ?? row.quantity_in_stock ?? 0, row)
  if (title === 'Shartnomalar') return row.contract_date || '—'
  if (title === 'Foydalanuvchilar') return row.can_view_clients ? 'Mijoz: bor' : 'Mijoz: yo‘q'
  if (title === 'Sotuvlar') {
    if (!showPrices) return `${row.quantity || 0} dona`
    return row.total_amount ? `${money(row.total_amount)} so‘m` : `${row.quantity || 0} dona`
  }
  if (title === 'Kassa') {
    if (!showPrices) return row.status_display || row.status || '—'
    return row.total_amount ? `${money(row.total_amount)} so‘m` : (row.remaining ? `${money(row.remaining)} qolgan` : '—')
  }
  if (!showPrices) return row.quantity || row.total_quantity || '—'
  return row.total_amount ? `${money(row.total_amount)} so‘m` : (row.available_quantity ?? row.total ?? '—')
}

function ContractDetailModal({ id, close, onNavigate }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError('')
      try {
        const data = await api.retrieve('/orders/contracts/', id)
        if (!cancelled) setDetail(data)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [id])

  const goTo = (page) => {
    close()
    onNavigate?.(page)
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <div className="editor contract-detail-modal">
        <div className="editor-head">
          <div>
            <p className="eyebrow">SHARTNOMA REESTRI</p>
            <h3>{detail?.contract_number || `Yozuv #${id}`}</h3>
            {detail?.product_name && <p className="muted">{detail.product_name}</p>}
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button>
        </div>
        {loading ? (
          <div className="contract-detail-loading"><SpinnerGap size={28} className="spin" /></div>
        ) : error ? (
          <p className="contract-detail-error">{error}</p>
        ) : detail ? (
          <>
            <dl className="contract-detail-grid">
              <div><dt>Shartnoma raqami</dt><dd>{detail.contract_number || '—'}</dd></div>
              <div><dt>Sana</dt><dd>{detail.contract_date || '—'}</dd></div>
              <div><dt>Mahsulot</dt><dd>{detail.product_name || '—'}</dd></div>
              <div><dt>Manba</dt><dd>{detail.source_type_display || detail.source_type || '—'}</dd></div>
              <div className="contract-detail-wide"><dt>Asos</dt><dd>{detail.asos || '—'}</dd></div>
              <div><dt>Faktura</dt><dd>{detail.faktura || '—'}</dd></div>
              <div><dt>Buyurtma</dt><dd>{detail.order ? `#${detail.order}` : '—'}</dd></div>
              <div><dt>Import</dt><dd>{detail.zakaz ? `#${detail.zakaz}` : '—'}</dd></div>
              <div><dt>Yaratgan</dt><dd>{detail.created_by_name || '—'}</dd></div>
              <div><dt>Yaratilgan vaqt</dt><dd>{detail.created_at || '—'}</dd></div>
            </dl>
            {(detail.order || detail.zakaz) && onNavigate && (
              <div className="contract-detail-links">
                {detail.order && (
                  <button type="button" className="secondary-button" onClick={() => goTo('Buyurtmalar')}>
                    Buyurtmaga o‘tish
                  </button>
                )}
                {detail.zakaz && (
                  <button type="button" className="secondary-button" onClick={() => goTo('Import')}>
                    Importga o‘tish
                  </button>
                )}
              </div>
            )}
          </>
        ) : null}
        <div className="editor-actions">
          <button type="button" className="primary-button" onClick={close}>Yopish</button>
        </div>
      </div>
    </div>
  )
}

function ProductContractsModal({ product, rows, close, onViewAll, onViewDetail }) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="editor product-contracts-modal">
        <div className="editor-head">
          <div>
            <p className="eyebrow">SHARTNOMALAR REESTRI</p>
            <h3>{product.name}</h3>
            <p className="muted">{product.serial_number || 'Seriya raqamsiz mahsulot'}</p>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button>
        </div>
        <p className="contracts-intro">
          Bu mahsulot bo‘yicha qaysi shartnoma, qaysi asos va qaysi amal (buyurtma, import, kirim) bilan ishlaganingizning rasmiy yozuvlari.
        </p>
        {rows.length ? (
          <div className="contracts-list">
            {rows.map((entry) => (
              <article
                className={`contract-card${onViewDetail ? ' contract-card-clickable' : ''}`}
                key={entry.id}
                role={onViewDetail ? 'button' : undefined}
                tabIndex={onViewDetail ? 0 : undefined}
                onClick={onViewDetail ? () => onViewDetail(entry.id) : undefined}
                onKeyDown={onViewDetail ? (event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onViewDetail(entry.id)
                  }
                } : undefined}
              >
                <div className="contract-card-head">
                  <b>{entry.contract_number || `Yozuv #${entry.id}`}</b>
                  <span>{entry.source_type_display || entry.source_type}</span>
                </div>
                <p>{entry.asos || 'Asos kiritilmagan'}</p>
                <small>
                  {[entry.contract_date, entry.faktura, entry.created_by_name].filter(Boolean).join(' • ')}
                </small>
              </article>
            ))}
          </div>
        ) : (
          <Empty label="Bu mahsulot uchun hali reestr yozuvi yo‘q" />
        )}
        <div className="editor-actions">
          {onViewAll && rows.length > 0 && (
            <button type="button" className="secondary-button" onClick={onViewAll}>Shartnomalar bo‘limi</button>
          )}
          <button type="button" className="primary-button" onClick={close}>Yopish</button>
        </div>
      </div>
    </div>
  )
}

function ResourcePage({ title, notify, reloadKey = 0, session, onDataChange, onNavigate }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [editing, setEditing] = useState(null)
  const [opening, setOpening] = useState(false)
  const [paying, setPaying] = useState(null)
  const [orderAction, setOrderAction] = useState(null)
  const [stockProduct, setStockProduct] = useState(null)
  const [contractProduct, setContractProduct] = useState(null)
  const [contractDetailId, setContractDetailId] = useState(null)

  const load = useCallback(async (silent = false, term = searchTerm) => {
    if (!resources[title]) return
    if (!silent) setLoading(true)
    try {
      setRows(list(await resources[title].load(term ? { search: term } : {})))
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [title, notify, searchTerm])

  useEffect(() => { load() }, [load, reloadKey])
  useAutoRefresh(() => load(true))

  const refreshAfterChange = () => {
    load(true)
    onDataChange?.()
  }

  const manageAbilities = {
    'Buyurtmalar': 'orders_manage',
    'Import': 'procurement_manage',
    'Ombor': 'warehouse_manage',
    'Kategoriyalar': 'warehouse_manage',
    'Qoldiqlar': 'warehouse_manage',
    'Mijozlar': 'clients_manage',
    'Sotuvlar': 'sales_manage',
    'Kassa': 'cash_manage',
    'Xarajatlar': 'expenses_manage',
    'Foydalanuvchilar': 'users_manage',
  }
  const canManage = can(session, manageAbilities[title])
  const canCreate = canManage && ['Mijozlar', 'Ombor', 'Buyurtmalar', 'Import', 'Kategoriyalar', 'Qoldiqlar', 'Sotuvlar', 'Xarajatlar', 'Foydalanuvchilar'].includes(title)

  const handleMarkRead = async (id) => {
    try {
      await api.notificationsMarkRead(id)
      await load(true)
      notify('Bildirishnoma o‘qilgan deb belgilandi.', 'success')
    } catch (err) {
      notify(err.message)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await api.notificationsMarkAllRead()
      await load(true)
      notify('Hammasi o‘qilgan deb belgilandi.', 'success')
    } catch (err) {
      notify(err.message)
    }
  }

  const handleSearch = (event) => {
    event.preventDefault()
    setSearchTerm(search.trim())
  }

  const handleEdit = async (row) => {
    if (!resources[title]) return
    setOpening(true)
    try {
      const detail = await api.retrieve(resources[title].path, row.id)
      setEditing(detail)
    } catch (err) {
      notify(err.message)
    } finally {
      setOpening(false)
    }
  }

  return (
    <div className="page resource-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">MODUL</p>
          <h1>{title}</h1>
          {title === 'Shartnomalar' && (
            <p className="contracts-registry-note">
              Yozuvlar avtomatik yaratiladi (buyurtma, import, kirim). Qo‘lda qo‘shish mumkin emas.
            </p>
          )}
        </div>
        <div className="heading-actions">
          {title === 'Bildirishnomalar' && (
            <button className="secondary-button" onClick={handleMarkAllRead}>Hammasini o‘qilgan</button>
          )}
          {canCreate && <button className="primary-button" onClick={() => setEditing({})}><Plus size={20} />Yangi qo‘shish</button>}
        </div>
      </div>
      <section className="data-panel">
        <div className="panel-head">
          <div><p className="eyebrow">RO‘YXAT</p><h3>{rows.length} ta yozuv</h3></div>
          <form className="resource-search" onSubmit={handleSearch}>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Qidirish" aria-label={`${title} qidirish`} />
            <button type="submit" className="icon-button" aria-label="Qidirish"><MagnifyingGlass size={20} /></button>
          </form>
        </div>
        {loading && !rows.length ? <SkeletonRows /> : !rows.length ? (
          title === 'Shartnomalar' ? (
            <Empty label="Hali reestr yozuvi yo‘q. Buyurtma, import yoki ombor kirimi amalga oshganda yozuvlar avtomatik paydo bo‘ladi." />
          ) : (
            <Empty label="Yozuv topilmadi" />
          )
        ) : (
          <div className="product-list">
            {rows.map((row, index) => (
              <div
                className={`product-row${title === 'Shartnomalar' ? ' product-row-clickable' : ''}`}
                key={row.id || index}
                onClick={title === 'Shartnomalar' ? () => setContractDetailId(row.id) : undefined}
                onKeyDown={title === 'Shartnomalar' ? (event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    setContractDetailId(row.id)
                  }
                } : undefined}
                role={title === 'Shartnomalar' ? 'button' : undefined}
                tabIndex={title === 'Shartnomalar' ? 0 : undefined}
              >
                <span className="rank">{String(index + 1).padStart(2, '0')}</span>
                {title === 'Bildirishnomalar' ? (
                  <>
                    <div className="product-name">
                      <b>{row.title}</b>
                      <small>{row.message}</small>
                    </div>
                    <span className="bar"><i style={{ width: row.is_read ? '100%' : '38%' }} /></span>
                    <b>{row.is_read ? 'O‘qilgan' : 'Yangi'}</b>
                    <button className="row-action" onClick={() => handleMarkRead(row.id)}>{row.is_read ? '✓' : 'O‘qish'}</button>
                  </>
                ) : (
                  <>
                    <div className="product-name">
                      <b>{rowTitle(title, row)}</b>
                      <small>{rowMeta(title, row)}</small>
                    </div>
                    <span className="bar"><i style={{ width: '58%' }} /></span>
                    <b>{rowValue(title, row, session)}</b>
                    <div className="row-actions">
            {canManage && !resources[title].readonly && <button className="row-action" disabled={opening} onClick={() => handleEdit(row)} aria-label="Tahrirlash"><PencilSimple size={18} /></button>}
                      {can(session, 'orders_manage') && title === 'Buyurtmalar' && !['fulfilled', 'cancelled'].includes(row.status) && (
                        <>
                          <button className="row-action" onClick={() => setOrderAction({ row, action: 'fulfill' })}>Yetkazish</button>
                          <button className="row-action" onClick={() => setOrderAction({ row, action: 'cancel' })}>Bekor</button>
                          {Number(row.backorder_qty || 0) > 0 && <button className="row-action" onClick={() => setOrderAction({ row, action: 'zakaz' })}>Import</button>}
                        </>
                      )}
                      {can(session, 'warehouse_manage') && title === 'Ombor' && <button className="row-action" onClick={() => setStockProduct(row)} aria-label="Kirim qilish">Kirim</button>}
                      {can(session, 'cash_manage') && title === 'Kassa' && row.remaining !== '0' && (
                        <button className="row-action" onClick={() => setPaying(row)} aria-label="To‘lov qabul qilish"><CurrencyCircleDollar size={18} /></button>
                      )}
                      {title === 'Shartnomalar' && (
                        <button
                          className="row-action"
                          aria-label="Ko‘rish"
                          onClick={(event) => {
                            event.stopPropagation()
                            setContractDetailId(row.id)
                          }}
                        >
                          <Eye size={18} />
                        </button>
                      )}
                      {title === 'Ombor' && (
                        <button
                          className="row-action"
                          title="Mahsulot shartnomalari reestri"
                          onClick={async (event) => {
                            event.stopPropagation()
                            setOpening(true)
                            try {
                              const rows = list(await api.productContracts(row.id))
                              if (!rows.length) {
                                notify('Bu mahsulot bo‘yicha hali shartnoma reestri yozuvi yo‘q.', 'warning')
                                return
                              }
                              setContractProduct({ product: row, rows })
                            } catch (err) {
                              notify(err.message)
                            } finally {
                              setOpening(false)
                            }
                          }}
                        >
                          Reestr
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
      {editing && (title === 'Buyurtmalar'
        ? <OrderEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} session={session} />
        : title === 'Import'
          ? <ZakazEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} session={session} />
        : title === 'Sotuvlar'
          ? <SaleEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} session={session} />
        : title === 'Foydalanuvchilar'
            ? <UserEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} />
          : title === 'Xarajatlar'
            ? <ExpenseEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} />
            : <Editor title={title} item={editing} path={resources[title].path} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} session={session} />
      )}
      {paying && <PaymentEditor item={paying} close={() => setPaying(null)} done={() => { setPaying(null); refreshAfterChange() }} notify={notify} />}
      {orderAction && <OrderActionEditor item={orderAction.row} action={orderAction.action} close={() => setOrderAction(null)} done={() => { setOrderAction(null); refreshAfterChange() }} notify={notify} />}
      {stockProduct && <StockInEditor item={stockProduct} close={() => setStockProduct(null)} done={() => { setStockProduct(null); refreshAfterChange() }} notify={notify} />}
      {contractProduct && (
        <ProductContractsModal
          product={contractProduct.product}
          rows={contractProduct.rows}
          close={() => setContractProduct(null)}
          onViewAll={can(session, 'contracts_view') && onNavigate
            ? () => { setContractProduct(null); onNavigate('Shartnomalar') }
            : null}
          onViewDetail={can(session, 'contracts_view')
            ? (entryId) => { setContractProduct(null); setContractDetailId(entryId) }
            : null}
        />
      )}
      {contractDetailId && (
        <ContractDetailModal
          id={contractDetailId}
          close={() => setContractDetailId(null)}
          onNavigate={onNavigate}
        />
      )}
    </div>
  )
}

const fields = {
  Ombor: [['name', 'Mahsulot nomi', true], ['model', 'Model'], ['serial_number', 'Seriya raqami', true], ['source', 'Manba / yetkazuvchi'], ['unit', 'O‘lchov birligi'], ['min_quantity', 'Minimal qoldiq'], ['purchase_price', 'Kelish narxi'], ['selling_price', 'Sotuv narxi'], ['quantity', 'Boshlang‘ich miqdor'], ['warehouse_location', 'Ombordagi joy']],
  Kategoriyalar: [['name', 'Kategoriya nomi', true], ['parent', 'Ota kategoriya']],
  Qoldiqlar: [['product', 'Mahsulot ID', true], ['quantity', 'Miqdor', true], ['reserved_quantity', 'Bron miqdor'], ['warehouse_location', 'Ombordagi joy', true]],
}

function Editor({ title, item, path, close, done, notify, session }) {
  const [form, setForm] = useState(() => ({ ...item, client_type: item?.client_type || 'individual' }))
  const [saving, setSaving] = useState(false)
  const [categories, setCategories] = useState([])
  const canManagePrices = can(session, 'prices_manage')

  useEffect(() => {
    if (title !== 'Kategoriyalar') return
    api.categories({ page_size: 200 })
      .then((data) => setCategories(list(data)))
      .catch((err) => notify(err.message))
  }, [title, notify])

  const parentOptions = useMemo(() => {
    if (title !== 'Kategoriyalar') return []
    const flat = flattenCategories(categories)
    if (!item?.id) return flat
    const node = findCategoryNode(categories, item.id)
    const excluded = new Set([item.id, ...collectDescendantIds(node)])
    return flat.filter((cat) => !excluded.has(cat.id))
  }, [title, categories, item?.id])
  const visibleFields = title === 'Ombor'
    ? fields[title].filter(([key]) => {
      if (key === 'purchase_price' || key === 'selling_price' || key === 'min_quantity') return canManagePrices
      return true
    })
    : fields[title]

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    const payload = Object.fromEntries(Object.entries(form).filter(([key, value]) => !['id', 'created_at', 'quantity_in_stock', 'available_quantity', 'reserved_quantity', 'stock_status', 'category_name', 'unit_display'].includes(key) && value !== undefined && value !== ''))
    if (title === 'Ombor') {
      if (payload.min_quantity) payload.min_quantity = Number(payload.min_quantity)
      if (payload.quantity) payload.quantity = Number(payload.quantity)
      if (!canManagePrices) {
        delete payload.purchase_price
        delete payload.selling_price
        delete payload.min_quantity
      }
    }
    if (title === 'Qoldiqlar') {
      if (payload.product) payload.product = Number(payload.product)
      if (payload.quantity) payload.quantity = Number(payload.quantity)
      if (payload.reserved_quantity) payload.reserved_quantity = Number(payload.reserved_quantity)
    }
    if (title === 'Kategoriyalar') {
      if (payload.parent) payload.parent = Number(payload.parent)
    }
    if (title === 'Mijozlar') {
      if (payload.client_type === 'individual') {
        payload.full_name = (payload.full_name || '').trim()
        payload.first_name = ''
        payload.last_name = ''
        payload.middle_name = ''
        payload.company_name = ''
        payload.inn = ''
      } else {
        payload.first_name = ''
        payload.last_name = ''
        payload.middle_name = ''
        payload.pinfl = ''
        payload.passport_number = ''
        payload.full_name = ''
      }
    }
    try {
      item.id ? await api.update(path, item.id, payload) : await api.create(path, payload)
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head">
          <div><p className="eyebrow">{item.id ? 'TAHRIRLASH' : 'YANGI YOZUV'}</p><h3>{title.slice(0, -1)} ma’lumotlari</h3></div>
          <button type="button" className="icon-button" onClick={close}><X size={20} /></button>
        </div>
        <div className="form-grid">
          {title === 'Mijozlar' ? (
            <>
              <label>Tur
                <select value={form.client_type || 'individual'} onChange={(event) => setForm({ ...form, client_type: event.target.value })}>
                  <option value="individual">Jismoniy shaxs</option>
                  <option value="legal">Yuridik shaxs</option>
                </select>
              </label>
              {form.client_type === 'legal' ? (
                <>
                  <label>Korxona nomi<input required value={form.company_name ?? ''} onChange={(event) => setForm({ ...form, company_name: event.target.value })} /></label>
                  <label>INN<input value={form.inn ?? ''} onChange={(event) => setForm({ ...form, inn: event.target.value })} /></label>
                  <label>Telefon<input required value={form.phone ?? ''} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
                  <label>E-mail<input type="email" value={form.email ?? ''} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
                  <label>Manzil<input value={form.address ?? ''} onChange={(event) => setForm({ ...form, address: event.target.value })} /></label>
                  <label className="full-width">Izoh<textarea value={form.comment ?? ''} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
                </>
              ) : (
                <>
                  <label>To‘liq ism<input required value={form.full_name ?? ''} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></label>
                  <label>JSHR (PINFL)<input required value={form.pinfl ?? ''} onChange={(event) => setForm({ ...form, pinfl: event.target.value })} /></label>
                  <label>Pasport seriya va raqami<input required value={form.passport_number ?? ''} onChange={(event) => setForm({ ...form, passport_number: event.target.value })} /></label>
                  <label>Telefon<input required value={form.phone ?? ''} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
                  <label>E-mail<input type="email" value={form.email ?? ''} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
                  <label>Manzil<input value={form.address ?? ''} onChange={(event) => setForm({ ...form, address: event.target.value })} /></label>
                  <label className="full-width">Izoh<textarea value={form.comment ?? ''} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
                </>
              )}
            </>
          ) : visibleFields?.map(([key, label, required]) => (
            <label key={key}>{label}
              {key === 'unit' ? (
                <select required value={form.unit || 'piece'} onChange={(event) => setForm({ ...form, unit: event.target.value })}>
                  {productUnits.map(([value, name]) => <option value={value} key={value}>{name}</option>)}
                </select>
              ) : key === 'parent' ? (
                <select value={form.parent ?? ''} onChange={(event) => setForm({ ...form, parent: event.target.value })}>
                  <option value="">Asosiy kategoriya (yuqori daraja)</option>
                  {parentOptions.map((cat) => (
                    <option value={cat.id} key={cat.id}>{`${'— '.repeat(cat.depth)}${cat.name}`}</option>
                  ))}
                </select>
              ) : (
                <input required={required} value={form[key] ?? ''} type={key === 'email' ? 'email' : ['min_quantity', 'quantity', 'purchase_price', 'selling_price'].includes(key) ? 'number' : 'text'} step={['purchase_price', 'selling_price'].includes(key) ? '0.01' : undefined} min={['min_quantity', 'quantity'].includes(key) ? '0' : undefined} onChange={(event) => setForm({ ...form, [key]: event.target.value })} />
              )}
            </label>
          ))}
        </div>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}</button>
        </div>
      </form>
    </div>
  )
}

function SaleEditor({ close, done, notify, item = null, session }) {
  const showPrices = can(session, 'prices_manage')
  const [clients, setClients] = useState([])
  const [products, setProducts] = useState([])
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(() => ({ client: item?.client || '', product: item?.product || '', quantity: item?.quantity || '1', sold_price: item?.sold_price || '', sold_to: item?.sold_to || '', destination: item?.destination || '', sold_date: item?.sold_date || new Date().toISOString().slice(0, 10), comment: item?.comment || '' }))
  const [items, setItems] = useState([{ product: '', quantity: '1', sold_price: '', comment: '' }])

  useEffect(() => {
    Promise.all([api.clients(), api.products()])
      .then(([clientData, productData]) => { setClients(list(clientData)); setProducts(list(productData)) })
      .catch((err) => notify(err.message))
  }, [notify])

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = {
        client: form.client || null,
        product: Number(form.product),
        quantity: Number(form.quantity),
        ...(showPrices ? { sold_price: Number(form.sold_price || 0) } : {}),
        sold_to: form.sold_to || '',
        destination: form.destination || '',
        sold_date: form.sold_date || new Date().toISOString().slice(0, 10),
        comment: form.comment || '',
      }
      if (item?.id) await api.update('/sales/', item.id, payload)
      else if (items.length > 1 || items[0].product) {
        await api.salesBulk({
          client: form.client || null,
          sold_to: form.sold_to || '',
          destination: form.destination || '',
          sold_date: form.sold_date || new Date().toISOString().slice(0, 10),
          items: items.filter((row) => row.product).map((row) => ({
            product: Number(row.product),
            quantity: Number(row.quantity),
            ...(showPrices ? { sold_price: row.sold_price } : {}),
            comment: row.comment || '',
          })),
        })
      } else await api.create('/sales/', payload)
      notify(item?.id ? 'Sotuv yangilandi.' : 'Sotuv saqlandi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head">
          <div><p className="eyebrow">{item?.id ? 'TAHRIRLASH' : 'YANGI SOTUV'}</p><h3>Sotuv ma’lumotlari</h3></div>
          <button type="button" className="icon-button" onClick={close}><X size={20} /></button>
        </div>
        <div className="form-grid">
          <label>Mijoz<select value={form.client} onChange={(event) => setForm({ ...form, client: event.target.value })}><option value="">Mijoz tanlanmagan</option>{clients.map((client) => <option value={client.id} key={client.id}>{client.company_name || client.full_name}</option>)}</select></label>
          {item?.id ? (
            <>
              <label>Mahsulot<select required value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })}><option value="">Mahsulotni tanlang</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number} ({product.unit_display || unitLabel(product.unit)})</option>)}</select></label>
              <label>Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label>
              {showPrices && <label>Sotuv narxi<input required min="0" step="0.01" type="number" value={form.sold_price} onChange={(event) => setForm({ ...form, sold_price: event.target.value })} /></label>}
            </>
          ) : (
            <div className="full-width line-items">
              <div className="line-head"><b>Mahsulotlar</b></div>
              {items.map((row, index) => (
                <div className="line-item" key={index}>
                  <select required value={row.product} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, product: event.target.value } : itemRow))}><option value="">Mahsulot</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number} ({product.unit_display || unitLabel(product.unit)})</option>)}</select>
                  <input required min="1" type="number" value={row.quantity} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, quantity: event.target.value } : itemRow))} />
                  {showPrices && <input required min="0" step="0.01" type="number" placeholder="Narx" value={row.sold_price} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, sold_price: event.target.value } : itemRow))} />}
                  <button type="button" className="row-action" disabled={items.length === 1} onClick={() => setItems(items.filter((_, i) => i !== index))}>O‘chirish</button>
                </div>
              ))}
              <button type="button" className="secondary-button add-line-button" onClick={() => setItems([...items, { product: '', quantity: '1', sold_price: '', comment: '' }])}><Plus size={16} />Mahsulot qo‘shish</button>
            </div>
          )}
          <label>Sotuvchi/kimga<select value={form.sold_to} onChange={(event) => setForm({ ...form, sold_to: event.target.value })}><option value="">Tanlanmagan</option><option value="Mijoz">Mijoz</option><option value="Operator">Operator</option><option value="Boshqa">Boshqa</option></select></label>
          <label>Manzil<input value={form.destination} onChange={(event) => setForm({ ...form, destination: event.target.value })} /></label>
          <label>Sana<input type="date" value={form.sold_date} onChange={(event) => setForm({ ...form, sold_date: event.target.value })} /></label>
          <label className="full-width">Izoh<textarea value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
        </div>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : item?.id ? 'Yangilash' : 'Saqlash'}</button>
        </div>
      </form>
    </div>
  )
}

function ExpenseEditor({ close, done, notify, item = null }) {
  const [expenseTypes, setExpenseTypes] = useState([])
  const [subTypes, setSubTypes] = useState([])
  const [saving, setSaving] = useState(false)
  const [file, setFile] = useState(null)
  const [form, setForm] = useState(() => ({ expense_type: item?.expense_type || '', sub_type: item?.sub_type || '', amount: item?.amount || '', currency: item?.currency || 'UZS', date: item?.date || new Date().toISOString().slice(0, 10), comment: item?.comment || '' }))

  useEffect(() => {
    api.expenseTypes()
      .then((data) => setExpenseTypes(list(data)))
      .catch((err) => notify(err.message))
  }, [notify])

  useEffect(() => {
    if (!form.expense_type) {
      setSubTypes([])
      return
    }
    api.expenseSubtypes()
      .then((data) => setSubTypes(list(data).filter((item) => String(item.expense_type) === String(form.expense_type))))
      .catch((err) => notify(err.message))
  }, [form.expense_type, notify])

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = new FormData()
      if (form.expense_type) payload.append('expense_type', form.expense_type)
      if (form.sub_type) payload.append('sub_type', form.sub_type)
      if (form.amount) payload.append('amount', form.amount)
      if (form.currency) payload.append('currency', form.currency)
      if (form.date) payload.append('date', form.date)
      if (form.comment) payload.append('comment', form.comment)
      if (file) payload.append('attachment', file)
      if (item?.id) await api.updateForm('/expenses/expenses/', item.id, payload)
      else await api.createForm('/expenses/expenses/', payload)
      notify(item?.id ? 'Rasxod yangilandi.' : 'Rasxod saqlandi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head">
          <div><p className="eyebrow">{item?.id ? 'TAHRIRLASH' : 'YANGI RASXOD'}</p><h3>Rasxod ma’lumotlari</h3></div>
          <button type="button" className="icon-button" onClick={close}><X size={20} /></button>
        </div>
        <div className="form-grid">
          <label>Toifa<select required value={form.expense_type} onChange={(event) => setForm({ ...form, expense_type: event.target.value, sub_type: '' })}><option value="">Tanlang</option>{expenseTypes.map((type) => <option value={type.id} key={type.id}>{type.name}</option>)}</select></label>
          <label>Turi<select value={form.sub_type} onChange={(event) => setForm({ ...form, sub_type: event.target.value })}><option value="">Tanlanmagan</option>{subTypes.map((type) => <option value={type.id} key={type.id}>{type.name}</option>)}</select></label>
          <label>Summa<input required min="0" step="0.01" type="number" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
          <label>Valyuta<select value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })}><option value="UZS">UZS</option><option value="USD">USD</option></select></label>
          <label>Sana<input type="date" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
          <label className="full-width file-field">Fayl
            <span className="file-picker">
              <span><FileText size={18} />{file?.name || 'Hujjat yoki rasm fayl tanlang'}</span>
              <b>Tanlash</b>
              <input type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            </span>
          </label>
          <label className="full-width">Izoh<textarea value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
        </div>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : item?.id ? 'Yangilash' : 'Saqlash'}</button>
        </div>
      </form>
    </div>
  )
}

function OrderEditor({ close, done, notify, item = null, session }) {
  const showPrices = can(session, 'prices_manage')
  const [clients, setClients] = useState([])
  const [products, setProducts] = useState([])
  const [saving, setSaving] = useState(false)
  const [file, setFile] = useState(null)
  const [form, setForm] = useState({ client: '', contract_number: '', contract_date: todayValue(), due_date: currentYearEndValue(), prepaid_amount: '0', product: '', itemId: null, quantity: '1', unit_price: '', comment: '', asos: '' })
  const [items, setItems] = useState([{ product: '', quantity: '1', unit_price: '' }])
  const [contractNumberEdited, setContractNumberEdited] = useState(false)

  const updateContractNumber = (value) => {
    setForm({ ...form, contract_number: value.replace(/[^\d/]/g, '') })
    setContractNumberEdited(true)
  }

  useEffect(() => {
    Promise.all([api.clients(), api.products()])
      .then(([clientData, productData]) => { setClients(list(clientData)); setProducts(list(productData)) })
      .catch((err) => notify(err.message))
  }, [notify])

  useEffect(() => {
    if (!item) {
      setForm({ client: '', contract_number: '', contract_date: todayValue(), due_date: currentYearEndValue(), prepaid_amount: '0', product: '', itemId: null, quantity: '1', unit_price: '', comment: '', asos: '' })
      setItems([{ product: '', quantity: '1', unit_price: '' }])
      setContractNumberEdited(false)
      return
    }
    setForm({
      client: item.client || '',
      contract_number: item.contract_number || '',
      contract_date: item.contract_date || todayValue(),
      due_date: item.due_date || '',
      prepaid_amount: item.prepaid_amount ?? '0',
      product: item.items?.[0]?.product || '',
      itemId: item.items?.[0]?.id || null,
      quantity: item.items?.[0]?.quantity || '1',
      unit_price: item.items?.[0]?.unit_price || '',
      comment: item.comment || '',
      asos: '',
    })
    setContractNumberEdited(Boolean(item.contract_number))
  }, [item])

  useEffect(() => {
    if (item?.id || contractNumberEdited || !form.contract_date) return
    let cancelled = false
    api.nextContractNumber({ contract_date: form.contract_date })
      .then((data) => {
        if (!cancelled) setForm((current) => ({ ...current, contract_number: data.contract_number || '' }))
      })
      .catch((err) => notify(err.message))
    return () => { cancelled = true }
  }, [item?.id, contractNumberEdited, form.contract_date, notify])

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      if (item?.id) {
        const payload = {
          client: form.client || null,
          contract_number: form.contract_number || '',
          contract_date: form.contract_date || null,
          due_date: form.due_date || null,
          prepaid_amount: showPrices ? Number(form.prepaid_amount || 0) : 0,
          comment: form.comment || '',
          asos: form.asos,
        }
        if (form.itemId) {
          payload.items = [{ id: form.itemId, quantity: Number(form.quantity) }]
          if (showPrices && form.unit_price !== '') payload.items[0].unit_price = form.unit_price
        }
        await api.update('/orders/', item.id, payload)
        notify('Buyurtma yangilandi.', 'success')
      } else {
        const payload = new FormData()
        if (form.client) payload.append('client', form.client)
        if (form.contract_number) payload.append('contract_number', form.contract_number)
        if (form.contract_date) payload.append('contract_date', form.contract_date)
        if (form.due_date) payload.append('due_date', form.due_date)
        if (showPrices) payload.append('prepaid_amount', form.prepaid_amount || '0')
        payload.append('comment', form.comment || '')
        payload.append('items', JSON.stringify(items.filter((row) => row.product).map((row) => ({
          product: Number(row.product),
          quantity: Number(row.quantity),
          ...(showPrices && row.unit_price ? { unit_price: row.unit_price } : {}),
        }))))
        if (file) payload.append('contract_file', file)
        const created = await api.createForm('/orders/', payload)
        const number = created?.contract_number || form.contract_number || 'avtomatik'
        notify(`Buyurtma yaratildi. Shartnoma №${number}`, 'success')
      }
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head">
          <div><p className="eyebrow">{item?.id ? 'TAHRIRLASH' : 'YANGI BUYURTMA'}</p><h3>Shartnoma bo‘yicha buyurtma</h3></div>
          <button type="button" className="icon-button" onClick={close}><X size={20} /></button>
        </div>
        <div className="form-grid">
          <label>Mijoz<select value={form.client} onChange={(event) => setForm({ ...form, client: event.target.value })}><option value="">Mijoz tanlanmagan</option>{clients.map((client) => <option value={client.id} key={client.id}>{client.company_name || client.full_name}</option>)}</select></label>
          <label>Shartnoma raqami<input value={form.contract_number} onChange={(event) => updateContractNumber(event.target.value)} placeholder="Masalan: 12/1108" inputMode="numeric" pattern="[0-9/]*" /></label>
          <label>Shartnoma tuzilgan sana<input type="date" value={form.contract_date} onChange={(event) => setForm({ ...form, contract_date: event.target.value })} /></label>
          <label>Yetkazish muddati<input type="date" value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} /></label>
          {item?.id ? (
            <>
              <label>Mahsulot<select required value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })}><option value="">Mahsulotni tanlang</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number} ({product.unit_display || unitLabel(product.unit)})</option>)}</select></label>
              <label>Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label>
              {showPrices && <label>Birlik narxi<input type="number" min="0" step="0.01" value={form.unit_price} onChange={(event) => setForm({ ...form, unit_price: event.target.value })} /></label>}
            </>
          ) : (
            <div className="full-width line-items">
              <div className="line-head"><b>Mahsulotlar</b></div>
              {items.map((row, index) => (
                <div className="line-item" key={index}>
                  <select required value={row.product} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, product: event.target.value } : itemRow))}><option value="">Mahsulot</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number} ({product.unit_display || unitLabel(product.unit)})</option>)}</select>
                  <input required min="1" type="number" value={row.quantity} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, quantity: event.target.value } : itemRow))} />
                  {showPrices && <input type="number" min="0" step="0.01" placeholder="Birlik narxi" value={row.unit_price} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, unit_price: event.target.value } : itemRow))} />}
                  <button type="button" className="row-action" disabled={items.length === 1} onClick={() => setItems(items.filter((_, i) => i !== index))}>O‘chirish</button>
                </div>
              ))}
              <button type="button" className="secondary-button add-line-button" onClick={() => setItems([...items, { product: '', quantity: '1', unit_price: '' }])}><Plus size={16} />Mahsulot qo‘shish</button>
            </div>
          )}
          {showPrices && <label>Oldindan to‘lov<input type="number" min="0" step="0.01" value={form.prepaid_amount} onChange={(event) => setForm({ ...form, prepaid_amount: event.target.value })} /></label>}
          {item?.id && <label className="full-width">Tahrirlash sababi<input required value={form.asos} onChange={(event) => setForm({ ...form, asos: event.target.value })} placeholder="Nima uchun o‘zgartirilayotganini yozing" /></label>}
          <label className="full-width file-field">Shartnoma fayli
            <span className="file-picker">
              <span><FileText size={18} />{file?.name || 'Word yoki PDF fayl tanlang'}</span>
              <b>Tanlash</b>
              <input type="file" accept=".doc,.docx,.pdf" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            </span>
          </label>
          <label className="full-width">Izoh<textarea value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
        </div>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : item?.id ? 'Yangilash' : 'Buyurtmani yaratish'}</button>
        </div>
      </form>
    </div>
  )
}

function OrderActionEditor({ item, action, close, done, notify }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ contract_number: item.contract_number || '', asos: '', faktura: '', supplier: '', expected_date: '' })
  const labels = { fulfill: 'Yetkazib berish', cancel: 'Buyurtmani bekor qilish', zakaz: 'Import yaratish' }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== ''))
      if (action === 'fulfill') await api.fulfillOrder(item.id, payload)
      else if (action === 'cancel') await api.cancelOrder(item.id, payload)
      else await api.createOrderZakaz(item.id, payload)
      notify(`${labels[action]} bajarildi.`, 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head"><div><p className="eyebrow">BUYURTMA AMALI</p><h3>{labels[action]}</h3></div><button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button></div>
        <p className="muted">Shartnoma №{item.contract_number || '—'} uchun amal.</p>
        <div className="form-grid">
          <label>Shartnoma raqami<input required value={form.contract_number} onChange={(event) => setForm({ ...form, contract_number: event.target.value })} /></label>
          <label>Faktura (ixtiyoriy)<input value={form.faktura} onChange={(event) => setForm({ ...form, faktura: event.target.value })} /></label>
          <label className="full-width">Asos / izoh<textarea required rows="3" value={form.asos} onChange={(event) => setForm({ ...form, asos: event.target.value })} placeholder="Amal sababi" /></label>
          {action === 'zakaz' && <><label>Yetkazuvchi<input value={form.supplier} onChange={(event) => setForm({ ...form, supplier: event.target.value })} /></label><label>Kutilgan sana<input type="date" value={form.expected_date} onChange={(event) => setForm({ ...form, expected_date: event.target.value })} /></label></>}
        </div>
        <div className="editor-actions"><button type="button" className="secondary-button" onClick={close}>Bekor qilish</button><button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : labels[action]}</button></div>
      </form>
    </div>
  )
}

function ZakazEditor({ close, done, notify, item = null, session }) {
  const showPrices = can(session, 'prices_manage')
  const isManagement = can(session, 'prices_manage')
  const isBackorder = item?.zakaz_type === 'backorder'
  const [products, setProducts] = useState([])
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(() => ({
    product: item?.product || '',
    quantity: item?.quantity || '1',
    received_qty: item?.received_qty || '0',
    unit_price: item?.unit_price || '',
    currency: item?.currency || 'UZS',
    supplier: item?.supplier || '',
    status: item?.status || 'new',
    payment_status: item?.payment_status || 'unpaid',
    contract_number: item?.contract_number || '',
    contract_date: item?.contract_date || todayValue(),
    faktura: item?.faktura || '',
    expected_date: item?.expected_date || '',
    warehouse_location: item?.warehouse_location || '',
    asos: item?.asos || '',
    comment: item?.comment || '',
  }))

  useEffect(() => {
    api.products().then((data) => setProducts(list(data))).catch((err) => notify(err.message))
  }, [notify])

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== '' && value !== null))
      if (payload.product) payload.product = Number(payload.product)
      if (payload.quantity) payload.quantity = Number(payload.quantity)
      if (payload.received_qty) payload.received_qty = Number(payload.received_qty)
      if (!showPrices || isBackorder) {
        delete payload.unit_price
        delete payload.currency
        delete payload.payment_status
      }
      if (item?.id) await api.update('/orders/zakaz/', item.id, payload)
      else await api.create('/orders/zakaz/', payload)
      notify(item?.id ? 'Import yangilandi.' : 'Import yaratildi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head"><div><p className="eyebrow">{item?.id ? 'IMPORT TAHRIRI' : 'YANGI IMPORT'}</p><h3>Yetkazuvchidan import</h3></div><button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button></div>
        <div className="form-grid">
          <div className={`import-top-row${isManagement ? ' has-received' : ''}`}>
            <label className="field-product">Mahsulot<select required disabled={Boolean(item?.order_contract)} value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })}><option value="">Mahsulotni tanlang</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number} ({product.unit_display || unitLabel(product.unit)})</option>)}</select></label>
            <label className="field-qty">Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} disabled={isBackorder && !isManagement} /></label>
            {isManagement && <label className="field-received">Qabul qilingan<input min="0" type="number" value={form.received_qty} onChange={(event) => setForm({ ...form, received_qty: event.target.value })} /></label>}
          </div>
          {showPrices && !isBackorder && <>
            <label>Narx<input required={!item?.id && showPrices} min="0" step="0.01" type="number" value={form.unit_price} onChange={(event) => setForm({ ...form, unit_price: event.target.value })} /></label>
            <label>Valyuta<select value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })}><option value="UZS">UZS</option><option value="USD">USD</option></select></label>
            <label>To‘lov statusi<select value={form.payment_status} onChange={(event) => setForm({ ...form, payment_status: event.target.value })}><option value="unpaid">To‘lanmagan</option><option value="partial">Qisman</option><option value="paid">To‘langan</option></select></label>
          </>}
          {isManagement && <label>Status<select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="new">Yangi</option><option value="confirmed">Tasdiqlandi</option><option value="received">Qabul qilindi</option><option value="cancelled">Bekor qilindi</option></select></label>}
          <label>Yetkazuvchi<input value={form.supplier} onChange={(event) => setForm({ ...form, supplier: event.target.value })} /></label>
          <label>Shartnoma raqami<input value={form.contract_number} onChange={(event) => setForm({ ...form, contract_number: event.target.value.replace(/[^\d/]/g, '') })} placeholder="12/1108" /></label>
          <label>Shartnoma sanasi<input type="date" value={form.contract_date} onChange={(event) => setForm({ ...form, contract_date: event.target.value })} /></label>
          <label>Faktura<input value={form.faktura} onChange={(event) => setForm({ ...form, faktura: event.target.value })} /></label>
          <label>Kutilgan sana<input type="date" value={form.expected_date} onChange={(event) => setForm({ ...form, expected_date: event.target.value })} /></label>
          <label>Ombor joyi<input value={form.warehouse_location} onChange={(event) => setForm({ ...form, warehouse_location: event.target.value })} /></label>
          <label className="full-width">Asos<textarea required={item?.id && form.status !== item.status} rows="3" value={form.asos} onChange={(event) => setForm({ ...form, asos: event.target.value })} /></label>
          <label className="full-width">Izoh<textarea rows="3" value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} /></label>
        </div>
        <div className="editor-actions"><button type="button" className="secondary-button" onClick={close}>Bekor qilish</button><button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}</button></div>
      </form>
    </div>
  )
}

function UserEditor({ close, done, notify, item = null }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(() => ({ username: item?.username || '', password: '', first_name: item?.first_name || '', last_name: item?.last_name || '', role: item?.role || 'OPERATOR', phone: item?.phone || '', telegram_id: item?.telegram_id || '', can_view_clients: Boolean(item?.can_view_clients), is_active: item?.is_active ?? true }))
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = { ...form }
      if (item?.id) {
        delete payload.password
        await api.update('/auth/users/', item.id, payload)
      } else {
        delete payload.is_active
        await api.registerUser(payload)
      }
      notify(item?.id ? 'Foydalanuvchi yangilandi.' : 'Foydalanuvchi yaratildi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head"><div><p className="eyebrow">{item?.id ? 'USER TAHRIRI' : 'YANGI USER'}</p><h3>Foydalanuvchi ruxsatlari</h3></div><button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button></div>
        <div className="form-grid">
          <label>Username<input required value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /></label>
          {!item?.id && <label>Parol<input required minLength="8" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>}
          <label>Ism<input value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} /></label>
          <label>Familiya<input value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} /></label>
          <label>Rol<select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}><option value="OPERATOR">Operator</option><option value="ACCOUNTANT">Accountant</option><option value="MANAGEMENT">Management</option></select></label>
          <label>Telefon<input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
          <label>Telegram ID<input value={form.telegram_id} onChange={(event) => setForm({ ...form, telegram_id: event.target.value })} /></label>
          <label className="check-field"><input type="checkbox" checked={form.can_view_clients} onChange={(event) => setForm({ ...form, can_view_clients: event.target.checked })} />Mijozlarni ko‘rish</label>
          <label className="check-field"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />Faol</label>
        </div>
        <div className="editor-actions"><button type="button" className="secondary-button" onClick={close}>Bekor qilish</button><button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}</button></div>
      </form>
    </div>
  )
}

function StockInEditor({ item, close, done, notify }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ quantity: '', warehouse_location: '', asos: '', contract_number: '', faktura: '' })
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = { ...form, quantity: Number(form.quantity) }
      Object.keys(payload).forEach((key) => { if (payload[key] === '') delete payload[key] })
      await api.addStock(item.id, payload)
      notify('Kirim muvaffaqiyatli rasmiylashtirildi.', 'success')
      done()
    } catch (err) { notify(err.message) } finally { setSaving(false) }
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head"><div><p className="eyebrow">OMBOR KIRIMI</p><h3>{item.name}</h3></div><button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button></div>
        <div className="form-grid">
          <label>Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label>
          <label>Ombordagi joy<input value={form.warehouse_location} onChange={(event) => setForm({ ...form, warehouse_location: event.target.value })} placeholder="Asosiy ombor" /></label>
          <label>Shartnoma raqami<input value={form.contract_number} onChange={(event) => setForm({ ...form, contract_number: event.target.value })} /></label>
          <label>Faktura<input value={form.faktura} onChange={(event) => setForm({ ...form, faktura: event.target.value })} /></label>
          <label className="full-width">Asos<input required value={form.asos} onChange={(event) => setForm({ ...form, asos: event.target.value })} placeholder="Masalan, kirim orderi №77" /></label>
        </div>
        <div className="editor-actions"><button type="button" className="secondary-button" onClick={close}>Bekor qilish</button><button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Kirim qilish'}</button></div>
      </form>
    </div>
  )
}

function PaymentEditor({ item, close, done, notify }) {
  const [amount, setAmount] = useState(item.remaining || '')
  const [comment, setComment] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await api.pay(item.id, { amount, comment })
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head">
          <div><p className="eyebrow">TO‘LOV QABUL QILISH</p><h3>{item.client_name || 'Hisob'} uchun to‘lov</h3></div>
          <button type="button" className="icon-button" onClick={close}><X size={20} /></button>
        </div>
        <p className="muted">Qolgan summa: <b>{money(item.remaining)} {item.currency}</b></p>
        <div className="form-grid">
          <label>Qabul qilinadigan summa<input required min="0.01" max={item.remaining} type="number" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
          <label>Izoh<input value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Masalan, ikkinchi to‘lov" /></label>
        </div>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'To‘lovni qabul qilish'}</button>
        </div>
      </form>
    </div>
  )
}

export default App
