import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Warehouse, Bell, Buildings, CaretDown, ChartLineUp,
  ClipboardText, CurrencyCircleDollar, DownloadSimple, FileText, Funnel, House, MagnifyingGlass,
  Package, PencilSimple, Plus, SignOut, SpinnerGap, Stack, Tag, TrendDown, TrendUp, Truck, UserGear, Users, WarningCircle, X, XCircle, DotsThree, CaretLeft, CaretRight,
} from '@phosphor-icons/react'
import { api, clearStoredSession, refreshAccessToken, saveSession, setAuthFailureHandler, tokenExpiresAt } from './api'

const navigation = [
  ['Bosh sahifa', House, 'dashboard'],
  ['Buyurtmalar', FileText, 'orders_view'],
  ['Zakazlar', Truck, 'procurement_view'],
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
const AUTO_REFRESH_MS = 30000
const workspace = 'Asosiy ombor'

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

function ToastStack({ toasts, dismiss }) {
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`} role="alert">
          <span className="toast-icon"><WarningCircle size={18} weight="fill" /></span>
          <div className="toast-body">
            <b>{toast.type === 'error' ? 'Xatolik' : toast.type === 'success' ? 'Muvaffaqiyatli' : 'Ogohlantirish'}</b>
            <span>{toast.message}</span>
          </div>
          <button type="button" className="toast-close" onClick={() => dismiss(toast.id)} aria-label="Yopish">
            <XCircle size={18} />
          </button>
        </div>
      ))}
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

  const notify = useCallback((message, type = 'error') => {
    const formatted = formatError(message)
    const key = `${type}:${formatted}`
    const now = Date.now()
    const lastSeen = recent.current.get(key) || 0
    if (now - lastSeen < 2000) return
    recent.current.set(key, now)
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, message: formatted, type }])
    const timer = setTimeout(() => dismiss(id), 5000)
    timers.current.set(id, timer)
  }, [dismiss])

  return { toasts, notify, dismiss }
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
  const { toasts, notify, dismiss } = useNotify()
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

  const loadDashboard = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const [summary, warehouse, cash, topProducts] = await api.reports()
      setDashboard({ summary, warehouse, cash, topProducts })
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [notify])

  useEffect(() => { if (session && can(session, 'dashboard')) loadDashboard() }, [session, loadDashboard])
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
      <ToastStack toasts={toasts} dismiss={dismiss} />
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
          <button key={label} onClick={() => navigate(label)} className={active === label ? 'nav-item is-active' : 'nav-item'}>
            <Icon size={19} weight={active === label ? 'fill' : 'regular'} />{label}
          </button>
        ))}</nav>
        <div className="sidebar-bottom"><button className="nav-item" onClick={logout}><SignOut size={19} />Chiqish</button></div>
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
            <button className="icon-button" aria-label="Qidiruv" onClick={() => navigate('Buyurtmalar')}><MagnifyingGlass size={20} /></button>
            <button className="icon-button notification" aria-label="Bildirishnomalar" onClick={() => {
              if (notificationPermission !== 'granted') requestNotifications()
              if (can(session, 'notifications_view')) navigate('Bildirishnomalar')
            }}><Bell size={20} /><i /></button>
            <ProfileDropdown session={session} onLogout={logout} />
          </div>
        </header>
        {active === 'Bosh sahifa' && can(session, 'dashboard') && <Dashboard data={dashboard} loading={loading && !dashboard} onCreateOrder={openOrderEditor} onNavigate={navigate} session={session} />}
        {active === 'Hisobotlar' && <ReportsPage notify={notify} />}
        {active !== 'Bosh sahifa' && active !== 'Hisobotlar' && <ResourcePage title={active} notify={notify} reloadKey={resourceReloadKey} session={session} />}
        {orderModalOpen && (
          <OrderEditor
            close={() => setOrderModalOpen(false)}
            done={() => {
              setOrderModalOpen(false)
              setResourceReloadKey((value) => value + 1)
              loadDashboard(true)
            }}
            notify={notify}
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
          <button key={label} onClick={() => navigate(label)} className={active === label ? 'bottom-nav-item is-active' : 'bottom-nav-item'}>
            <Icon size={22} weight={active === label ? 'fill' : 'regular'} />
            <span>{label}</span>
          </button>
        ))}
        {secondaryMobileNav.length > 0 && (
          <button onClick={() => setMobileMenuOpen((value) => !value)} className={mobileMenuOpen ? 'bottom-nav-item is-active' : 'bottom-nav-item'}>
            <DotsThree size={25} weight="bold" />
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
  const { toasts, notify, dismiss } = useNotify()

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
      <ToastStack toasts={toasts} dismiss={dismiss} />
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

function Dashboard({ data, loading, onCreateOrder, onNavigate, session }) {
  const summary = data?.summary || {}
  const warehouse = data?.warehouse || {}
  const cash = data?.cash || {}
  const products = data?.topProducts || []

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">BUGUNGI KO‘RINISH</p>
          <h1>Assalomu alaykum, ishlar nazoratda.</h1>
        </div>
        <div className="heading-actions">
          {can(session, 'orders_manage') && <button className="primary-button" onClick={onCreateOrder}><Plus size={18} />Yangi buyurtma</button>}
        </div>
      </div>
      <section className="metric-grid">
        <Metric icon={CurrencyCircleDollar} label="Bugungi tushum" value={`${money(summary.kassa_collected_uzs)} so‘m`} note="To‘langan hisoblar" trend="up" />
        <Metric icon={ClipboardText} label="Jami savdo" value={`${money(summary.sales_revenue_total)} so‘m`} note="Davr bo‘yicha" trend="up" />
        <Metric icon={Package} label="Ombordagi birliklar" value={money(warehouse.total_quantity)} note={`${warehouse.total_product_types || 0} turdagi mahsulot`} trend="neutral" />
        <Metric icon={FileText} label="Kechikkan to‘lovlar" value={summary.overdue_payments_count || 0} note="E’tibor talab qiladi" trend="down" />
      </section>
      <section className="dashboard-grid">
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
        <div className="data-panel cash-panel">
          <div className="panel-head">
            <div><p className="eyebrow">KASSA</p><h3>To‘lovlar holati</h3></div>
            <CurrencyCircleDollar size={25} weight="duotone" />
          </div>
          <div className="cash-total"><span>Qabul qilingan</span><b>{money(cash.sum_paid_uzs)} <small>so‘m</small></b></div>
          <div className="cash-status">
            <span><i className="status paid" />To‘langan <b>{cash.total_paid || 0}</b></span>
            <span><i className="status partial" />Qisman <b>{cash.total_partial || 0}</b></span>
            <span><i className="status overdue" />Kechikkan <b>{cash.total_overdue || 0}</b></span>
          </div>
        </div>
      </section>
      <section className="lower-grid">
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
        <div className="action-panel">
          <span className="action-icon"><FileText size={23} weight="duotone" /></span>
          <p className="eyebrow">TEZKOR AMAL</p>
          <h3>Yangi buyurtmani rasmiylashtiring</h3>
          <p>Mahsulotlarni tanlang va mijozga tegishli hujjatni bir necha qadamda yarating.</p>
          {can(session, 'orders_manage') && <button className="light-button" onClick={onCreateOrder}>Buyurtma yaratish <span>→</span></button>}
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
            <button className="secondary-button" disabled={exporting === 'sales'} onClick={() => exportFile('sales', api.exportSales)}><DownloadSimple size={17} />Sotuvlar</button>
            <button className="secondary-button" disabled={exporting === 'stock'} onClick={() => exportFile('stock', api.exportStock)}><DownloadSimple size={17} />Ombor</button>
            <button className="secondary-button" disabled={exporting === 'expenses'} onClick={() => exportFile('expenses', api.exportExpenses)}><DownloadSimple size={17} />Xarajatlar</button>
            <button className="secondary-button" disabled={exporting === 'payments'} onClick={() => exportFile('payments', api.exportPayments)}><DownloadSimple size={17} />To‘lovlar</button>
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
  'Zakazlar': { load: api.zakaz, path: '/orders/zakaz/' },
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
  if (title === 'Zakazlar') return row.product_name || `Zakaz #${row.id}`
  if (title === 'Qoldiqlar') return row.product_name || row.product || `Qoldiq #${row.id}`
  if (title === 'Foydalanuvchilar') return row.username
  return row.company_name || row.full_name || row.client_name || row.name || `Hujjat #${row.id}`
}

function rowMeta(title, row) {
  if (title === 'Shartnomalar') return [row.product_name, row.source_type_display, row.asos].filter(Boolean).join(' • ') || row.created_at || '—'
  if (title === 'Zakazlar') return [row.status_display || row.status, row.supplier, row.expected_date].filter(Boolean).join(' • ') || '—'
  if (title === 'Qoldiqlar') return [row.warehouse_location, `bron: ${row.reserved_quantity || 0}`].filter(Boolean).join(' • ')
  if (title === 'Foydalanuvchilar') return [row.role, row.is_active ? 'faol' : 'bloklangan'].filter(Boolean).join(' • ')
  if (title === 'Mijozlar') return [row.phone, row.passport_number, row.inn].filter(Boolean).join(' • ') || row.created_at || '—'
  return row.serial_number || row.status || row.phone || row.created_at || '—'
}

function rowValue(title, row) {
  if (title === 'Zakazlar') return row.total ? `${money(row.total)} ${row.currency || ''}` : `${row.quantity || 0} dona`
  if (title === 'Qoldiqlar') return `${row.quantity || 0} dona`
  if (title === 'Shartnomalar') return row.contract_date || '—'
  if (title === 'Foydalanuvchilar') return row.can_view_clients ? 'Mijoz: bor' : 'Mijoz: yo‘q'
  return row.total_amount ? `${money(row.total_amount)} so‘m` : (row.available_quantity ?? row.total ?? '—')
}

function ResourcePage({ title, notify, reloadKey = 0, session }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [editing, setEditing] = useState(null)
  const [opening, setOpening] = useState(false)
  const [paying, setPaying] = useState(null)
  const [orderAction, setOrderAction] = useState(null)
  const [stockProduct, setStockProduct] = useState(null)

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

  const manageAbilities = {
    'Buyurtmalar': 'orders_manage',
    'Zakazlar': 'procurement_manage',
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
  const canCreate = canManage && ['Mijozlar', 'Ombor', 'Buyurtmalar', 'Zakazlar', 'Kategoriyalar', 'Qoldiqlar', 'Sotuvlar', 'Xarajatlar', 'Foydalanuvchilar'].includes(title)

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
        </div>
        <div className="heading-actions">
          {title === 'Bildirishnomalar' && (
            <button className="secondary-button" onClick={handleMarkAllRead}>Hammasini o‘qilgan</button>
          )}
          {canCreate && <button className="primary-button" onClick={() => setEditing({})}><Plus size={18} />Yangi qo‘shish</button>}
        </div>
      </div>
      <section className="data-panel">
        <div className="panel-head">
          <div><p className="eyebrow">RO‘YXAT</p><h3>{rows.length} ta yozuv</h3></div>
          <form className="resource-search" onSubmit={handleSearch}>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Qidirish" aria-label={`${title} qidirish`} />
            <button type="submit" className="icon-button" aria-label="Qidirish"><MagnifyingGlass size={19} /></button>
          </form>
        </div>
        {loading && !rows.length ? <SkeletonRows /> : (
          <div className="product-list">
            {rows.map((row, index) => (
              <div className="product-row" key={row.id || index}>
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
                    <b>{rowValue(title, row)}</b>
                    <div className="row-actions">
                      {canManage && !resources[title].readonly && <button className="row-action" disabled={opening} onClick={() => handleEdit(row)} aria-label="Tahrirlash"><PencilSimple size={17} /></button>}
                      {can(session, 'orders_manage') && title === 'Buyurtmalar' && !['fulfilled', 'cancelled'].includes(row.status) && (
                        <>
                          <button className="row-action" onClick={() => setOrderAction({ row, action: 'fulfill' })}>Yetkazish</button>
                          <button className="row-action" onClick={() => setOrderAction({ row, action: 'cancel' })}>Bekor</button>
                          {Number(row.backorder_qty || 0) > 0 && <button className="row-action" onClick={() => setOrderAction({ row, action: 'zakaz' })}>Zakaz</button>}
                        </>
                      )}
                      {can(session, 'warehouse_manage') && title === 'Ombor' && <button className="row-action" onClick={() => setStockProduct(row)} aria-label="Kirim qilish">Kirim</button>}
                      {can(session, 'cash_manage') && title === 'Kassa' && row.remaining !== '0' && (
                        <button className="row-action" onClick={() => setPaying(row)} aria-label="To‘lov qabul qilish"><CurrencyCircleDollar size={17} /></button>
                      )}
                      {title === 'Ombor' && <button className="row-action" onClick={async () => {
                        try {
                          const rows = list(await api.productContracts(row.id))
                          notify(rows.length ? `${rows.length} ta shartnoma reestri yozuvi topildi.` : 'Bu mahsulotda shartnoma reestri yo‘q.', rows.length ? 'success' : 'warning')
                        } catch (err) { notify(err.message) }
                      }}>Reestr</button>}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
      {editing && (title === 'Buyurtmalar'
        ? <OrderEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); load() }} notify={notify} />
        : title === 'Zakazlar'
          ? <ZakazEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); load() }} notify={notify} />
        : title === 'Sotuvlar'
          ? <SaleEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); load() }} notify={notify} />
          : title === 'Foydalanuvchilar'
            ? <UserEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); load() }} notify={notify} />
          : title === 'Xarajatlar'
            ? <ExpenseEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); load() }} notify={notify} />
            : <Editor title={title} item={editing} path={resources[title].path} close={() => setEditing(null)} done={() => { setEditing(null); load() }} notify={notify} />
      )}
      {paying && <PaymentEditor item={paying} close={() => setPaying(null)} done={() => { setPaying(null); load() }} notify={notify} />}
      {orderAction && <OrderActionEditor item={orderAction.row} action={orderAction.action} close={() => setOrderAction(null)} done={() => { setOrderAction(null); load() }} notify={notify} />}
      {stockProduct && <StockInEditor item={stockProduct} close={() => setStockProduct(null)} done={() => { setStockProduct(null); load() }} notify={notify} />}
    </div>
  )
}

const fields = {
  Ombor: [['name', 'Mahsulot nomi', true], ['model', 'Model'], ['serial_number', 'Seriya raqami', true], ['source', 'Manba / yetkazuvchi'], ['min_quantity', 'Minimal qoldiq'], ['quantity', 'Boshlang‘ich miqdor'], ['warehouse_location', 'Ombordagi joy']],
  Kategoriyalar: [['name', 'Kategoriya nomi', true], ['parent', 'Parent ID']],
  Qoldiqlar: [['product', 'Mahsulot ID', true], ['quantity', 'Miqdor', true], ['reserved_quantity', 'Bron miqdor'], ['warehouse_location', 'Ombordagi joy', true]],
}

function Editor({ title, item, path, close, done, notify }) {
  const [form, setForm] = useState(() => ({ ...item, client_type: item?.client_type || 'individual' }))
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    const payload = Object.fromEntries(Object.entries(form).filter(([key, value]) => !['id', 'created_at', 'quantity_in_stock', 'available_quantity', 'reserved_quantity', 'stock_status', 'category_name'].includes(key) && value !== undefined && value !== ''))
    if (title === 'Ombor') {
      if (payload.min_quantity) payload.min_quantity = Number(payload.min_quantity)
      if (payload.quantity) payload.quantity = Number(payload.quantity)
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
        const fullName = [payload.last_name, payload.first_name, payload.middle_name].filter(Boolean).join(' ').trim()
        payload.full_name = fullName
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
                  <option value="individual">Fizik shaxs</option>
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
                  <label>Ism<input required value={form.first_name ?? ''} onChange={(event) => setForm({ ...form, first_name: event.target.value })} /></label>
                  <label>Familiya<input required value={form.last_name ?? ''} onChange={(event) => setForm({ ...form, last_name: event.target.value })} /></label>
                  <label>Otasining ismi<input required value={form.middle_name ?? ''} onChange={(event) => setForm({ ...form, middle_name: event.target.value })} /></label>
                  <label>PINFL<input required value={form.pinfl ?? ''} onChange={(event) => setForm({ ...form, pinfl: event.target.value })} /></label>
                  <label>Pasport raqami<input required value={form.passport_number ?? ''} onChange={(event) => setForm({ ...form, passport_number: event.target.value })} /></label>
                  <label>Telefon<input required value={form.phone ?? ''} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
                  <label>E-mail<input type="email" value={form.email ?? ''} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
                  <label>Manzil<input value={form.address ?? ''} onChange={(event) => setForm({ ...form, address: event.target.value })} /></label>
                  <label className="full-width">Izoh<textarea value={form.comment ?? ''} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
                </>
              )}
            </>
          ) : fields[title].map(([key, label, required]) => (
            <label key={key}>{label}
              <input required={required} value={form[key] ?? ''} type={key === 'email' ? 'email' : key === 'min_quantity' || key === 'quantity' ? 'number' : 'text'} onChange={(event) => setForm({ ...form, [key]: event.target.value })} />
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

function SaleEditor({ close, done, notify, item = null }) {
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
        sold_price: Number(form.sold_price || 0),
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
          items: items.filter((row) => row.product).map((row) => ({ product: Number(row.product), quantity: Number(row.quantity), sold_price: row.sold_price, comment: row.comment || '' })),
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
              <label>Mahsulot<select required value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })}><option value="">Mahsulotni tanlang</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number}</option>)}</select></label>
              <label>Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label>
              <label>Sotuv narxi<input required min="0" step="0.01" type="number" value={form.sold_price} onChange={(event) => setForm({ ...form, sold_price: event.target.value })} /></label>
            </>
          ) : (
            <div className="full-width line-items">
              <div className="line-head"><b>Mahsulotlar</b></div>
              {items.map((row, index) => (
                <div className="line-item" key={index}>
                  <select required value={row.product} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, product: event.target.value } : itemRow))}><option value="">Mahsulot</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number}</option>)}</select>
                  <input required min="1" type="number" value={row.quantity} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, quantity: event.target.value } : itemRow))} />
                  <input required min="0" step="0.01" type="number" placeholder="Narx" value={row.sold_price} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, sold_price: event.target.value } : itemRow))} />
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

function OrderEditor({ close, done, notify, item = null }) {
  const [clients, setClients] = useState([])
  const [products, setProducts] = useState([])
  const [saving, setSaving] = useState(false)
  const [file, setFile] = useState(null)
  const [form, setForm] = useState({ client: '', contract_number: '', contract_date: new Date().toISOString().slice(0, 10), due_date: '', prepaid_amount: '0', product: '', itemId: null, quantity: '1', unit_price: '', comment: '', asos: '' })
  const [items, setItems] = useState([{ product: '', quantity: '1', unit_price: '' }])

  const updateContractNumber = (value) => {
    setForm({ ...form, contract_number: value.replace(/[^\d/]/g, '') })
  }

  useEffect(() => {
    Promise.all([api.clients(), api.products()])
      .then(([clientData, productData]) => { setClients(list(clientData)); setProducts(list(productData)) })
      .catch((err) => notify(err.message))
  }, [notify])

  useEffect(() => {
    if (!item) {
      setForm({ client: '', contract_number: '', contract_date: new Date().toISOString().slice(0, 10), due_date: '', prepaid_amount: '0', product: '', itemId: null, quantity: '1', unit_price: '', comment: '', asos: '' })
      setItems([{ product: '', quantity: '1', unit_price: '' }])
      return
    }
    setForm({
      client: item.client || '',
      contract_number: item.contract_number || '',
      contract_date: item.contract_date || new Date().toISOString().slice(0, 10),
      due_date: item.due_date || '',
      prepaid_amount: item.prepaid_amount ?? '0',
      product: item.items?.[0]?.product || '',
      itemId: item.items?.[0]?.id || null,
      quantity: item.items?.[0]?.quantity || '1',
      unit_price: item.items?.[0]?.unit_price || '',
      comment: item.comment || '',
      asos: '',
    })
  }, [item])

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
          prepaid_amount: Number(form.prepaid_amount || 0),
          comment: form.comment || '',
          asos: form.asos,
        }
        if (form.itemId) {
          payload.items = [{ id: form.itemId, quantity: Number(form.quantity) }]
          if (form.unit_price !== '') payload.items[0].unit_price = form.unit_price
        }
        await api.update('/orders/', item.id, payload)
        notify('Buyurtma yangilandi.', 'success')
      } else {
        const payload = new FormData()
        if (form.client) payload.append('client', form.client)
        if (form.contract_number) payload.append('contract_number', form.contract_number)
        if (form.contract_date) payload.append('contract_date', form.contract_date)
        if (form.due_date) payload.append('due_date', form.due_date)
        payload.append('prepaid_amount', form.prepaid_amount || '0')
        payload.append('comment', form.comment || '')
        payload.append('items', JSON.stringify(items.filter((row) => row.product).map((row) => ({ product: Number(row.product), quantity: Number(row.quantity), unit_price: row.unit_price || null }))))
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
          <label>Shartnoma sanasi<input type="date" value={form.contract_date} onChange={(event) => setForm({ ...form, contract_date: event.target.value })} /></label>
          {item?.id ? (
            <>
              <label>Mahsulot<select required value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })}><option value="">Mahsulotni tanlang</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number}</option>)}</select></label>
              <label>Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label>
              <label>Birlik narxi<input type="number" min="0" step="0.01" value={form.unit_price} onChange={(event) => setForm({ ...form, unit_price: event.target.value })} /></label>
            </>
          ) : (
            <div className="full-width line-items">
              <div className="line-head"><b>Mahsulotlar</b></div>
              {items.map((row, index) => (
                <div className="line-item" key={index}>
                  <select required value={row.product} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, product: event.target.value } : itemRow))}><option value="">Mahsulot</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number}</option>)}</select>
                  <input required min="1" type="number" value={row.quantity} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, quantity: event.target.value } : itemRow))} />
                  <input type="number" min="0" step="0.01" placeholder="Birlik narxi" value={row.unit_price} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, unit_price: event.target.value } : itemRow))} />
                  <button type="button" className="row-action" disabled={items.length === 1} onClick={() => setItems(items.filter((_, i) => i !== index))}>O‘chirish</button>
                </div>
              ))}
              <button type="button" className="secondary-button add-line-button" onClick={() => setItems([...items, { product: '', quantity: '1', unit_price: '' }])}><Plus size={16} />Mahsulot qo‘shish</button>
            </div>
          )}
          <label>Oldindan to‘lov<input type="number" min="0" step="0.01" value={form.prepaid_amount} onChange={(event) => setForm({ ...form, prepaid_amount: event.target.value })} /></label>
          <label>Yetkazish muddati<input type="date" value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} /></label>
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
  const labels = { fulfill: 'Yetkazib berish', cancel: 'Buyurtmani bekor qilish', zakaz: 'Zakaz yaratish' }

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

function ZakazEditor({ close, done, notify, item = null }) {
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
      if (item?.id) await api.update('/orders/zakaz/', item.id, payload)
      else await api.create('/orders/zakaz/', payload)
      notify(item?.id ? 'Zakaz yangilandi.' : 'Zakaz yaratildi.', 'success')
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
        <div className="editor-head"><div><p className="eyebrow">{item?.id ? 'ZAKAZ TAHRIRI' : 'YANGI ZAKAZ'}</p><h3>Yetkazuvchidan buyurtma</h3></div><button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button></div>
        <div className="form-grid">
          <label>Mahsulot<select required disabled={Boolean(item?.order_contract)} value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })}><option value="">Mahsulotni tanlang</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number}</option>)}</select></label>
          <label>Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label>
          <label>Qabul qilingan<input min="0" type="number" value={form.received_qty} onChange={(event) => setForm({ ...form, received_qty: event.target.value })} /></label>
          <label>Narx<input required={!item?.id} min="0" step="0.01" type="number" value={form.unit_price} onChange={(event) => setForm({ ...form, unit_price: event.target.value })} /></label>
          <label>Valyuta<select value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })}><option value="UZS">UZS</option><option value="USD">USD</option></select></label>
          <label>Status<select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="new">Yangi</option><option value="confirmed">Tasdiqlandi</option><option value="received">Qabul qilindi</option><option value="cancelled">Bekor qilindi</option></select></label>
          <label>To‘lov statusi<select value={form.payment_status} onChange={(event) => setForm({ ...form, payment_status: event.target.value })}><option value="unpaid">To‘lanmagan</option><option value="partial">Qisman</option><option value="paid">To‘langan</option></select></label>
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
