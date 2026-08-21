import { useEffect, useState } from 'react'
import { Check, SpinnerGap, X } from '@phosphor-icons/react'
import { api } from '../api'
import DataTable from './DataTable'
import StatusBadge from './StatusBadge'
import { can } from '../lib/permissions'
import { formatDateUz, list } from '../lib/utils'

const STATUS_BADGES = {
  pending: { label: 'Kutilmoqda', tone: 'warning' },
  approved: { label: 'Tasdiqlandi', tone: 'success' },
  rejected: { label: 'Rad etildi', tone: 'danger' },
}

const KIND_LABELS = {
  client_create: 'Yangi mijoz',
  client_update: 'Mijoz tahriri',
  expense_create: 'Yangi xarajat',
  expense_update: 'Xarajat tahriri',
}

function RejectPrompt({ item, close, done, notify }) {
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (!note.trim()) {
      notify('Rad etish sababi majburiy.')
      return
    }
    setSaving(true)
    try {
      await api.pendingChangeReject(item.id, note.trim())
      notify('Rad etildi.', 'success')
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
            <p className="eyebrow">TASDIQLASH</p>
            <h3>Rad etish sababi</h3>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={18} /></button>
        </div>
        <label>Izoh<textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} required /></label>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Rad etish'}</button>
        </div>
      </form>
    </div>
  )
}

export default function ApprovalsPage({ notify, session, reloadKey = 0 }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [rejecting, setRejecting] = useState(null)
  const [tick, setTick] = useState(0)
  const canManage = can(session, 'approvals_manage')

  useEffect(() => {
    let cancelled = false
    async function run() {
      setLoading(true)
      try {
        const data = await api.pendingChanges()
        if (!cancelled) setItems(list(data))
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

  const approve = async (row) => {
    try {
      await api.pendingChangeApprove(row.id)
      notify('Tasdiqlandi.', 'success')
      refresh()
    } catch (err) {
      notify(err.message)
    }
  }

  const columns = [
    { key: 'kind', label: 'Turi', render: (row) => KIND_LABELS[row.kind] || row.kind },
    { key: 'summary', label: 'Tavsif' },
    { key: 'requested_by_name', label: 'Kim yubordi' },
    { key: 'status', label: 'Holati', render: (row) => <StatusBadge status={row.status} label={STATUS_BADGES[row.status]?.label} tone={STATUS_BADGES[row.status]?.tone} /> },
    { key: 'created_at', label: 'Sana', render: (row) => formatDateUz(row.created_at) },
  ]

  return (
    <div className="page approvals-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">TASDIQLASH</p>
          <h1>Buxgalter o‘zgarishlari</h1>
          <p className="muted">
            {canManage
              ? 'Buxgalter kiritgan yangi mijoz/xarajat yozuvlari — kuchga kirishi uchun tasdiqlang.'
              : 'Siz yuborgan o‘zgarishlar va ularning holati.'}
          </p>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={items}
        loading={loading}
        emptyLabel="Tasdiqlash kutayotgan o‘zgarish yo‘q."
        renderActions={canManage ? (row) => (
          row.status === 'pending' && (
            <div className="booking-actions">
              <button type="button" className="icon-button" title="Tasdiqlash" onClick={() => approve(row)}>
                <Check size={16} />
              </button>
              <button type="button" className="icon-button" title="Rad etish" onClick={() => setRejecting(row)}>
                <X size={16} />
              </button>
            </div>
          )
        ) : undefined}
      />

      {rejecting && (
        <RejectPrompt
          item={rejecting}
          close={() => setRejecting(null)}
          done={() => { setRejecting(null); refresh() }}
          notify={notify}
        />
      )}
    </div>
  )
}
