import { SpinnerGap, WarningCircle } from '@phosphor-icons/react'

export default function ConfirmDialog({
  title = 'Tasdiqlash',
  message,
  confirmLabel = 'Ha, o‘chirish',
  cancelLabel = 'Bekor qilish',
  tone = 'danger',
  loading = false,
  onConfirm,
  onCancel,
}) {
  return (
    <div className="modal-backdrop confirm-dialog-backdrop" role="presentation">
      <div className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-dialog-title">
        <div className={`confirm-dialog-icon confirm-dialog-icon--${tone}`}>
          <WarningCircle size={28} weight="fill" />
        </div>
        <h3 id="confirm-dialog-title">{title}</h3>
        {message && <p className="confirm-dialog-message">{message}</p>}
        <div className="confirm-dialog-actions">
          <button type="button" className="secondary-button" disabled={loading} onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={tone === 'danger' ? 'danger-button' : 'primary-button'}
            disabled={loading}
            onClick={onConfirm}
          >
            {loading ? <SpinnerGap size={18} className="spin" /> : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
