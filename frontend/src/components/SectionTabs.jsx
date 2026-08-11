import { NAV_GROUPS } from '../lib/constants'
import { can } from '../lib/permissions'

export default function SectionTabs({ groupKey, active, onSelect, session }) {
  const tabs = NAV_GROUPS[groupKey]?.filter((tab) => can(session, tab.ability)) || []
  if (tabs.length < 2) return null
  return (
    <div className="section-tabs" role="tablist" aria-label={`${groupKey} bo‘limlari`}>
      {tabs.map((tab) => (
        <button
          key={tab.page}
          type="button"
          role="tab"
          aria-selected={active === tab.page}
          className={active === tab.page ? 'section-tab is-active' : 'section-tab'}
          onClick={() => onSelect(tab.page)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
