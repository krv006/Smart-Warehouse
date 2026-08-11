import { TrendDown, TrendUp } from '@phosphor-icons/react'

export default function Metric({ icon: Icon, label, value, note, trend }) {
  return (
    <article className="metric">
      <span className={`metric-icon${trend === 'down' ? ' down' : trend === 'neutral' ? ' neutral' : ''}`}>
        <Icon size={22} weight="duotone" />
      </span>
      <div>
        <p>{label}</p>
        <h2 className="kpi-value">{value}</h2>
        {note && (
          <small>
            {trend === 'up' && <TrendUp size={14} />}
            {trend === 'down' && <TrendDown size={14} />}
            {note}
          </small>
        )}
      </div>
    </article>
  )
}
