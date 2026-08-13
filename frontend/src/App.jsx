import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Warehouse, Bell, Buildings, CaretDown, ChartLineUp,
  ClipboardText, CurrencyCircleDollar, DownloadSimple, Eye, FileText, Funnel, House, MagnifyingGlass,
  Package, PencilSimple, Plus, SignOut, SpinnerGap, Trash, TrendDown, TrendUp, Truck, UserGear, Users, WarningCircle, X, XCircle, DotsThree, CaretLeft, CaretRight, CheckCircle,
} from '@phosphor-icons/react'
import { api, clearStoredSession, refreshAccessToken, saveSession, setAuthFailureHandler, tokenExpiresAt } from './api'
import DataTable, { BulkActionsBar, StatusBadge, TablePagination } from './components/DataTable'
import GlobalSearch, { useGlobalSearchHotkey } from './components/GlobalSearch'
import ClientDetailPage from './components/ClientDetailPage'
import ListFiltersPanel from './components/ListFiltersPanel'
import SearchableCombobox from './components/SearchableCombobox'
import ConfirmDialog from './components/ConfirmDialog'
import FieldError from './components/FieldError'
import EmptyState from './components/EmptyState'
import StatusChangeModal, { InlineStatusSelect } from './components/StatusChangeModal'
import { buildListQueryParams, emptyStateConfig, exportRowsCsv, hasActiveListFilters } from './listFilters'
import { clientDetailPath, crumbFromPath, invoiceDetailPath, invoiceEditPath, invoiceNewPath, parseAppPath, pathForPage } from './routes'
import { clientOptionLabel, clientSearchText, fetchClient, searchClients } from './lib/clients'
import { validateClientFields, validateCompanyProfile } from './lib/uzValidators'

const NAV_GROUPS = {
  Ombor: [
    { page: 'Ombor', label: 'Mahsulotlar', ability: 'warehouse_view' },
    { page: 'Kategoriyalar', label: 'Kategoriyalar', ability: 'categories_view' },
    { page: 'Qoldiqlar', label: 'Qoldiqlar', ability: 'stocks_view' },
  ],
  Moliya: [
    { page: 'Kassa', label: 'Kassa', ability: 'cash_view' },
    { page: 'Xarajatlar', label: 'Xarajatlar', ability: 'expenses_view' },
  ],
}

const SIDEBAR_NAV = [
  ['Bosh sahifa', House, 'dashboard'],
  ['Buyurtmalar', FileText, 'einvoice_view'],
  ['Import', Truck, 'procurement_view'],
  ['Shartnomalar', ClipboardText, 'contracts_view'],
  ['Ombor', Package, '__group_ombor__'],
  ['Mijozlar', Users, 'clients_view'],
  ['Sotuvlar', TrendUp, 'sales_view'],
  ['Moliya', CurrencyCircleDollar, '__group_moliya__'],
  ['Hisobotlar', ChartLineUp, 'reports_view'],
]

const HIDDEN_PAGES = {
  Bildirishnomalar: 'notifications_view',
  Foydalanuvchilar: 'users_view',
}

const money = (value) => new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 0 }).format(Number(value || 0))
/** Valyuta kursi — Infinbank MB kursi kabi, yaxlitlamasdan (masalan 11 889,95). */
const moneyRate = (value) => {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return new Intl.NumberFormat('uz-UZ', { minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(num)
}
const list = (data) => Array.isArray(data) ? data : data?.results || []

function flattenCategories(nodes, depth = 0, result = []) {
  for (const node of nodes) {
    result.push({ id: node.id, name: node.name, depth })
    if (node.children?.length) flattenCategories(node.children, depth + 1, result)
  }
  return result
}

function findCategoryNode(nodes, id) {
  for (const node of nodes) {
    if (node.id === id) return node
    const found = findCategoryNode(node.children || [], id)
    if (found) return found
  }
  return null
}

function collectDescendantIds(node) {
  const ids = []
  for (const child of node?.children || []) {
    ids.push(child.id)
    ids.push(...collectDescendantIds(child))
  }
  return ids
}
const AUTO_REFRESH_MS = 30000
const workspace = 'Asosiy ombor'
const productUnits = [
  ['piece', 'dona'],
  ['kg', 'kg'],
  ['liter', 'l'],
  ['meter', 'm'],
  ['sqm', 'm²'],
  ['cbm', 'm³'],
  ['barrel', 'bochka'],
  ['ton', 'tonna'],
  ['set', 'komplekt'],
  ['gram', 'gram'],
  ['cm', 'sm'],
  ['mm', 'mm'],
  ['ml', 'ml'],
  ['box', 'quti'],
  ['pack', 'pachka'],
  ['pair', 'juft'],
  ['roll', 'rulon'],
  ['bag', 'qop'],
  ['sheet', 'list'],
]
const eInvoiceUnits = productUnits.filter(([key]) => (
  ['piece', 'kg', 'liter', 'meter', 'sqm', 'cbm', 'barrel', 'ton', 'set'].includes(key)
))
const unitLabel = (value) => productUnits.find(([key]) => key === value)?.[1] || value || 'dona'
const vatOptions = [
  ['none', 'QQS siz'],
  ['0', '0%'],
  ['6', '6%'],
  ['12', '12%'],
  ['15', '15%'],
]
const vatLabel = (value) => vatOptions.find(([key]) => key === value)?.[1] || value || 'QQS siz'
const quantityWithUnit = (value, row = {}) => `${money(value)} ${row.unit_display || unitLabel(row.unit)}`

const documentTypeLabels = {
  contract_sk: 'Shartnoma (SK)',
  invoice: 'Hisob-faktura',
  act: 'Dalolatnoma',
}
const documentTypeLabel = (value) => documentTypeLabels[value] || value || 'Hujjat'

function bankRateValue(bank, side) {
  if (!bank) return null
  return side === 'sell' ? bank.sell_rate : bank.buy_rate
}

function BankRateDropdown({
  marketBanks,
  infinRate,
  manualRate,
  value,
  side,
  compact = false,
  header = false,
  canManage = false,
  disabled = false,
  onSelectInfinbank,
  onSelectBank,
  onSelectManual,
  onSelectSide,
}) {
  const showSide = value.startsWith('bank:')
  return (
    <div className={`fx-bank-select-wrap${compact ? ' fx-bank-select-wrap--compact' : ''}${header ? ' fx-bank-select-wrap--header' : ''}`}>
      <select
        className="fx-bank-select"
        value={value}
        disabled={disabled || !canManage}
        aria-label="Bank tanlash"
        onChange={(event) => {
          const next = event.target.value
          if (next === 'infinbank') onSelectInfinbank?.()
          else if (next === 'manual') onSelectManual?.()
          else if (next.startsWith('bank:')) onSelectBank?.(next.slice(5))
        }}
      >
        <option value="infinbank">
          Infinbank MB{infinRate ? ` — ${moneyRate(infinRate)}` : ''}
        </option>
        {marketBanks.map((bank) => {
          const rate = bankRateValue(bank, side)
          return (
            <option key={bank.code} value={`bank:${bank.code}`}>
              {bank.name}{rate ? ` — ${moneyRate(rate)}` : ''}
            </option>
          )
        })}
        {manualRate != null && (
          <option value="manual">
            Qo‘lda — {moneyRate(manualRate)}
          </option>
        )}
      </select>
      {showSide && (
        <select
          className="fx-bank-side-select"
          value={side}
          disabled={disabled || !canManage}
          aria-label="Kurs turi"
          onChange={(event) => onSelectSide?.(event.target.value)}
        >
          <option value="sell">Sotish</option>
          <option value="buy">Sotib olish</option>
        </select>
      )}
    </div>
  )
}

function FxRatePanel({ session, notify, compact = false, header = false, onSourceChange }) {
  const [snapshot, setSnapshot] = useState(null)
  const [manualDraft, setManualDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [sourceSaving, setSourceSaving] = useState(false)
  const [uiSource, setUiSource] = useState('infinbank')
  const canManage = can(session, 'users_manage')

  const load = useCallback(async (refresh = false) => {
    const data = await api.exchangeRateLatest(refresh)
    setSnapshot(data)
    setManualDraft(data.manual?.mb_rate ?? '')
    return data
  }, [])

  useEffect(() => {
    load().catch((err) => notify(err.message))
    const timer = setInterval(() => { load().catch(() => {}) }, AUTO_REFRESH_MS)
    return () => clearInterval(timer)
  }, [load, notify])

  const serverSource = snapshot?.preferred_rate_source || snapshot?.active_source || 'infinbank'
  const activeSource = uiSource
  const infinRate = snapshot?.infinbank?.mb_rate
  const manualRate = snapshot?.manual?.mb_rate
  const marketBanks = snapshot?.market_rates?.banks || []
  const selectedBankCode = snapshot?.preferred_bank_code || snapshot?.active_bank_code || ''
  const selectedBankSide = snapshot?.preferred_bank_side || snapshot?.active_bank_side || 'sell'
  const displayRate = snapshot?.mb_rate ?? (
    serverSource === 'manual' && manualRate ? manualRate : infinRate
  )
  const activeBankName = snapshot?.active_bank_name
    || marketBanks.find((bank) => bank.code === selectedBankCode)?.name

  useEffect(() => {
    setUiSource(serverSource)
  }, [serverSource])

  const applySettings = async (payload, successMessage) => {
    setSourceSaving(true)
    try {
      await api.updateExchangeRateSettings(payload)
      await load()
      onSourceChange?.()
      if (successMessage) notify(successMessage, 'success')
    } catch (err) {
      notify(err.message)
    } finally {
      setSourceSaving(false)
    }
  }

  const setSource = async (source) => {
    if (!canManage) return
    if (source === 'manual' && !manualRate) {
      setUiSource('manual')
      return
    }
    if (source === 'bank') {
      const fallbackCode = selectedBankCode || marketBanks[0]?.code
      if (!fallbackCode) {
        notify('Bank kurslari hali yuklanmagan.', 'error')
        return
      }
      setUiSource('bank')
      await applySettings({
        preferred_rate_source: 'bank',
        preferred_bank_code: fallbackCode,
        preferred_bank_side: selectedBankSide,
      }, 'Hisob-kitobda tanlangan bank kursi ishlatiladi.')
      return
    }
    setUiSource(source)
    await applySettings(
      { preferred_rate_source: source },
      source === 'manual'
        ? 'Hisob-kitobda qo‘lda kurs ishlatiladi.'
        : 'Hisob-kitobda Infinbank MB kursi ishlatiladi.',
    )
  }

  const selectBank = async (code) => {
    if (!canManage || !code) return
    setUiSource('bank')
    await applySettings({
      preferred_rate_source: 'bank',
      preferred_bank_code: code,
      preferred_bank_side: selectedBankSide,
    })
  }

  const selectBankSide = async (side) => {
    if (!canManage) return
    const code = selectedBankCode || marketBanks[0]?.code
    if (!code) return
    setUiSource('bank')
    await applySettings({
      preferred_rate_source: 'bank',
      preferred_bank_code: code,
      preferred_bank_side: side,
    })
  }

  const bankSelectValue = activeSource === 'manual' && manualRate != null
    ? 'manual'
    : activeSource === 'bank' && selectedBankCode
      ? `bank:${selectedBankCode}`
      : 'infinbank'

  const bankDropdownProps = {
    marketBanks,
    infinRate,
    manualRate,
    value: bankSelectValue,
    side: selectedBankSide,
    canManage,
    disabled: sourceSaving,
    onSelectInfinbank: () => setSource('infinbank'),
    onSelectBank: selectBank,
    onSelectManual: () => setSource('manual'),
    onSelectSide: selectBankSide,
  }

  const saveManual = async (event) => {
    event?.preventDefault?.()
    if (!canManage || !manualDraft) return
    const parsed = Number(manualDraft)
    if (!Number.isFinite(parsed) || parsed <= 0) return
    if (manualRate != null && Number(manualRate) === parsed) return
    setSaving(true)
    try {
      await api.create('/cash/exchange-rates/', {
        currency: 'USD',
        mb_rate: manualDraft,
        buy_rate: manualDraft,
        sell_rate: manualDraft,
        manual_override: true,
        note: 'Qo‘lda kiritilgan kurs',
      })
      await api.updateExchangeRateSettings({ preferred_rate_source: 'manual' })
      await load()
      setUiSource('manual')
      onSourceChange?.()
      notify('Qo‘lda kurs saqlandi.', 'success')
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleManualKeyDown = (event) => {
    if (event.key !== 'Enter') return
    event.preventDefault()
    saveManual()
    event.currentTarget.blur()
  }

  if (header) {
    return (
      <div className="fx-card fx-card--header">
        <BankRateDropdown {...bankDropdownProps} header />
        <strong className="fx-rate-readonly">{displayRate ? moneyRate(displayRate) : '—'}</strong>
        {canManage && (
          <button type="button" className="fx-refresh" onClick={() => load(true).catch((err) => notify(err.message))} aria-label="Kurslarni yangilash" title="Kurslarni yangilash">
            ↻
          </button>
        )}
      </div>
    )
  }

  if (compact) {
    return (
      <div className="fx-card fx-card--dual fx-card--embedded fx-card--compact">
        <span className="fx-card-title">USD kurs (hisob-kitob)</span>
        <div className="fx-source-row">
          {activeSource === 'manual' ? (
            <div className="fx-source-tabs fx-source-tabs--inline" role="tablist" aria-label="USD kurs manbasi">
              <button type="button" role="tab" aria-selected={false} disabled={sourceSaving || !canManage} className="fx-source-tab" onClick={() => setSource(bankSelectValue.startsWith('bank:') ? 'bank' : 'infinbank')}>
                Bank
              </button>
              <button type="button" role="tab" aria-selected className="fx-source-tab is-active">
                Qo‘lda
              </button>
            </div>
          ) : (
            <>
              <BankRateDropdown {...bankDropdownProps} compact />
              <button
                type="button"
                role="tab"
                aria-selected={false}
                disabled={sourceSaving || !canManage}
                className="fx-source-tab fx-source-tab--manual"
                onClick={() => setSource('manual')}
              >
                Qo‘lda
              </button>
            </>
          )}
        </div>
        {activeSource !== 'manual' && canManage && (
          <div className="fx-compact-toolbar">
            <button type="button" className="fx-refresh" onClick={() => load(true).catch((err) => notify(err.message))} aria-label="Kurslarni yangilash" title="Kurslarni yangilash">
              ↻
            </button>
          </div>
        )}
        {activeSource === 'manual' && (
          canManage ? (
            <input
              type="number"
              min="0"
              step="0.01"
              className="fx-manual-input"
              value={manualDraft}
              placeholder="Kurs kiriting"
              onChange={(event) => setManualDraft(event.target.value)}
              onBlur={() => saveManual()}
              onKeyDown={handleManualKeyDown}
              disabled={saving}
              aria-label="Qo‘lda USD kursi"
            />
          ) : (
            <strong className="fx-rate-readonly fx-rate-readonly--compact">{manualRate ? moneyRate(manualRate) : '—'}</strong>
          )
        )}
        <p className="fx-active-note">Hisobda: <b>{displayRate ? `${moneyRate(displayRate)} so‘m` : '—'}</b></p>
      </div>
    )
  }

  return (
    <div className="fx-card fx-card--dual">
      <span className="fx-card-title">USD kurs (hisob-kitob)</span>
      {activeSource === 'manual' ? (
        <div className="fx-source-tabs" role="tablist" aria-label="USD kurs manbasi">
          <button type="button" role="tab" aria-selected={false} disabled={sourceSaving || !canManage} className="fx-source-tab" onClick={() => setSource(bankSelectValue.startsWith('bank:') ? 'bank' : 'infinbank')}>
            Bank
          </button>
          <button type="button" role="tab" aria-selected className="fx-source-tab is-active">
            Qo‘lda
          </button>
        </div>
      ) : (
        <BankRateDropdown {...bankDropdownProps} />
      )}
      {activeSource !== 'manual' && canManage && (
        <div className="fx-rate-row">
          <button type="button" className="fx-refresh" onClick={() => load(true).catch((err) => notify(err.message))} aria-label="Kurslarni yangilash" title="Kurslarni yangilash">
            ↻ Yangilash
          </button>
          <button
            type="button"
            className="fx-manual-switch"
            disabled={sourceSaving}
            onClick={() => setSource('manual')}
          >
            Qo‘lda kurs
          </button>
        </div>
      )}
      {activeSource === 'manual' && (
        canManage ? (
          <form className="fx-rate-form" onSubmit={saveManual}>
            <span className="fx-rate-label">Qo‘lda</span>
            <input type="number" min="0" step="0.01" value={manualDraft} onChange={(event) => setManualDraft(event.target.value)} aria-label="Qo‘lda USD kursi" />
            <button type="submit" disabled={saving}>{saving ? '…' : 'Saqlash'}</button>
          </form>
        ) : (
          <div className="fx-rate-row">
            <span className="fx-rate-label">Qo‘lda</span>
            <strong className="fx-rate-readonly">{manualRate ? moneyRate(manualRate) : '—'}</strong>
          </div>
        )
      )}
      <p className="fx-active-note">
        Hisobda: <b>{displayRate ? `${moneyRate(displayRate)} so‘m` : '—'}</b>
        {activeSource === 'bank' && activeBankName ? ` (${activeBankName})` : ''}
      </p>
    </div>
  )
}

const formatDateUz = (iso) => {
  if (!iso) return '—'
  const [year, month, day] = String(iso).slice(0, 10).split('-')
  if (!year || !month || !day) return iso
  return `${day}.${month}.${year}`
}

const formatDateTimeUz = (iso) => {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return formatDateUz(iso)
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const year = date.getFullYear()
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${day}.${month}.${year} ${hours}:${minutes}`
}

const userInitials = (name) => {
  if (!name) return '—'
  const parts = String(name).trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toLowerCase()
  return String(name).slice(0, 2).toLowerCase()
}

const UZ_ONES = ['', 'bir', 'ikki', 'uch', "to'rt", 'besh', 'olti', 'yetti', 'sakkiz', "to'qqiz"]
const UZ_TEENS = ["o'n", "o'n bir", "o'n ikki", "o'n uch", "o'n to'rt", "o'n besh", "o'n olti", "o'n yetti", "o'n sakkiz", "o'n to'qqiz"]
const UZ_TENS = ['', "o'n", 'yigirma', "o'ttiz", 'qirq', 'ellik', 'oltmish', 'yetmish', 'sakson', "to'qson"]

function threeDigitsToWordsUz(num) {
  const n = Number(num) || 0
  if (!n) return ''
  const hundreds = Math.floor(n / 100)
  const rest = n % 100
  const parts = []
  if (hundreds) {
    parts.push(hundreds === 1 ? 'bir yuz' : `${UZ_ONES[hundreds]} yuz`)
  }
  if (rest > 0) {
    if (rest < 10) parts.push(UZ_ONES[rest])
    else if (rest < 20) parts.push(UZ_TEENS[rest - 10])
    else {
      const tens = Math.floor(rest / 10)
      const ones = rest % 10
      parts.push(UZ_TENS[tens])
      if (ones) parts.push(UZ_ONES[ones])
    }
  }
  return parts.join(' ').trim()
}

function integerToWordsUz(value) {
  const num = Math.floor(Math.abs(Number(value) || 0))
  if (num === 0) return 'nol'
  const scales = [
    [1_000_000_000, 'milliard'],
    [1_000_000, 'million'],
    [1_000, 'ming'],
  ]
  let rest = num
  const parts = []
  for (const [scale, label] of scales) {
    const chunk = Math.floor(rest / scale)
    if (chunk) {
      parts.push(`${threeDigitsToWordsUz(chunk)} ${label}`.trim())
      rest %= scale
    }
  }
  if (rest) parts.push(threeDigitsToWordsUz(rest))
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

function numberToWordsUzbek(value) {
  const amount = Math.round(Number(value || 0) * 100) / 100
  const sum = Math.floor(amount)
  const tiyin = Math.round((amount - sum) * 100)
  return {
    sumWords: integerToWordsUz(sum),
    tiyinWords: integerToWordsUz(tiyin),
    sum,
    tiyin,
  }
}

const moneyDecimal = (value) => new Intl.NumberFormat('uz-UZ', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0))

function useClickOutside(ref, onClose, active) {
  useEffect(() => {
    if (!active) return undefined
    const handler = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [ref, onClose, active])
}

function useAutoRefresh(callback, enabled = true) {
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  useEffect(() => {
    if (!enabled) return undefined
    const id = setInterval(() => callbackRef.current(true), AUTO_REFRESH_MS)
    return () => clearInterval(id)
  }, [enabled])
}

function useTokenRefresh(enabled) {
  useEffect(() => {
    if (!enabled) return undefined
    let timer
    let disposed = false
    const schedule = async () => {
      const expiresAt = tokenExpiresAt(localStorage.getItem('warehouse_access') || '')
      // Refresh two minutes before expiry; an invalid/missing expiry is refreshed now.
      const delay = Math.max(15_000, expiresAt ? expiresAt - Date.now() - 120_000 : 0)
      timer = window.setTimeout(async () => {
        try {
          await refreshAccessToken()
          if (!disposed) schedule()
        } catch {
          // refreshAccessToken clears the stored session and informs App.
        }
      }, delay)
    }
    schedule()
    return () => { disposed = true; window.clearTimeout(timer) }
  }, [enabled])
}

function formatError(message) {
  if (!message) return 'So‘rovni bajarib bo‘lmadi.'
  if (/permission|forbidden|403/i.test(message)) return 'Bu amalni bajarish uchun ruxsatingiz yo‘q.'
  return message
}

const asText = (value, fallback = '—') => value === undefined || value === null || value === '' ? fallback : value
const todayValue = () => new Date().toISOString().slice(0, 10)
const currentYearEndValue = () => `${new Date().getFullYear()}-12-31`

function monthStartValue(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`
}

function monthEndValue(date = new Date()) {
  const y = date.getFullYear()
  const m = date.getMonth()
  const last = new Date(y, m + 1, 0).getDate()
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(last).padStart(2, '0')}`
}

function prevMonthRangeValue() {
  const d = new Date()
  d.setDate(1)
  d.setMonth(d.getMonth() - 1)
  return { date_from: monthStartValue(d), date_to: monthEndValue(d) }
}

function yearStartValue() {
  return `${new Date().getFullYear()}-01-01`
}

function formatPeriodRange(period) {
  if (!period?.date_from && !period?.date_to) return 'barcha davr'
  if (period.date_from === period.date_to) return period.date_from
  return `${period.date_from || '…'} — ${period.date_to || '…'}`
}

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

function FilterDateRangeCalendar({ dateFrom, dateTo, onChange }) {
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
    <div className="filter-calendar filter-date-range-calendar" role="group" aria-label="Davr">
      <div className="filter-calendar-header">
        <span className="filter-calendar-label">Davr</span>
        <span className="filter-calendar-value">{rangeLabel}</span>
      </div>
      <div className="filter-calendar-widget">
        <div className="filter-calendar-nav">
          <button type="button" className="filter-calendar-nav-btn" onClick={() => setViewDate(new Date(viewYear, viewMonth - 1, 1))} aria-label="Oldingi oy">
            <CaretLeft size={16} />
          </button>
          <div className="filter-calendar-nav-title">
            <span className="filter-calendar-month-name">{UZBEK_MONTHS[viewMonth]}</span>
            <div className="filter-calendar-year-wrap" ref={yearDropdownRef}>
              <button
                type="button"
                className="filter-calendar-year-btn"
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
          <button type="button" className="filter-calendar-nav-btn" onClick={() => setViewDate(new Date(viewYear, viewMonth + 1, 1))} aria-label="Keyingi oy">
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

function periodMetricNote(base, period) {
  if (period.date_from === todayValue() && period.date_to === todayValue()) return `${base} (bugun)`
  if (!period.date_from && !period.date_to) return `${base} (barcha davr)`
  return `${base} (${formatPeriodRange(period)})`
}

function buildDashboardFilterParams(filters) {
  const params = {}
  if (filters?.date_from) params.date_from = filters.date_from
  if (filters?.date_to) params.date_to = filters.date_to
  if (filters?.currency) params.currency = filters.currency
  if (filters?.category) params.category = filters.category
  if (filters?.client) params.client = filters.client
  if (filters?.supplier?.trim()) params.supplier = filters.supplier.trim()
  if (filters?.product) params.product = filters.product
  if (filters?.payment_status) params.payment_status = filters.payment_status
  return params
}

const DEFAULT_DASHBOARD_FILTERS = () => ({
  preset: 'custom',
  date_from: todayValue(),
  date_to: todayValue(),
  currency: '',
  category: '',
  client: '',
  supplier: '',
  product: '',
  payment_status: '',
})

const CURRENCY_FILTERS = [
  { id: '', label: 'Hammasi' },
  { id: 'UZS', label: 'UZS' },
  { id: 'USD', label: 'USD' },
]

const PAYMENT_STATUS_FILTERS = [
  { id: '', label: 'Hammasi' },
  { id: 'pending', label: 'Kutilmoqda' },
  { id: 'partial', label: 'Qisman' },
  { id: 'paid', label: 'To‘langan' },
  { id: 'overdue', label: 'Kechikkan' },
]

const TOAST_DURATION = { error: 16000, warning: 12000, success: 7000 }

function ToastStack({ toasts, dismiss, pauseToast, resumeToast }) {
  const icons = { error: XCircle, success: CheckCircle, warning: WarningCircle }
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => {
        const Icon = icons[toast.type] || WarningCircle
        return (
          <div
            key={toast.id}
            className={`toast toast-${toast.type}`}
            role="alert"
            onMouseEnter={() => pauseToast(toast.id)}
            onMouseLeave={() => resumeToast(toast.id)}
            onFocus={() => pauseToast(toast.id)}
            onBlur={() => resumeToast(toast.id)}
          >
            <span className="toast-icon"><Icon size={22} weight="fill" /></span>
            <div className="toast-body">
              <b>{toast.type === 'error' ? 'Xatolik' : toast.type === 'success' ? 'Muvaffaqiyatli' : 'Ogohlantirish'}</b>
              <span>{toast.message}</span>
            </div>
            <button type="button" className="toast-close" onClick={() => dismiss(toast.id)} aria-label="Yopish">
              <X size={18} />
            </button>
            <span
              className="toast-progress"
              style={{ animationDuration: `${toast.durationMs}ms`, animationPlayState: toast.paused ? 'paused' : 'running' }}
              aria-hidden="true"
            />
          </div>
        )
      })}
    </div>
  )
}

function useNotify() {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())
  const recent = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) { clearTimeout(timer); timers.current.delete(id) }
  }, [])

  const scheduleDismiss = useCallback((id, delayMs) => {
    const timer = setTimeout(() => dismiss(id), delayMs)
    timers.current.set(id, timer)
    return timer
  }, [dismiss])

  const pauseToast = useCallback((id) => {
    const timer = timers.current.get(id)
    if (!timer) return
    clearTimeout(timer)
    timers.current.delete(id)
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, paused: true } : t)))
  }, [])

  const resumeToast = useCallback((id) => {
    setToasts((prev) => {
      const toast = prev.find((t) => t.id === id)
      if (!toast?.paused) return prev
      scheduleDismiss(id, 6000)
      return prev.map((t) => (t.id === id ? { ...t, paused: false } : t))
    })
  }, [scheduleDismiss])

  const notify = useCallback((message, type = 'error') => {
    const formatted = formatError(message)
    const key = `${type}:${formatted}`
    const now = Date.now()
    const lastSeen = recent.current.get(key) || 0
    if (now - lastSeen < 1500) return
    recent.current.set(key, now)
    const id = Date.now() + Math.random()
    const durationMs = TOAST_DURATION[type] || TOAST_DURATION.error
    setToasts((prev) => [...prev, { id, message: formatted, type, durationMs, paused: false }])
    scheduleDismiss(id, durationMs)
  }, [scheduleDismiss])

  return { toasts, notify, dismiss, pauseToast, resumeToast }
}

function formatRelativeTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const diffMs = Date.now() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Hozir'
  if (diffMin < 60) return `${diffMin} daqiqa oldin`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} soat oldin`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay} kun oldin`
  return date.toLocaleDateString('uz-UZ')
}

function NotificationDropdown({ onViewAll, notify, onRequestPermission, browserPermission }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const ref = useRef(null)
  useClickOutside(ref, () => setOpen(false), open)

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      setItems(list(await api.notifications({ page_size: 12 })))
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [notify])

  useEffect(() => {
    load(true)
    const timer = setInterval(() => load(true), AUTO_REFRESH_MS)
    return () => clearInterval(timer)
  }, [load])

  useEffect(() => {
    if (open) load()
  }, [open, load])

  const unreadCount = items.filter((item) => !item.is_read).length

  const toggle = () => {
    setOpen((value) => !value)
    if (browserPermission !== 'granted') onRequestPermission()
  }

  const markRead = async (id) => {
    try {
      await api.notificationsMarkRead(id)
      await load(true)
    } catch (err) {
      notify(err.message)
    }
  }

  const markAllRead = async () => {
    try {
      await api.notificationsMarkAllRead()
      await load(true)
      notify('Hammasi o‘qilgan deb belgilandi.', 'success')
    } catch (err) {
      notify(err.message)
    }
  }

  return (
    <div className="dropdown notification-dropdown" ref={ref}>
      <button
        type="button"
        className="icon-button notification"
        aria-label="Bildirishnomalar"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={toggle}
      >
        <Bell size={20} />
        {unreadCount > 0 && <i aria-hidden="true" />}
      </button>
      {open && (
        <div className="dropdown-menu notification-menu" role="menu">
          <div className="notification-menu-head">
            <div>
              <b>Bildirishnomalar</b>
              {unreadCount > 0 && <small>{unreadCount} ta yangi</small>}
            </div>
            {unreadCount > 0 && (
              <button type="button" className="text-button" onClick={markAllRead}>Hammasini o‘qilgan</button>
            )}
          </div>
          <div className="notification-menu-body">
            {loading && !items.length ? (
              <div className="notification-empty"><SpinnerGap size={22} className="spin" />Yuklanmoqda…</div>
            ) : items.length ? items.map((item) => (
              <button
                type="button"
                key={item.id}
                className={item.is_read ? 'notification-item is-read' : 'notification-item'}
                onClick={() => { if (!item.is_read) markRead(item.id) }}
              >
                <span className="notification-item-icon"><Bell size={16} weight={item.is_read ? 'regular' : 'fill'} /></span>
                <span className="notification-item-body">
                  <b>{item.title}</b>
                  <span>{item.message}</span>
                  <small>{formatRelativeTime(item.created_at)}</small>
                </span>
                {!item.is_read && <span className="notification-dot" aria-hidden="true" />}
              </button>
            )) : (
              <div className="notification-empty">Bildirishnoma yo‘q</div>
            )}
          </div>
          <div className="notification-menu-foot">
            <button type="button" className="secondary-button" onClick={() => { onViewAll(); setOpen(false) }}>
              Barchasini ko‘rish
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function can(session, ability) {
  if (!ability) return true
  if (session?.is_superuser) return true
  return Boolean(session?.abilities?.[ability])
}

function editorSectionTitle(title) {
  const labels = {
    Ombor: 'Ombor',
    Kategoriyalar: 'Kategoriya',
    Qoldiqlar: 'Qoldiq',
    Mijozlar: 'Mijoz',
  }
  return labels[title] || title
}

function canNavItem(session, ability) {
  if (ability === '__group_ombor__') return NAV_GROUPS.Ombor.some((tab) => can(session, tab.ability))
  if (ability === '__group_moliya__') return NAV_GROUPS.Moliya.some((tab) => can(session, tab.ability))
  return can(session, ability)
}

function getSidebarGroupKey(label) {
  if (label === 'Ombor') return 'Ombor'
  if (label === 'Moliya') return 'Moliya'
  return null
}

function getGroupForPage(page) {
  for (const [key, tabs] of Object.entries(NAV_GROUPS)) {
    if (tabs.some((tab) => tab.page === page)) return key
  }
  return null
}

function isPageInGroup(page, groupKey) {
  return NAV_GROUPS[groupKey]?.some((tab) => tab.page === page)
}

function isSidebarActive(sidebarLabel, active) {
  const group = getSidebarGroupKey(sidebarLabel)
  if (group) return isPageInGroup(active, group)
  return active === sidebarLabel
}

function defaultGroupPage(session, groupKey) {
  return NAV_GROUPS[groupKey]?.find((tab) => can(session, tab.ability))?.page
}

function allowedSidebar(session) {
  return SIDEBAR_NAV.filter(([, , ability]) => canNavItem(session, ability))
}

function getPageDisplayTitle(page) {
  for (const tabs of Object.values(NAV_GROUPS)) {
    const tab = tabs.find((item) => item.page === page)
    if (tab) return tab.label
  }
  return page
}

function pageCrumbLabel(active) {
  const group = getGroupForPage(active)
  if (!group) return active
  return `${group} / ${getPageDisplayTitle(active)}`
}

function isAccessiblePage(session, page) {
  if (page === 'Bosh sahifa') return can(session, 'dashboard')
  if (page === 'Hisobotlar') return can(session, 'reports_view')
  if (page === 'Buyurtmalar') return can(session, 'einvoice_view')
  if (HIDDEN_PAGES[page]) return can(session, HIDDEN_PAGES[page])
  const group = getGroupForPage(page)
  if (group) {
    const tab = NAV_GROUPS[group].find((item) => item.page === page)
    return Boolean(tab && can(session, tab.ability))
  }
  const sidebarItem = SIDEBAR_NAV.find(([label]) => label === page)
  if (sidebarItem) return canNavItem(session, sidebarItem[2])
  return false
}

function SectionTabs({ groupKey, active, onSelect, session }) {
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

const emptyCompanyProfile = () => ({
  stir: '',
  name: '',
  director_jshshr: '',
  director_fish: '',
  mfo: '',
  bank_name: '',
  oked: '',
  bank_account: '',
  address: '',
  phone: '',
  email: '',
})

function CompanyProfileModal({ close, notify, session }) {
  const canEdit = can(session, 'users_manage')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(emptyCompanyProfile)
  const [errors, setErrors] = useState({})
  const [validatedOnce, setValidatedOnce] = useState(false)

  const clearFieldError = (key) => {
    setErrors((current) => {
      if (!current[key]) return current
      const next = { ...current }
      delete next[key]
      return next
    })
  }

  const updateField = (key, value) => {
    clearFieldError(key)
    setForm((current) => ({ ...current, [key]: value }))
  }

  const runValidation = () => {
    const nextErrors = validateCompanyProfile(form)
    setErrors(nextErrors)
    setValidatedOnce(true)
    return nextErrors
  }

  const handleFieldBlur = (key) => {
    if (!validatedOnce) return
    const nextErrors = validateCompanyProfile(form)
    setErrors((current) => {
      const next = { ...current }
      if (nextErrors[key]) next[key] = nextErrors[key]
      else delete next[key]
      return next
    })
  }

  useEffect(() => {
    let cancelled = false
    api.companyProfile()
      .then((data) => {
        if (!cancelled) {
          setForm({
            stir: data.stir || '',
            name: data.name || '',
            director_jshshr: data.director_jshshr || '',
            director_fish: data.director_fish || '',
            mfo: data.mfo || '',
            bank_name: data.bank_name || '',
            oked: data.oked || '',
            bank_account: data.bank_account || '',
            address: data.address || '',
            phone: data.phone || '',
            email: data.email || '',
          })
        }
      })
      .catch((err) => notify(err.message))
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [notify])

  const submit = async (event) => {
    event.preventDefault()
    if (!canEdit) return
    const nextErrors = runValidation()
    if (Object.keys(nextErrors).length) {
      document.querySelector('.company-profile-editor .field-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setSaving(true)
    try {
      await api.updateCompanyProfile(form)
      window.dispatchEvent(new CustomEvent('company-profile-updated'))
      notify('Korxona profili saqlandi.', 'success')
      close()
    } catch (err) {
      if (err.fields && Object.keys(err.fields).length) {
        setErrors((current) => ({ ...current, ...err.fields }))
        setValidatedOnce(true)
      } else {
        notify(err.message)
      }
    } finally {
      setSaving(false)
    }
  }

  const fieldClass = (key) => (errors[key] ? 'field-invalid' : '')

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor company-profile-editor" onSubmit={submit} noValidate>
        <div className="editor-head">
          <div>
            <p className="eyebrow">PROFIL</p>
            <h3>Yuridik shaxs ma’lumotlari</h3>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button>
        </div>
        {loading ? <SkeletonRows /> : (
          <>
            <p className="muted company-profile-note">
              Buyurtmalar va hujjatlarda «Sizning ma’lumotlaringiz» sifatida ishlatiladi.
              {!canEdit && ' Faqat ko‘rish rejimi.'}
            </p>
            <div className="form-grid">
              <label className={fieldClass('stir')}>STIR / INN
                <input
                  value={form.stir}
                  onChange={(e) => updateField('stir', e.target.value.replace(/\D/g, '').slice(0, 9))}
                  onBlur={() => handleFieldBlur('stir')}
                  disabled={!canEdit}
                  inputMode="numeric"
                  placeholder="9 ta raqam"
                  aria-invalid={Boolean(errors.stir)}
                />
                <FieldError message={errors.stir} />
              </label>
              <label className={`full-width${errors.name ? ' field-invalid' : ''}`}>Nomi
                <input value={form.name} onChange={(e) => updateField('name', e.target.value)} disabled={!canEdit} />
                <FieldError message={errors.name} />
              </label>
              <label className={fieldClass('director_jshshr')}>Rahbar JSHSHIR
                <input
                  value={form.director_jshshr}
                  onChange={(e) => updateField('director_jshshr', e.target.value.replace(/\D/g, '').slice(0, 14))}
                  onBlur={() => handleFieldBlur('director_jshshr')}
                  disabled={!canEdit}
                  inputMode="numeric"
                  placeholder="14 ta raqam"
                  aria-invalid={Boolean(errors.director_jshshr)}
                />
                <FieldError message={errors.director_jshshr} />
              </label>
              <label className={fieldClass('director_fish')}>Rahbar F.I.Sh.
                <input value={form.director_fish} onChange={(e) => updateField('director_fish', e.target.value)} disabled={!canEdit} />
                <FieldError message={errors.director_fish} />
              </label>
              <label className={fieldClass('mfo')}>MFO
                <input
                  value={form.mfo}
                  onChange={(e) => updateField('mfo', e.target.value.replace(/\D/g, '').slice(0, 5))}
                  onBlur={() => handleFieldBlur('mfo')}
                  disabled={!canEdit}
                  inputMode="numeric"
                  placeholder="5 ta raqam"
                  aria-invalid={Boolean(errors.mfo)}
                />
                <FieldError message={errors.mfo} />
              </label>
              <label className={fieldClass('bank_name')}>Bank nomi
                <input value={form.bank_name} onChange={(e) => updateField('bank_name', e.target.value)} disabled={!canEdit} />
                <FieldError message={errors.bank_name} />
              </label>
              <label className={fieldClass('oked')}>OKED
                <input
                  value={form.oked}
                  onChange={(e) => updateField('oked', e.target.value.replace(/\D/g, '').slice(0, 5))}
                  onBlur={() => handleFieldBlur('oked')}
                  disabled={!canEdit}
                  inputMode="numeric"
                  placeholder="5 ta raqam"
                  aria-invalid={Boolean(errors.oked)}
                />
                <FieldError message={errors.oked} />
              </label>
              <label className={fieldClass('bank_account')}>Hisob raqami
                <input
                  value={form.bank_account}
                  onChange={(e) => updateField('bank_account', e.target.value.replace(/\D/g, '').slice(0, 20))}
                  onBlur={() => handleFieldBlur('bank_account')}
                  disabled={!canEdit}
                  inputMode="numeric"
                  placeholder="20 ta raqam"
                  aria-invalid={Boolean(errors.bank_account)}
                />
                <FieldError message={errors.bank_account} />
              </label>
              <label className={`full-width${errors.address ? ' field-invalid' : ''}`}>Manzil
                <textarea rows="2" value={form.address} onChange={(e) => updateField('address', e.target.value)} disabled={!canEdit} />
                <FieldError message={errors.address} />
              </label>
              <label className={fieldClass('phone')}>Telefon
                <input
                  value={form.phone}
                  onChange={(e) => updateField('phone', e.target.value)}
                  onBlur={() => handleFieldBlur('phone')}
                  disabled={!canEdit}
                  placeholder="+998 XX XXX XX XX"
                  aria-invalid={Boolean(errors.phone)}
                />
                <FieldError message={errors.phone} />
              </label>
              <label className={fieldClass('email')}>E-mail
                <input
                  type="email"
                  value={form.email || ''}
                  onChange={(e) => updateField('email', e.target.value)}
                  onBlur={() => handleFieldBlur('email')}
                  disabled={!canEdit}
                  aria-invalid={Boolean(errors.email)}
                />
                <FieldError message={errors.email} />
              </label>
            </div>
          </>
        )}
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Yopish</button>
          {canEdit && <button className="primary-button" disabled={saving || loading}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}</button>}
        </div>
      </form>
    </div>
  )
}

function ProfileDropdown({ session, onLogout, notify, onNavigate }) {
  const [open, setOpen] = useState(false)
  const [companyOpen, setCompanyOpen] = useState(false)
  const ref = useRef(null)
  useClickOutside(ref, () => setOpen(false), open)

  return (
    <>
      <div className="dropdown profile-dropdown" ref={ref}>
        <button type="button" className="profile dropdown-trigger" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="menu">
          <span>{session.username.slice(0, 1).toUpperCase()}</span>
          <div><b>{session.username}</b><small>{session.role}</small></div>
          <CaretDown size={15} className={open ? 'caret-open' : ''} />
        </button>
        {open && (
          <ul className="dropdown-menu profile-menu" role="menu">
            <li className="dropdown-meta">
              <b>{session.username}</b>
              <small>{session.role}</small>
            </li>
            <li>
              {can(session, 'users_manage') && (
                <button type="button" role="menuitem" onClick={() => { setCompanyOpen(true); setOpen(false) }}>
                  <Buildings size={17} />Korxona profili
                </button>
              )}
            </li>
            <li>
              {can(session, 'users_view') && (
                <button type="button" role="menuitem" onClick={() => { onNavigate('Foydalanuvchilar'); setOpen(false) }}>
                  <UserGear size={17} />Foydalanuvchilar
                </button>
              )}
            </li>
            <li><button type="button" role="menuitem" onClick={() => { onLogout(); setOpen(false) }}><SignOut size={17} />Chiqish</button></li>
          </ul>
        )}
      </div>
      {companyOpen && <CompanyProfileModal close={() => setCompanyOpen(false)} notify={notify} session={session} />}
    </>
  )
}

function App() {
  const [session, setSession] = useState(() => JSON.parse(localStorage.getItem('warehouse_user') || 'null'))
  const location = useLocation()
  const routerNavigate = useNavigate()
  const routeInfo = parseAppPath(location.pathname)
  const active = routeInfo.page || 'Bosh sahifa'
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(false)
  const [notificationPermission, setNotificationPermission] = useState(() => (typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'default'))
  const [clientEditFromDetail, setClientEditFromDetail] = useState(null)
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false)
  const [resourceReloadKey, setResourceReloadKey] = useState(0)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('warehouse_sidebar_collapsed') === '1')
  const [dashboardFilters, setDashboardFilters] = useState(() => DEFAULT_DASHBOARD_FILTERS())
  const { toasts, notify, dismiss, pauseToast, resumeToast } = useNotify()
  const seenNotifications = useRef(new Set())
  const navItems = allowedSidebar(session)
  const primaryMobileNav = navItems.slice(0, 4)
  const secondaryMobileNav = navItems.slice(4)
  const activeGroup = getGroupForPage(active)
  useGlobalSearchHotkey(() => setGlobalSearchOpen(true))
  const navigateToPath = (path) => {
    routerNavigate(path)
    setMobileMenuOpen(false)
  }
  const navigate = (label) => {
    const group = getSidebarGroupKey(label)
    if (group) {
      const page = defaultGroupPage(session, group)
      if (page) routerNavigate(pathForPage(page))
    } else {
      routerNavigate(pathForPage(label))
    }
    setMobileMenuOpen(false)
  }
  const toggleSidebar = () => {
    setSidebarCollapsed((value) => {
      localStorage.setItem('warehouse_sidebar_collapsed', value ? '0' : '1')
      return !value
    })
  }

  useEffect(() => {
    setAuthFailureHandler(() => setSession(null))
    return () => setAuthFailureHandler(null)
  }, [])
  useTokenRefresh(Boolean(session))

  const loadDashboard = useCallback(async (silent = false, filters = dashboardFilters) => {
    if (!silent) setLoading(true)
    try {
      const params = buildDashboardFilterParams(filters)
      const [[summary, warehouse, cash, topProducts], monthly] = await Promise.all([
        api.reports(params),
        api.monthlyTrend(6, params),
      ])
      setDashboard({ summary, warehouse, cash, topProducts, monthly })
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [notify, dashboardFilters])

  const changeDashboardFilters = useCallback((nextFilters) => {
    setDashboardFilters((current) => ({ ...current, ...nextFilters }))
  }, [])

  useEffect(() => {
    if (session && can(session, 'dashboard')) loadDashboard()
  }, [session, loadDashboard, dashboardFilters])
  useAutoRefresh(() => { if (session && can(session, 'dashboard') && active === 'Bosh sahifa') loadDashboard(true) }, Boolean(session))

  useEffect(() => {
    if (!session) return undefined
    let cancelled = false
    api.me()
      .then((user) => {
        if (!cancelled) {
          saveSession({ user })
          setSession(user)
        }
      })
      .catch((err) => {
        if (!cancelled && err.status !== 401) notify(err.message)
      })
    return () => { cancelled = true }
  }, [session?.id, notify])

  useEffect(() => {
    if (!session || routeInfo.kind !== 'unknown') return
    const first = navItems[0]?.[0]
    if (!first) return
    const group = getSidebarGroupKey(first)
    routerNavigate(pathForPage(group ? defaultGroupPage(session, group) || first : first))
  }, [session, routeInfo.kind, navItems, routerNavigate])

  useEffect(() => {
    if (!session) return undefined
    let cancelled = false
    const syncNotifications = async () => {
      if (typeof window === 'undefined' || !('Notification' in window) || Notification.permission !== 'granted') return
      try {
        const payload = list(await api.notifications())
        const unread = payload.filter((item) => !item.is_read && !seenNotifications.current.has(item.id))
        if (!cancelled && unread.length) {
          unread.forEach((item) => {
            new Notification(item.title, { body: item.message, icon: '/vite.svg' })
            seenNotifications.current.add(item.id)
          })
        }
      } catch (err) {
        if (!cancelled) console.error(err)
      }
    }
    syncNotifications()
    const timer = setInterval(syncNotifications, 30000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [session])

  const requestNotifications = useCallback(async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      notify('Brauzer bildirishnomalarini qo‘llab-quvvatlamaydi.', 'warning')
      return
    }
    if (Notification.permission === 'granted') {
      setNotificationPermission('granted')
      notify('Bildirishnomalar allaqachon yoqilgan.', 'success')
      return
    }
    const result = await Notification.requestPermission()
    setNotificationPermission(result)
    if (result === 'granted') {
      notify('Bildirishnomalar ruxsat berildi.', 'success')
    } else {
      notify('Bildirishnomalar uchun ruxsat berilmadi.', 'warning')
    }
  }, [notify])

  const logout = () => {
    clearStoredSession()
    setSession(null)
  }

  const openBuyurtma = (clientId = null) => {
    if (!can(session, 'einvoice_manage')) return notify('Bu amalni bajarish uchun ruxsatingiz yo‘q.')
    routerNavigate(invoiceNewPath(), { state: clientId ? { clientId } : {} })
  }

  if (!session) return <Login onSuccess={setSession} />
  return (
    <main className={sidebarCollapsed ? 'app-shell sidebar-collapsed' : 'app-shell'}>
      <ToastStack toasts={toasts} dismiss={dismiss} pauseToast={pauseToast} resumeToast={resumeToast} />
      <aside className={sidebarCollapsed ? 'sidebar is-collapsed' : 'sidebar'}>
        <div className="brand">
          <span className="brand-mark"><Warehouse size={22} weight="fill" /></span>
          <span>smart.<b>ombor</b></span>
          <button className="sidebar-toggle" type="button" onClick={toggleSidebar} aria-label={sidebarCollapsed ? 'Sidebar ochish' : 'Sidebar yopish'}>
            {sidebarCollapsed ? <CaretRight size={17} /> : <CaretLeft size={17} />}
          </button>
        </div>
        <div className="workspace">
          <span>ISH MAYDONI</span>
          <b className="workspace-name">{workspace}</b>
        </div>
        <nav>{navItems.map(([label, Icon]) => (
          <button key={label} onClick={() => navigate(label)} className={isSidebarActive(label, active) ? 'nav-item is-active' : 'nav-item'} title={label}>
            <span className="nav-icon"><Icon size={20} weight={isSidebarActive(label, active) ? 'fill' : 'regular'} /></span>
            <span className="nav-label">{label}</span>
          </button>
        ))}</nav>
        <div className="sidebar-bottom"><button className="nav-item" onClick={logout} title="Chiqish"><span className="nav-icon"><SignOut size={20} /></span><span className="nav-label">Chiqish</span></button></div>
      </aside>
      <section className="content">
        <header className="topbar">
          <div className="crumb"><span>Smart ombor</span><span>/</span><b>{crumbFromPath(location.pathname)}</b></div>
          <div className="top-actions">
            <FxRatePanel session={session} notify={notify} header onSourceChange={() => loadDashboard(true)} />
            <button className="icon-button" aria-label="Global qidiruv" title="Qidiruv (Ctrl+K)" onClick={() => setGlobalSearchOpen(true)}><MagnifyingGlass size={20} /></button>
            <NotificationDropdown
              browserPermission={notificationPermission}
              onRequestPermission={requestNotifications}
              onViewAll={() => { if (can(session, 'notifications_view')) navigate('Bildirishnomalar') }}
              notify={notify}
            />
            <ProfileDropdown session={session} onLogout={logout} notify={notify} onNavigate={navigate} />
          </div>
        </header>
        {routeInfo.kind === 'client-detail' && can(session, 'clients_view') && (
          <ClientDetailPage
            clientId={routeInfo.clientId}
            tab={routeInfo.tab}
            session={session}
            notify={notify}
            onNavigate={navigateToPath}
            onEditClient={(client) => setClientEditFromDetail(client)}
            onNewOrder={(client) => openBuyurtma(client.id)}
            onNewSale={() => { routerNavigate(pathForPage('Sotuvlar')); notify('Yangi sotuv formasi ochiladi.', 'success') }}
          />
        )}
        {routeInfo.kind !== 'client-detail' && active === 'Bosh sahifa' && can(session, 'dashboard') && (
          <Dashboard
            data={dashboard}
            loading={loading && !dashboard}
            period={dashboardFilters}
            onPeriodChange={changeDashboardFilters}
            onCreateBuyurtma={openBuyurtma}
            onNavigate={navigate}
            session={session}
          />
        )}
        {routeInfo.kind !== 'client-detail' && active === 'Hisobotlar' && can(session, 'reports_view') && <ReportsPage notify={notify} />}
        {(routeInfo.kind === 'page' || routeInfo.kind === 'invoice-detail' || routeInfo.kind === 'invoice-new' || routeInfo.kind === 'invoice-edit') && active === 'Buyurtmalar' && can(session, 'einvoice_view') && (
          <BuyurtmalarPage
            notify={notify}
            session={session}
            routeMode={
              routeInfo.kind === 'invoice-new' ? 'new'
                : routeInfo.kind === 'invoice-edit' ? 'edit'
                  : routeInfo.kind === 'invoice-detail' ? 'view'
                    : 'list'
            }
            invoiceId={routeInfo.invoiceId || null}
            prefillClientId={routeInfo.kind === 'invoice-new' ? (location.state?.clientId ?? null) : null}
          />
        )}
        {routeInfo.kind !== 'client-detail' && active !== 'Bosh sahifa' && active !== 'Hisobotlar' && active !== 'Buyurtmalar' && isAccessiblePage(session, active) && resources[active] && (
          <>
            {activeGroup && (
              <SectionTabs groupKey={activeGroup} active={active} onSelect={(page) => routerNavigate(pathForPage(page))} session={session} />
            )}
            <ResourcePage
              title={active}
              notify={notify}
              reloadKey={resourceReloadKey}
              session={session}
              onDataChange={() => loadDashboard(true)}
              onNavigate={navigate}
              navigateToPath={navigateToPath}
            />
          </>
        )}
        <GlobalSearch open={globalSearchOpen} onClose={() => setGlobalSearchOpen(false)} session={session} onNavigate={navigateToPath} />
        {clientEditFromDetail && (
          <Editor
            title="Mijozlar"
            item={clientEditFromDetail}
            path="/clients/"
            close={() => setClientEditFromDetail(null)}
            done={() => { setClientEditFromDetail(null); setResourceReloadKey((v) => v + 1) }}
            notify={notify}
            session={session}
          />
        )}
      </section>
      {mobileMenuOpen && secondaryMobileNav.length > 0 && (
        <div className="mobile-menu-panel" role="dialog" aria-label="Barcha bo‘limlar">
          {secondaryMobileNav.map(([label, Icon]) => (
            <button key={label} onClick={() => navigate(label)} className={isSidebarActive(label, active) ? 'mobile-menu-item is-active' : 'mobile-menu-item'}>
              <Icon size={20} weight={isSidebarActive(label, active) ? 'fill' : 'regular'} />{label}
            </button>
          ))}
          <button className="mobile-menu-item danger" onClick={logout}><SignOut size={20} />Chiqish</button>
        </div>
      )}
      <nav className="bottom-nav" aria-label="Mobil menyu">
        {primaryMobileNav.map(([label, Icon]) => (
          <button key={label} onClick={() => navigate(label)} className={isSidebarActive(label, active) ? 'bottom-nav-item is-active' : 'bottom-nav-item'} title={label}>
            <Icon size={22} weight={isSidebarActive(label, active) ? 'fill' : 'regular'} />
            <span>{label}</span>
          </button>
        ))}
        {secondaryMobileNav.length > 0 && (
          <button onClick={() => setMobileMenuOpen((value) => !value)} className={mobileMenuOpen ? 'bottom-nav-item is-active' : 'bottom-nav-item'} aria-label="Ko‘proq bo‘limlar" title="Ko‘proq">
            <DotsThree size={22} weight="bold" />
            <span>Ko‘proq</span>
          </button>
        )}
      </nav>
    </main>
  )
}

function Login({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { toasts, notify, dismiss, pauseToast, resumeToast } = useNotify()

  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    try {
      const data = await api.login(username, password)
      saveSession(data)
      onSuccess(data.user)
    } catch (err) {
      notify(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <ToastStack toasts={toasts} dismiss={dismiss} pauseToast={pauseToast} resumeToast={resumeToast} />
      <section className="login-aside">
        <div className="brand"><span className="brand-mark"><Warehouse size={22} weight="fill" /></span><span>smart.<b>ombor</b></span></div>
        <div className="login-copy">
          <p className="eyebrow">BIR TIZIM, TO‘LIQ NAZORAT</p>
          <h1>Ombor, hujjat va hisoblar bir joyda.</h1>
          <p>Har bir buyurtma, qoldiq va to‘lovning holatini real vaqtda kuzating.</p>
        </div>
        <div className="aside-footer"><span className="live-dot" />Tizim ishlayapti</div>
      </section>
      <section className="login-form-wrap">
        <form className="login-form" onSubmit={submit}>
          <p className="eyebrow">XUSH KELIBSIZ</p>
          <h2>Hisobingizga kiring</h2>
          <p className="muted">Davom etish uchun login ma’lumotlaringizni kiriting.</p>
          <label>Login<input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required /></label>
          <label>Parol<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /></label>
          <button className="primary-button" disabled={loading}>{loading ? <SpinnerGap size={19} className="spin" /> : 'Tizimga kirish'}</button>
          <p className="form-footnote">Kirish huquqi administrator tomonidan beriladi.</p>
        </form>
      </section>
    </main>
  )
}

function importPeriodLabel(summary) {
  const uzs = Number(summary.import_paid_uzs || summary.import_paid_today_uzs || 0)
  const usd = Number(summary.import_paid_usd || summary.import_paid_today_usd || 0)
  if (uzs > 0) return `${money(uzs)} so‘m`
  if (usd > 0) return `$${money(usd)}`
  return '0 so‘m'
}

function importPeriodNote(summary) {
  const usd = Number(summary.import_paid_usd || summary.import_paid_today_usd || 0)
  const rate = Number(summary.mb_rate_today || 0)
  if (usd > 0 && rate > 0) return `$${money(usd)} · MB kurs ${moneyRate(rate)}`
  return 'Yetkazuvchi to‘lovi (MB kursida)'
}

function filterContextNote(filters, lookup = {}) {
  const extras = []
  if (filters.category) {
    const cat = lookup.categories?.find((item) => String(item.id) === String(filters.category))
    if (cat?.name) extras.push(cat.name)
  }
  if (filters.client) {
    const client = lookup.clients?.find((item) => String(item.id) === String(filters.client))
    if (client?.full_name || client?.company_name) extras.push(client.full_name || client.company_name)
  }
  if (filters.supplier?.trim()) extras.push(filters.supplier.trim())
  if (filters.product) {
    const product = lookup.products?.find((item) => String(item.id) === String(filters.product))
    if (product?.name) extras.push(product.name)
  }
  if (filters.payment_status) {
    const payment = PAYMENT_STATUS_FILTERS.find((item) => item.id === filters.payment_status)
    if (payment?.label) extras.push(payment.label)
  }
  return extras.length ? ` · ${extras.join(', ')}` : ''
}

function isDefaultDashboardPeriod(filters) {
  return filters.date_from === todayValue() && filters.date_to === todayValue()
}

function buildDashboardFilterChips(filters, lookup = {}) {
  const chips = []
  if (!isDefaultDashboardPeriod(filters)) {
    chips.push({
      key: 'period',
      label: formatPeriodRange(filters),
      patch: { preset: 'custom', date_from: todayValue(), date_to: todayValue() },
    })
  }
  if (filters.currency) {
    const currency = CURRENCY_FILTERS.find((item) => item.id === filters.currency)
    chips.push({ key: 'currency', label: currency?.label || filters.currency, patch: { currency: '' } })
  }
  if (filters.category) {
    const cat = lookup.categories?.find((item) => String(item.id) === String(filters.category))
    chips.push({ key: 'category', label: cat?.name || 'Kategoriya', patch: { category: '' } })
  }
  if (filters.client) {
    const client = lookup.clients?.find((item) => String(item.id) === String(filters.client))
    chips.push({
      key: 'client',
      label: client?.full_name || client?.company_name || 'Mijoz',
      patch: { client: '' },
    })
  }
  if (filters.product) {
    const product = lookup.products?.find((item) => String(item.id) === String(filters.product))
    chips.push({ key: 'product', label: product?.name || 'Mahsulot', patch: { product: '' } })
  }
  if (filters.supplier?.trim()) {
    chips.push({ key: 'supplier', label: `Yetkazuvchi: ${filters.supplier.trim()}`, patch: { supplier: '' } })
  }
  if (filters.payment_status) {
    const payment = PAYMENT_STATUS_FILTERS.find((item) => item.id === filters.payment_status)
    chips.push({ key: 'payment_status', label: payment?.label || filters.payment_status, patch: { payment_status: '' } })
  }
  return chips
}

function FilterSearchSelect({
  id,
  label,
  value,
  onChange,
  options,
  loading,
  getLabel,
  getValue = (item) => item.id,
  emptyLabel = 'Hammasi',
}) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return options
    return options.filter((item) => getLabel(item).toLowerCase().includes(needle))
  }, [options, query, getLabel])

  useEffect(() => {
    if (!value) setQuery('')
  }, [value])

  return (
    <div className="filter-field">
      <label className="filter-field-label" htmlFor={id}>{label}</label>
      {options.length > 8 && (
        <div className="filter-search-wrap">
          <MagnifyingGlass size={16} aria-hidden="true" />
          <input
            type="search"
            className="filter-search-input"
            placeholder="Qidirish..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label={`${label} bo‘yicha qidirish`}
          />
        </div>
      )}
      <select
        id={id}
        className="filter-select"
        value={value || ''}
        disabled={loading}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{emptyLabel}</option>
        {filtered.map((item) => (
          <option key={getValue(item)} value={getValue(item)}>{getLabel(item)}</option>
        ))}
      </select>
    </div>
  )
}

function DashboardFiltersMenu({ filters, onChange }) {
  const [open, setOpen] = useState(false)
  const [customFrom, setCustomFrom] = useState(filters.date_from || todayValue())
  const [customTo, setCustomTo] = useState(filters.date_to || todayValue())
  const [supplierDraft, setSupplierDraft] = useState(filters.supplier || '')
  const [options, setOptions] = useState({ categories: [], clients: [], products: [], loading: false })
  const ref = useRef(null)
  const menuRef = useRef(null)
  const optionsLoaded = useRef(false)
  const closeMenu = useCallback(() => setOpen(false), [])
  useClickOutside(ref, closeMenu, open)

  const loadOptions = useCallback(() => {
    if (optionsLoaded.current) return
    optionsLoaded.current = true
    setOptions((prev) => ({ ...prev, loading: true }))
    Promise.all([
      api.categories({ page_size: 100 }),
      api.clients({ page_size: 100 }),
      api.products({ page_size: 200 }),
    ]).then(([categories, clients, products]) => {
      setOptions({
        categories: list(categories),
        clients: list(clients),
        products: list(products),
        loading: false,
      })
    }).catch(() => {
      optionsLoaded.current = false
      setOptions((prev) => ({ ...prev, loading: false }))
    })
  }, [])

  useEffect(() => { loadOptions() }, [loadOptions])

  useEffect(() => {
    setCustomFrom(filters.date_from || todayValue())
    setCustomTo(filters.date_to || todayValue())
    setSupplierDraft(filters.supplier || '')
  }, [filters.date_from, filters.date_to, filters.supplier])

  useEffect(() => {
    if (!open) return undefined
    loadOptions()
    return undefined
  }, [open, loadOptions])

  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeMenu()
      }
      if (event.key === 'Tab' && menuRef.current) {
        const focusables = menuRef.current.querySelectorAll(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )
        if (!focusables.length) return
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, closeMenu])

  useEffect(() => {
    if (!open || !menuRef.current) return undefined
    const timer = window.setTimeout(() => {
      const first = menuRef.current?.querySelector('button, input, select')
      first?.focus()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [open])

  const applyDateRange = useCallback((from, to) => {
    let date_from = from
    let date_to = to
    if (date_from && date_to && date_from > date_to) {
      [date_from, date_to] = [date_to, date_from]
    }
    onChange({ preset: 'custom', date_from, date_to })
  }, [onChange])

  const handleRangeChange = useCallback(({ date_from, date_to }) => {
    setCustomFrom(date_from)
    setCustomTo(date_to)
    applyDateRange(date_from, date_to)
  }, [applyDateRange])

  const applyCurrency = (currency) => onChange({ currency })

  const applyPaymentStatus = (payment_status) => onChange({ payment_status })

  const applySupplier = (event) => {
    event.preventDefault()
    onChange({ supplier: supplierDraft.trim() })
  }

  const clearSupplierDraft = () => {
    setSupplierDraft('')
    onChange({ supplier: '' })
  }

  const resetFilters = () => {
    onChange(DEFAULT_DASHBOARD_FILTERS())
    closeMenu()
  }

  const removeChip = (patch) => {
    onChange(patch)
    if (patch.supplier === '') setSupplierDraft('')
    if (patch.date_from === todayValue() && patch.date_to === todayValue()) {
      setCustomFrom(todayValue())
      setCustomTo(todayValue())
    }
  }

  const chips = buildDashboardFilterChips(filters, options)
  const extraChipCount = chips.filter((chip) => chip.key !== 'period').length
  const triggerPeriodLabel = formatPeriodRange(filters)

  return (
    <div className="period-filter-wrap">
      <div className="period-filter dropdown" ref={ref}>
        <button
          type="button"
          className="secondary-button period-filter-trigger"
          aria-expanded={open}
          aria-haspopup="dialog"
          aria-controls="dashboard-filters-menu"
          onClick={() => setOpen((value) => !value)}
        >
          <Funnel size={18} />
          Filtrlar
          <span className="period-filter-current">{triggerPeriodLabel}</span>
          {extraChipCount > 0 && (
            <span className="filter-count-badge" aria-label={`${extraChipCount} ta qo‘shimcha filtr`}>
              +{extraChipCount}
            </span>
          )}
        </button>
        {open && (
          <div
            id="dashboard-filters-menu"
            ref={menuRef}
            className="period-filter-menu"
            role="dialog"
            aria-modal="true"
            aria-label="Filtrlar"
          >
            <div className="period-filter-head">
              <div className="period-filter-head-row">
                <div className="period-filter-head-copy">
                  <b className="period-filter-head-label">Filtrlar</b>
                  <p className="period-filter-head-note">O‘zgarishlar darhol qo‘llanadi</p>
                </div>
                <button
                  type="button"
                  className="icon-button period-filter-close"
                  onClick={closeMenu}
                  aria-label="Filtrlarni yopish"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            <div className="period-filter-body">
              <div className="filter-panel">
                <div className="filter-panel-dates" aria-labelledby="filter-davr">
                  <span className="visually-hidden" id="filter-davr">Davr</span>
                  <FilterDateRangeCalendar
                    dateFrom={customFrom}
                    dateTo={customTo}
                    onChange={handleRangeChange}
                  />
                </div>

                <div className="filter-panel-meta">
                  <div className="filter-panel-meta-block">
                    <span className="filter-section-title" id="filter-currency">Valyuta</span>
                    <div className="period-tabs period-tabs--compact" role="tablist" aria-labelledby="filter-currency">
                      {CURRENCY_FILTERS.map((item) => (
                        <button
                          key={item.id || 'all'}
                          type="button"
                          role="tab"
                          aria-selected={filters.currency === item.id}
                          className={filters.currency === item.id ? 'period-tab is-active' : 'period-tab'}
                          onClick={() => applyCurrency(item.id)}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="filter-panel-meta-block">
                    <span className="filter-section-title" id="filter-payment">To‘lov holati</span>
                    <div className="period-tabs period-tabs--compact" role="tablist" aria-labelledby="filter-payment">
                      {PAYMENT_STATUS_FILTERS.map((item) => (
                        <button
                          key={item.id || 'all'}
                          type="button"
                          role="tab"
                          aria-selected={filters.payment_status === item.id}
                          className={filters.payment_status === item.id ? 'period-tab is-active' : 'period-tab'}
                          onClick={() => applyPaymentStatus(item.id)}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="filter-panel-fields">
                  <FilterSearchSelect
                    id="filter-category"
                    label="Kategoriya"
                    value={filters.category}
                    loading={options.loading}
                    options={options.categories}
                    getLabel={(item) => item.name}
                    onChange={(category) => onChange({ category })}
                  />
                  <FilterSearchSelect
                    id="filter-client"
                    label="Mijoz"
                    value={filters.client}
                    loading={options.loading}
                    options={options.clients}
                    getLabel={(item) => item.full_name || item.company_name || `#${item.id}`}
                    onChange={(client) => onChange({ client })}
                  />
                  <FilterSearchSelect
                    id="filter-product"
                    label="Mahsulot"
                    value={filters.product}
                    loading={options.loading}
                    options={options.products}
                    getLabel={(item) => `${item.name}${item.serial_number ? ` (${item.serial_number})` : ''}`}
                    onChange={(product) => onChange({ product })}
                  />
                  <div className="filter-field">
                    <span className="filter-field-label" id="filter-supplier">Yetkazuvchi</span>
                    <form className="filter-supplier-form" onSubmit={applySupplier}>
                      <input
                        type="text"
                        className="filter-text-input"
                        placeholder="Yetkazuvchi nomi"
                        value={supplierDraft}
                        aria-labelledby="filter-supplier"
                        onChange={(event) => setSupplierDraft(event.target.value)}
                      />
                      <button type="submit" className="secondary-button">Qo‘llash</button>
                    </form>
                    {filters.supplier?.trim() && (
                      <button type="button" className="text-button filter-clear-inline" onClick={clearSupplierDraft}>
                        Tozalash
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="period-filter-footer">
              {chips.length > 0 ? (
                <div className="filter-chips" aria-label="Faol filtrlar">
                  {chips.map((chip) => (
                    <button
                      key={chip.key}
                      type="button"
                      className="filter-chip"
                      onClick={() => removeChip(chip.patch)}
                      aria-label={`${chip.label} filtrini olib tashlash`}
                    >
                      <span>{chip.label}</span>
                      <X size={14} weight="bold" />
                    </button>
                  ))}
                </div>
              ) : (
                <span className="period-filter-footer-note">Qo‘shimcha filtr tanlanmagan</span>
              )}
              <div className="period-filter-footer-actions">
                {chips.length > 0 && (
                  <button type="button" className="text-button filter-reset" onClick={resetFilters}>
                    Barchasini tozalash
                  </button>
                )}
                <button type="button" className="primary-button period-filter-done" onClick={closeMenu}>
                  Tayyor
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
      {!open && chips.length > 0 && (
        <div className="filter-chips filter-chips--bar" aria-label="Faol filtrlar">
          {chips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              className="filter-chip"
              onClick={() => removeChip(chip.patch)}
              aria-label={`${chip.label} filtrini olib tashlash`}
            >
              <span>{chip.label}</span>
              <X size={14} weight="bold" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function Dashboard({ data, loading, period, onPeriodChange, onCreateBuyurtma, onNavigate, session }) {
  const summary = data?.summary || {}
  const warehouse = data?.warehouse || {}
  const products = data?.topProducts || []
  const monthly = data?.monthly || []
  const filterSuffix = filterContextNote(period)

  const kassaValue = period.currency === 'USD'
    ? `$${money(summary.kassa_collected_usd || 0)}`
    : `${money(summary.kassa_collected_uzs || summary.kassa_collected_today_uzs || 0)} so‘m`
  const salesValue = money(summary.sales_revenue_uzs || summary.sales_revenue_total || 0)
  const kassaNote = (period.currency === 'USD'
    ? periodMetricNote('Mijoz to‘lovlari (USD)', period)
    : periodMetricNote('Mijoz to‘lovlari', period)) + filterSuffix
  const salesNote = periodMetricNote('Faqat sotuvlar (import emas)', period) + filterSuffix
  const importNote = importPeriodNote(summary) + filterSuffix
  const overdueNote = (period.payment_status ? 'Filtrlangan to‘lovlar' : 'Hozirgi holat') + filterSuffix

  return (
    <div className="page">
      <div className="page-heading page-heading-compact">
        <div className="heading-actions">
          <DashboardFiltersMenu filters={period} onChange={onPeriodChange} />
          {can(session, 'einvoice_manage') && <button className="primary-button" onClick={onCreateBuyurtma}><Plus size={20} />Yangi buyurtma</button>}
        </div>
      </div>

      <section className="metric-grid">
        <Metric icon={CurrencyCircleDollar} label="Tushum" value={kassaValue} note={kassaNote} trend="up" />
        <Metric icon={Truck} label="Import" value={importPeriodLabel(summary)} note={importNote} trend="neutral" />
        <Metric icon={ClipboardText} label="Savdo" value={`${salesValue} so‘m`} note={salesNote} trend="up" />
        <Metric icon={Package} label="Ombordagi birliklar" value={money(warehouse.total_quantity)} note={`${warehouse.total_product_types || 0} turdagi mahsulot · hozirgi holat`} trend="neutral" />
        <Metric icon={FileText} label="Kechikkan to‘lovlar" value={summary.overdue_payments_count || 0} note={overdueNote} trend="down" />
      </section>
      <section className="dashboard-grid dashboard-grid-single">
        <div className="data-panel products-panel">
          <div className="panel-head">
            <div><p className="eyebrow">SOTUVLAR TAHLILI</p><h3>Eng faol mahsulotlar</h3></div>
            {can(session, 'sales_view') && <button className="text-button" onClick={() => onNavigate('Sotuvlar')}>Barchasi <span>→</span></button>}
          </div>
          <div className="product-list">
            {loading ? <SkeletonRows /> : products.length ? products.slice(0, 5).map((product, i) => (
              <div className="product-row" key={product.product || i}>
                <span className="rank">0{i + 1}</span>
                <div className="product-name"><b>{product.name}</b><small>{product.serial_number || 'Kodsiz mahsulot'}</small></div>
                <b>{product.sold_qty} dona</b>
              </div>
            )) : <Empty label="Sotuv ma’lumotlari hali yo‘q" />}
          </div>
        </div>
      </section>
      <section className="data-panel monthly-panel">
        <div className="panel-head">
          <div><p className="eyebrow">OYMA-OY</p><h3>Oylik moliyaviy ko‘rinish</h3></div>
        </div>
        {loading && !monthly.length ? <SkeletonRows /> : monthly.length ? (
          <table className="report-table monthly-table">
            <thead>
              <tr>
                <th>Oy</th>
                <th>Tushum</th>
                <th>Import</th>
                <th>Savdo</th>
              </tr>
            </thead>
            <tbody>
              {monthly.map((row) => (
                <tr key={`${row.year}-${row.month}`}>
                  <td><b>{row.label}</b></td>
                  <td>{money(row.kassa_uzs)} so‘m</td>
                  <td>
                    {Number(row.import_uzs) > 0
                      ? `${money(row.import_uzs)} so‘m`
                      : Number(row.import_usd) > 0
                        ? `$${money(row.import_usd)}`
                        : '—'}
                  </td>
                  <td>{money(row.sales_uzs)} so‘m</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty label="Oylik ma’lumotlar hali yo‘q" />}
      </section>
      <section className="lower-grid lower-grid-single">
        <div className="data-panel stock-panel">
          <div className="panel-head">
            <div><p className="eyebrow">OMBOR HOLATI</p><h3>Diqqat talab qiluvchi qoldiqlar</h3></div>
            {can(session, 'warehouse_view') && <button className="icon-button" aria-label="Omborga o‘tish" onClick={() => onNavigate('Ombor')}><Funnel size={19} /></button>}
          </div>
          {loading ? <SkeletonRows /> : list(warehouse.low_stock).length ? list(warehouse.low_stock).slice(0, 4).map((item) => (
            <div className="stock-row" key={item.product__id}>
              <span className="stock-icon"><Package size={18} /></span>
              <div><b>{item.product__name}</b><small>{item.product__serial_number}</small></div>
              <span className="warning-tag">{item.quantity} / min {item.product__min_quantity}</span>
            </div>
          )) : <Empty label="Kritik qoldiq aniqlanmadi" />}
        </div>
      </section>
    </div>
  )
}

function ReportsPage({ notify }) {
  const [tab, setTab] = useState('moliyaviy')
  const [data, setData] = useState(null)
  const [extra, setExtra] = useState(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState('')

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const [[summary, warehouse, cash, topProducts], expensesSummary, paymentsSummary] = await Promise.all([
        api.reports(),
        api.expensesSummary(),
        api.paymentsSummary(),
      ])
      setData({ summary, warehouse, cash, topProducts })
      setExtra({ expensesSummary, paymentsSummary })
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [notify])

  useEffect(() => { load() }, [load])
  useAutoRefresh(() => load(true))

  const summary = data?.summary || {}
  const warehouse = data?.warehouse || {}
  const cash = data?.cash || {}
  const products = data?.topProducts || []
  const expensesSummary = extra?.expensesSummary || {}
  const paymentsSummary = extra?.paymentsSummary || {}

  const tabs = [
    ['moliyaviy', 'Moliyaviy', CurrencyCircleDollar],
    ['ombor', 'Ombor', Package],
    ['sotuv', 'Sotuvlar', TrendUp],
    ['xarajat', 'Xarajatlar', ClipboardText],
    ['export', 'Excel', DownloadSimple],
  ]

  const exportFile = async (key, fn) => {
    setExporting(key)
    try {
      await fn()
      notify('Excel fayl yuklandi.', 'success')
    } catch (err) {
      notify(err.message)
    } finally {
      setExporting('')
    }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">TAHLILIY HISOBOT</p>
          <h1>Hisobotlar va statistika</h1>
        </div>
      </div>

      <div className="report-tabs">
        {tabs.map(([key, label, Icon]) => (
          <button key={key} className={tab === key ? 'tab-button is-active' : 'tab-button'} onClick={() => setTab(key)}>
            <Icon size={17} />{label}
          </button>
        ))}
      </div>

      {tab === 'moliyaviy' && (
        <>
          <div className="report-grid">
            <div className="report-stat"><span>Jami savdo daromadi</span><b>{money(summary.sales_revenue_total)} so‘m</b></div>
            <div className="report-stat"><span>Kassaga tushgan</span><b>{money(cash.sum_paid_uzs)} so‘m</b></div>
            <div className="report-stat"><span>Payment summary</span><b>{money(paymentsSummary.sum_paid_uzs)} so‘m</b></div>
            <div className="report-stat"><span>Kechikkan to‘lovlar</span><b>{summary.overdue_payments_count || 0} ta</b></div>
          </div>
          <section className="data-panel">
            <div className="panel-head"><div><p className="eyebrow">TO‘LOVLAR</p><h3>To‘lovlar bo‘yicha tafsilot</h3></div></div>
            {loading && !data ? <SkeletonRows /> : (
              <table className="report-table">
                <thead><tr><th>Holat</th><th>Soni</th><th>Ulushi</th></tr></thead>
                <tbody>
                  {[
                    ['To‘langan', cash.total_paid || 0, '#34d399'],
                    ['Qisman to‘langan', cash.total_partial || 0, '#fbbf24'],
                    ['Kechikkan', cash.total_overdue || 0, '#f87171'],
                  ].map(([label, count, color]) => {
                    const total = (cash.total_paid || 0) + (cash.total_partial || 0) + (cash.total_overdue || 0) || 1
                    const pct = Math.round((Number(count) / total) * 100)
                    return (
                      <tr key={label}>
                        <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><i className="status" style={{ background: color }} />{label}</span></td>
                        <td>{count}</td>
                        <td>{pct}%</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}

      {tab === 'xarajat' && (
        <>
          <div className="report-grid">
            <div className="report-stat"><span>Jami UZS xarajat</span><b>{money(expensesSummary.total_uzs)} so‘m</b></div>
            <div className="report-stat"><span>Jami USD xarajat</span><b>{money(expensesSummary.total_usd)} USD</b></div>
            <div className="report-stat"><span>Yozuvlar soni</span><b>{expensesSummary.count || 0}</b></div>
          </div>
          <section className="data-panel">
            <div className="panel-head"><div><p className="eyebrow">XARAJATLAR</p><h3>Toifalar bo‘yicha</h3></div></div>
            {list(expensesSummary.by_type).length ? (
              <table className="report-table">
                <thead><tr><th>Toifa</th><th>UZS</th><th>USD</th></tr></thead>
                <tbody>{list(expensesSummary.by_type).map((item) => (
                  <tr key={item.expense_type}><td>{item.name}</td><td>{money(item.total_uzs)} so‘m</td><td>{money(item.total_usd)} USD</td></tr>
                ))}</tbody>
              </table>
            ) : <Empty label="Xarajat summary ma’lumotlari yo‘q" />}
          </section>
        </>
      )}

      {tab === 'export' && (
        <section className="data-panel">
          <div className="panel-head"><div><p className="eyebrow">EXCEL EXPORT</p><h3>Hisobot fayllari</h3></div></div>
          <div className="export-grid">
            <button className="secondary-button" disabled={exporting === 'sales'} onClick={() => exportFile('sales', api.exportSales)}><DownloadSimple size={18} />Sotuvlar</button>
            <button className="secondary-button" disabled={exporting === 'stock'} onClick={() => exportFile('stock', api.exportStock)}><DownloadSimple size={18} />Ombor</button>
            <button className="secondary-button" disabled={exporting === 'expenses'} onClick={() => exportFile('expenses', api.exportExpenses)}><DownloadSimple size={18} />Xarajatlar</button>
            <button className="secondary-button" disabled={exporting === 'payments'} onClick={() => exportFile('payments', api.exportPayments)}><DownloadSimple size={18} />To‘lovlar</button>
          </div>
        </section>
      )}

      {tab === 'ombor' && (
        <>
          <div className="report-grid">
            <div className="report-stat"><span>Jami birliklar</span><b>{money(warehouse.total_quantity)}</b></div>
            <div className="report-stat"><span>Mahsulot turlari</span><b>{warehouse.total_product_types || 0}</b></div>
            <div className="report-stat"><span>Kritik qoldiqlar</span><b>{list(warehouse.low_stock).length}</b></div>
          </div>
          <section className="data-panel">
            <div className="panel-head"><div><p className="eyebrow">QOLDIQLAR</p><h3>Minimal qoldiqdan past mahsulotlar</h3></div></div>
            {loading && !data ? <SkeletonRows /> : list(warehouse.low_stock).length ? (
              <table className="report-table">
                <thead><tr><th>Mahsulot</th><th>Seriya</th><th>Qoldiq</th><th>Minimum</th></tr></thead>
                <tbody>
                  {list(warehouse.low_stock).map((item) => (
                    <tr key={item.product__id}>
                      <td>{item.product__name}</td>
                      <td>{item.product__serial_number || '—'}</td>
                      <td>{item.quantity}</td>
                      <td>{item.product__min_quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Empty label="Kritik qoldiq topilmadi" />}
          </section>
        </>
      )}

      {tab === 'sotuv' && (
        <>
          <div className="report-grid">
            <div className="report-stat"><span>Eng ko‘p sotilgan</span><b>{products[0]?.name || '—'}</b></div>
            <div className="report-stat"><span>Faol mahsulotlar</span><b>{products.length}</b></div>
            <div className="report-stat"><span>Jami sotilgan dona</span><b>{products.reduce((s, p) => s + Number(p.sold_qty || 0), 0)}</b></div>
          </div>
          <section className="data-panel">
            <div className="panel-head"><div><p className="eyebrow">REYTING</p><h3>Mahsulotlar bo‘yicha sotuvlar</h3></div></div>
            {loading && !data ? <SkeletonRows /> : products.length ? (
              <table className="report-table">
                <thead><tr><th>#</th><th>Mahsulot</th><th>Seriya</th><th>Sotilgan</th></tr></thead>
                <tbody>
                  {products.map((product, i) => (
                    <tr key={product.product || i}>
                      <td>{String(i + 1).padStart(2, '0')}</td>
                      <td>{product.name}</td>
                      <td>{product.serial_number || '—'}</td>
                      <td>{product.sold_qty} dona</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Empty label="Sotuv ma’lumotlari yo‘q" />}
          </section>
        </>
      )}
    </div>
  )
}

function Metric({ icon: Icon, label, value, note, trend }) {
  return (
    <article className="metric">
      <span className={`metric-icon ${trend}`}><Icon size={22} weight="duotone" /></span>
      <div>
        <p>{label}</p>
        <h2>{value}</h2>
        <small>{trend === 'up' ? <TrendUp size={14} /> : trend === 'down' ? <TrendDown size={14} /> : <Buildings size={14} />} {note}</small>
      </div>
    </article>
  )
}

function SkeletonRows() {
  return <div className="skeleton-wrap"><i /><i /><i /><i /></div>
}

function Empty({ label }) {
  return <div className="empty"><Package size={24} weight="thin" /><span>{label}</span></div>
}

const resources = {
  'Import': { load: api.zakaz, path: '/orders/zakaz/' },
  'Shartnomalar': { load: api.contracts, path: '/orders/contracts/', readonly: true },
  'Ombor': { load: api.products, path: '/warehouse/products/' },
  'Kategoriyalar': { load: api.categories, path: '/warehouse/categories/' },
  'Qoldiqlar': { load: api.stocks, path: '/warehouse/stocks/' },
  'Mijozlar': { load: api.clients, path: '/clients/' },
  'Sotuvlar': { load: api.sales, path: '/sales/' },
  'Kassa': { load: api.payments, path: '/cash/payments/' },
  'Xarajatlar': { load: api.expenses, path: '/expenses/expenses/' },
  'Foydalanuvchilar': { load: api.users, path: '/auth/users/' },
  'Bildirishnomalar': { load: api.notifications, path: '/notifications/' },
}

function rowTitle(title, row) {
  if (title === 'Shartnomalar') return row.contract_number || `Reestr #${row.id}`
  if (title === 'Import') return row.product_name || `Import #${row.id}`
  if (title === 'Qoldiqlar') return row.product_name || row.product || `Qoldiq #${row.id}`
  if (title === 'Foydalanuvchilar') return row.username
  return row.company_name || row.full_name || row.client_name || row.name || `Hujjat #${row.id}`
}

function rowMeta(title, row) {
  if (title === 'Shartnomalar') {
    const parts = [row.product_name, row.source_type_display]
    if (row.asos && row.asos !== row.source_type_display) parts.push(row.asos)
    return parts.filter(Boolean).join(' • ') || row.created_at || '—'
  }
  if (title === 'Import') return [row.status_display || row.status, row.supplier, row.expected_date].filter(Boolean).join(' • ') || '—'
  if (title === 'Qoldiqlar') return [row.warehouse_location, `bron: ${row.reserved_quantity || 0}`].filter(Boolean).join(' • ')
  if (title === 'Foydalanuvchilar') return [row.role, row.is_active ? 'faol' : 'bloklangan'].filter(Boolean).join(' • ')
  if (title === 'Mijozlar') return [row.phone, row.inn, row.pinfl, row.passport_number, row.director_jshshr].filter(Boolean).join(' • ') || row.created_at || '—'
  return row.serial_number || row.status || row.phone || row.created_at || '—'
}

function rowValue(title, row, session) {
  const showPrices = can(session, 'prices_view')
  if (title === 'Import') {
    if (!showPrices || !row.total) return `${row.quantity || 0} dona`
    return `${money(row.total)} ${row.currency || ''}`
  }
  if (title === 'Qoldiqlar') return quantityWithUnit(row.quantity || 0, row)
  if (title === 'Ombor') return quantityWithUnit(row.available_quantity ?? row.quantity_in_stock ?? 0, row)
  if (title === 'Shartnomalar') return row.contract_date || '—'
  if (title === 'Foydalanuvchilar') return row.can_view_clients ? 'Mijoz: bor' : 'Mijoz: yo‘q'
  if (title === 'Sotuvlar') {
    if (!showPrices) return `${row.quantity || 0} dona`
    return row.total_amount ? `${money(row.total_amount)} so‘m` : `${row.quantity || 0} dona`
  }
  if (title === 'Kassa') {
    if (!showPrices) return row.status_display || row.status || '—'
    return row.total_amount ? `${money(row.total_amount)} so‘m` : (row.remaining ? `${money(row.remaining)} qolgan` : '—')
  }
  if (!showPrices) return row.quantity || row.total_quantity || '—'
  return row.total_amount ? `${money(row.total_amount)} so‘m` : (row.available_quantity ?? row.total ?? '—')
}

const GRID_PAGES = new Set(['Mijozlar', 'Sotuvlar', 'Import', 'Ombor', 'Kassa', 'Xarajatlar'])

const ORDER_STATUS_BADGES = {
  pending: { label: 'Kutilmoqda', tone: 'warning' },
  partial: { label: 'Qisman', tone: 'warning' },
  reserved: { label: 'Bron', tone: 'info' },
  fulfilled: { label: 'Yetkazildi', tone: 'success' },
  cancelled: { label: 'Bekor', tone: 'danger' },
  new: { label: 'Yangi', tone: 'info' },
  confirmed: { label: 'Tasdiqlandi', tone: 'info' },
  received: { label: 'Qabul qilindi', tone: 'success' },
  paid: { label: 'To‘langan', tone: 'success' },
  overdue: { label: 'Muddati o‘tgan', tone: 'danger' },
}

const GRID_SORT_FIELDS = {
  Mijozlar: { name: 'company_name', created_at: 'created_at', status: 'is_active' },
  Sotuvlar: { product: 'sold_date', created_at: 'sold_date', total: 'sold_date' },
  Import: { product: 'created_at', created_at: 'created_at', status: 'status' },
  Ombor: { name: 'name', created_at: 'created_at', quantity: 'name' },
  Kassa: { client: 'due_date', created_at: 'created_at', status: 'status' },
  Xarajatlar: { amount: 'date', created_at: 'date' },
}

function getGridColumns(title, session, { renderStatus } = {}) {
  const showPrices = can(session, 'prices_view')
  if (title === 'Mijozlar') {
    return [
      { key: 'name', label: 'Nom', sortable: true, exportValue: (row) => row.company_name || row.full_name || '', render: (row) => row.company_name || row.full_name || '—' },
      { key: 'phone', label: 'Telefon', render: (row) => row.phone || '—' },
      { key: 'inn', label: 'STIR', render: (row) => row.inn || '—' },
      { key: 'created_at', label: 'Sana', sortable: true, render: (row) => formatDateUz(row.created_at) },
      { key: 'status', label: 'Status', sortable: true, render: (row) => (
        renderStatus?.(row) || (
          <StatusBadge status={row.is_active ? 'active' : 'inactive'} label={row.is_active ? 'Faol' : 'Nofaol'} tone={row.is_active ? 'success' : 'neutral'} />
        )
      ) },
    ]
  }
  if (title === 'Sotuvlar') {
    return [
      { key: 'product', label: 'Mahsulot', sortable: true, render: (row) => row.product_name || row.product || '—' },
      { key: 'client', label: 'Mijoz', render: (row) => row.client_name || row.sold_to || '—' },
      { key: 'total', label: 'Summa', sortable: true, render: (row) => rowValue(title, row, session) },
      { key: 'created_at', label: 'Sana', sortable: true, render: (row) => formatDateUz(row.sold_date || row.created_at) },
    ]
  }
  if (title === 'Import') {
    return [
      { key: 'product', label: 'Mahsulot', sortable: true, exportValue: (row) => rowTitle(title, row), render: (row) => rowTitle(title, row) },
      { key: 'status', label: 'Status', sortable: true, render: (row) => {
        if (renderStatus) return renderStatus(row)
        const meta = ORDER_STATUS_BADGES[row.status] || { label: row.status_display || row.status, tone: 'neutral' }
        return <StatusBadge status={row.status} label={meta.label} tone={meta.tone} />
      } },
      { key: 'total', label: 'Summa', render: (row) => rowValue(title, row, session) },
      { key: 'created_at', label: 'Sana', sortable: true, render: (row) => formatDateUz(row.expected_date || row.created_at) },
    ]
  }
  if (title === 'Ombor') {
    return [
      { key: 'name', label: 'Mahsulot', sortable: true, render: (row) => row.name || '—' },
      { key: 'serial', label: 'Seriya', render: (row) => row.serial_number || '—' },
      { key: 'quantity', label: 'Qoldiq', sortable: true, render: (row) => rowValue(title, row, session) },
      { key: 'created_at', label: 'Joy', render: (row) => row.warehouse_location || '—' },
    ]
  }
  if (title === 'Kassa') {
    return [
      { key: 'client', label: 'Mijoz', sortable: true, render: (row) => row.client_name || '—' },
      { key: 'status', label: 'Status', sortable: true, render: (row) => {
        const meta = ORDER_STATUS_BADGES[row.status] || { label: row.status_display || row.status, tone: 'neutral' }
        return <StatusBadge status={row.status} label={meta.label} tone={meta.tone} />
      } },
      { key: 'total', label: 'Summa', render: (row) => rowValue(title, row, session) },
      { key: 'created_at', label: 'Muddat', sortable: true, render: (row) => formatDateUz(row.due_date) },
    ]
  }
  if (title === 'Xarajatlar') {
    return [
      { key: 'type', label: 'Toifa', render: (row) => row.expense_type_name || row.expense_type || '—' },
      { key: 'amount', label: 'Summa', sortable: true, render: (row) => `${money(row.amount)} ${row.currency || 'UZS'}` },
      { key: 'created_at', label: 'Sana', sortable: true, render: (row) => formatDateUz(row.date || row.created_at) },
      { key: 'comment', label: 'Izoh', render: (row) => row.comment || '—' },
    ]
  }
  return []
}

function ContractDetailModal({ id, close, onNavigate, navigateToPath }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError('')
      try {
        const data = await api.retrieve('/orders/contracts/', id)
        if (!cancelled) setDetail(data)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [id])

  const goTo = (page) => {
    close()
    onNavigate?.(page)
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <div className="editor contract-detail-modal">
        <div className="editor-head">
          <div>
            <p className="eyebrow">SHARTNOMA REESTRI</p>
            <h3>{detail?.contract_number || `Yozuv #${id}`}</h3>
            {detail?.product_name && <p className="muted">{detail.product_name}</p>}
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button>
        </div>
        {loading ? (
          <div className="contract-detail-loading"><SpinnerGap size={28} className="spin" /></div>
        ) : error ? (
          <p className="contract-detail-error">{error}</p>
        ) : detail ? (
          <>
            <dl className="contract-detail-grid">
              <div><dt>Shartnoma raqami</dt><dd>{detail.contract_number || '—'}</dd></div>
              <div><dt>Sana</dt><dd>{detail.contract_date || '—'}</dd></div>
              <div><dt>Mahsulot</dt><dd>{detail.product_name || '—'}</dd></div>
              <div><dt>Manba</dt><dd>{detail.source_type_display || detail.source_type || '—'}</dd></div>
              <div className="contract-detail-wide"><dt>Asos</dt><dd>{detail.asos || '—'}</dd></div>
              <div><dt>Faktura</dt><dd>{detail.faktura || '—'}</dd></div>
              <div><dt>Buyurtma</dt><dd>{detail.order ? `#${detail.order}` : '—'}</dd></div>
              <div><dt>Import</dt><dd>{detail.zakaz ? `#${detail.zakaz}` : '—'}</dd></div>
              <div><dt>Buyurtma (SK)</dt><dd>{detail.invoice ? detail.contract_number || `#${detail.invoice}` : '—'}</dd></div>
              <div><dt>Yaratgan</dt><dd>{detail.created_by_name || '—'}</dd></div>
              <div><dt>Yaratilgan vaqt</dt><dd>{detail.created_at || '—'}</dd></div>
            </dl>
            {(detail.order || detail.zakaz || detail.invoice) && onNavigate && (
              <div className="contract-detail-links">
                {detail.invoice && navigateToPath && (
                  <button type="button" className="secondary-button" onClick={() => { close(); navigateToPath(invoiceDetailPath(detail.invoice)) }}>
                    Buyurtmaga (SK) o‘tish
                  </button>
                )}
                {detail.order && (
                  <button type="button" className="secondary-button" onClick={() => goTo('Buyurtmalar')}>
                    Buyurtmaga o‘tish
                  </button>
                )}
                {detail.zakaz && (
                  <button type="button" className="secondary-button" onClick={() => goTo('Import')}>
                    Importga o‘tish
                  </button>
                )}
              </div>
            )}
          </>
        ) : null}
        <div className="editor-actions">
          <button type="button" className="primary-button" onClick={close}>Yopish</button>
        </div>
      </div>
    </div>
  )
}

function ProductContractsModal({ product, rows, close, onViewAll, onViewDetail }) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="editor product-contracts-modal">
        <div className="editor-head">
          <div>
            <p className="eyebrow">SHARTNOMALAR REESTRI</p>
            <h3>{product.name}</h3>
            <p className="muted">{product.serial_number || 'Seriya raqamsiz mahsulot'}</p>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button>
        </div>
        <p className="contracts-intro">
          Bu mahsulot bo‘yicha qaysi shartnoma, qaysi asos va qaysi amal (buyurtma, import, kirim) bilan ishlaganingizning rasmiy yozuvlari.
        </p>
        {rows.length ? (
          <div className="contracts-list">
            {rows.map((entry) => (
              <article
                className={`contract-card${onViewDetail ? ' contract-card-clickable' : ''}`}
                key={entry.id}
                role={onViewDetail ? 'button' : undefined}
                tabIndex={onViewDetail ? 0 : undefined}
                onClick={onViewDetail ? () => onViewDetail(entry.id) : undefined}
                onKeyDown={onViewDetail ? (event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onViewDetail(entry.id)
                  }
                } : undefined}
              >
                <div className="contract-card-head">
                  <b>{entry.contract_number || `Yozuv #${entry.id}`}</b>
                  <span>{entry.source_type_display || entry.source_type}</span>
                </div>
                <p>{entry.asos || 'Asos kiritilmagan'}</p>
                <small>
                  {[entry.contract_date, entry.faktura, entry.created_by_name].filter(Boolean).join(' • ')}
                </small>
              </article>
            ))}
          </div>
        ) : (
          <Empty label="Bu mahsulot uchun hali reestr yozuvi yo‘q" />
        )}
        <div className="editor-actions">
          {onViewAll && rows.length > 0 && (
            <button type="button" className="secondary-button" onClick={onViewAll}>Shartnomalar bo‘limi</button>
          )}
          <button type="button" className="primary-button" onClick={close}>Yopish</button>
        </div>
      </div>
    </div>
  )
}

function ResourcePage({ title, notify, reloadKey = 0, session, onDataChange, onNavigate, navigateToPath }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [listFilters, setListFilters] = useState({ status: '', client: '', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [sortKey, setSortKey] = useState('created_at')
  const [sortDir, setSortDir] = useState('desc')
  const [selectedIds, setSelectedIds] = useState([])
  const [statusChange, setStatusChange] = useState(null)
  const pageSize = 25
  const useGrid = GRID_PAGES.has(title)
  const [editing, setEditing] = useState(null)
  const [opening, setOpening] = useState(false)
  const [paying, setPaying] = useState(null)
  const [stockProduct, setStockProduct] = useState(null)
  const [contractProduct, setContractProduct] = useState(null)
  const [contractDetailId, setContractDetailId] = useState(null)

  const apiSortField = GRID_SORT_FIELDS[title]?.[sortKey] || sortKey
  const apiOrdering = `${sortDir === 'desc' ? '-' : ''}${apiSortField}`

  const load = useCallback(async (silent = false, term = searchTerm) => {
    if (!resources[title]) return
    if (!silent) setLoading(true)
    try {
      const filterParams = useGrid ? buildListQueryParams(title, listFilters) : {}
      const params = useGrid
        ? { page, page_size: pageSize, ordering: apiOrdering, ...filterParams, ...(term ? { search: term } : {}) }
        : (term ? { search: term } : {})
      const data = await resources[title].load(params)
      if (data?.results) {
        setRows(data.results)
        setTotalCount(data.count || 0)
      } else {
        const payload = list(data)
        setRows(payload)
        setTotalCount(payload.length)
      }
      setSelectedIds([])
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [title, notify, searchTerm, page, apiOrdering, useGrid, listFilters])

  useEffect(() => { setPage(1) }, [searchTerm, title, listFilters])
  useEffect(() => { load() }, [load, reloadKey])
  useAutoRefresh(() => load(true))

  const refreshAfterChange = () => {
    load(true)
    onDataChange?.()
  }

  const manageAbilities = {
    'Import': 'procurement_manage',
    'Ombor': 'warehouse_manage',
    'Kategoriyalar': 'warehouse_manage',
    'Qoldiqlar': 'warehouse_manage',
    'Mijozlar': 'clients_manage',
    'Sotuvlar': 'sales_manage',
    'Kassa': 'cash_manage',
    'Xarajatlar': 'expenses_manage',
    'Foydalanuvchilar': 'users_manage',
  }
  const createAbilities = {
    'Ombor': 'warehouse_create',
  }
  const canManage = can(session, manageAbilities[title])
  const canCreate = (can(session, createAbilities[title] || manageAbilities[title]))
    && ['Mijozlar', 'Ombor', 'Import', 'Kategoriyalar', 'Qoldiqlar', 'Sotuvlar', 'Xarajatlar', 'Foydalanuvchilar'].includes(title)
  const canEditRows = canManage && !resources[title]?.readonly

  const handleMarkRead = async (id) => {
    try {
      await api.notificationsMarkRead(id)
      await load(true)
      notify('Bildirishnoma o‘qilgan deb belgilandi.', 'success')
    } catch (err) {
      notify(err.message)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await api.notificationsMarkAllRead()
      await load(true)
      notify('Hammasi o‘qilgan deb belgilandi.', 'success')
    } catch (err) {
      notify(err.message)
    }
  }

  const handleSearch = (event) => {
    event.preventDefault()
    setSearchTerm(search.trim())
  }

  const handleEdit = async (row) => {
    if (!resources[title]) return
    setOpening(true)
    try {
      const detail = await api.retrieve(resources[title].path, row.id)
      setEditing(detail)
    } catch (err) {
      notify(err.message)
    } finally {
      setOpening(false)
    }
  }

  const handleSort = (key) => {
    if (sortKey === key) setSortDir((value) => (value === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const handleRowClick = (row) => {
    if (title === 'Mijozlar') navigateToPath?.(clientDetailPath(row.id))
    else if (title === 'Shartnomalar') setContractDetailId(row.id)
  }

  const selectedRows = useMemo(
    () => rows.filter((row) => selectedIds.includes(row.id)),
    [rows, selectedIds],
  )

  const gridColumns = useMemo(() => getGridColumns(title, session, {
    renderStatus: (row) => {
      if (title === 'Import' && can(session, 'order_status_manage')) {
        const locked = ['received', 'cancelled'].includes(row.status)
        const transitions = {
          new: ['new', 'confirmed', 'cancelled'],
          confirmed: ['confirmed', 'received', 'cancelled'],
          received: ['received'],
          cancelled: ['cancelled'],
        }
        const allowed = transitions[row.status] || [row.status]
        const options = allowed.map((value) => ({
          value,
          label: ORDER_STATUS_BADGES[value]?.label || value,
        }))
        return (
          <InlineStatusSelect
            value={row.status}
            options={options}
            disabled={locked}
            onChange={(next) => {
              if (next === row.status) return
              setStatusChange({ mode: 'import', rows: [row], targetStatus: next })
            }}
          />
        )
      }
      const meta = ORDER_STATUS_BADGES[row.status] || { label: row.status_display || row.status, tone: 'neutral' }
      if (title === 'Mijozlar') {
        return <StatusBadge status={row.is_active ? 'active' : 'inactive'} label={row.is_active ? 'Faol' : 'Nofaol'} tone={row.is_active ? 'success' : 'neutral'} />
      }
      return <StatusBadge status={row.status} label={meta.label} tone={meta.tone} />
    },
  }), [title, session])

  const handleBulkExport = () => {
    if (!selectedRows.length) return
    exportRowsCsv(`${title.toLowerCase()}-export.csv`, gridColumns, selectedRows)
    notify(`${selectedRows.length} ta yozuv eksport qilindi.`, 'success')
  }

  const handleBulkStatus = () => {
    if (!selectedRows.length || title !== 'Import') return
    setStatusChange({ mode: 'import', rows: selectedRows, targetStatus: listFilters.status || 'confirmed' })
  }

  const submitStatusChange = async (payload) => {
    const { mode, rows: targetRows } = statusChange
    const targetStatus = payload.targetStatus || statusChange.targetStatus
    if (mode === 'import') {
      for (const row of targetRows) {
        const body = {
          status: targetStatus,
          asos: payload.asos,
          contract_number: payload.contract_number || row.contract_number,
          faktura: payload.faktura || row.faktura,
        }
        if (targetStatus === 'received') body.received_qty = payload.received_qty || row.quantity
        await api.update('/orders/zakaz/', row.id, body)
      }
      notify('Import statusi yangilandi.', 'success')
    }
    setStatusChange(null)
    refreshAfterChange()
  }

  const emptyCfg = emptyStateConfig(title)
  const showEmptyCta = !searchTerm && !hasActiveListFilters(listFilters) && canCreate

  const renderRowActions = (row) => (
    <>
      {canEditRows && <button className="row-action" disabled={opening} onClick={() => handleEdit(row)} aria-label="Tahrirlash"><PencilSimple size={18} /></button>}
      {can(session, 'warehouse_manage') && title === 'Ombor' && <button className="row-action" onClick={() => setStockProduct(row)} aria-label="Kirim">Kirim</button>}
      {can(session, 'cash_manage') && title === 'Kassa' && row.remaining !== '0' && (
        <button className="row-action" onClick={() => setPaying(row)} aria-label="To‘lov"><CurrencyCircleDollar size={18} /></button>
      )}
    </>
  )

  return (
    <div className="page resource-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">MODUL</p>
          <h1>{getPageDisplayTitle(title)}</h1>
          {title === 'Shartnomalar' && (
            <p className="contracts-registry-note">
              Yozuvlar avtomatik yaratiladi (buyurtma SK, import, kirim). Qo‘lda qo‘shish mumkin emas.
            </p>
          )}
        </div>
        <div className="heading-actions">
          {title === 'Bildirishnomalar' && (
            <button className="secondary-button" onClick={handleMarkAllRead}>Hammasini o‘qilgan</button>
          )}
          {canCreate && <button className="primary-button" onClick={() => setEditing({})}><Plus size={20} />Yangi qo‘shish</button>}
        </div>
      </div>
      <section className="data-panel">
        <div className="panel-head">
          <div><p className="eyebrow">RO‘YXAT</p><h3>{useGrid ? totalCount : rows.length} ta yozuv</h3></div>
          <div className="panel-head-actions">
            {useGrid && <ListFiltersPanel title={title} filters={listFilters} onChange={setListFilters} />}
            <form className="resource-search" onSubmit={handleSearch}>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Qidirish" aria-label={`${title} qidirish`} />
              <button type="submit" className="icon-button" aria-label="Qidirish"><MagnifyingGlass size={20} /></button>
            </form>
          </div>
        </div>
        {useGrid && (
          <BulkActionsBar count={selectedIds.length} onClear={() => setSelectedIds([])}>
            <button type="button" className="secondary-button" disabled={!selectedIds.length} onClick={handleBulkExport}>
              <DownloadSimple size={18} />
              Eksport
            </button>
            {title === 'Import' && can(session, 'order_status_manage') && (
              <button type="button" className="secondary-button" disabled={!selectedIds.length} onClick={handleBulkStatus}>
                Status o‘zgartirish
              </button>
            )}
          </BulkActionsBar>
        )}
        {useGrid ? (
          <>
            <DataTable
              columns={gridColumns}
              rows={rows}
              sortKey={sortKey}
              sortDir={sortDir}
              onSort={handleSort}
              loading={loading}
              onRowClick={['Mijozlar', 'Shartnomalar'].includes(title) ? handleRowClick : undefined}
              renderActions={renderRowActions}
              emptyLabel={title === 'Shartnomalar' ? 'Hali reestr yozuvi yo‘q.' : emptyCfg.label}
              emptyCta={showEmptyCta && emptyCfg.cta ? {
                label: emptyCfg.label,
                ctaLabel: emptyCfg.cta,
                onCta: () => setEditing({}),
              } : null}
              selectable={useGrid}
              selectedIds={selectedIds}
              onSelectionChange={setSelectedIds}
            />
            <TablePagination page={page} pageSize={pageSize} total={totalCount} onPageChange={setPage} />
          </>
        ) : loading && !rows.length ? <SkeletonRows /> : !rows.length ? (
          title === 'Shartnomalar' ? (
            <Empty label="Hali reestr yozuvi yo‘q. Buyurtma, import yoki ombor kirimi amalga oshganda yozuvlar avtomatik paydo bo‘ladi." />
          ) : (
            <Empty label="Yozuv topilmadi" />
          )
        ) : (
          <div className="product-list">
            {rows.map((row, index) => (
              <div
                className={`product-row${title === 'Shartnomalar' ? ' product-row-clickable' : ''}`}
                key={row.id || index}
                onClick={title === 'Shartnomalar' ? () => setContractDetailId(row.id) : undefined}
                onKeyDown={title === 'Shartnomalar' ? (event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    setContractDetailId(row.id)
                  }
                } : undefined}
                role={title === 'Shartnomalar' ? 'button' : undefined}
                tabIndex={title === 'Shartnomalar' ? 0 : undefined}
              >
                <span className="rank">{String(index + 1).padStart(2, '0')}</span>
                {title === 'Bildirishnomalar' ? (
                  <>
                    <div className="product-name">
                      <b>{row.title}</b>
                      <small>{row.message}</small>
                    </div>
                    <b>{row.is_read ? 'O‘qilgan' : 'Yangi'}</b>
                    <button className="row-action" onClick={() => handleMarkRead(row.id)}>{row.is_read ? '✓' : 'O‘qish'}</button>
                  </>
                ) : (
                  <>
                    <div className="product-name">
                      <b>{rowTitle(title, row)}</b>
                      <small>{rowMeta(title, row)}</small>
                    </div>
                    <b>{rowValue(title, row, session)}</b>
                    <div className="row-actions">
            {canEditRows && <button className="row-action" disabled={opening} onClick={() => handleEdit(row)} aria-label="Tahrirlash"><PencilSimple size={18} /></button>}
                      {can(session, 'warehouse_manage') && title === 'Ombor' && <button className="row-action" onClick={() => setStockProduct(row)} aria-label="Kirim qilish">Kirim</button>}
                      {can(session, 'cash_manage') && title === 'Kassa' && row.remaining !== '0' && (
                        <button className="row-action" onClick={() => setPaying(row)} aria-label="To‘lov qabul qilish"><CurrencyCircleDollar size={18} /></button>
                      )}
                      {title === 'Shartnomalar' && (
                        <button
                          className="row-action"
                          aria-label="Ko‘rish"
                          onClick={(event) => {
                            event.stopPropagation()
                            setContractDetailId(row.id)
                          }}
                        >
                          <Eye size={18} />
                        </button>
                      )}
                      {title === 'Ombor' && (
                        <button
                          className="row-action"
                          title="Mahsulot shartnomalari reestri"
                          onClick={async (event) => {
                            event.stopPropagation()
                            setOpening(true)
                            try {
                              const rows = list(await api.productContracts(row.id))
                              if (!rows.length) {
                                notify('Bu mahsulot bo‘yicha hali shartnoma reestri yozuvi yo‘q.', 'warning')
                                return
                              }
                              setContractProduct({ product: row, rows })
                            } catch (err) {
                              notify(err.message)
                            } finally {
                              setOpening(false)
                            }
                          }}
                        >
                          Reestr
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
      {editing && (title === 'Import'
          ? <ZakazEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} session={session} />
        : title === 'Sotuvlar'
          ? <SaleEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} session={session} />
        : title === 'Foydalanuvchilar'
            ? <UserEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} />
          : title === 'Xarajatlar'
            ? <ExpenseEditor item={editing.id ? editing : null} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} session={session} />
            : <Editor title={title} item={editing} path={resources[title].path} close={() => setEditing(null)} done={() => { setEditing(null); refreshAfterChange() }} notify={notify} session={session} />
      )}
      {paying && <PaymentEditor item={paying} close={() => setPaying(null)} done={() => { setPaying(null); refreshAfterChange() }} notify={notify} />}
      {stockProduct && <StockInEditor item={stockProduct} close={() => setStockProduct(null)} done={() => { setStockProduct(null); refreshAfterChange() }} notify={notify} />}
      {contractProduct && (
        <ProductContractsModal
          product={contractProduct.product}
          rows={contractProduct.rows}
          close={() => setContractProduct(null)}
          onViewAll={can(session, 'contracts_view') && onNavigate
            ? () => { setContractProduct(null); onNavigate('Shartnomalar') }
            : null}
          onViewDetail={can(session, 'contracts_view')
            ? (entryId) => { setContractProduct(null); setContractDetailId(entryId) }
            : null}
        />
      )}
      {contractDetailId && (
        <ContractDetailModal
          id={contractDetailId}
          close={() => setContractDetailId(null)}
          onNavigate={onNavigate}
          navigateToPath={navigateToPath}
        />
      )}
      {statusChange && (
        <StatusChangeModal
          mode={statusChange.mode}
          rows={statusChange.rows}
          targetStatus={statusChange.targetStatus}
          onClose={() => setStatusChange(null)}
          onSubmit={submitStatusChange}
        />
      )}
    </div>
  )
}

const fields = {
  Ombor: [['name', 'Mahsulot nomi', true], ['model', 'Model'], ['serial_number', 'Seriya raqami', true], ['barcode', 'Shtrix kod'], ['source', 'Manba / yetkazuvchi'], ['unit', 'O‘lchov birligi'], ['min_quantity', 'Minimal qoldiq'], ['purchase_price', 'Kelish narxi'], ['selling_price', 'Sotuv narxi'], ['delivery_price', 'Yetkazish narxi'], ['vat_percent', 'QQS %'], ['quantity', 'Boshlang‘ich miqdor'], ['warehouse_location', 'Ombordagi joy']],
  Kategoriyalar: [['name', 'Kategoriya nomi', true], ['parent', 'Ota kategoriya']],
  Qoldiqlar: [['product', 'Mahsulot ID', true], ['quantity', 'Miqdor', true], ['reserved_quantity', 'Bron miqdor'], ['warehouse_location', 'Ombordagi joy', true]],
}

function validateClientForm(form) {
  return validateClientFields(form)
}

function validateEditorForm(title, form, visibleFields) {
  const errors = {}
  if (title === 'Mijozlar') return validateClientForm(form)
  visibleFields?.forEach(([key, label, required]) => {
    if (required && !(String(form[key] ?? '').trim())) errors[key] = `${label} kiritilishi shart`
  })
  return errors
}

function Editor({ title, item, path, close, done, notify, session }) {
  const [form, setForm] = useState(() => ({ ...item, client_type: item?.client_type || 'individual' }))
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [categories, setCategories] = useState([])
  const canManagePrices = can(session, 'prices_manage')
  const canDelete = Boolean(item?.id && ['Mijozlar', 'Ombor', 'Kategoriyalar', 'Qoldiqlar'].includes(title))

  useEffect(() => {
    if (title !== 'Kategoriyalar') return
    api.categories({ page_size: 200 })
      .then((data) => setCategories(list(data)))
      .catch((err) => notify(err.message))
  }, [title, notify])

  const parentOptions = useMemo(() => {
    if (title !== 'Kategoriyalar') return []
    const flat = flattenCategories(categories)
    if (!item?.id) return flat
    const node = findCategoryNode(categories, item.id)
    const excluded = new Set([item.id, ...collectDescendantIds(node)])
    return flat.filter((cat) => !excluded.has(cat.id))
  }, [title, categories, item?.id])
  const visibleFields = title === 'Ombor'
    ? fields[title].filter(([key]) => {
      if (key === 'purchase_price' || key === 'selling_price' || key === 'min_quantity' || key === 'delivery_price') return canManagePrices
      if (key === 'vat_percent') return can(session, 'prices_view')
      return true
    })
    : fields[title]

  const submit = async (event) => {
    event.preventDefault()
    const nextErrors = validateEditorForm(title, form, visibleFields)
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors)
      return
    }
    setErrors({})
    setSaving(true)
    const payload = Object.fromEntries(Object.entries(form).filter(([key, value]) => !['id', 'created_at', 'quantity_in_stock', 'available_quantity', 'reserved_quantity', 'stock_status', 'category_name', 'unit_display'].includes(key) && value !== undefined && value !== ''))
    if (title === 'Ombor') {
      if (payload.min_quantity) payload.min_quantity = Number(payload.min_quantity)
      if (payload.quantity) payload.quantity = Number(payload.quantity)
      if (!canManagePrices) {
        delete payload.purchase_price
        delete payload.selling_price
        delete payload.min_quantity
      }
    }
    if (title === 'Qoldiqlar') {
      if (payload.product) payload.product = Number(payload.product)
      if (payload.quantity) payload.quantity = Number(payload.quantity)
      if (payload.reserved_quantity) payload.reserved_quantity = Number(payload.reserved_quantity)
    }
    if (title === 'Kategoriyalar') {
      if (payload.parent) payload.parent = Number(payload.parent)
    }
    if (title === 'Mijozlar') {
      if (payload.client_type === 'individual') {
        payload.full_name = (payload.full_name || '').trim()
        payload.first_name = ''
        payload.last_name = ''
        payload.middle_name = ''
        payload.company_name = ''
        payload.inn = ''
      } else {
        payload.first_name = ''
        payload.last_name = ''
        payload.middle_name = ''
        payload.pinfl = ''
        payload.passport_number = ''
        payload.full_name = ''
      }
    }
    try {
      const result = item.id ? await api.update(path, item.id, payload) : await api.create(path, payload)
      done(result)
    } catch (err) {
      if (err.fields && Object.keys(err.fields).length) setErrors((current) => ({ ...current, ...err.fields }))
      else notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await api.remove(path, item.id)
      notify('Yozuv o‘chirildi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setDeleting(false)
      setDeleteConfirm(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head">
          <div><p className="eyebrow">{item.id ? 'TAHRIRLASH' : 'YANGI YOZUV'}</p><h3>{editorSectionTitle(title)} ma’lumotlari</h3></div>
          <button type="button" className="icon-button" onClick={close}><X size={20} /></button>
        </div>
        <div className="form-grid">
          {title === 'Mijozlar' ? (
            <>
              <label>Tur
                <select value={form.client_type || 'individual'} onChange={(event) => setForm({ ...form, client_type: event.target.value })}>
                  <option value="individual">Jismoniy shaxs</option>
                  <option value="legal">Yuridik shaxs</option>
                </select>
              </label>
              {form.client_type === 'legal' ? (
                <>
                  <label>Korxona nomi<input value={form.company_name ?? ''} onChange={(event) => setForm({ ...form, company_name: event.target.value })} /><FieldError message={errors.company_name} /></label>
                  <label className={errors.inn ? 'field-invalid' : ''}>INN (STIR)
                    <input value={form.inn ?? ''} onChange={(event) => { setErrors((current) => { const next = { ...current }; delete next.inn; return next }); setForm({ ...form, inn: event.target.value.replace(/\D/g, '').slice(0, 9) }) }} inputMode="numeric" placeholder="9 ta raqam" aria-invalid={Boolean(errors.inn)} />
                    <FieldError message={errors.inn} />
                  </label>
                  <label>Rahbar JSHSHIR<input value={form.director_jshshr ?? ''} onChange={(event) => setForm({ ...form, director_jshshr: event.target.value.replace(/\D/g, '').slice(0, 14) })} inputMode="numeric" placeholder="14 ta raqam" /></label>
                  <label>Rahbar F.I.Sh.<input value={form.director_fish ?? ''} onChange={(event) => setForm({ ...form, director_fish: event.target.value })} /></label>
                  <label className={errors.mfo ? 'field-invalid' : ''}>MFO
                    <input value={form.mfo ?? ''} onChange={(event) => { setErrors((current) => { const next = { ...current }; delete next.mfo; return next }); setForm({ ...form, mfo: event.target.value.replace(/\D/g, '').slice(0, 5) }) }} inputMode="numeric" placeholder="5 ta raqam" aria-invalid={Boolean(errors.mfo)} />
                    <FieldError message={errors.mfo} />
                  </label>
                  <label>OKED<input value={form.oked ?? ''} onChange={(event) => setForm({ ...form, oked: event.target.value })} /></label>
                  <label>Bank nomi<input value={form.bank_name ?? ''} onChange={(event) => setForm({ ...form, bank_name: event.target.value })} /></label>
                  <label>Hisob raqami<input value={form.bank_account ?? ''} onChange={(event) => setForm({ ...form, bank_account: event.target.value })} /></label>
                  <label>Telefon<input value={form.phone ?? ''} onChange={(event) => setForm({ ...form, phone: event.target.value })} /><FieldError message={errors.phone} /></label>
                  <label>E-mail<input type="email" value={form.email ?? ''} onChange={(event) => setForm({ ...form, email: event.target.value })} /><FieldError message={errors.email} /></label>
                  <label>Manzil<input value={form.address ?? ''} onChange={(event) => setForm({ ...form, address: event.target.value })} /></label>
                  <label className="full-width">Izoh<textarea value={form.comment ?? ''} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
                </>
              ) : (
                <>
                  <label>To‘liq ism<input value={form.full_name ?? ''} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /><FieldError message={errors.full_name} /></label>
                  <label>JSHR (PINFL)<input value={form.pinfl ?? ''} onChange={(event) => setForm({ ...form, pinfl: event.target.value })} /><FieldError message={errors.pinfl} /></label>
                  <label>Pasport seriya va raqami<input value={form.passport_number ?? ''} onChange={(event) => setForm({ ...form, passport_number: event.target.value })} /><FieldError message={errors.passport_number} /></label>
                  <label>Telefon<input value={form.phone ?? ''} onChange={(event) => setForm({ ...form, phone: event.target.value })} /><FieldError message={errors.phone} /></label>
                  <label>E-mail<input type="email" value={form.email ?? ''} onChange={(event) => setForm({ ...form, email: event.target.value })} /><FieldError message={errors.email} /></label>
                  <label>Manzil<input value={form.address ?? ''} onChange={(event) => setForm({ ...form, address: event.target.value })} /></label>
                  <label className="full-width">Izoh<textarea value={form.comment ?? ''} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
                </>
              )}
            </>
          ) : visibleFields?.map(([key, label, required]) => (
            <label key={key}>{label}
              {key === 'unit' ? (
                <select required value={form.unit || 'piece'} onChange={(event) => setForm({ ...form, unit: event.target.value })}>
                  {productUnits.map(([value, name]) => <option value={value} key={value}>{name}</option>)}
                </select>
              ) : key === 'vat_percent' ? (
                <select value={form.vat_percent || 'none'} onChange={(event) => setForm({ ...form, vat_percent: event.target.value })}>
                  {vatOptions.map(([value, name]) => <option value={value} key={value}>{name}</option>)}
                </select>
              ) : key === 'parent' ? (
                <select value={form.parent ?? ''} onChange={(event) => setForm({ ...form, parent: event.target.value })}>
                  <option value="">Asosiy kategoriya (yuqori daraja)</option>
                  {parentOptions.map((cat) => (
                    <option value={cat.id} key={cat.id}>{`${'— '.repeat(cat.depth)}${cat.name}`}</option>
                  ))}
                </select>
              ) : (
                <input required={required} value={form[key] ?? ''} type={key === 'email' ? 'email' : ['min_quantity', 'quantity', 'purchase_price', 'selling_price', 'delivery_price'].includes(key) ? 'number' : 'text'} step={['purchase_price', 'selling_price', 'delivery_price'].includes(key) ? '0.01' : undefined} min={['min_quantity', 'quantity'].includes(key) ? '0' : undefined} onChange={(event) => setForm({ ...form, [key]: event.target.value })} />
              )}
              <FieldError message={errors[key]} />
            </label>
          ))}
        </div>
        <div className="editor-actions">
          {canDelete && (
            <button type="button" className="danger-button editor-delete" onClick={() => setDeleteConfirm(true)}>
              <Trash size={18} />
              O‘chirish
            </button>
          )}
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}</button>
        </div>
      </form>
      {deleteConfirm && (
        <ConfirmDialog
          title="Yozuvni o‘chirish"
          message={`"${rowTitle(title, item)}" yozuvini o‘chirishni tasdiqlaysizmi? Bu amalni qaytarib bo‘lmaydi.`}
          confirmLabel="Ha, o‘chirish"
          loading={deleting}
          onCancel={() => setDeleteConfirm(false)}
          onConfirm={handleDelete}
        />
      )}
    </div>
  )
}

function SaleEditor({ close, done, notify, item = null, session }) {
  const showPrices = can(session, 'prices_manage')
  const [clients, setClients] = useState([])
  const [products, setProducts] = useState([])
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(() => ({ client: item?.client || '', product: item?.product || '', quantity: item?.quantity || '1', sold_price: item?.sold_price || '', sold_to: item?.sold_to || '', destination: item?.destination || '', sold_date: item?.sold_date || new Date().toISOString().slice(0, 10), comment: item?.comment || '' }))
  const [items, setItems] = useState([{ product: '', quantity: '1', sold_price: '', comment: '' }])
  const [errors, setErrors] = useState({})
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    api.products({ page_size: 500 })
      .then((productData) => setProducts(list(productData)))
      .catch((err) => notify(err.message))
    if (can(session, 'clients_view')) {
      api.clients({ page_size: 500 })
        .then((clientData) => setClients(list(clientData)))
        .catch((err) => notify(err.message))
    }
  }, [notify, session])

  const submit = async (event) => {
    event.preventDefault()
    const nextErrors = {}
    if (item?.id && !form.product) nextErrors.product = 'Mahsulot tanlanishi shart'
    if (!item?.id && !items.some((row) => row.product)) nextErrors.items = 'Kamida bitta mahsulot tanlang'
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors)
      return
    }
    setErrors({})
    setSaving(true)
    try {
      const payload = {
        client: form.client || null,
        product: Number(form.product),
        quantity: Number(form.quantity),
        ...(showPrices ? { sold_price: Number(form.sold_price || 0) } : {}),
        sold_to: form.sold_to || '',
        destination: form.destination || '',
        sold_date: form.sold_date || new Date().toISOString().slice(0, 10),
        comment: form.comment || '',
      }
      if (item?.id) await api.update('/sales/', item.id, payload)
      else if (items.length > 1 || items[0].product) {
        await api.salesBulk({
          client: form.client || null,
          sold_to: form.sold_to || '',
          destination: form.destination || '',
          sold_date: form.sold_date || new Date().toISOString().slice(0, 10),
          items: items.filter((row) => row.product).map((row) => ({
            product: Number(row.product),
            quantity: Number(row.quantity),
            ...(showPrices ? { sold_price: row.sold_price } : {}),
            comment: row.comment || '',
          })),
        })
      } else await api.create('/sales/', payload)
      notify(item?.id ? 'Sotuv yangilandi.' : 'Sotuv saqlandi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await api.remove('/sales/', item.id)
      notify('Sotuv o‘chirildi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setDeleting(false)
      setDeleteConfirm(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head">
          <div><p className="eyebrow">{item?.id ? 'TAHRIRLASH' : 'YANGI SOTUV'}</p><h3>Sotuv ma’lumotlari</h3></div>
          <button type="button" className="icon-button" onClick={close}><X size={20} /></button>
        </div>
        <div className="form-grid">
          <SearchableCombobox
            id="sale-client"
            label="Mijoz"
            value={form.client}
            onChange={(value) => setForm({ ...form, client: value })}
            options={clients}
            onSearch={can(session, 'clients_view') ? searchClients : undefined}
            getLabel={clientOptionLabel}
            getSearchText={clientSearchText}
            placeholder="F.I.Sh, INN/STIR, JSHSHIR, passport, kompaniya, email..."
          />
          {item?.id ? (
            <>
              <label>Mahsulot<select required value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })}><option value="">Mahsulotni tanlang</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number} ({product.unit_display || unitLabel(product.unit)})</option>)}</select><FieldError message={errors.product} /></label>
              <label>Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label>
              {showPrices && <label>Sotuv narxi<input required min="0" step="0.01" type="number" value={form.sold_price} onChange={(event) => setForm({ ...form, sold_price: event.target.value })} /></label>}
            </>
          ) : (
            <div className="full-width line-items">
              <div className="line-head"><b>Mahsulotlar</b></div>
              {items.map((row, index) => (
                <div className="line-item" key={index}>
                  <select required value={row.product} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, product: event.target.value } : itemRow))}><option value="">Mahsulot</option>{products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number} ({product.unit_display || unitLabel(product.unit)})</option>)}</select>
                  <input required min="1" type="number" value={row.quantity} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, quantity: event.target.value } : itemRow))} />
                  {showPrices && <input required min="0" step="0.01" type="number" placeholder="Narx" value={row.sold_price} onChange={(event) => setItems(items.map((itemRow, i) => i === index ? { ...itemRow, sold_price: event.target.value } : itemRow))} />}
                  <button type="button" className="row-action" disabled={items.length === 1} onClick={() => setItems(items.filter((_, i) => i !== index))}>O‘chirish</button>
                </div>
              ))}
              <button type="button" className="secondary-button add-line-button" onClick={() => setItems([...items, { product: '', quantity: '1', sold_price: '', comment: '' }])}><Plus size={16} />Mahsulot qo‘shish</button>
              <FieldError message={errors.items} />
            </div>
          )}
          <label>Sotuvchi/kimga<select value={form.sold_to} onChange={(event) => setForm({ ...form, sold_to: event.target.value })}><option value="">Tanlanmagan</option><option value="Mijoz">Mijoz</option><option value="Operator">Operator</option><option value="Boshqa">Boshqa</option></select></label>
          <label>Manzil<input value={form.destination} onChange={(event) => setForm({ ...form, destination: event.target.value })} /></label>
          <label>Sana<input type="date" value={form.sold_date} onChange={(event) => setForm({ ...form, sold_date: event.target.value })} /></label>
          <label className="full-width">Izoh<textarea value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
        </div>
        <div className="editor-actions">
          {item?.id && (
            <button type="button" className="danger-button editor-delete" onClick={() => setDeleteConfirm(true)}>
              <Trash size={18} />
              O‘chirish
            </button>
          )}
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : item?.id ? 'Yangilash' : 'Saqlash'}</button>
        </div>
      </form>
      {deleteConfirm && (
        <ConfirmDialog
          title="Sotuvni o‘chirish"
          message="Bu sotuvni o‘chirishni tasdiqlaysizmi? Ombor qoldig‘i qayta tiklanadi."
          confirmLabel="Ha, o‘chirish"
          loading={deleting}
          onCancel={() => setDeleteConfirm(false)}
          onConfirm={handleDelete}
        />
      )}
    </div>
  )
}

function ExpenseEditor({ close, done, notify, item = null, session }) {
  const [expenseTypes, setExpenseTypes] = useState([])
  const [subTypes, setSubTypes] = useState([])
  const [saving, setSaving] = useState(false)
  const [file, setFile] = useState(null)
  const [form, setForm] = useState(() => ({ expense_type: item?.expense_type || '', sub_type: item?.sub_type || '', amount: item?.amount || '', currency: item?.currency || 'UZS', date: item?.date || new Date().toISOString().slice(0, 10), comment: item?.comment || '' }))
  const [errors, setErrors] = useState({})
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    api.expenseTypes()
      .then((data) => setExpenseTypes(list(data)))
      .catch((err) => notify(err.message))
  }, [notify])

  useEffect(() => {
    if (!form.expense_type) {
      setSubTypes([])
      return
    }
    api.expenseSubtypes()
      .then((data) => setSubTypes(list(data).filter((item) => String(item.expense_type) === String(form.expense_type))))
      .catch((err) => notify(err.message))
  }, [form.expense_type, notify])

  const submit = async (event) => {
    event.preventDefault()
    const nextErrors = {}
    if (!form.expense_type) nextErrors.expense_type = 'Toifa tanlanishi shart'
    if (!form.amount || Number(form.amount) <= 0) nextErrors.amount = 'Summa kiritilishi shart'
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors)
      return
    }
    setErrors({})
    setSaving(true)
    try {
      const payload = new FormData()
      if (form.expense_type) payload.append('expense_type', form.expense_type)
      if (form.sub_type) payload.append('sub_type', form.sub_type)
      if (form.amount) payload.append('amount', form.amount)
      if (form.currency) payload.append('currency', form.currency)
      if (form.date) payload.append('date', form.date)
      if (form.comment) payload.append('comment', form.comment)
      if (file) payload.append('attachment', file)
      if (item?.id) await api.updateForm('/expenses/expenses/', item.id, payload)
      else await api.createForm('/expenses/expenses/', payload)
      notify(item?.id ? 'Rasxod yangilandi.' : 'Rasxod saqlandi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await api.remove('/expenses/expenses/', item.id)
      notify('Rasxod o‘chirildi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setDeleting(false)
      setDeleteConfirm(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head">
          <div><p className="eyebrow">{item?.id ? 'TAHRIRLASH' : 'YANGI RASXOD'}</p><h3>Rasxod ma’lumotlari</h3></div>
          <button type="button" className="icon-button" onClick={close}><X size={20} /></button>
        </div>
        <div className="form-grid">
          <label>Toifa<select required value={form.expense_type} onChange={(event) => setForm({ ...form, expense_type: event.target.value, sub_type: '' })}><option value="">Tanlang</option>{expenseTypes.map((type) => <option value={type.id} key={type.id}>{type.name}</option>)}</select><FieldError message={errors.expense_type} /></label>
          <label>Turi<select value={form.sub_type} onChange={(event) => setForm({ ...form, sub_type: event.target.value })}><option value="">Tanlanmagan</option>{subTypes.map((type) => <option value={type.id} key={type.id}>{type.name}</option>)}</select></label>
          <label>Summa<input required min="0" step="0.01" type="number" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /><FieldError message={errors.amount} /></label>
          <label>Valyuta<select value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })}><option value="UZS">UZS</option><option value="USD">USD</option></select></label>
          {form.currency === 'USD' && session && (
            <div className="full-width"><FxRatePanel session={session} notify={notify} compact /></div>
          )}
          <label>Sana<input type="date" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
          <label className="full-width file-field">Fayl
            <span className="file-picker">
              <span><FileText size={18} />{file?.name || 'Hujjat yoki rasm fayl tanlang'}</span>
              <b>Tanlash</b>
              <input type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            </span>
          </label>
          <label className="full-width">Izoh<textarea value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} rows="3" /></label>
        </div>
        <div className="editor-actions">
          {item?.id && (
            <button type="button" className="danger-button editor-delete" onClick={() => setDeleteConfirm(true)}>
              <Trash size={18} />
              O‘chirish
            </button>
          )}
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : item?.id ? 'Yangilash' : 'Saqlash'}</button>
        </div>
      </form>
      {deleteConfirm && (
        <ConfirmDialog
          title="Rasxodni o‘chirish"
          message="Bu rasxod yozuvini o‘chirishni tasdiqlaysizmi?"
          confirmLabel="Ha, o‘chirish"
          loading={deleting}
          onCancel={() => setDeleteConfirm(false)}
          onConfirm={handleDelete}
        />
      )}
    </div>
  )
}


const emptyManualImportLine = () => ({
  name: '',
  serial_number: '',
  barcode: '',
  unit: 'piece',
  quantity: '1',
  unit_price: '',
  vat_percent: 'none',
  delivery_amount: 0,
  vat_amount: 0,
  total_amount: 0,
})

function ZakazEditor({ close, done, notify, item = null, session }) {
  const showPrices = can(session, 'prices_manage')
  const isManagement = can(session, 'order_status_manage')
  const canAddProduct = can(session, 'warehouse_create')
  const isBackorder = item?.zakaz_type === 'backorder'
  const isNew = !item?.id
  const productLocked = Boolean(item?.order_contract)
  const [products, setProducts] = useState([])
  const [saving, setSaving] = useState(false)
  const [entryMode, setEntryMode] = useState('select')
  const [showNewProduct, setShowNewProduct] = useState(false)
  const [newProductSaving, setNewProductSaving] = useState(false)
  const [newProduct, setNewProduct] = useState({ name: '', serial_number: '', barcode: '', unit: 'piece', vat_percent: 'none' })
  const [manualLine, setManualLine] = useState(emptyManualImportLine)
  const [form, setForm] = useState(() => ({
    product: item?.product || '',
    quantity: item?.quantity || '1',
    received_qty: item?.received_qty || '0',
    unit_price: item?.unit_price || '',
    currency: item?.currency || 'UZS',
    supplier: item?.supplier || '',
    status: item?.status || 'new',
    payment_status: item?.payment_status || 'unpaid',
    contract_number: item?.contract_number || '',
    contract_date: item?.contract_date || todayValue(),
    faktura: item?.faktura || '',
    expected_date: item?.expected_date || '',
    warehouse_location: item?.warehouse_location || '',
    asos: item?.asos || '',
    comment: item?.comment || '',
  }))

  useEffect(() => {
    api.products().then((data) => setProducts(list(data))).catch((err) => notify(err.message))
  }, [notify])

  const manualTotals = useMemo(() => calcInvoiceLine({
    ...manualLine,
    quantity: manualLine.quantity,
    unit_price: manualLine.unit_price,
    vat_percent: manualLine.vat_percent,
  }, false), [manualLine])

  const updateManualLine = (patch) => {
    setManualLine((current) => {
      const next = { ...current, ...patch }
      return calcInvoiceLine(next, false)
    })
  }

  const createInlineProduct = async () => {
    if (!newProduct.name.trim()) return notify('Mahsulot nomi kiritilishi shart.')
    setNewProductSaving(true)
    try {
      const payload = {
        name: newProduct.name.trim(),
        serial_number: newProduct.serial_number.trim() || undefined,
        barcode: newProduct.barcode.trim() || undefined,
        unit: newProduct.unit,
        vat_percent: newProduct.vat_percent,
      }
      const created = await api.create('/warehouse/products/', payload)
      setProducts((current) => [...current, created])
      setForm((current) => ({ ...current, product: String(created.id) }))
      setShowNewProduct(false)
      setNewProduct({ name: '', serial_number: '', barcode: '', unit: 'piece', vat_percent: 'none' })
      notify('Yangi mahsulot qo‘shildi.', 'success')
    } catch (err) {
      notify(err.message)
    } finally {
      setNewProductSaving(false)
    }
  }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== '' && value !== null))
      if (entryMode === 'manual' && isNew && !isBackorder) {
        if (!manualLine.name.trim()) throw new Error('Tovar nomi kiritilishi shart.')
        payload.new_product = {
          name: manualLine.name.trim(),
          serial_number: manualLine.serial_number.trim(),
          barcode: manualLine.barcode.trim() || null,
          unit: manualLine.unit,
          vat_percent: manualLine.vat_percent || 'none',
        }
        if (showPrices) {
          payload.new_product.purchase_price = manualLine.unit_price || null
          payload.new_product.delivery_price = manualTotals.delivery_amount || null
        }
        payload.quantity = Number(manualLine.quantity || 1)
        if (showPrices) payload.unit_price = Number(manualLine.unit_price || 0)
        delete payload.product
      } else {
        if (payload.product) payload.product = Number(payload.product)
        if (payload.quantity) payload.quantity = Number(payload.quantity)
      }
      if (payload.received_qty) payload.received_qty = Number(payload.received_qty)
      if (!showPrices || isBackorder) {
        delete payload.unit_price
        delete payload.currency
        delete payload.payment_status
        delete payload.new_product
      }
      if (item?.id) await api.update('/orders/zakaz/', item.id, payload)
      else await api.create('/orders/zakaz/', payload)
      notify(item?.id ? 'Import yangilandi.' : 'Import yaratildi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor import-editor" onSubmit={submit}>
        <div className="editor-head"><div><p className="eyebrow">{item?.id ? 'IMPORT TAHRIRI' : 'YANGI IMPORT'}</p><h3>Yetkazuvchidan import</h3></div><button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button></div>
        <div className="form-grid">
          {isNew && !isBackorder && !productLocked && (
            <div className="full-width import-mode-tabs">
              <button type="button" className={entryMode === 'select' ? 'is-active' : ''} onClick={() => setEntryMode('select')}>Ro‘yxatdan tanlash</button>
              <button type="button" className={entryMode === 'manual' ? 'is-active' : ''} onClick={() => setEntryMode('manual')}>Qo‘lda kiritish</button>
            </div>
          )}

          {entryMode === 'manual' && isNew && !isBackorder ? (
            <div className="full-width import-manual-block">
              <div className="import-top-row">
                <label className="field-product">Tovar nomi<input required value={manualLine.name} onChange={(e) => updateManualLine({ name: e.target.value })} /></label>
                <label>Mahsulot raqami<input value={manualLine.serial_number} onChange={(e) => updateManualLine({ serial_number: e.target.value })} placeholder="Avtomatik" /></label>
                <label>Shtrix kod<input value={manualLine.barcode} onChange={(e) => updateManualLine({ barcode: e.target.value })} /></label>
                <label>O‘lchov birligi
                  <select value={manualLine.unit} onChange={(e) => updateManualLine({ unit: e.target.value })}>
                    {productUnits.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                  </select>
                </label>
                <label className="field-qty">Soni<input required min="1" type="number" value={manualLine.quantity} onChange={(e) => updateManualLine({ quantity: e.target.value })} /></label>
                {showPrices && <>
                  <label>Narx<input required min="0" step="0.01" type="number" value={manualLine.unit_price} onChange={(e) => updateManualLine({ unit_price: e.target.value })} /></label>
                  <label>QQS %
                    <select value={manualLine.vat_percent} onChange={(e) => updateManualLine({ vat_percent: e.target.value })}>
                      {vatOptions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                    </select>
                  </label>
                  <label>Yetkazish<input readOnly value={moneyDecimal(manualTotals.delivery_amount)} /></label>
                  <label>QQS miqdori<input readOnly value={moneyDecimal(manualTotals.vat_amount)} /></label>
                  <label>JAMI<input readOnly value={moneyDecimal(manualTotals.total_amount)} /></label>
                </>}
              </div>
              <p className="muted import-manual-note">Mahsulot import bilan birga ombor ro‘yxatiga qo‘shiladi.</p>
            </div>
          ) : (
            <>
              <div className={`import-top-row${isManagement ? ' has-received' : ''}`}>
                <label className="field-product">
                  Mahsulot
                  <div className="import-product-row">
                    <select required disabled={productLocked} value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })}>
                      <option value="">Mahsulotni tanlang</option>
                      {products.map((product) => <option value={product.id} key={product.id}>{product.name} — {product.serial_number} ({product.unit_display || unitLabel(product.unit)})</option>)}
                    </select>
                    {isNew && !productLocked && canAddProduct && (
                      <button type="button" className="secondary-button import-add-product" onClick={() => setShowNewProduct((v) => !v)}>
                        <Plus size={16} />Yangi mahsulot
                      </button>
                    )}
                  </div>
                </label>
                <label className="field-qty">Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} disabled={isBackorder && !isManagement} /></label>
                {isManagement && <label className="field-received">Qabul qilingan<input min="0" type="number" value={form.received_qty} onChange={(event) => setForm({ ...form, received_qty: event.target.value })} /></label>}
              </div>
              {showNewProduct && canAddProduct && (
                <div className="full-width import-new-product">
                  <p className="eyebrow">YANGI MAHSULOT</p>
                  <div className="form-grid">
                    <label>Tovar nomi<input required value={newProduct.name} onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })} /></label>
                    <label>Mahsulot raqami<input value={newProduct.serial_number} onChange={(e) => setNewProduct({ ...newProduct, serial_number: e.target.value })} placeholder="Avtomatik" /></label>
                    <label>Shtrix kod<input value={newProduct.barcode} onChange={(e) => setNewProduct({ ...newProduct, barcode: e.target.value })} /></label>
                    <label>O‘lchov birligi
                      <select value={newProduct.unit} onChange={(e) => setNewProduct({ ...newProduct, unit: e.target.value })}>
                        {productUnits.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                      </select>
                    </label>
                    <label>QQS %
                      <select value={newProduct.vat_percent} onChange={(e) => setNewProduct({ ...newProduct, vat_percent: e.target.value })}>
                        {vatOptions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="import-new-product-actions">
                    <button type="button" className="secondary-button" onClick={() => setShowNewProduct(false)}>Bekor qilish</button>
                    <button type="button" className="primary-button" disabled={newProductSaving} onClick={createInlineProduct}>
                      {newProductSaving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash va tanlash'}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {showPrices && !isBackorder && entryMode !== 'manual' && <>
            <label>Narx<input required={!item?.id && showPrices} min="0" step="0.01" type="number" value={form.unit_price} onChange={(event) => setForm({ ...form, unit_price: event.target.value })} /></label>
            <label>Valyuta<select value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })}><option value="UZS">UZS</option><option value="USD">USD</option></select></label>
            <label>To‘lov statusi<select value={form.payment_status} onChange={(event) => setForm({ ...form, payment_status: event.target.value })}><option value="unpaid">To‘lanmagan</option><option value="partial">Qisman</option><option value="paid">To‘langan</option></select></label>
          </>}
          {entryMode === 'manual' && showPrices && !isBackorder && <>
            <label>Valyuta<select value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })}><option value="UZS">UZS</option><option value="USD">USD</option></select></label>
            <label>To‘lov statusi<select value={form.payment_status} onChange={(event) => setForm({ ...form, payment_status: event.target.value })}><option value="unpaid">To‘lanmagan</option><option value="partial">Qisman</option><option value="paid">To‘langan</option></select></label>
          </>}
          {form.currency === 'USD' && showPrices && !isBackorder && (
            <div className="full-width"><FxRatePanel session={session} notify={notify} compact /></div>
          )}
          {isManagement && <label>Status<select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="new">Yangi</option><option value="confirmed">Tasdiqlandi</option><option value="received">Qabul qilindi</option><option value="cancelled">Bekor qilindi</option></select></label>}
          <label>Yetkazuvchi<input value={form.supplier} onChange={(event) => setForm({ ...form, supplier: event.target.value })} /></label>
          <label>Shartnoma raqami<input value={form.contract_number} onChange={(event) => setForm({ ...form, contract_number: event.target.value.replace(/[^\d/]/g, '') })} placeholder="12/1108" /></label>
          <label>Shartnoma sanasi<input type="date" value={form.contract_date} onChange={(event) => setForm({ ...form, contract_date: event.target.value })} /></label>
          <label>Faktura<input value={form.faktura} onChange={(event) => setForm({ ...form, faktura: event.target.value })} /></label>
          <label>Kutilgan sana<input type="date" value={form.expected_date} onChange={(event) => setForm({ ...form, expected_date: event.target.value })} /></label>
          <label>Ombor joyi<input value={form.warehouse_location} onChange={(event) => setForm({ ...form, warehouse_location: event.target.value })} /></label>
          <label className="full-width">Asos<textarea required={item?.id && form.status !== item.status} rows="3" value={form.asos} onChange={(event) => setForm({ ...form, asos: event.target.value })} /></label>
          <label className="full-width">Izoh<textarea rows="3" value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} /></label>
        </div>
        <div className="editor-actions"><button type="button" className="secondary-button" onClick={close}>Bekor qilish</button><button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}</button></div>
      </form>
    </div>
  )
}

function UserEditor({ close, done, notify, item = null }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(() => ({ username: item?.username || '', password: '', first_name: item?.first_name || '', last_name: item?.last_name || '', role: item?.role || 'OPERATOR', phone: item?.phone || '', telegram_id: item?.telegram_id || '', can_view_clients: Boolean(item?.can_view_clients), is_active: item?.is_active ?? true }))
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = { ...form }
      if (item?.id) {
        delete payload.password
        await api.update('/auth/users/', item.id, payload)
      } else {
        delete payload.is_active
        await api.registerUser(payload)
      }
      notify(item?.id ? 'Foydalanuvchi yangilandi.' : 'Foydalanuvchi yaratildi.', 'success')
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
        <div className="editor-head"><div><p className="eyebrow">{item?.id ? 'USER TAHRIRI' : 'YANGI USER'}</p><h3>Foydalanuvchi ruxsatlari</h3></div><button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button></div>
        <div className="form-grid">
          <label>Username<input required value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /></label>
          {!item?.id && <label>Parol<input required minLength="8" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>}
          <label>Ism<input value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} /></label>
          <label>Familiya<input value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} /></label>
          <label>Rol<select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}><option value="OPERATOR">Operator</option><option value="ACCOUNTANT">Accountant</option><option value="MANAGEMENT">Management</option></select></label>
          <label>Telefon<input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
          <label>Telegram ID<input value={form.telegram_id} onChange={(event) => setForm({ ...form, telegram_id: event.target.value })} /></label>
          <label className="check-field"><input type="checkbox" checked={form.can_view_clients} onChange={(event) => setForm({ ...form, can_view_clients: event.target.checked })} />Mijozlarni ko‘rish</label>
          <label className="check-field"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />Faol</label>
        </div>
        <div className="editor-actions"><button type="button" className="secondary-button" onClick={close}>Bekor qilish</button><button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}</button></div>
      </form>
    </div>
  )
}

function StockInEditor({ item, close, done, notify }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ quantity: '', warehouse_location: '', asos: '', contract_number: '', faktura: '' })
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = { ...form, quantity: Number(form.quantity) }
      Object.keys(payload).forEach((key) => { if (payload[key] === '') delete payload[key] })
      await api.addStock(item.id, payload)
      notify('Kirim muvaffaqiyatli rasmiylashtirildi.', 'success')
      done()
    } catch (err) { notify(err.message) } finally { setSaving(false) }
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor" onSubmit={submit}>
        <div className="editor-head"><div><p className="eyebrow">OMBOR KIRIMI</p><h3>{item.name}</h3></div><button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button></div>
        <div className="form-grid">
          <label>Miqdor<input required min="1" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label>
          <label>Ombordagi joy<input value={form.warehouse_location} onChange={(event) => setForm({ ...form, warehouse_location: event.target.value })} placeholder="Asosiy ombor" /></label>
          <label>Shartnoma raqami<input value={form.contract_number} onChange={(event) => setForm({ ...form, contract_number: event.target.value })} /></label>
          <label>Faktura<input value={form.faktura} onChange={(event) => setForm({ ...form, faktura: event.target.value })} /></label>
          <label className="full-width">Asos<input required value={form.asos} onChange={(event) => setForm({ ...form, asos: event.target.value })} placeholder="Masalan, kirim orderi №77" /></label>
        </div>
        <div className="editor-actions"><button type="button" className="secondary-button" onClick={close}>Bekor qilish</button><button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Kirim qilish'}</button></div>
      </form>
    </div>
  )
}

function PaymentEditor({ item, close, done, notify }) {
  const [amount, setAmount] = useState(item.remaining || '')
  const [comment, setComment] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await api.pay(item.id, { amount, comment })
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
          <div><p className="eyebrow">TO‘LOV QABUL QILISH</p><h3>{item.client_name || 'Hisob'} uchun to‘lov</h3></div>
          <button type="button" className="icon-button" onClick={close}><X size={20} /></button>
        </div>
        <p className="muted">Qolgan summa: <b>{money(item.remaining)} {item.currency}</b></p>
        <div className="form-grid">
          <label>Qabul qilinadigan summa<input required min="0.01" max={item.remaining} type="number" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
          <label>Izoh<input value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Masalan, ikkinchi to‘lov" /></label>
        </div>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'To‘lovni qabul qilish'}</button>
        </div>
      </form>
    </div>
  )
}

function calcInvoiceLine(line, reverse, editedField = null) {
  const qty = Number(line.quantity || 0)
  const price = Number(line.unit_price || 0)
  const vatRate = line.vat_percent === 'none' || !line.vat_percent ? 0 : Number(line.vat_percent)

  if (reverse) {
    let delivery = Number(line.delivery_amount || 0)
    const totalInput = Number(line.total_amount || 0)

    if (editedField === 'vat_amount') {
      const vat = Number(line.vat_amount || 0)
      const total = delivery > 0
        ? Math.round((delivery + vat) * 100) / 100
        : (totalInput || Math.round((delivery + vat) * 100) / 100)
      return { ...line, delivery_amount: delivery, vat_amount: vat, total_amount: total }
    }

    if (editedField === 'total_amount' && totalInput > 0 && vatRate > 0) {
      const netDelivery = Math.round((totalInput / (1 + vatRate / 100)) * 100) / 100
      const vat = Math.round((totalInput - netDelivery) * 100) / 100
      return { ...line, delivery_amount: netDelivery, vat_amount: vat, total_amount: totalInput }
    }

    if (!delivery && qty > 0 && price > 0) {
      delivery = Math.round(qty * price * 100) / 100
    }

    if (delivery > 0 && vatRate > 0) {
      const vat = Math.round(delivery * vatRate) / 100
      const total = Math.round((delivery + vat) * 100) / 100
      return { ...line, delivery_amount: delivery, vat_amount: vat, total_amount: total }
    }

    const vat = Number(line.vat_amount || 0)
    const total = totalInput || (delivery ? Math.round((delivery + vat) * 100) / 100 : 0)
    return { ...line, delivery_amount: delivery, vat_amount: vat, total_amount: total }
  }

  const delivery = Math.round(qty * price * 100) / 100
  const vat = Math.round(delivery * vatRate) / 100
  const total = Math.round((delivery + vat) * 100) / 100
  return { ...line, delivery_amount: delivery, vat_amount: vat, total_amount: total }
}

function emptyInvoiceLine(num = 1) {
  return { line_number: num, product: '', product_name: '', identification_code: '', barcode: '', unit: 'piece', quantity: '1', unit_price: '', delivery_amount: 0, vat_percent: 'none', vat_amount: 0, total_amount: 0 }
}

function validateEInvoice(editing, { showPrices, company } = {}) {
  const errors = {}
  const trim = (value) => (value ?? '').toString().trim()

  if (!trim(editing.contract_number)) {
    errors.contract_number = 'Shartnoma raqamini kiriting'
  } else if (!/^\d+\/\d{4}$/.test(trim(editing.contract_number))) {
    errors.contract_number = 'Format: raqam/DDMM (masalan 12/1108)'
  }

  if (!trim(editing.place_signed)) {
    errors.place_signed = 'Tuzilgan joyini kiriting'
  }

  if (!editing.contract_date) {
    errors.contract_date = 'Tuzilgan sanani tanlang'
  }

  if (!editing.valid_until) {
    errors.valid_until = 'Amal qilish muddatini tanlang'
  } else if (editing.contract_date && editing.valid_until < editing.contract_date) {
    errors.valid_until = 'Muddat tuzilgan sanadan oldin bo‘lmasin'
  }

  if (!editing.client) {
    errors.client = 'Mijozni tanlang'
  }

  const executorType = editing.executor_type || 'company_profile'
  if (executorType === 'company_profile') {
    if (!company?.name?.trim() || !company?.stir?.trim()) {
      errors.company = 'Korxona profilida nom va STIR to‘ldirilgan bo‘lishi kerak'
    }
  } else if (!editing.executor_client) {
    errors.executor_client = 'Bajaruvchi korxonani tanlang'
  }

  if (!trim(editing.content_title)) {
    errors.content_title = 'Sarlavhani yozing'
  }

  if (!trim(editing.content_body)) {
    errors.content_body = 'Mazmun matnini yozing'
  }

  const lines = editing.lines || []
  let hasValidLine = false
  lines.forEach((line, index) => {
    const prefix = `lines.${index}`
    const name = trim(line.product_name)
    const qty = Number(line.quantity)
    const idCode = trim(line.identification_code)

    if (!name) errors[`${prefix}.product_name`] = 'Tovar nomini kiriting'
    if (!qty || qty < 1 || !Number.isFinite(qty)) {
      errors[`${prefix}.quantity`] = 'Soni kamida 1 bo‘lishi kerak'
    }
    if (!idCode) errors[`${prefix}.identification_code`] = 'Identifikatsiya kodini kiriting'

    if (showPrices && !editing.reverse_calculation) {
      const price = Number(line.unit_price)
      if (line.unit_price === '' || line.unit_price == null || !Number.isFinite(price) || price < 0) {
        errors[`${prefix}.unit_price`] = 'Narxni kiriting'
      }
    }

    if (name && qty >= 1 && idCode) hasValidLine = true
  })

  if (!hasValidLine) {
    errors.lines = 'Kamida bitta to‘liq mahsulot qatori kerak'
  }

  return errors
}

function EInvoiceFieldError({ message }) {
  if (!message) return null
  return <span className="field-error" role="alert">{message}</span>
}

function invoiceProductsLabel(row) {
  const lines = row.lines || []
  if (!lines.length) return '—'
  const names = lines.map((line) => line.product_name).filter(Boolean)
  if (!names.length) return '—'
  if (names.length === 1) return names[0]
  return `${names[0]} (+${names.length - 1})`
}

function invoiceTotalQuantity(row) {
  return (row.lines || []).reduce((sum, line) => sum + Number(line.quantity || 0), 0)
}

function buildInvoiceTotals(invoice) {
  const lines = (invoice?.lines || []).map((line) => calcInvoiceLine(line, invoice?.reverse_calculation))
  return lines.reduce((acc, line) => ({
    delivery: acc.delivery + Number(line.delivery_amount || 0),
    vat: acc.vat + Number(line.vat_amount || 0),
    grand: acc.grand + Number(line.total_amount || 0),
  }), { delivery: 0, vat: 0, grand: 0 })
}

function companyPartyData(company) {
  return {
    name: company?.name,
    address: company?.address,
    phone: company?.phone,
    fax: company?.fax,
    stir: company?.stir,
    oked: company?.oked,
    bank_account: company?.bank_account,
    bank_name: company?.bank_name,
    mfo: company?.mfo,
    director_jshshr: company?.director_jshshr,
    director_fish: company?.director_fish,
  }
}

function clientPartyData(client) {
  return {
    name: client?.company_name || client?.full_name,
    address: client?.address,
    phone: client?.phone,
    fax: client?.fax,
    stir: client?.inn,
    oked: client?.oked,
    bank_account: client?.bank_account,
    bank_name: client?.bank_name,
    mfo: client?.mfo,
    director_jshshr: client?.director_jshshr || client?.pinfl,
    director_fish: client?.director_fish || client?.full_name,
  }
}

function executorPartyData(invoice, company, executorClient) {
  const type = invoice?.executor_type || 'company_profile'
  if (type === 'client') {
    if (executorClient) return clientPartyData(executorClient)
    if (invoice?.executor_name) return { name: invoice.executor_name }
    return {}
  }
  return companyPartyData(company)
}

function PartyInfoGrid({ data }) {
  return (
    <dl className="party-info-grid">
      <div><dt>STIR</dt><dd>{data.stir || '—'}</dd></div>
      <div><dt>Nomi</dt><dd>{data.name || '—'}</dd></div>
      <div><dt>JSHSHIR</dt><dd>{data.director_jshshr || '—'}</dd></div>
      <div><dt>F.I.Sh.</dt><dd>{data.director_fish || '—'}</dd></div>
      <div><dt>MFO</dt><dd>{data.mfo || '—'}</dd></div>
      <div><dt>Bank</dt><dd>{data.bank_name || '—'}</dd></div>
      <div><dt>OKED</dt><dd>{data.oked || '—'}</dd></div>
      <div><dt>Hisob raqami</dt><dd>{data.bank_account || '—'}</dd></div>
      <div className="party-info-wide"><dt>Manzil</dt><dd>{data.address || '—'}</dd></div>
      <div><dt>Telefon</dt><dd>{data.phone || '—'}</dd></div>
      <div><dt>Faks</dt><dd>{data.fax || '—'}</dd></div>
    </dl>
  )
}

function ContractPartyRequisites({ title, data }) {
  return (
    <div className="contract-party-requisites">
      <h4>{title}</h4>
      <dl className="contract-party-requisites-list">
        <div><dt>Nomi</dt><dd>{data.name || '—'}</dd></div>
        <div><dt>Manzil</dt><dd>{data.address || '—'}</dd></div>
        <div><dt>Telefon</dt><dd>{data.phone || '—'}</dd></div>
        <div><dt>Faks</dt><dd>{data.fax || '—'}</dd></div>
        <div><dt>STIR</dt><dd>{data.stir || '—'}</dd></div>
        <div><dt>IFUT/OKED</dt><dd>{data.oked || '—'}</dd></div>
        <div><dt>X/R</dt><dd>{data.bank_account || '—'}</dd></div>
        <div><dt>Bank</dt><dd>{data.bank_name || '—'}</dd></div>
        <div><dt>MFO</dt><dd>{data.mfo || '—'}</dd></div>
      </dl>
    </div>
  )
}

function InvoiceContractModal({ invoice, company, client, executorClient, showPrices, onClose, onEdit, canEdit }) {
  const lines = (invoice.lines || []).map((line) => calcInvoiceLine(line, invoice.reverse_calculation))
  const totals = buildInvoiceTotals(invoice)
  const executorData = executorPartyData(invoice, company, executorClient)
  const customerName = client?.company_name || client?.full_name || invoice.client_name || '—'
  const validRange = invoice.valid_until
    ? `${formatDateUz(invoice.contract_date)} — ${formatDateUz(invoice.valid_until)} gacha`
    : formatDateUz(invoice.contract_date)

  return (
    <div className="modal-backdrop invoice-contract-backdrop" role="presentation" onClick={onClose}>
      <div className="invoice-contract-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <header className="invoice-contract-head">
          <div>
            <h2>Shartnoma № {invoice.contract_number || '—'}</h2>
            <p className="invoice-contract-subtitle">{documentTypeLabel(invoice.document_type)}</p>
            <p className="invoice-contract-meta">
              {[invoice.place_signed, validRange].filter(Boolean).join(' · ') || '—'}
            </p>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Yopish"><X size={20} /></button>
        </header>

        <div className="invoice-contract-parties">
          <div className="invoice-contract-party">
            <span className="invoice-contract-party-label">Bajaruvchi</span>
            <strong>{executorData.name || '—'}</strong>
          </div>
          <div className="invoice-contract-party">
            <span className="invoice-contract-party-label">Buyurtmachi</span>
            <strong>{customerName}</strong>
          </div>
        </div>

        <div className="invoice-contract-table-wrap">
          <table className="invoice-contract-table">
            <thead>
              <tr>
                <th>№</th>
                <th>Mahsulot</th>
                <th>Shtrix</th>
                <th>Birlik</th>
                <th>Soni</th>
                {showPrices && (
                  <>
                    <th>Narx</th>
                    <th>QQS%</th>
                    <th>QQS</th>
                    <th>Jami</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={index}>
                  <td>{index + 1}</td>
                  <td>{line.product_name || '—'}</td>
                  <td>{line.barcode || '—'}</td>
                  <td>{unitLabel(line.unit)}</td>
                  <td>{money(line.quantity)}</td>
                  {showPrices && (
                    <>
                      <td>{moneyDecimal(line.unit_price)}</td>
                      <td>{vatLabel(line.vat_percent)}</td>
                      <td>{moneyDecimal(line.vat_amount)}</td>
                      <td><strong>{moneyDecimal(line.total_amount)}</strong></td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {showPrices && (
          <p className="invoice-contract-summary">
            Yetkazish: <strong>{moneyDecimal(totals.delivery)}</strong>
            {' · '}
            QQS: <strong>{moneyDecimal(totals.vat)}</strong>
            {' · '}
            Jami: <strong>{moneyDecimal(totals.grand)}</strong>
          </p>
        )}

        {(invoice.content_title || invoice.content_body) && (
          <div className="invoice-contract-mazmun">
            {invoice.content_title ? <strong>{invoice.content_title}</strong> : null}
            {invoice.content_body ? <div className="invoice-contract-mazmun-body">{invoice.content_body}</div> : null}
          </div>
        )}

        <section className="invoice-contract-requisites-section">
          <h3>2. Tomonlarni yuridik manzillari va rekvizitlari</h3>
          <div className="invoice-contract-requisites-grid">
            <ContractPartyRequisites title="Bajaruvchi" data={executorData} />
            <ContractPartyRequisites title="Buyurtmachi" data={clientPartyData(client) || { name: invoice.client_name }} />
          </div>
        </section>

        <div className="invoice-contract-actions">
          {canEdit && onEdit && (
            <button type="button" className="secondary-button" onClick={onEdit}>Tahrirlash</button>
          )}
          <button type="button" className="primary-button" onClick={onClose}>Yopish</button>
        </div>
      </div>
    </div>
  )
}

function DocumentPreviewModal({ invoice, company, client, executorClient, totals, showPrices, onClose }) {
  const lines = (invoice.lines || []).map((line) => calcInvoiceLine(line, invoice.reverse_calculation))
  const amountWords = numberToWordsUzbek(totals.grand)
  const docTitle = invoice.name || documentTypeLabel(invoice.document_type)
  const executorData = executorPartyData(invoice, company, executorClient)
  const executorName = executorData.name || 'Bajaruvchi'
  const executorDirector = executorData.director_fish || executorName
  const customerName = client?.company_name || client?.full_name || 'Buyurtmachi'
  const customerDirector = client?.director_fish || client?.full_name || customerName

  const partyBlock = (title, data) => (
    <div className="preview-party">
      <h4>{title}</h4>
      <dl>
        <div><dt>Nomi</dt><dd>{data.name || '—'}</dd></div>
        <div><dt>Manzil</dt><dd>{data.address || '—'}</dd></div>
        <div><dt>Telefon</dt><dd>{data.phone || '—'}</dd></div>
        <div><dt>Faks</dt><dd>{data.fax || '—'}</dd></div>
        <div><dt>STIR</dt><dd>{data.stir || '—'}</dd></div>
        <div><dt>IFUT/OKED</dt><dd>{data.oked || '—'}</dd></div>
        <div><dt>X/R</dt><dd>{data.bank_account || '—'}</dd></div>
        <div><dt>Bank</dt><dd>{data.bank_name || '—'}</dd></div>
        <div><dt>MFO</dt><dd>{data.mfo || '—'}</dd></div>
      </dl>
    </div>
  )

  return (
    <div className="modal-backdrop document-preview-backdrop" role="presentation" onClick={onClose}>
      <div className="document-preview-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <div className="document-preview-toolbar">
          <button type="button" className="icon-button" onClick={onClose} aria-label="Yopish"><X size={20} /></button>
        </div>

        <article className="document-preview-paper">
          <header className="document-preview-header">
            <p className="document-preview-doc-title">{docTitle}</p>
            <h2 className="document-preview-contract-no">Shartnoma №{invoice.contract_number || '—'}</h2>
            <div className="document-preview-meta">
              <span>{invoice.place_signed || '—'}</span>
              <span>
                {formatDateUz(invoice.contract_date)}
                {invoice.valid_until ? ` — ${formatDateUz(invoice.valid_until)} gacha` : ''}
              </span>
            </div>
          </header>

          <p className="document-preview-intro">
            <b>Bajaruvchi</b> {executorDirector} ({executorName}) va <b>Buyurtmachi</b> {customerDirector} ({customerName}) o‘rtasida tuzilgan shartnoma.
          </p>

          <section className="document-preview-section">
            <h3>{invoice.content_title || '1.'}</h3>
            <div className="document-preview-table-wrap">
              <table className="document-preview-table">
                <thead>
                  <tr>
                    <th>№</th>
                    <th>Mahsulot nomi</th>
                    <th>National Catalog Code</th>
                    <th>Barcode</th>
                    <th>O‘lchov birligi</th>
                    <th>Miqdori</th>
                    {showPrices && (
                      <>
                        <th>Narx</th>
                        <th>Etkazib berish qiymati</th>
                        <th>QQS (Stavka/Summa)</th>
                        <th>Etkazib berish narxi QQS bilan</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line, index) => (
                    <tr key={index}>
                      <td>{index + 1}</td>
                      <td>{line.product_name || '—'}</td>
                      <td>{line.identification_code || '—'}</td>
                      <td>{line.barcode || '—'}</td>
                      <td>{unitLabel(line.unit)}</td>
                      <td>{money(line.quantity)}</td>
                      {showPrices && (
                        <>
                          <td>{moneyDecimal(line.unit_price)}</td>
                          <td>{moneyDecimal(line.delivery_amount)}</td>
                          <td>{vatLabel(line.vat_percent)} / {moneyDecimal(line.vat_amount)}</td>
                          <td>{moneyDecimal(line.total_amount)}</td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
                {showPrices && (
                  <tfoot>
                    <tr>
                      <td colSpan={7}><b>Jami</b></td>
                      <td><b>{moneyDecimal(totals.delivery)}</b></td>
                      <td><b>{moneyDecimal(totals.vat)}</b></td>
                      <td><b>{moneyDecimal(totals.grand)}</b></td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
            {showPrices && (
              <p className="document-preview-total-words">
                Shartnomaning umumiy miqdori {amountWords.sumWords} sum {amountWords.tiyinWords} tiyin ({moneyDecimal(totals.grand)} so‘m).
              </p>
            )}
            {invoice.content_body ? (
              <div className="document-preview-clauses">{invoice.content_body}</div>
            ) : null}
          </section>

          <section className="document-preview-section">
            <h3>2. Tomonlarni yuridik manzillari va rekvizitlari</h3>
            <div className="document-preview-parties">
              {partyBlock('Bajaruvchi', executorData)}
              {partyBlock('Buyurtmachi', {
                name: client?.company_name || client?.full_name,
                address: client?.address,
                phone: client?.phone,
                fax: client?.fax,
                stir: client?.inn,
                oked: client?.oked,
                bank_account: client?.bank_account,
                bank_name: client?.bank_name,
                mfo: client?.mfo,
              })}
            </div>
          </section>
        </article>
      </div>
    </div>
  )
}

function ClientPickerField({
  id,
  label,
  value,
  selectedOption,
  onOpen,
  onClear,
  error,
  required = false,
  placeholder = 'Korxonani tanlang...',
}) {
  const display = selectedOption ? clientOptionLabel(selectedOption) : ''
  return (
    <div className={`client-picker-field${error ? ' has-error' : ''}`}>
      {label && (
        <label className="client-picker-label" htmlFor={id}>
          {label}
          {required && <span className="required-mark" aria-hidden="true"> *</span>}
        </label>
      )}
      <div className="client-picker-trigger-wrap">
        <button
          type="button"
          id={id}
          className={`client-picker-trigger${!value ? ' is-empty' : ''}${error ? ' input-invalid' : ''}`}
          onClick={onOpen}
        >
          <span className="client-picker-trigger-text">{display || placeholder}</span>
          <MagnifyingGlass size={16} aria-hidden="true" />
        </button>
        {value && onClear && (
          <button
            type="button"
            className="client-picker-clear"
            onClick={(event) => {
              event.stopPropagation()
              onClear()
            }}
            aria-label="Tozalash"
          >
            <X size={14} />
          </button>
        )}
      </div>
      <FieldError message={error} />
    </div>
  )
}

function ClientPickerModal({
  title = 'Korxonani tanlash',
  eyebrow = 'MIJOZLAR REESTRI',
  selectedId,
  onSelect,
  onClose,
  onAddNew,
  canSearch = true,
  canAdd = false,
}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const debounceRef = useRef(null)

  useEffect(() => {
    if (!canSearch) return undefined
    const q = query.trim()
    if (q.length < 2) {
      setResults([])
      setSearching(false)
      return undefined
    }
    setSearching(true)
    window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(async () => {
      try {
        const data = await searchClients(q)
        setResults(data)
      } catch {
        setResults([])
      } finally {
        setSearching(false)
      }
    }, 400)
    return () => window.clearTimeout(debounceRef.current)
  }, [query, canSearch])

  const showMinLengthHint = canSearch && query.trim().length > 0 && query.trim().length < 2
  const showEmpty = !searching && !showMinLengthHint && query.trim().length >= 2 && results.length === 0
  const showPrompt = !query.trim() && !searching

  return (
    <div className="modal-backdrop product-picker-backdrop" role="presentation" onClick={onClose}>
      <div
        className="product-picker-modal client-picker-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="client-picker-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="product-picker-head">
          <div>
            <p className="eyebrow">{eyebrow}</p>
            <h3 id="client-picker-title">{title}</h3>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Yopish"><X size={20} /></button>
        </div>
        {canSearch && (
          <label className="product-picker-search">
            <MagnifyingGlass size={18} />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="F.I.Sh, INN/STIR, JSHSHIR, passport, kompaniya, email..."
            />
            {searching && <SpinnerGap size={16} className="spin" aria-hidden="true" />}
          </label>
        )}
        <div className="product-picker-list">
          {showPrompt && (
            <p className="muted product-picker-empty">Qidirish uchun kamida 2 ta belgi kiriting.</p>
          )}
          {showMinLengthHint && (
            <p className="muted product-picker-empty">Kamida 2 ta belgi kiriting.</p>
          )}
          {showEmpty && (
            <p className="muted product-picker-empty">Natija topilmadi.</p>
          )}
          {results.map((client) => (
            <button
              type="button"
              key={client.id}
              className={`product-picker-item client-picker-item${String(client.id) === String(selectedId) ? ' is-selected' : ''}`}
              onClick={() => onSelect(client)}
            >
              <span className="product-picker-item-name">{clientOptionLabel(client)}</span>
              {client.phone ? <span className="product-picker-item-code">{client.phone}</span> : null}
            </button>
          ))}
        </div>
        {canAdd && onAddNew && (
          <div className="client-picker-footer">
            <button type="button" className="secondary-button" onClick={onAddNew}>
              <Plus size={16} />
              Yangi korxona qo‘shish
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function scrollToFirstEInvoiceError() {
  document.querySelector('.e-invoice-form .field-error, .e-invoice-form .input-invalid, .e-invoice-form .field-invalid')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function ProductPickerModal({ products, onSelect, onClose }) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return products
    return products.filter((p) => {
      const name = (p.name || '').toLowerCase()
      const code = (p.serial_number || '').toLowerCase()
      const barcode = (p.barcode || '').toLowerCase()
      return name.includes(q) || code.includes(q) || barcode.includes(q)
    })
  }, [products, query])

  return (
    <div className="modal-backdrop product-picker-backdrop" role="presentation" onClick={onClose}>
      <div className="product-picker-modal" role="dialog" aria-modal="true" aria-labelledby="product-picker-title" onClick={(event) => event.stopPropagation()}>
        <div className="product-picker-head">
          <div>
            <p className="eyebrow">OMBOR</p>
            <h3 id="product-picker-title">Tovarni tanlash</h3>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Yopish"><X size={20} /></button>
        </div>
        <label className="product-picker-search">
          <MagnifyingGlass size={18} />
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Nom, identifikatsiya kodi, shtrix kod..."
          />
        </label>
        <div className="product-picker-list">
          {filtered.length === 0 ? (
            <p className="muted product-picker-empty">Tovar topilmadi.</p>
          ) : (
            filtered.map((product) => (
              <button
                type="button"
                key={product.id}
                className="product-picker-item"
                onClick={() => onSelect(product)}
              >
                <span className="product-picker-item-name">{product.name}</span>
                {product.serial_number ? <span className="product-picker-item-code">{product.serial_number}</span> : null}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function BuyurtmalarPage({ notify, session, routeMode = 'list', invoiceId = null, prefillClientId = null }) {
  const navigate = useNavigate()
  const showPrices = can(session, 'prices_view')
  const canManage = can(session, 'einvoice_manage')
  const isListPage = routeMode === 'list' || routeMode === 'view'
  const isEditorPage = routeMode === 'new' || routeMode === 'edit'
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)
  const [selectedClientDetail, setSelectedClientDetail] = useState(null)
  const [selectedExecutorClientDetail, setSelectedExecutorClientDetail] = useState(null)
  const [products, setProducts] = useState([])
  const [company, setCompany] = useState(null)
  const [saving, setSaving] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [viewInvoice, setViewInvoice] = useState(null)
  const [viewClient, setViewClient] = useState(null)
  const [viewExecutorClient, setViewExecutorClient] = useState(null)
  const [viewLoading, setViewLoading] = useState(false)
  const [contractNumberEdited, setContractNumberEdited] = useState(false)
  const [errors, setErrors] = useState({})
  const [validatedOnce, setValidatedOnce] = useState(false)
  const [clientQuickAddOpen, setClientQuickAddOpen] = useState(false)
  const [clientQuickAddTarget, setClientQuickAddTarget] = useState('client')
  const [clientPickerTarget, setClientPickerTarget] = useState(null)
  const [productPickerLineIndex, setProductPickerLineIndex] = useState(null)
  const routeBootstrapped = useRef('')
  const notifyRef = useRef(notify)
  const sessionRef = useRef(session)
  const viewFetchKeyRef = useRef(null)

  notifyRef.current = notify
  sessionRef.current = session

  const loadInvoiceForView = async (id) => {
    const fetchKey = String(id)
    if (!fetchKey || viewFetchKeyRef.current === fetchKey) return
    viewFetchKeyRef.current = fetchKey
    setViewLoading(true)

    try {
      const detail = await api.invoice(id)
      if (viewFetchKeyRef.current !== fetchKey) return

      let clientDetail = null
      let executorClientDetail = null
      if (detail.client && can(sessionRef.current, 'clients_view')) {
        clientDetail = await fetchClient(detail.client).catch(() => null)
      }
      if (
        detail.executor_type === 'client'
        && detail.executor_client
        && can(sessionRef.current, 'clients_view')
      ) {
        executorClientDetail = await fetchClient(detail.executor_client).catch(() => null)
      }
      if (viewFetchKeyRef.current !== fetchKey) return

      setViewInvoice(detail)
      setViewClient(clientDetail)
      setViewExecutorClient(executorClientDetail)
    } catch (err) {
      if (viewFetchKeyRef.current === fetchKey) {
        viewFetchKeyRef.current = null
        notifyRef.current(err.message)
      }
    } finally {
      if (viewFetchKeyRef.current === fetchKey) {
        setViewLoading(false)
      }
    }
  }

  const clearFieldError = (key) => {
    setErrors((current) => {
      if (!current[key]) return current
      const next = { ...current }
      delete next[key]
      if (key.startsWith('lines.')) delete next.lines
      return next
    })
  }

  const clearLineErrors = () => {
    setErrors((current) => {
      const next = { ...current }
      Object.keys(next).forEach((key) => {
        if (key === 'lines' || key.startsWith('lines.')) delete next[key]
      })
      return next
    })
  }

  const runValidation = () => {
    const nextErrors = validateEInvoice(editing, { showPrices, company })
    setErrors(nextErrors)
    setValidatedOnce(true)
    return nextErrors
  }
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [invoiceData, productData, profile] = await Promise.all([
        api.invoices(),
        api.products({ page_size: 200 }),
        api.companyProfile(),
      ])
      setRows(list(invoiceData))
      setProducts(list(productData))
      setCompany(profile)
    } catch (err) {
      notifyRef.current(err.message)
    } finally {
      setLoading(false)
    }
  }, [session?.id])

  const refreshCompanyProfile = useCallback(async () => {
    try {
      const profile = await api.companyProfile()
      setCompany(profile)
      return profile
    } catch (err) {
      notifyRef.current(err.message)
      return null
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const handler = () => { refreshCompanyProfile() }
    window.addEventListener('company-profile-updated', handler)
    return () => window.removeEventListener('company-profile-updated', handler)
  }, [refreshCompanyProfile])

  useEffect(() => {
    if (!editing?.client || !can(sessionRef.current, 'clients_view')) {
      setSelectedClientDetail(null)
      return undefined
    }
    let cancelled = false
    fetchClient(editing.client)
      .then((detail) => { if (!cancelled) setSelectedClientDetail(detail) })
      .catch((err) => { if (!cancelled) { setSelectedClientDetail(null); notifyRef.current(err.message) } })
    return () => { cancelled = true }
  }, [editing?.client])

  useEffect(() => {
    const executorType = editing?.executor_type || 'company_profile'
    if (executorType !== 'client' || !editing?.executor_client || !can(sessionRef.current, 'clients_view')) {
      setSelectedExecutorClientDetail(null)
      return undefined
    }
    let cancelled = false
    fetchClient(editing.executor_client)
      .then((detail) => { if (!cancelled) setSelectedExecutorClientDetail(detail) })
      .catch((err) => {
        if (!cancelled) {
          setSelectedExecutorClientDetail(null)
          notifyRef.current(err.message)
        }
      })
    return () => { cancelled = true }
  }, [editing?.executor_type, editing?.executor_client])

  const closeView = () => {
    setViewInvoice(null)
    setViewClient(null)
    setViewExecutorClient(null)
    viewFetchKeyRef.current = null
    setViewLoading(false)
    if (routeMode === 'view') {
      navigate(pathForPage('Buyurtmalar'))
    }
  }

  const openView = (row) => {
    void loadInvoiceForView(row.id)
  }

  useEffect(() => {
    if (routeMode !== 'view' || !invoiceId) return undefined
    void loadInvoiceForView(invoiceId)
    return undefined
  }, [routeMode, invoiceId])

  const openEditFromView = () => {
    if (!viewInvoice?.id) return
    const id = viewInvoice.id
    setViewInvoice(null)
    setViewClient(null)
    setViewExecutorClient(null)
    navigate(invoiceEditPath(id))
  }

  const buyurtmaColumns = useMemo(() => {
    const cols = [
      { key: 'idx', label: '№', render: (row) => rows.findIndex((item) => item.id === row.id) + 1 },
      { key: 'client', label: 'Mijoz', render: (row) => row.client_name || '—' },
      { key: 'contract', label: 'Shartnoma', render: (row) => row.contract_number || '—' },
      { key: 'product', label: 'Mahsulot', render: (row) => invoiceProductsLabel(row) },
      { key: 'qty', label: 'Soni', render: (row) => money(invoiceTotalQuantity(row)) },
    ]
    if (showPrices) {
      cols.push({
        key: 'total',
        label: 'Jami summa',
        render: (row) => (row.grand_total != null ? `${moneyDecimal(row.grand_total)} so'm` : '—'),
      })
    }
    cols.push({
      key: 'date',
      label: 'Muddat',
      render: (row) => formatDateUz(row.contract_date) || '—',
    })
    cols.push({
      key: 'type',
      label: 'Turi',
      render: (row) => row.document_type_display || documentTypeLabel(row.document_type),
    })
    return cols
  }, [showPrices, rows])

  const openClientQuickAdd = (target) => {
    setClientQuickAddTarget(target)
    setClientPickerTarget(null)
    setClientQuickAddOpen(true)
  }

  const handleClientPickerSelect = (target, client) => {
    if (target === 'executor') {
      clearFieldError('executor_client')
      setEditing((current) => (current ? { ...current, executor_client: client.id } : current))
      setSelectedExecutorClientDetail(client)
    } else {
      clearFieldError('client')
      setEditing((current) => (current ? { ...current, client: client.id } : current))
      setSelectedClientDetail(client)
    }
    setClientPickerTarget(null)
  }

  const closeEditor = () => {
    setContractNumberEdited(false)
    setErrors({})
    setValidatedOnce(false)
    setPreviewOpen(false)
    setEditing(null)
    navigate(pathForPage('Buyurtmalar'))
  }

  const initNewEditor = (clientId = '') => {
    setContractNumberEdited(false)
    setErrors({})
    setValidatedOnce(false)
    setPreviewOpen(false)
    setEditing({
      document_type: 'contract_sk',
      name: '',
      contract_number: '',
      place_signed: '',
      contract_date: todayValue(),
      valid_until: currentYearEndValue(),
      client: clientId ? String(clientId) : '',
      executor_type: 'company_profile',
      executor_client: '',
      reverse_calculation: false,
      comment: '',
      content_title: '1.',
      content_body: '',
      lines: [emptyInvoiceLine()],
    })
  }

  const loadEditor = async (id) => {
    try {
      const [detail, profile] = await Promise.all([
        api.invoice(id),
        api.companyProfile(),
      ])
      setCompany(profile)
      setContractNumberEdited(true)
      setErrors({})
      setValidatedOnce(false)
      setPreviewOpen(false)
      setEditing({
        ...detail,
        client: detail.client || '',
        executor_type: detail.executor_type || 'company_profile',
        executor_client: detail.executor_client || '',
        lines: (detail.lines?.length ? detail.lines : [emptyInvoiceLine()]).map((line) => ({
          ...line,
          product: line.product || '',
          quantity: String(line.quantity ?? 1),
          unit_price: line.unit_price ?? '',
        })),
      })
    } catch (err) {
      notify(err.message)
      navigate(pathForPage('Buyurtmalar'))
    }
  }

  useEffect(() => {
    const key = `${routeMode}:${invoiceId || ''}:${prefillClientId || ''}`
    if (routeBootstrapped.current === key) return
    routeBootstrapped.current = key

    if (routeMode === 'new') {
      if (!canManage) {
        notify('Bu amalni bajarish uchun ruxsatingiz yo‘q.')
        navigate(pathForPage('Buyurtmalar'))
        return
      }
      initNewEditor(prefillClientId || '')
      return
    }
    if (routeMode === 'edit' && invoiceId) {
      if (!canManage) {
        notify('Bu amalni bajarish uchun ruxsatingiz yo‘q.')
        navigate(pathForPage('Buyurtmalar'))
        return
      }
      loadEditor(invoiceId)
      return
    }
    if (routeMode === 'list') {
      setEditing(null)
      setViewInvoice(null)
      setViewClient(null)
      setViewExecutorClient(null)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeMode, invoiceId, prefillClientId, canManage])

  useEffect(() => {
    if (!editing || editing.id || contractNumberEdited || !editing.contract_date) return
    let cancelled = false
    api.nextContractNumber({ contract_date: editing.contract_date })
      .then((data) => {
        if (!cancelled) {
          setEditing((current) => (
            current && !current.id ? { ...current, contract_number: data.contract_number || '' } : current
          ))
        }
      })
      .catch((err) => notify(err.message))
    return () => { cancelled = true }
  }, [editing?.id, contractNumberEdited, editing?.contract_date, notify])

  const openEdit = (row) => {
    navigate(invoiceEditPath(row.id))
  }

  const updateLine = (index, patch) => {
    clearLineErrors()
    setEditing((current) => {
      const lines = current.lines.map((line, i) => {
        if (i !== index) return line
        let next = { ...line, ...patch }
        if (patch.product !== undefined) {
          const product = products.find((p) => String(p.id) === String(patch.product))
          if (product) {
            next = {
              ...next,
              product_name: product.name,
              identification_code: product.serial_number,
              barcode: product.barcode || '',
              unit: product.unit || 'piece',
              unit_price: showPrices ? (product.selling_price || product.delivery_price || next.unit_price || '') : next.unit_price,
              vat_percent: product.vat_percent || next.vat_percent || 'none',
            }
          }
        }
        if (!current.reverse_calculation) next = calcInvoiceLine(next, false)
        else next = calcInvoiceLine(next, true, Object.keys(patch)[0])
        return next
      })
      return { ...current, lines }
    })
  }

  const updateLineProductName = (index, name) => {
    const product = products.find((p) => p.name === name)
    if (product) {
      updateLine(index, { product: product.id, product_name: product.name })
      return
    }
    updateLine(index, { product: '', product_name: name })
  }

  const toggleReverse = (checked) => {
    setEditing((current) => ({
      ...current,
      reverse_calculation: checked,
      lines: current.lines.map((line) => calcInvoiceLine(line, checked)),
    }))
  }

  const addLineBelow = (index) => {
    setEditing((current) => {
      const lines = [...current.lines]
      lines.splice(index + 1, 0, emptyInvoiceLine(lines.length + 1))
      return { ...current, lines }
    })
  }

  const removeLine = (index) => {
    setEditing((current) => {
      if (current.lines.length <= 1) return current
      return { ...current, lines: current.lines.filter((_, i) => i !== index) }
    })
  }

  const totals = useMemo(() => {
    if (!editing?.lines) return { delivery: 0, vat: 0, grand: 0 }
    return editing.lines.reduce((acc, line) => ({
      delivery: acc.delivery + Number(line.delivery_amount || 0),
      vat: acc.vat + Number(line.vat_amount || 0),
      grand: acc.grand + Number(line.total_amount || 0),
    }), { delivery: 0, vat: 0, grand: 0 })
  }, [editing?.lines])

  const handlePreview = async () => {
    const profile = await refreshCompanyProfile()
    const nextErrors = validateEInvoice(editing, { showPrices, company: profile })
    setErrors(nextErrors)
    setValidatedOnce(true)
    if (Object.keys(nextErrors).length) {
      scrollToFirstEInvoiceError()
      return
    }
    setPreviewOpen(true)
  }

  const handleFieldBlur = () => {
    if (!validatedOnce || !editing) return
    setErrors(validateEInvoice(editing, { showPrices, company }))
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!canManage) return notify('Bu amalni bajarish uchun ruxsatingiz yo‘q.')
    const nextErrors = runValidation()
    if (Object.keys(nextErrors).length) {
      scrollToFirstEInvoiceError()
      return
    }
    setSaving(true)
    try {
      const payload = {
        document_type: editing.document_type,
        name: editing.name,
        contract_number: editing.contract_number,
        place_signed: editing.place_signed,
        contract_date: editing.contract_date || null,
        valid_until: editing.valid_until || null,
        client: editing.client || null,
        executor_type: editing.executor_type || 'company_profile',
        executor_client: (editing.executor_type || 'company_profile') === 'client'
          ? (editing.executor_client || null)
          : null,
        reverse_calculation: editing.reverse_calculation,
        comment: editing.comment || '',
        content_title: editing.content_title || '',
        content_body: editing.content_body || '',
        lines: editing.lines.map((line, index) => {
          const computed = calcInvoiceLine(line, editing.reverse_calculation)
          return {
            ...(line.id ? { id: line.id } : {}),
            line_number: index + 1,
            product: computed.product || null,
            product_name: computed.product_name,
            identification_code: computed.identification_code,
            barcode: computed.barcode,
            unit: computed.unit || 'piece',
            quantity: Number(computed.quantity || 1),
            unit_price: computed.unit_price || 0,
            delivery_amount: computed.delivery_amount || 0,
            vat_percent: computed.vat_percent || 'none',
            vat_amount: computed.vat_amount || 0,
            total_amount: computed.total_amount || 0,
          }
        }),
      }
      if (editing.id) await api.updateInvoice(editing.id, payload)
      else await api.createInvoice(payload)
      notify('Buyurtma saqlandi.', 'success')
      closeEditor()
      load()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  const selectedClient = selectedClientDetail
  const selectedExecutorClient = selectedExecutorClientDetail
  const executorType = editing?.executor_type || 'company_profile'

  return (
    <div className={`page e-invoice-page${isEditorPage ? ' e-invoice-page--editor' : ''}`}>
      <div className="page-heading">
        <div>
          <p className="eyebrow">MODUL</p>
          <h1>{isEditorPage ? (routeMode === 'new' ? 'Yangi buyurtma' : 'Buyurtmani tahrirlash') : 'Buyurtmalar'}</h1>
        </div>
        {canManage && isListPage && (
          <button className="primary-button" type="button" onClick={() => navigate(invoiceNewPath())}><Plus size={20} />Yangi buyurtma</button>
        )}
      </div>

      {isListPage ? (
        <section className="data-panel buyurtmalar-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">RO‘YXAT</p>
              <h3>{rows.length} ta hujjat</h3>
            </div>
          </div>
          {viewLoading && !viewInvoice ? (
            <div className="buyurtmalar-loading"><SpinnerGap size={28} className="spin" /></div>
          ) : (
            <DataTable
              columns={buyurtmaColumns}
              rows={rows}
              rowKey={(row) => row.id}
              loading={loading}
              emptyLabel="Hali buyurtma yo‘q."
              emptyCta={canManage ? { label: 'Hali buyurtma yo‘q.', ctaLabel: 'Yangi buyurtma', onCta: () => navigate(invoiceNewPath()) } : undefined}
              onRowClick={(row) => openView(row)}
              renderActions={(row) => (
                <>
                  <button type="button" className="row-action" aria-label="Shartnomani ko‘rish" onClick={(event) => { event.stopPropagation(); openView(row) }}>
                    <Eye size={18} />
                  </button>
                  {canManage && (
                    <button type="button" className="row-action" aria-label="Tahrirlash" onClick={(event) => { event.stopPropagation(); openEdit(row) }}>
                      <PencilSimple size={18} />
                    </button>
                  )}
                </>
              )}
            />
          )}
        </section>
      ) : isEditorPage && editing ? (
        <form className="e-invoice-form" onSubmit={submit}>
          <div className="e-invoice-toolbar">
            <button type="button" className="secondary-button" onClick={closeEditor}>Orqaga</button>
          </div>

          <section className="e-invoice-section">
            <h3>Hujjat ma’lumotlari</h3>
            <div className="form-grid">
              <label>Hujjat turi
                <select value={editing.document_type} onChange={(e) => setEditing({ ...editing, document_type: e.target.value })}>
                  <option value="contract_sk">Shartnoma (SK)</option>
                  <option value="invoice">Hisob-faktura</option>
                  <option value="act">Dalolatnoma</option>
                </select>
              </label>
              <label>Nomi<input value={editing.name || ''} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></label>
              <label className={errors.contract_number ? 'field-invalid' : ''}>Shartnoma raqami
                <input
                  value={editing.contract_number || ''}
                  onChange={(e) => { clearFieldError('contract_number'); setContractNumberEdited(true); setEditing({ ...editing, contract_number: e.target.value.replace(/[^\d/]/g, '') }) }}
                  onBlur={handleFieldBlur}
                  placeholder="Masalan: 12/1108"
                  inputMode="numeric"
                  pattern="[0-9/]*"
                  aria-invalid={Boolean(errors.contract_number)}
                />
                <EInvoiceFieldError message={errors.contract_number} />
              </label>
              <label className={errors.place_signed ? 'field-invalid' : ''}>Tuzilgan joyi
                <input
                  value={editing.place_signed || ''}
                  onChange={(e) => { clearFieldError('place_signed'); setEditing({ ...editing, place_signed: e.target.value }) }}
                  onBlur={handleFieldBlur}
                  aria-invalid={Boolean(errors.place_signed)}
                />
                <EInvoiceFieldError message={errors.place_signed} />
              </label>
              <label className={errors.contract_date ? 'field-invalid' : ''}>Tuzilgan sana
                <input
                  type="date"
                  value={editing.contract_date || ''}
                  onChange={(e) => { clearFieldError('contract_date'); clearFieldError('valid_until'); setEditing({ ...editing, contract_date: e.target.value }) }}
                  onBlur={handleFieldBlur}
                  aria-invalid={Boolean(errors.contract_date)}
                />
                <EInvoiceFieldError message={errors.contract_date} />
              </label>
              <label className={errors.valid_until ? 'field-invalid' : ''}>Amal qilish muddati
                <input
                  type="date"
                  value={editing.valid_until || ''}
                  onChange={(e) => { clearFieldError('valid_until'); setEditing({ ...editing, valid_until: e.target.value }) }}
                  onBlur={handleFieldBlur}
                  aria-invalid={Boolean(errors.valid_until)}
                />
                <EInvoiceFieldError message={errors.valid_until} />
              </label>
            </div>
          </section>

          <section className="e-invoice-section e-invoice-parties-section">
            <div className="e-invoice-parties-row">
              <div className="e-invoice-party-panel">
                <h3>Bajaruvchi ma’lumotlari</h3>
                <label className="e-invoice-executor-type">
                  Bajaruvchi manbasi
                  <select
                    value={executorType}
                    onChange={(e) => {
                      const value = e.target.value
                      clearFieldError('company')
                      clearFieldError('executor_client')
                      setEditing({
                        ...editing,
                        executor_type: value,
                        executor_client: value === 'company_profile' ? '' : editing.executor_client,
                      })
                    }}
                  >
                    <option value="company_profile">Korxona profili (bizning)</option>
                    <option value="client">Boshqa korxona (reestrdan)</option>
                  </select>
                </label>
                {executorType === 'company_profile' ? (
                  <>
                    {errors.company ? <EInvoiceFieldError message={errors.company} /> : null}
                    <PartyInfoGrid data={companyPartyData(company)} />
                    <p className="muted e-invoice-profile-hint">Profilni tahrirlash: menyudan «Korxona profili».</p>
                  </>
                ) : (
                  <>
                    <ClientPickerField
                      id="e-invoice-executor"
                      label="Bajaruvchi korxona"
                      value={editing.executor_client || ''}
                      selectedOption={selectedExecutorClientDetail}
                      onOpen={() => {
                        if (!can(session, 'clients_view')) {
                          notify('Mijozlar reestrini ko‘rish ruxsati yo‘q.')
                          return
                        }
                        setClientPickerTarget('executor')
                      }}
                      onClear={() => {
                        clearFieldError('executor_client')
                        setEditing({ ...editing, executor_client: '' })
                        setSelectedExecutorClientDetail(null)
                      }}
                      error={errors.executor_client}
                      required
                      placeholder="Korxonani tanlang..."
                    />
                    {selectedExecutorClient && (
                      <PartyInfoGrid data={clientPartyData(selectedExecutorClient)} />
                    )}
                  </>
                )}
              </div>
              <div className="e-invoice-party-panel">
                <h3>Hamkorning ma’lumotlari</h3>
                <ClientPickerField
                  id="e-invoice-client"
                  label="Mijoz"
                  value={editing.client || ''}
                  selectedOption={selectedClientDetail}
                  onOpen={() => {
                    if (!can(session, 'clients_view')) {
                      notify('Mijozlar reestrini ko‘rish ruxsati yo‘q.')
                      return
                    }
                    setClientPickerTarget('client')
                  }}
                  onClear={() => {
                    clearFieldError('client')
                    setEditing({ ...editing, client: '' })
                    setSelectedClientDetail(null)
                  }}
                  error={errors.client}
                  required
                  placeholder="Hamkorni tanlang..."
                />
                {selectedClient && <PartyInfoGrid data={clientPartyData(selectedClient)} />}
              </div>
            </div>
          </section>

          <section className="e-invoice-section">
            <h3>Mahsulot qatorlari</h3>
            <p className="muted e-invoice-lines-note">
              Shartnomalar reestriga tushishi uchun tovar ombordagi mahsulot bilan mos kelishi kerak (nom yoki identifikatsiya kodi).
            </p>
            {errors.lines ? <EInvoiceFieldError message={errors.lines} /> : null}
            <div className="e-invoice-lines">
              <div className="e-invoice-lines-toolbar">
                <label className="reverse-check e-invoice-reverse-check">
                  <input type="checkbox" checked={editing.reverse_calculation} onChange={(e) => toggleReverse(e.target.checked)} />
                  Teskari hisob
                </label>
                <div className="e-invoice-lines-toolbar-end">
                  <a href="https://tasnif.soliq.uz/" className="e-invoice-mxik-link" target="_blank" rel="noopener noreferrer">
                    MXIK kodlari
                  </a>
                </div>
              </div>
              <div className="e-invoice-table-wrap">
                <table className="e-invoice-table e-invoice-table--light">
                  <thead>
                    <tr>
                      <th>№</th>
                      <th>Tovar nomi</th>
                      <th>Identifikatsiya kodi</th>
                      <th>Shtrix kod</th>
                      <th>O‘lchov birligi</th>
                      <th>Soni</th>
                      {showPrices && (
                        <>
                          <th>Narxi</th>
                          <th>Yetkazish narxi</th>
                          <th>QQS %</th>
                          <th>QQS miqdori</th>
                          <th>Jami</th>
                        </>
                      )}
                      <th className="e-invoice-actions-head" aria-label="Amallar" />
                    </tr>
                  </thead>
                  <tbody>
                    {editing.lines.map((line, index) => (
                      <tr key={index}>
                        <td className="e-invoice-num">{index + 1}</td>
                        <td className="e-invoice-product">
                          <div className="e-invoice-product-field">
                            <input
                              list={`einv-product-${index}`}
                              value={line.product_name || ''}
                              onChange={(e) => updateLineProductName(index, e.target.value)}
                              onBlur={handleFieldBlur}
                              placeholder="Tovar nomi"
                              aria-label="Tovar nomi"
                              aria-invalid={Boolean(errors[`lines.${index}.product_name`])}
                              className={errors[`lines.${index}.product_name`] ? 'input-invalid' : ''}
                            />
                            <button
                              type="button"
                              className="icon-button e-invoice-product-pick"
                              onClick={() => setProductPickerLineIndex(index)}
                              aria-label="Ombordan tovar tanlash"
                              title="Ombordan tanlash"
                            >
                              <Package size={16} />
                            </button>
                          </div>
                          <datalist id={`einv-product-${index}`}>
                            {products.map((p) => <option value={p.name} key={p.id} />)}
                          </datalist>
                          <EInvoiceFieldError message={errors[`lines.${index}.product_name`]} />
                        </td>
                        <td>
                          <input
                            list={`einv-idcode-${index}`}
                            value={line.identification_code || ''}
                            onChange={(e) => updateLine(index, { identification_code: e.target.value })}
                            onBlur={handleFieldBlur}
                            placeholder="Kod"
                            aria-label="Identifikatsiya kodi"
                            aria-invalid={Boolean(errors[`lines.${index}.identification_code`])}
                            className={errors[`lines.${index}.identification_code`] ? 'input-invalid' : ''}
                          />
                          <datalist id={`einv-idcode-${index}`}>
                            {products.map((p) => p.serial_number).filter(Boolean).map((code) => (
                              <option value={code} key={code} />
                            ))}
                          </datalist>
                          <EInvoiceFieldError message={errors[`lines.${index}.identification_code`]} />
                        </td>
                        <td><input value={line.barcode || ''} onChange={(e) => updateLine(index, { barcode: e.target.value })} placeholder="Shtrix kod" aria-label="Shtrix kod" /></td>
                        <td className="e-invoice-unit">
                          <select value={line.unit || 'piece'} onChange={(e) => updateLine(index, { unit: e.target.value })} aria-label="O‘lchov birligi">
                            {eInvoiceUnits.map(([v, n]) => <option value={v} key={v}>{n}</option>)}
                          </select>
                        </td>
                        <td>
                          <input
                            type="number"
                            min="1"
                            value={line.quantity}
                            onChange={(e) => updateLine(index, { quantity: e.target.value })}
                            onBlur={handleFieldBlur}
                            aria-label="Soni"
                            aria-invalid={Boolean(errors[`lines.${index}.quantity`])}
                            className={errors[`lines.${index}.quantity`] ? 'input-invalid' : ''}
                          />
                          <EInvoiceFieldError message={errors[`lines.${index}.quantity`]} />
                        </td>
                        {showPrices && (
                          <>
                            <td>
                              <input
                                type="number"
                                min="0"
                                step="0.01"
                                readOnly={!editing.reverse_calculation}
                                value={line.unit_price}
                                onChange={(e) => updateLine(index, { unit_price: e.target.value })}
                                onBlur={handleFieldBlur}
                                aria-invalid={Boolean(errors[`lines.${index}.unit_price`])}
                                className={errors[`lines.${index}.unit_price`] ? 'input-invalid' : ''}
                              />
                              <EInvoiceFieldError message={errors[`lines.${index}.unit_price`]} />
                            </td>
                            <td><input type="number" min="0" step="0.01" readOnly={!editing.reverse_calculation} value={line.delivery_amount} onChange={(e) => updateLine(index, { delivery_amount: e.target.value })} /></td>
                            <td>
                              <select value={line.vat_percent || 'none'} onChange={(e) => updateLine(index, { vat_percent: e.target.value })}>
                                {vatOptions.map(([v, n]) => <option value={v} key={v}>{n}</option>)}
                              </select>
                            </td>
                            <td><input type="number" min="0" step="0.01" readOnly={!editing.reverse_calculation} value={line.vat_amount} onChange={(e) => updateLine(index, { vat_amount: e.target.value })} /></td>
                            <td><input type="number" min="0" step="0.01" readOnly={!editing.reverse_calculation} value={line.total_amount} onChange={(e) => updateLine(index, { total_amount: e.target.value })} /></td>
                          </>
                        )}
                        <td className="e-invoice-row-actions">
                          <div className="e-invoice-row-actions-inner">
                            <button
                              type="button"
                              className="e-invoice-row-btn e-invoice-row-btn--delete"
                              onClick={() => removeLine(index)}
                              disabled={editing.lines.length <= 1}
                              aria-label="Qatorni o‘chirish"
                            >
                              <Trash size={16} />
                            </button>
                            <button
                              type="button"
                              className="e-invoice-row-btn e-invoice-row-btn--add"
                              onClick={() => addLineBelow(index)}
                              aria-label="Qator qo‘shish"
                            >
                              <Plus size={16} weight="bold" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  {showPrices && (
                    <tfoot>
                      <tr>
                        <td colSpan={7}><b>Jami</b></td>
                        <td><b>{moneyDecimal(totals.delivery)}</b></td>
                        <td />
                        <td><b>{moneyDecimal(totals.vat)}</b></td>
                        <td><b>{moneyDecimal(totals.grand)}</b></td>
                        <td />
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
              {showPrices && (
                <p className="e-invoice-grand-total">Jami: <strong>{moneyDecimal(totals.grand)}</strong></p>
              )}
            </div>
          </section>

          <section className="e-invoice-section mazmun-section">
            <h3>Mazmun</h3>
            <div className="form-grid">
              <label className={`full-width${errors.content_title ? ' field-invalid' : ''}`}>Sarlavha
                <input
                  value={editing.content_title || ''}
                  onChange={(e) => { clearFieldError('content_title'); setEditing({ ...editing, content_title: e.target.value }) }}
                  onBlur={handleFieldBlur}
                  placeholder="1. ..."
                  aria-invalid={Boolean(errors.content_title)}
                />
                <EInvoiceFieldError message={errors.content_title} />
              </label>
              <label className={`full-width${errors.content_body ? ' field-invalid' : ''}`}>Matn
                <textarea
                  rows={8}
                  value={editing.content_body || ''}
                  onChange={(e) => { clearFieldError('content_body'); setEditing({ ...editing, content_body: e.target.value }) }}
                  onBlur={handleFieldBlur}
                  placeholder="Shartnoma bandlarini qo‘lda kiriting..."
                  aria-invalid={Boolean(errors.content_body)}
                />
                <EInvoiceFieldError message={errors.content_body} />
              </label>
            </div>
            <div className="e-invoice-actions">
              <button type="button" className="secondary-button" onClick={handlePreview}>
                <Eye size={18} />Hujjatni ko‘rsatish
              </button>
              <button type="button" className="secondary-button" onClick={closeEditor}>Bekor qilish</button>
              {canManage && (
                <button className="primary-button" disabled={saving}>
                  {saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}
                </button>
              )}
            </div>
          </section>
        </form>
      ) : isEditorPage ? (
        <div className="buyurtmalar-loading"><SpinnerGap size={28} className="spin" /></div>
      ) : null}

      {previewOpen && editing && (
        <DocumentPreviewModal
          invoice={editing}
          company={company}
          client={selectedClient}
          executorClient={selectedExecutorClient}
          totals={totals}
          showPrices={showPrices}
          onClose={() => setPreviewOpen(false)}
        />
      )}

      {viewInvoice && (
        <InvoiceContractModal
          invoice={viewInvoice}
          company={company}
          client={viewClient}
          executorClient={viewExecutorClient}
          showPrices={showPrices}
          onClose={closeView}
          onEdit={canManage ? openEditFromView : null}
          canEdit={canManage}
        />
      )}

      {clientPickerTarget && can(session, 'clients_view') && (
        <ClientPickerModal
          title={clientPickerTarget === 'executor' ? 'Bajaruvchi korxonani tanlash' : 'Hamkorni tanlash'}
          selectedId={clientPickerTarget === 'executor' ? editing?.executor_client : editing?.client}
          canSearch={can(session, 'clients_view')}
          canAdd={can(session, 'clients_manage')}
          onClose={() => setClientPickerTarget(null)}
          onSelect={(client) => handleClientPickerSelect(clientPickerTarget, client)}
          onAddNew={() => openClientQuickAdd(clientPickerTarget)}
        />
      )}

      {clientQuickAddOpen && can(session, 'clients_manage') && (
        <Editor
          title="Mijozlar"
          item={{ client_type: 'legal' }}
          path="/clients/"
          close={() => setClientQuickAddOpen(false)}
          done={(created) => {
            setClientQuickAddOpen(false)
            if (created?.id) {
              if (clientQuickAddTarget === 'executor') {
                clearFieldError('executor_client')
                setEditing((current) => (current ? { ...current, executor_client: created.id } : current))
                setSelectedExecutorClientDetail(created)
              } else {
                clearFieldError('client')
                setEditing((current) => (current ? { ...current, client: created.id } : current))
                setSelectedClientDetail(created)
              }
            }
          }}
          notify={notify}
          session={session}
        />
      )}

      {productPickerLineIndex !== null && (
        <ProductPickerModal
          products={products}
          onClose={() => setProductPickerLineIndex(null)}
          onSelect={(product) => {
            updateLine(productPickerLineIndex, { product: product.id })
            setProductPickerLineIndex(null)
          }}
        />
      )}
    </div>
  )
}

export default App
