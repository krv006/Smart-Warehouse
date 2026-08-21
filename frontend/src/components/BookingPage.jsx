import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { ArrowsLeftRight, Bookmarks, Check, Clock, Plus, SpinnerGap, Trash, X } from '@phosphor-icons/react'
import { api } from '../api'
import DataTable from './DataTable'
import StatusBadge from './StatusBadge'
import { can } from '../lib/permissions'
import { formatDateUz, list } from '../lib/utils'

const STATUS_BADGES = {
  pending: { label: 'Kutilmoqda', tone: 'warning' },
  confirmed: { label: 'Tasdiqlangan', tone: 'success' },
  rejected: { label: 'Rad etildi', tone: 'danger' },
  cancelled: { label: 'Bekor qilindi', tone: 'neutral' },
}

const productLabel = (product) => {
  if (!product) return '—'
  const serial = (product.serial_number || '').trim()
  return serial ? `${product.name} · raqam: ${serial}` : product.name
}

function NewBookingForm({ products, close, done, notify }) {
  const [product, setProduct] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (!product) {
      notify('Mahsulot tanlang.')
      return
    }
    setSaving(true)
    try {
      await api.create('/orders/booking/', { product: Number(product), quantity: Number(quantity || 1) })
      notify('Bron so‘rovi yuborildi — tasdiqlash uchun Adminga bildirishnoma ketdi.', 'success')
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
          <div>
            <p className="eyebrow">BRON</p>
            <h3>Yangi bron so‘rovi</h3>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={18} /></button>
        </div>
        <div className="form-grid">
          <label>Mahsulot
            <select value={product} onChange={(e) => setProduct(e.target.value)} required>
              <option value="">Tanlang</option>
              {products.map((p) => <option key={p.id} value={p.id}>{productLabel(p)}</option>)}
            </select>
          </label>
          <label>Miqdor<input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} required /></label>
        </div>
        <p className="muted">Bron darhol ombordan band qilinadi — boshqa sotuvchi shu miqdordan ortiq band qila olmaydi. Admin tasdiqlashi kerak.</p>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Yuborish'}</button>
        </div>
      </form>
    </div>
  )
}

function ReassignPicker({ booking, salesUsers, close, done, notify }) {
  const [salesRep, setSalesRep] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (!salesRep) return
    setSaving(true)
    try {
      await api.bookingReassign(booking.id, Number(salesRep))
      notify('Bron boshqa sotuvchiga o‘tkazildi.', 'success')
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
          <div>
            <p className="eyebrow">BRON</p>
            <h3>Bronni boshqa sotuvchiga o‘tkazish</h3>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={18} /></button>
        </div>
        <label>Yangi sotuvchi
          <select value={salesRep} onChange={(e) => setSalesRep(e.target.value)} required>
            <option value="">Tanlang</option>
            {salesUsers.filter((u) => u.id !== booking.sales_rep).map((u) => (
              <option key={u.id} value={u.id}>{u.first_name || u.username}</option>
            ))}
          </select>
        </label>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving || !salesRep}>{saving ? <SpinnerGap size={18} className="spin" /> : 'O‘tkazish'}</button>
        </div>
      </form>
    </div>
  )
}

export default function BookingPage({ notify, session, reloadKey = 0 }) {
  const location = useLocation()
  const highlightBookingId = location.state?.highlightBookingId ?? null
  const [items, setItems] = useState([])
  const [products, setProducts] = useState([])
  const [salesUsers, setSalesUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [reassigning, setReassigning] = useState(null)
  const [tick, setTick] = useState(0)
  const isManagement = can(session, 'booking_manage')

  useEffect(() => {
    let cancelled = false
    async function run() {
      setLoading(true)
      try {
        const [bookingData, productData, userData] = await Promise.all([
          api.bookings(),
          api.products({ page_size: 200 }),
          isManagement ? api.users({ role: 'SALES', page_size: 100 }) : Promise.resolve([]),
        ])
        if (cancelled) return
        setItems(list(bookingData))
        setProducts(list(productData))
        setSalesUsers(list(userData))
      } catch (err) {
        if (!cancelled) notify(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    run()
    return () => { cancelled = true }
  }, [reloadKey, tick]) // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = () => setTick((n) => n + 1)

  const act = async (fn, successMessage) => {
    try {
      await fn()
      notify(successMessage, 'success')
      refresh()
    } catch (err) {
      notify(err.message)
    }
  }

  const cancelBooking = (row) => {
    if (!window.confirm('Bronni bekor qilishni tasdiqlaysizmi?')) return
    act(() => api.remove('/orders/booking/', row.id), 'Bron bekor qilindi.')
  }

  const columns = [
    { key: 'product_name', label: 'Mahsulot' },
    { key: 'quantity', label: 'Miqdor' },
    { key: 'sales_rep_name', label: 'Sotuvchi', render: (row) => row.sales_rep_name || `#${row.sales_rep}` },
    { key: 'status', label: 'Holati', render: (row) => <StatusBadge status={row.status} label={STATUS_BADGES[row.status]?.label} tone={STATUS_BADGES[row.status]?.tone} /> },
    { key: 'created_at', label: 'Sana', render: (row) => formatDateUz(row.created_at) },
  ]

  return (
    <div className="page booking-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">SOTUVCHILAR</p>
          <h1>Bron</h1>
          <p className="muted">
            {isManagement
              ? 'Barcha sotuvchilarning bron so‘rovlari — tasdiqlang, rad eting yoki boshqa sotuvchiga o‘tkazing.'
              : 'Sotuv qilishdan oldin mahsulotni band qilib qo‘ying — Admin tasdiqlashi kerak.'}
          </p>
        </div>
        <button className="primary-button" onClick={() => setCreating(true)}><Plus size={18} /> Yangi bron</button>
      </div>

      {!isManagement && (
        <section className="metric-grid">
          <article className="metric">
            <span className="metric-icon neutral"><Bookmarks size={22} weight="duotone" /></span>
            <div><p>Jami bronlarim</p><h2>{items.length}</h2></div>
          </article>
          <article className="metric">
            <span className="metric-icon up"><Clock size={22} weight="duotone" /></span>
            <div><p>Kutilmoqda</p><h2>{items.filter((r) => r.status === 'pending').length}</h2></div>
          </article>
          <article className="metric">
            <span className="metric-icon up"><Check size={22} weight="duotone" /></span>
            <div><p>Tasdiqlangan</p><h2>{items.filter((r) => r.status === 'confirmed').length}</h2></div>
          </article>
        </section>
      )}

      {highlightBookingId && !items.some((row) => row.id === highlightBookingId) && !loading && (
        <p className="muted">Bildirishnomadagi bron (#{highlightBookingId}) ro‘yxatda topilmadi — allaqachon boshqa xodimga o‘tkazilgan yoki o‘chirilgan bo‘lishi mumkin.</p>
      )}
      <DataTable
        columns={columns}
        rows={highlightBookingId ? [...items].sort((a, b) => (a.id === highlightBookingId ? -1 : b.id === highlightBookingId ? 1 : 0)) : items}
        rowClassName={(row) => (row.id === highlightBookingId ? 'is-selected' : '')}
        loading={loading}
        emptyLabel="Hali bron yo‘q."
        renderActions={(row) => (
          <div className="booking-actions">
            {isManagement && row.status === 'pending' && (
              <>
                <button type="button" className="icon-button" title="Tasdiqlash" onClick={() => act(() => api.bookingConfirm(row.id), 'Bron tasdiqlandi.')}>
                  <Check size={16} />
                </button>
                <button type="button" className="icon-button" title="Rad etish" onClick={() => act(() => api.bookingReject(row.id), 'Bron rad etildi.')}>
                  <X size={16} />
                </button>
              </>
            )}
            {isManagement && (row.status === 'pending' || row.status === 'confirmed') && (
              <button type="button" className="icon-button" title="Boshqa sotuvchiga o‘tkazish" onClick={() => setReassigning(row)}>
                <ArrowsLeftRight size={16} />
              </button>
            )}
            {(row.status === 'pending' || row.status === 'confirmed') && (
              <button type="button" className="icon-button" title="Bekor qilish" onClick={() => cancelBooking(row)}>
                <Trash size={16} />
              </button>
            )}
          </div>
        )}
      />

      {creating && (
        <NewBookingForm
          products={products}
          close={() => setCreating(false)}
          done={() => { setCreating(false); refresh() }}
          notify={notify}
        />
      )}
      {reassigning && (
        <ReassignPicker
          booking={reassigning}
          salesUsers={salesUsers}
          close={() => setReassigning(null)}
          done={() => { setReassigning(null); refresh() }}
          notify={notify}
        />
      )}
    </div>
  )
}
