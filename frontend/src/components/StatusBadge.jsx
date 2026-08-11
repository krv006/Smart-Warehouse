export default function StatusBadge({ status, label, tone = 'neutral' }) {
  return (
    <span className={`status-badge status-badge--${tone}`} data-status={status}>
      {label || status}
    </span>
  )
}
