import { useEffect, useMemo, useRef, useState } from 'react'
import { CaretDown, CaretLeft, CaretRight } from '@phosphor-icons/react'
import { todayValue } from '../lib/utils'

const CALENDAR_WEEKDAYS = ['Du', 'Se', 'Cho', 'Pa', 'Ju', 'Sha', 'Ya']
const UZBEK_MONTHS = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr']
const CALENDAR_YEAR_SPAN = 10

function calendarYearOptions(centerYear = new Date().getFullYear()) {
  const years = []
  for (let year = centerYear - CALENDAR_YEAR_SPAN; year <= centerYear + CALENDAR_YEAR_SPAN; year += 1) {
    years.push(year)
  }
  return years
}

function parseIsoDate(value) {
  if (!value) return null
  const [y, m, d] = value.split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

function toIsoDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function buildMonthGrid(viewYear, viewMonth) {
  const startOffset = (new Date(viewYear, viewMonth, 1).getDay() + 6) % 7
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()
  const cells = []
  for (let i = 0; i < startOffset; i += 1) {
    const d = new Date(viewYear, viewMonth, i - startOffset + 1)
    cells.push({ date: d, inMonth: false, iso: toIsoDate(d) })
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    const d = new Date(viewYear, viewMonth, day)
    cells.push({ date: d, inMonth: true, iso: toIsoDate(d) })
  }
  while (cells.length % 7 !== 0) {
    const d = new Date(cells[cells.length - 1].date)
    d.setDate(d.getDate() + 1)
    cells.push({ date: d, inMonth: false, iso: toIsoDate(d) })
  }
  return cells
}

export default function FilterDateRangeCalendar({
  dateFrom,
  dateTo,
  onChange,
  label = 'Davr',
  className = '',
  disabled = false,
}) {
  const [viewDate, setViewDate] = useState(() => parseIsoDate(dateFrom) || new Date())
  const [pickPhase, setPickPhase] = useState('start')
  const [anchor, setAnchor] = useState(null)
  const [yearDropdownOpen, setYearDropdownOpen] = useState(false)
  const yearDropdownRef = useRef(null)

  useEffect(() => {
    const parsed = parseIsoDate(dateFrom)
    if (parsed) setViewDate(parsed)
  }, [dateFrom])

  useEffect(() => {
    if (!yearDropdownOpen) return undefined
    const handleClickOutside = (event) => {
      if (yearDropdownRef.current && !yearDropdownRef.current.contains(event.target)) {
        setYearDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [yearDropdownOpen])

  const viewYear = viewDate.getFullYear()
  const viewMonth = viewDate.getMonth()
  const yearOptions = useMemo(() => calendarYearOptions(new Date().getFullYear()), [])
  const cells = useMemo(() => buildMonthGrid(viewYear, viewMonth), [viewYear, viewMonth])
  const todayIso = todayValue()

  const highlightFrom = dateFrom
  const highlightTo = dateTo
  const rangeLabel = dateFrom && dateTo
    ? (dateFrom === dateTo ? dateFrom : `${dateFrom} — ${dateTo}`)
    : 'Sanani tanlang'

  const handleDayClick = (iso) => {
    if (disabled) return
    if (pickPhase === 'start') {
      setAnchor(iso)
      setPickPhase('end')
      onChange({ date_from: iso, date_to: iso })
      return
    }
    let from = anchor || dateFrom
    let to = iso
    if (from > to) [from, to] = [to, from]
    setPickPhase('start')
    setAnchor(null)
    onChange({ date_from: from, date_to: to })
  }

  return (
    <div className={`filter-calendar filter-date-range-calendar ${className}`.trim()} role="group" aria-label={label}>
      <div className="filter-calendar-header">
        <span className="filter-calendar-label">{label}</span>
        <span className="filter-calendar-value">{rangeLabel}</span>
      </div>
      <div className={`filter-calendar-widget${disabled ? ' is-disabled' : ''}`}>
        <div className="filter-calendar-nav">
          <button type="button" className="filter-calendar-nav-btn" disabled={disabled} onClick={() => setViewDate(new Date(viewYear, viewMonth - 1, 1))} aria-label="Oldingi oy">
            <CaretLeft size={16} />
          </button>
          <div className="filter-calendar-nav-title">
            <span className="filter-calendar-month-name">{UZBEK_MONTHS[viewMonth]}</span>
            <div className="filter-calendar-year-wrap" ref={yearDropdownRef}>
              <button
                type="button"
                className="filter-calendar-year-btn"
                disabled={disabled}
                onClick={() => setYearDropdownOpen((open) => !open)}
                aria-expanded={yearDropdownOpen}
                aria-haspopup="listbox"
                aria-label={`Yil: ${viewYear}`}
              >
                {viewYear}
                <CaretDown size={12} aria-hidden="true" />
              </button>
              {yearDropdownOpen && (
                <ul className="filter-calendar-year-dropdown" role="listbox" aria-label="Yilni tanlang">
                  {yearOptions.map((year) => (
                    <li key={year}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={year === viewYear}
                        className={year === viewYear ? 'is-active' : undefined}
                        onClick={() => {
                          setViewDate(new Date(year, viewMonth, 1))
                          setYearDropdownOpen(false)
                        }}
                      >
                        {year}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <button type="button" className="filter-calendar-nav-btn" disabled={disabled} onClick={() => setViewDate(new Date(viewYear, viewMonth + 1, 1))} aria-label="Keyingi oy">
            <CaretRight size={16} />
          </button>
        </div>
        <div className="filter-calendar-weekdays" aria-hidden="true">
          {CALENDAR_WEEKDAYS.map((day) => (
            <span key={day} className="filter-calendar-weekday">{day}</span>
          ))}
        </div>
        <div className="filter-calendar-days" role="grid">
          {cells.map((cell) => {
            const isStart = highlightFrom === cell.iso
            const isEnd = highlightTo === cell.iso
            const isInRange = highlightFrom && highlightTo
              && cell.iso > highlightFrom && cell.iso < highlightTo
            const isToday = cell.iso === todayIso
            return (
              <button
                key={cell.iso}
                type="button"
                role="gridcell"
                disabled={disabled}
                className={[
                  'filter-calendar-day',
                  !cell.inMonth && 'is-outside',
                  isInRange && 'is-in-range',
                  isStart && 'is-range-start',
                  isEnd && 'is-range-end',
                  (isStart || isEnd) && 'is-selected',
                  isToday && 'is-today',
                ].filter(Boolean).join(' ')}
                onClick={() => handleDayClick(cell.iso)}
                aria-label={cell.iso}
                aria-selected={isStart || isEnd}
              >
                {cell.date.getDate()}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
