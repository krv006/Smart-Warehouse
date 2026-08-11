import { Package, Plus } from '@phosphor-icons/react'

export default function EmptyState({ label, ctaLabel, onCta }) {
  return (
    <div className="empty-state">
      <Package size={32} weight="thin" />
      <p>{label}</p>
      {ctaLabel && onCta && (
        <button type="button" className="primary-button empty-state-cta" onClick={onCta}>
          <Plus size={18} />
          {ctaLabel}
        </button>
      )}
    </div>
  )
}
