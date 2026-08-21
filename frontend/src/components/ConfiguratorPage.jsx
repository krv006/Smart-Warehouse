import { useEffect, useMemo, useState } from 'react'
import { Plus, SpinnerGap, Trash, X } from '@phosphor-icons/react'
import { api } from '../api'
import DataTable from './DataTable'
import { formatDateUz, list, money } from '../lib/utils'

const productLabel = (product) => {
  if (!product) return '—'
  const serial = (product.serial_number || '').trim()
  return serial ? `${product.name} · raqam: ${serial}` : product.name
}

function emptyRow() {
  return { key: Math.random().toString(36).slice(2), product: '', quantity: '1', unit_price: '' }
}

function ConfigurationBuilder({ item, products, clients, close, done, notify }) {
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState(item?.name || '')
  const [clientId, setClientId] = useState(item?.client || '')
  const [comment, setComment] = useState(item?.comment || '')
  const [rows, setRows] = useState(() => {
    if (item?.items?.length) {
      return item.items.map((row) => ({
        key: String(row.id), product: String(row.product), quantity: String(row.quantity),
        unit_price: row.unit_price != null ? String(row.unit_price) : '',
      }))
    }
    return [emptyRow()]
  })

  const productById = useMemo(() => Object.fromEntries(products.map((p) => [String(p.id), p])), [products])

  const total = rows.reduce((sum, row) => {
    const product = productById[row.product]
    const unitPrice = row.unit_price !== '' ? Number(row.unit_price) : Number(product?.selling_price || 0)
    return sum + unitPrice * Number(row.quantity || 0)
  }, 0)

  const updateRow = (key, patch) => setRows((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  const removeRow = (key) => setRows((prev) => (prev.length > 1 ? prev.filter((row) => row.key !== key) : prev))
  const addRow = () => setRows((prev) => [...prev, emptyRow()])

  const submit = async (event) => {
    event.preventDefault()
    const validRows = rows.filter((row) => row.product)
    if (!validRows.length) {
      notify('Kamida bitta mahsulot tanlang.')
      return
    }
    setSaving(true)
    try {
      const payload = {
        name,
        client: clientId || null,
        comment: comment || '',
        items: validRows.map((row) => ({
          product: Number(row.product),
          quantity: Number(row.quantity || 1),
          ...(row.unit_price !== '' ? { unit_price: row.unit_price } : {}),
        })),
      }
      if (item?.id) await api.update('/configurator/', item.id, payload)
      else await api.create('/configurator/', payload)
      notify('Konfiguratsiya saqlandi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor configurator-builder" onSubmit={submit}>
        <div className="editor-head">
          <div>
            <p className="eyebrow">KONFIGURATOR</p>
            <h3>{item?.id ? 'Konfiguratsiyani tahrirlash' : 'Yangi konfiguratsiya'}</h3>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={18} /></button>
        </div>
        <div className="form-grid">
          <label>Nomi<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Masalan: Mijoz X uchun server" /></label>
          <label>Mijoz
            <select value={clientId} onChange={(e) => setClientId(e.target.value)}>
              <option value="">— Mijozsiz —</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.company_name || c.full_name || `#${c.id}`}</option>)}
            </select>
          </label>
          <label className="full-width">Izoh<textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2} /></label>
        </div>

        <table className="configurator-items">
          <thead>
            <tr><th>Mahsulot</th><th>Miqdor</th><th>Narx (bo‘sh — joriy narx)</th><th>Jami</th><th /></tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const product = productById[row.product]
              const unitPrice = row.unit_price !== '' ? Number(row.unit_price) : Number(product?.selling_price || 0)
              const subtotal = unitPrice * Number(row.quantity || 0)
              return (
                <tr key={row.key}>
                  <td>
                    <select value={row.product} onChange={(e) => updateRow(row.key, { product: e.target.value })}>
                      <option value="">Tanlang</option>
                      {products.map((p) => <option key={p.id} value={p.id}>{productLabel(p)}</option>)}
                    </select>
                  </td>
                  <td><input type="number" min="1" value={row.quantity} onChange={(e) => updateRow(row.key, { quantity: e.target.value })} /></td>
                  <td><input type="number" min="0" step="0.01" value={row.unit_price} onChange={(e) => updateRow(row.key, { unit_price: e.target.value })} placeholder={product?.selling_price ? money(product.selling_price) : ''} /></td>
                  <td>{money(subtotal)}</td>
                  <td><button type="button" className="icon-button" onClick={() => removeRow(row.key)}><Trash size={16} /></button></td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <button type="button" className="secondary-button" onClick={addRow}><Plus size={16} /> Qator qo‘shish</button>

        <p className="configurator-total">Jami narx: <b>{money(total)} so‘m</b></p>

        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}</button>
        </div>
      </form>
    </div>
  )
}

export default function ConfiguratorPage({ notify, session, reloadKey = 0 }) {
  const [items, setItems] = useState([])
  const [products, setProducts] = useState([])
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)
  const [creating, setCreating] = useState(false)
  const [refreshTick, setRefreshTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    async function run() {
      setLoading(true)
      try {
        const [configData, productData, clientData] = await Promise.all([
          api.configurations(),
          api.products({ page_size: 200 }),
          api.clients({ page_size: 200 }),
        ])
        if (cancelled) return
        setItems(list(configData))
        setProducts(list(productData))
        setClients(list(clientData))
      } catch (err) {
        if (!cancelled) notify(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    run()
    return () => { cancelled = true }
  }, [reloadKey, refreshTick]) // eslint-disable-line react-hooks/exhaustive-deps

  const remove = async (row) => {
    if (!window.confirm('Konfiguratsiyani o‘chirishni tasdiqlaysizmi?')) return
    try {
      await api.remove('/configurator/', row.id)
      notify('O‘chirildi.', 'success')
      setItems((prev) => prev.filter((r) => r.id !== row.id))
    } catch (err) {
      notify(err.message)
    }
  }

  const columns = [
    { key: 'name', label: 'Nomi', render: (row) => row.name || `Konfiguratsiya #${row.id}` },
    { key: 'client', label: 'Mijoz', render: (row) => clients.find((c) => c.id === row.client)?.company_name || '—' },
    { key: 'items', label: 'Mahsulotlar soni', render: (row) => row.items?.length || 0 },
    { key: 'total', label: 'Jami narx', render: (row) => `${money(row.total)} so‘m` },
    { key: 'created_by_name', label: 'Yaratdi' },
    { key: 'created_at', label: 'Sana', render: (row) => formatDateUz(row.created_at) },
  ]

  return (
    <div className="page configurator-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">KONFIGURATOR</p>
          <h1>Konfigurator</h1>
          <p className="muted">Bazadagi mavjud tovarlardan server/to‘plam yig‘ing va jami narxini ko‘ring.</p>
        </div>
        <button className="primary-button" onClick={() => setCreating(true)}><Plus size={18} /> Yangi konfiguratsiya</button>
      </div>

      <DataTable
        columns={columns}
        rows={items}
        loading={loading}
        emptyLabel="Hali konfiguratsiya yaratilmagan."
        onRowClick={(row) => setEditing(row)}
        renderActions={(row) => (
          <button type="button" className="icon-button" onClick={(e) => { e.stopPropagation(); remove(row) }}>
            <Trash size={16} />
          </button>
        )}
      />

      {(creating || editing) && (
        <ConfigurationBuilder
          item={editing}
          products={products}
          clients={clients}
          close={() => { setCreating(false); setEditing(null) }}
          done={() => { setCreating(false); setEditing(null); setRefreshTick((n) => n + 1) }}
          notify={notify}
        />
      )}
    </div>
  )
}
