import { useCallback, useMemo, useState } from 'react'
import {
  ClipboardText,
  CurrencyCircleDollar,
  DownloadSimple,
  Package,
  SpinnerGap,
  TrendUp,
  Truck,
} from '@phosphor-icons/react'
import { api } from '../api'
import { todayValue } from '../lib/utils'
import FilterDateRangeCalendar from './FilterDateRangeCalendar'

const REPORT_TYPES = [
  { id: 'sales', label: 'Sotuvlar', icon: TrendUp, hasPeriod: true, hint: 'Sotuv sanasi bo‘yicha filtrlanadi.' },
  { id: 'kassa', label: 'Kassa', icon: CurrencyCircleDollar, hasPeriod: true, hint: 'Tushum va kirim chiqimlari bir jadvalda.' },
  { id: 'import', label: 'Kirim', icon: Truck, hasPeriod: true, hint: 'Chet eldan kelgan mustaqil zakazlar.' },
  { id: 'expenses', label: 'Xarajatlar', icon: ClipboardText, hasPeriod: true, hint: 'Rasxod sanasi bo‘yicha.' },
  { id: 'stock', label: 'Ombor holati', icon: Package, hasPeriod: false, hint: 'Joriy qoldiqlar — davr tanlanmaydi.' },
]

const PERIOD_PRESETS = [
  { id: 'all', label: 'Barcha davr' },
  { id: 'this_month', label: 'Joriy oy' },
  { id: 'last_month', label: 'O‘tgan oy' },
  { id: 'this_year', label: 'Joriy yil' },
  { id: 'custom', label: 'Boshqa davr' },
]

function monthStart(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`
}

function monthEnd(date = new Date()) {
  const y = date.getFullYear()
  const m = date.getMonth()
  const last = new Date(y, m + 1, 0).getDate()
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(last).padStart(2, '0')}`
}

function prevMonthRange() {
  const d = new Date()
  d.setDate(1)
  d.setMonth(d.getMonth() - 1)
  return { date_from: monthStart(d), date_to: monthEnd(d) }
}

function resolvePeriod(preset, dateFrom, dateTo) {
  const today = todayValue()
  if (preset === 'all') return {}
  if (preset === 'this_month') {
    return { date_from: monthStart(), date_to: monthEnd() }
  }
  if (preset === 'last_month') return prevMonthRange()
  if (preset === 'this_year') {
    return { date_from: `${new Date().getFullYear()}-01-01`, date_to: today }
  }
  const from = dateFrom || today
  const to = dateTo || today
  if (from > to) return { date_from: to, date_to: from }
  return { date_from: from, date_to: to }
}

function formatPeriodLabel(preset, dateFrom, dateTo) {
  if (preset === 'all') return 'Barcha davr'
  const p = resolvePeriod(preset, dateFrom, dateTo)
  if (!p.date_from && !p.date_to) return 'Barcha davr'
  if (p.date_from === p.date_to) return p.date_from
  return `${p.date_from} — ${p.date_to}`
}

export default function ReportExportPanel({ notify }) {
  const [reportType, setReportType] = useState('sales')
  const [periodPreset, setPeriodPreset] = useState('this_month')
  const [dateFrom, setDateFrom] = useState(monthStart())
  const [dateTo, setDateTo] = useState(monthEnd())
  const [exporting, setExporting] = useState(false)

  const selectedReport = useMemo(
    () => REPORT_TYPES.find((r) => r.id === reportType) || REPORT_TYPES[0],
    [reportType],
  )

  const periodLabel = useMemo(
    () => (selectedReport.hasPeriod
      ? formatPeriodLabel(periodPreset, dateFrom, dateTo)
      : 'Joriy holat (snapshot)'),
    [selectedReport, periodPreset, dateFrom, dateTo],
  )

  const applyPreset = useCallback((preset) => {
    setPeriodPreset(preset)
    if (preset === 'all') {
      setDateFrom('')
      setDateTo('')
      return
    }
    const range = resolvePeriod(preset, dateFrom, dateTo)
    if (range.date_from) setDateFrom(range.date_from)
    if (range.date_to) setDateTo(range.date_to)
  }, [dateFrom, dateTo])

  const handleCalendarChange = useCallback(({ date_from, date_to }) => {
    setPeriodPreset('custom')
    setDateFrom(date_from)
    setDateTo(date_to)
  }, [])

  const handleExport = async () => {
    setExporting(true)
    try {
      const params = selectedReport.hasPeriod
        ? resolvePeriod(periodPreset, dateFrom, dateTo)
        : {}
      await api.exportReport(reportType, params)
      notify('Excel hisobot yuklandi.', 'success')
    } catch (err) {
      notify(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <section className="data-panel report-export-panel">
      <div className="report-export-hero">
        <div>
          <p className="eyebrow">EXCEL EXPORT</p>
          <h3>Hisobot yuklab olish</h3>
          <p className="muted">Hisobot turini tanlang, davrni kalendardan belgilang va Excel faylni yuklang.</p>
        </div>
      </div>

      <div className="report-export-layout">
        <div className="report-export-main">
          <div className="report-export-section">
            <span className="report-export-section-label">Hisobot turi</span>
            <div className="report-type-grid" role="radiogroup" aria-label="Hisobot turi">
              {REPORT_TYPES.map((item) => {
                const Icon = item.icon
                const active = reportType === item.id
                return (
                  <button
                    key={item.id}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    className={active ? 'report-type-card is-active' : 'report-type-card'}
                    onClick={() => setReportType(item.id)}
                  >
                    <span className="report-type-icon"><Icon size={22} weight={active ? 'fill' : 'regular'} /></span>
                    <span className="report-type-label">{item.label}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {selectedReport.hasPeriod ? (
            <div className="report-export-section">
              <span className="report-export-section-label">Tez tanlov</span>
              <div className="report-period-chips" role="tablist" aria-label="Davr">
                {PERIOD_PRESETS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    aria-selected={periodPreset === item.id}
                    className={periodPreset === item.id ? 'report-period-chip is-active' : 'report-period-chip'}
                    onClick={() => applyPreset(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <p className="muted report-export-hint">{selectedReport.hint}</p>
            </div>
          ) : (
            <div className="report-export-snapshot-note">
              <Package size={20} weight="duotone" />
              <p>{selectedReport.hint}</p>
            </div>
          )}
        </div>

        {selectedReport.hasPeriod && (
          <aside className="report-export-calendar-aside">
            <FilterDateRangeCalendar
              dateFrom={dateFrom}
              dateTo={dateTo}
              onChange={handleCalendarChange}
              label="Davr oralig‘i"
              className="report-export-calendar"
              disabled={periodPreset === 'all'}
            />
            {periodPreset === 'all' && (
              <p className="muted report-export-calendar-note">Barcha davr tanlangan — kalendardan aniq oralik tanlash uchun boshqa tez tanlovni bosing.</p>
            )}
          </aside>
        )}
      </div>

      <div className="report-export-footer">
        <div className="report-export-summary">
          <span className="report-export-summary-label">Tanlangan</span>
          <strong>{selectedReport.label}</strong>
          <span className="report-export-summary-sep">·</span>
          <span>{periodLabel}</span>
        </div>
        <button type="button" className="primary-button report-export-submit" disabled={exporting} onClick={handleExport}>
          {exporting ? <SpinnerGap size={18} className="spin" /> : <DownloadSimple size={20} />}
          Excel yuklab olish
        </button>
      </div>
    </section>
  )
}
