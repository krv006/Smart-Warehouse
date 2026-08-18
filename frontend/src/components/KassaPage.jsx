import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowDown,
  ArrowsLeftRight,
  ArrowUp,
  CalendarBlank,
  CurrencyCircleDollar,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  SpinnerGap,
  Warning,
  Wallet,
  X,
} from '@phosphor-icons/react'
import { api } from '../api'
import DataTable, { TablePagination } from './DataTable'
import { can } from '../lib/permissions'
import { formatDateUz, list, money, moneyDecimal, todayValue } from '../lib/utils'

function KassaMetric({ icon: Icon, label, value, tone = 'neutral', onEdit }) {
  return (
    <article className={`metric kassa-metric kassa-metric--${tone}`}>
      <span className={`metric-icon ${tone}`}><Icon size={22} weight="duotone" /></span>
      <div>
        <p>{label}</p>
        <h2>{value}</h2>
      </div>
      {onEdit && (
        <button
          type="button"
          className="icon-button kassa-metric-edit"
          onClick={onEdit}
          aria-label={`${label} — qo‘lda tuzatish`}
          title="Qo‘lda tuzatish"
        >
          <PencilSimple size={16} />
        </button>
      )}
    </article>
  )
}

/**
 * Kassa balansini (UZS/USD) qo'lda tuzatish — yakuniy qiymat kiritiladi,
 * farq (delta) backendda hisoblanadi va DBga (`CashBalanceAdjustment`)
 * yoziladi. `asos` MAJBURIY — kim, qachon, nima uchun tarixda saqlanadi.
 */
function AdjustBalanceModal({ currency, currentBalance, close, done, notify }) {
  const [targetBalance, setTargetBalance] = useState(String(currentBalance ?? ''))
  const [asos, setAsos] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (!asos.trim()) return notify('Asos (sabab) kiritilishi shart.')
    setSaving(true)
    try {
      await api.adjustCashBalance({
        currency,
        target_balance: targetBalance,
        asos: asos.trim(),
      })
      notify('Kassa balansi tuzatildi.', 'success')
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
          <div>
            <p className="eyebrow">QO‘LDA TUZATISH</p>
            <h3>Kassa balansi ({currency})</h3>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button>
        </div>
        <p className="muted">
          Joriy balans: <b>{currency === 'USD' ? `$${moneyDecimal(currentBalance)}` : `${money(currentBalance)} UZS`}</b>
        </p>
        <div className="form-grid">
          <label className="full-width">
            Yangi balans ({currency})
            <input
              required
              type="number"
              step="0.01"
              value={targetBalance}
              onChange={(e) => setTargetBalance(e.target.value)}
            />
          </label>
          <label className="full-width">
            Asos (sabab) <span aria-hidden="true">*</span>
            <textarea
              required
              rows={3}
              value={asos}
              onChange={(e) => setAsos(e.target.value)}
              placeholder="Masalan: Inventarizatsiya natijasida farq aniqlandi"
            />
          </label>
        </div>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>
            {saving ? <SpinnerGap size={18} className="spin" /> : 'Tuzatishni saqlash'}
          </button>
        </div>
      </form>
    </div>
  )
}

function PaymentPayModal({ item, close, done, notify }) {
  const [amount, setAmount] = useState(item.remaining || '')
  const [comment, setComment] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await api.pay(item.payment_id, { amount, comment })
      notify('To‘lov qabul qilindi.', 'success')
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
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button>
        </div>
        <p className="muted">Qolgan summa: <b>{money(item.remaining)} {item.currency}</b></p>
        <div className="form-grid">
          <label>Qabul qilinadigan summa<input required min="0.01" max={item.remaining} type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
          <label>Izoh<input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Masalan, ikkinchi to‘lov" /></label>
        </div>
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving}>{saving ? <SpinnerGap size={18} className="spin" /> : 'To‘lovni qabul qilish'}</button>
        </div>
      </form>
    </div>
  )
}

function PaymentCreateModal({ close, done, notify }) {
  const [sales, setSales] = useState([])
  const [clients, setClients] = useState([])
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    sale: '',
    client: '',
    paid_amount: '0',
    currency: 'UZS',
    due_date: '',
  })

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoadingOptions(true)
      try {
        const [salesData, clientsData] = await Promise.all([
          api.sales({ page_size: 200 }),
          api.clients({ page_size: 200 }),
        ])
        if (!cancelled) {
          setSales(list(salesData))
          setClients(list(clientsData))
        }
      } catch (err) {
        if (!cancelled) notify(err.message)
      } finally {
        if (!cancelled) setLoadingOptions(false)
      }
    })()
    return () => { cancelled = true }
  }, [notify])

  const selectedSale = useMemo(
    () => sales.find((s) => String(s.id) === String(form.sale)),
    [sales, form.sale],
  )

  const saleTotal = selectedSale
    ? Number(selectedSale.sold_price || 0) * Number(selectedSale.quantity || 1)
    : 0
  const saleCommission = saleTotal ? Math.round(saleTotal * 0.15) : 0

  const handleSaleChange = (saleId) => {
    const sale = sales.find((s) => String(s.id) === String(saleId))
    setForm((current) => ({
      ...current,
      sale: saleId,
      client: sale?.client ? String(sale.client) : current.client,
      currency: current.currency || 'UZS',
    }))
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!form.sale) return notify('Sotuvni tanlang.')
    setSaving(true)
    try {
      const payload = {
        sale: Number(form.sale),
        currency: form.currency,
        paid_amount: form.paid_amount || '0',
      }
      if (form.client) payload.client = form.client
      if (form.due_date) payload.due_date = form.due_date
      await api.create('/cash/payments/', payload)
      notify('To‘lov yozuvi yaratildi.', 'success')
      done()
    } catch (err) {
      notify(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="editor payment-create-modal" onSubmit={submit}>
        <div className="editor-head">
          <div>
            <p className="eyebrow">YANGI TO‘LOV</p>
            <h3>Yangi to‘lov yozuvi</h3>
            <p className="muted">Sotuvni tanlang — jami va 15% komissiya avtomatik hisoblanadi.</p>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="Yopish"><X size={20} /></button>
        </div>
        {loadingOptions ? (
          <div className="payment-create-loading"><SpinnerGap size={28} className="spin" /></div>
        ) : (
          <div className="form-grid">
            <label className="full-width">
              Sotuv
              <select required value={form.sale} onChange={(e) => handleSaleChange(e.target.value)}>
                <option value="">Sotuvni tanlang</option>
                {sales.map((sale) => (
                  <option key={sale.id} value={sale.id}>
                    {sale.product_name || `#${sale.id}`} — {formatDateUz(sale.sold_date)} — {money(Number(sale.sold_price || 0) * Number(sale.quantity || 1))} so‘m
                  </option>
                ))}
              </select>
            </label>
            <label className="full-width">
              Mijoz
              <select value={form.client} onChange={(e) => setForm({ ...form, client: e.target.value })}>
                <option value="">— Mijozsiz —</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>{client.company_name || client.full_name || `#${client.id}`}</option>
                ))}
              </select>
            </label>
            {selectedSale && (
              <p className="muted full-width payment-create-preview">
                Jami: <b>{money(saleTotal)} so‘m</b> · Komissiya (15%): <b>{money(saleCommission)} so‘m</b>
              </p>
            )}
            <label>Boshlang‘ich to‘lov<input min="0" step="0.01" type="number" value={form.paid_amount} onChange={(e) => setForm({ ...form, paid_amount: e.target.value })} /></label>
            <label>Valyuta
              <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
                <option value="UZS">UZS</option>
                <option value="USD">USD</option>
              </select>
            </label>
            <label className="full-width">To‘lov muddati<input type="date" value={form.due_date} min={todayValue()} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></label>
          </div>
        )}
        <div className="editor-actions">
          <button type="button" className="secondary-button" onClick={close}>Bekor qilish</button>
          <button className="primary-button" disabled={saving || loadingOptions}>{saving ? <SpinnerGap size={18} className="spin" /> : 'Saqlash'}</button>
        </div>
      </form>
    </div>
  )
}

function ledgerSourceLabel(row) {
  if (row.source === 'import') return 'Import'
  if (row.source === 'order') return 'Buyurtma'
  if (row.source === 'sale') return 'Sotuv'
  if (row.source === 'expense') return 'Rasxod'
  if (row.source === 'adjustment') return 'Qo‘lda tuzatish'
  return row.source || '—'
}

function ledgerKindLabel(row) {
  return row.kind === 'out' ? 'Chiqim' : 'Tushum'
}

/** Bankning tanlangan kurs qatori (sotish narxi bo‘yicha, UZS → USD hisob-kitobi uchun). */
function bankSellRate(bank) {
  const rate = Number(bank?.sell_rate ?? bank?.buy_rate ?? 0)
  return Number.isFinite(rate) && rate > 0 ? rate : null
}

/**
 * Valyuta konvertori — kiritilgan summani tanlangan bank kursi bo‘yicha
 * UZS <-> USD ga aylantirib ko‘rsatadi. "Konvertatsiya qilish" bosilsa
 * natija DBga yoziladi (`CashConversion`) va kassa balansi (UZS/USD)
 * shunga qarab yangilanadi — manba valyutadan ayiriladi, maqsad
 * valyutaga qo‘shiladi.
 */
function CurrencyConverter({ notify, canManage, onConverted }) {
  const [snapshot, setSnapshot] = useState(null)
  const [bankKey, setBankKey] = useState('infinbank')
  const [amount, setAmount] = useState('')
  const [direction, setDirection] = useState('uzs_to_usd')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    api.exchangeRateLatest().then((data) => {
      if (active) setSnapshot(data)
    }).catch((err) => {
      if (active) notify?.(err.message)
    })
    return () => { active = false }
  }, [notify])

  const rateOptions = useMemo(() => {
    const options = []
    const infinRate = Number(snapshot?.infinbank?.mb_rate)
    if (Number.isFinite(infinRate) && infinRate > 0) {
      options.push({ key: 'infinbank', label: 'Infinbank MB', rate: infinRate })
    }
    ;(snapshot?.market_rates?.banks || []).forEach((bank) => {
      const rate = bankSellRate(bank)
      if (rate) options.push({ key: `bank:${bank.code}`, label: bank.name, rate })
    })
    return options
  }, [snapshot])

  useEffect(() => {
    if (rateOptions.length && !rateOptions.some((o) => o.key === bankKey)) {
      setBankKey(rateOptions[0].key)
    }
  }, [rateOptions, bankKey])

  const selected = rateOptions.find((o) => o.key === bankKey) || rateOptions[0] || null
  const numericAmount = Number(amount)
  const hasAmount = amount !== '' && Number.isFinite(numericAmount) && numericAmount > 0
  const isUzsToUsd = direction === 'uzs_to_usd'
  const result = selected && hasAmount
    ? (isUzsToUsd ? numericAmount / selected.rate : numericAmount * selected.rate)
    : null

  const submit = async (event) => {
    event.preventDefault()
    if (!selected || !hasAmount) return
    setSaving(true)
    try {
      await api.cashConvert({
        direction,
        amount: String(numericAmount),
        rate: String(selected.rate),
      })
      notify?.('Konvertatsiya bajarildi va kassa balansiga yozildi.', 'success')
      setAmount('')
      onConverted?.()
    } catch (err) {
      notify?.(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="data-panel kassa-converter">
      <div className="kassa-converter-head">
        <p className="eyebrow">HISOB-KITOB</p>
        <h3>Valyuta konvertori</h3>
      </div>
      {rateOptions.length === 0 ? (
        <p className="muted">Kurslar yuklanmoqda…</p>
      ) : (
        <form className="kassa-converter-body" onSubmit={submit}>
          <div className="kassa-converter-direction" role="group" aria-label="Yo‘nalish">
            <button
              type="button"
              className={isUzsToUsd ? 'period-tab is-active' : 'period-tab'}
              onClick={() => setDirection('uzs_to_usd')}
            >
              UZS <ArrowsLeftRight size={14} /> USD
            </button>
            <button
              type="button"
              className={!isUzsToUsd ? 'period-tab is-active' : 'period-tab'}
              onClick={() => setDirection('usd_to_uzs')}
            >
              USD <ArrowsLeftRight size={14} /> UZS
            </button>
          </div>
          <label className="kassa-converter-field">
            <span>Summa ({isUzsToUsd ? 'UZS' : 'USD'})</span>
            <input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              placeholder={isUzsToUsd ? 'Masalan: 15000000' : 'Masalan: 1000'}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
          <label className="kassa-converter-field">
            <span>Kurs (bank)</span>
            <select value={bankKey} onChange={(e) => setBankKey(e.target.value)} aria-label="Bank kursi">
              {rateOptions.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label} — {moneyDecimal(option.rate)}
                </option>
              ))}
            </select>
          </label>
          <div className="kassa-converter-result">
            <span>Natija</span>
            <strong>{result != null ? (isUzsToUsd ? `$${moneyDecimal(result)}` : `${moneyDecimal(result)} UZS`) : '—'}</strong>
          </div>
          {canManage && (
            <button type="submit" className="primary-button" disabled={!hasAmount || saving}>
              {saving ? <SpinnerGap size={18} className="spin" /> : 'Konvertatsiya qilish'}
            </button>
          )}
        </form>
      )}
    </section>
  )
}

export default function KassaPage({ notify, session, onDataChange, reloadKey = 0 }) {
  const showPrices = can(session, 'prices_view')
  const canManage = can(session, 'cash_manage')
  const canAdjustBalance = Boolean(session?.is_management)
  const [rows, setRows] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [paying, setPaying] = useState(null)
  const [creating, setCreating] = useState(false)
  const [adjusting, setAdjusting] = useState(null)
  const pageSize = 25

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const params = {
        page,
        page_size: pageSize,
        ...(searchTerm ? { search: searchTerm } : {}),
        ...(sourceFilter ? { source: sourceFilter } : {}),
      }
      const requests = [api.kassaLedger(params)]
      if (showPrices) requests.push(api.paymentsSummary())
      const [ledgerData, summaryData] = await Promise.all(requests)
      const payload = list(ledgerData)
      if (ledgerData?.results) {
        setRows(payload)
        setTotalCount(ledgerData.count || 0)
      } else {
        setRows(payload)
        setTotalCount(payload.length)
      }
      if (summaryData) setSummary(summaryData)
    } catch (err) {
      if (!silent) notify(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [notify, page, searchTerm, sourceFilter, showPrices])

  useEffect(() => { setPage(1) }, [searchTerm, sourceFilter])
  useEffect(() => { load() }, [load, reloadKey])

  const columns = useMemo(() => {
    const base = [
      {
        key: 'kind',
        label: 'Turi',
        render: (row) => (
          <span className={`kassa-kind kassa-kind--${row.kind}`}>
            {row.kind === 'out' ? <ArrowDown size={16} weight="bold" /> : <ArrowUp size={16} weight="bold" />}
            {ledgerKindLabel(row)}
          </span>
        ),
      },
      { key: 'source', label: 'Manba', render: (row) => ledgerSourceLabel(row) },
      { key: 'label', label: 'Izoh', render: (row) => row.label || '—' },
      { key: 'date', label: 'Sana', render: (row) => formatDateUz(row.date) },
    ]
    if (!showPrices) return base
    return [
      ...base,
      {
        key: 'amount',
        label: 'Summa',
        render: (row) => (
          <span className={row.kind === 'out' ? 'kassa-amount-out' : 'kassa-amount-in'}>
            {row.kind === 'out' ? '−' : '+'}
            {money(row.amount)} {row.currency || 'UZS'}
          </span>
        ),
      },
      { key: 'client', label: 'Kim / Etkazuvchi', render: (row) => row.client_name || '—' },
    ]
  }, [showPrices])

  const refresh = () => {
    load(true)
    onDataChange?.()
  }

  const netBalance = summary ? Number(summary.net_balance_uzs || 0) : 0
  const netTone = netBalance >= 0 ? 'success' : 'danger'
  const netBalanceUsd = summary ? Number(summary.net_balance_usd || 0) : 0
  const netToneUsd = netBalanceUsd >= 0 ? 'success' : 'danger'

  return (
    <div className="page kassa-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">MOLIYA</p>
          <h1>Kassa</h1>
          <p className="muted">Sotuv tushumlari, import chiqimlari va kassa balansi.</p>
        </div>
        {canManage && (
          <div className="heading-actions">
            <button type="button" className="primary-button" onClick={() => setCreating(true)}>
              <Plus size={20} />Yangi to‘lov
            </button>
          </div>
        )}
      </div>

      {showPrices && summary && (
        <section className="metric-grid kassa-metrics">
          <KassaMetric
            icon={Wallet} label="Kassa balansi (UZS)" value={`UZS ${money(summary.net_balance_uzs)}`} tone={netTone}
            onEdit={canAdjustBalance ? () => setAdjusting('UZS') : null}
          />
          <KassaMetric
            icon={Wallet} label="Kassa balansi (USD)" value={`$${moneyDecimal(summary.net_balance_usd)}`} tone={netToneUsd}
            onEdit={canAdjustBalance ? () => setAdjusting('USD') : null}
          />
          <KassaMetric icon={ArrowUp} label="Tushum (UZS)" value={`UZS ${money(summary.sum_in_uzs ?? summary.sum_paid_uzs)}`} tone="success" />
          <KassaMetric icon={ArrowDown} label="Import chiqim (UZS)" value={`UZS ${money(summary.sum_import_uzs)}`} tone="warning" />
          <KassaMetric icon={CurrencyCircleDollar} label="Komissiya (UZS)" value={`UZS ${money(summary.total_commission_uzs)}`} />
        </section>
      )}

      <CurrencyConverter notify={notify} canManage={canManage} onConverted={refresh} />

      <div className="kassa-layout">
        <section className="data-panel kassa-table-panel">
          <div className="panel-head kassa-panel-head">
            <form className="resource-search kassa-search" onSubmit={(e) => { e.preventDefault(); setSearchTerm(search.trim()) }}>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Sotuv, import yoki shartnoma bo‘yicha qidirish..."
                aria-label="Kassa qidirish"
              />
              <button type="submit" className="icon-button" aria-label="Qidirish"><MagnifyingGlass size={20} /></button>
            </form>
            <div className="kassa-filters">
              <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} aria-label="Manba filtri">
                <option value="">Barcha manba</option>
                <option value="sale">Sotuv</option>
                <option value="order">Buyurtma</option>
                <option value="import">Import</option>
                <option value="expense">Rasxod</option>
                <option value="adjustment">Qo‘lda tuzatish</option>
              </select>
            </div>
          </div>
          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            emptyLabel="Ma’lumot topilmadi"
            rowClassName={(row) => (row.kind === 'out' ? 'kassa-row-out' : 'kassa-row-in')}
            renderActions={(row) => (
              canManage && row.kind === 'in' && row.payment_id
              && Number(row.remaining || 0) > 0 ? (
                <button type="button" className="row-action" onClick={() => setPaying(row)} aria-label="To‘lov qabul qilish">
                  <CurrencyCircleDollar size={18} />
                </button>
              ) : null
            )}
          />
          <TablePagination page={page} pageSize={pageSize} total={totalCount} onPageChange={setPage} />
        </section>

        {showPrices && summary && (
          <aside className="data-panel kassa-forecast">
            <p className="eyebrow">XULOSA</p>
            <h3>Kassa holati</h3>
            <ul className="kassa-forecast-list">
              <li>
                <div><b>Kechikkan to‘lovlar</b></div>
                <span>{summary.total_overdue || 0} ta</span>
              </li>
              <li>
                <div><b>Buyurtma qoldig‘i</b></div>
                <span>{money(summary.sum_order_due_uzs)} UZS</span>
              </li>
            </ul>
            <p className="muted kassa-balance-note">
              Balans = tushumlar − import chiqimlari. Sotuv yaratilganda tushum avtomatik yoziladi.
            </p>
          </aside>
        )}
      </div>

      {creating && (
        <PaymentCreateModal
          close={() => setCreating(false)}
          done={() => { setCreating(false); refresh() }}
          notify={notify}
        />
      )}
      {paying && (
        <PaymentPayModal
          item={paying}
          close={() => setPaying(null)}
          done={() => { setPaying(null); refresh() }}
          notify={notify}
        />
      )}
      {adjusting && (
        <AdjustBalanceModal
          currency={adjusting}
          currentBalance={adjusting === 'USD' ? summary?.net_balance_usd : summary?.net_balance_uzs}
          close={() => setAdjusting(null)}
          done={() => { setAdjusting(null); refresh() }}
          notify={notify}
        />
      )}
    </div>
  )
}
