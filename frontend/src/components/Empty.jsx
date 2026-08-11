import { Package } from '@phosphor-icons/react'

export default function Empty({ label }) {
  return (
    <div className="empty">
      <Package size={24} weight="thin" />
      <span>{label}</span>
    </div>
  )
}
