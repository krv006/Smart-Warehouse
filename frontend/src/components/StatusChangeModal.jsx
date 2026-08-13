import { useState } from 'react'
import { SpinnerGap, X } from '@phosphor-icons/react'
import FieldError from './FieldError'

const IMPORT_STATUS_LABELS = {
  new: 'Yangi',
  confirmed: 'Tasdiqlandi',
  ordered: 'Etkazuvchiga yuborildi',
  received: 'Qabul qilindi',
  cancelled: 'Bekor qilindi',
}

const ORDER_ACTION_LABELS = {
  fulfilled: 'Yetkazildi',
  cancelled: 'Bekor qilindi',
}

export default function StatusChangeModal({
  mode,
  rows = [],
  targetStatus: initialTarget,
  onClose,
  onSubmit,
}) {
  const first = rows[0] || {}
  const [targetStatus, setTargetStatus] = useState(initialTarget || first.status || 'confirmed')
  const [form, setForm] = useState({
    contract_number: first.contract_number || '',
    faktura: first.faktura || '',
    asos: '',
    received_qty: first.received_qty ?? first.quantity ?? '',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const isImport = mode === 'import'
  const isOrder = mode === 'order'
  const statusLabel = isImport
    ? IMPORT_STATUS_LABELS[targetStatus] || targetStatus
    : ORDER_ACTION_LABELS[targetStatus] || targetStatus

  const needsContract = isImport && ['confirmed', 'ordered', 'received'].includes(targetStatus)
  const needsFaktura = isImport && targetStatus === 'received'
  const needsReceivedQty = isImport && targetStatus === 'received'

  const validate = () => {
    const next = {}
    if (!form.asos.trim()) next.asos = 'Asos (izoh) kiritilishi shart'
    if ((needsContract || isOrder) && !form.contract_number.trim()) {
      next.contract_number = 'Shartnoma raqami kiritilishi shart'
    }
    if (needsFaktura && !form.faktura.trim()) next.faktura = 'Faktura kiritilishi shart'
    if (needsReceivedQty && !Number(form.received_qty)) next.received_qty = 'Qabul miqdori kiritilishi shart'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      await onSubmit({
        targetStatus,
        contract_number: form.contract_number.trim(),
        faktura: form.faktura.trim(),
        asos: form.asos.trim(),
        received_qty: Number(form.received_qty || 0),
      })
      onClose()
    } catch (err) {
      setErrors({ form: err.message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor status-change-modal" onSubmit={submit}>
        <div className="editor-head">
          <div>
            <p className="eyebrow">STATUS O‘ZGARTIRISH</p>
            <h3>
              {rows.length > 1
                ? `${rows.length} ta yozuv → ${statusLabel}`
                : `${statusLabel} holatiga o‘tkazish`}
            </h3>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Yopish">
            <X size={20} />
          </button>
        </div>
        <div className="form-grid">
          {mode === 'import' && rows.length > 1 && (
            <label>
              Yangi status
              <select value={targetStatus} onChange={(event) => setTargetStatus(event.target.value)}>
                <option value="confirmed">Tasdiqlandi</option>
                <option value="ordered">Etkazuvchiga yuborildi</option>
                <option value="received">Qabul qilindi</option>
                <option value="cancelled">Bekor qilindi</option>
              </select>
            </label>
          )}
          {(needsContract || isOrder) && (
            <label>
              Shartnoma raqami
              <input
                value={form.contract_number}
                onChange={(event) => setForm({ ...form, contract_number: event.target.value })}
              />
              <FieldError message={errors.contract_number} />
            </label>
          )}
          {needsFaktura && (
            <label>
              Faktura
              <input
                value={form.faktura}
                onChange={(event) => setForm({ ...form, faktura: event.target.value })}
              />
              <FieldError message={errors.faktura} />
            </label>
          )}
          {needsReceivedQty && (
            <label>
              Qabul miqdori
              <input
                type="number"
                min="1"
                value={form.received_qty}
                onChange={(event) => setForm({ ...form, received_qty: event.target.value })}
              />
              <FieldError message={errors.received_qty} />
            </label>
          )}
          <label className="full-width">
            Asos (izoh)
            <textarea
              rows="3"
              value={form.asos}
              onChange={(event) => setForm({ ...form, asos: event.target.value })}
              placeholder="Nima uchun status o‘zgartirilayotganini yozing"
            />
            <FieldError message={errors.asos} />
          </label>
          <FieldError message={errors.form} />
        </div>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={onClose}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>
            {saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}
          </button>
        </div>
      </form>
    </div>
  )
}

export function InlineStatusSelect({
  value,
  options,
  disabled,
  onChange,
}) {
  return (
    <select
      className="inline-status-select"
      value={value}
      disabled={disabled}
      onClick={(event) => event.stopPropagation()}
      onChange={(event) => {
        event.stopPropagation()
        onChange(event.target.value)
      }}
    >
      {options.map((item) => (
        <option key={item.value} value={item.value}>{item.label}</option>
      ))}
    </select>
  )
}
