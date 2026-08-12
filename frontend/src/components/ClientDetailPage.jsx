import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, PencilSimple, Plus, SpinnerGap, TrendUp } from '@phosphor-icons/react'
import { api } from '../api'
import DataTable, { StatusBadge, TablePagination } from './DataTable'
import { clientDetailPath, pathForPage } from '../routes'

const list = (data) => (Array.isArray(data) ? data : data?.results || [])
const money = (value) => new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 0 }).format(Number(value || 0))

const TAB_LABELS = {
  umumiy: 'Umumiy',
  buyurtmalar: 'Buyurtmalar',
  sotuvlar: 'Sotuvlar',
  tolovlar: 'To‘lovlar',
}

const documentTypeLabels = {
  contract_sk: 'Shartnoma (SK)',
  invoice: 'Hisob-faktura',
  act: 'Dalolatnoma',
}

function can(session, ability) {
  if (!ability) return true
  if (session?.is_superuser) return true
  return Boolean(session?.abilities?.[ability])
}

function clientDisplayName(client) {
  if (!client) return '—'
  return client.client_type === 'legal'
    ? (client.company_name || client.inn || 'Yuridik shaxs')
    : (client.full_name || [client.last_name, client.first_name].filter(Boolean).join(' ') || 'Jismoniy shaxs')
}

function formatDate(iso) {
  if (!iso) return '—'
  const [y, m, d] = String(iso).slice(0, 10).split('-')
  return y && m && d ? `${d}.${m}.${y}` : iso
}

export default function ClientDetailPage({
  clientId,
  tab = 'umumiy',
  session,
  notify,
  onNavigate,
  onEditClient,
  onNewOrder,
  onNewSale,
}) {
  const [client, setClient] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tabLoading, setTabLoading] = useState(false)
  const [invoices, setInvoices] = useState([])
  const [sales, setSales] = useState([])
  const [payments, setPayments] = useState([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  const loadClient = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.retrieve('/clients/', clientId)
      setClient(data)
    } catch (err) {
      notify(err.message)
    } finally {
      setLoading(false)
    }
  }, [clientId, notify])

  useEffect(() => { loadClient() }, [loadClient])

  const loadTabData = useCallback(async () => {
    if (!clientId) return
    setTabLoading(true)
    try {
      if (tab === 'buyurtmalar' && can(session, 'einvoice_view')) {
        const data = await api.invoices({ client: clientId, page, page_size: 15, ordering: '-created_at' })
        setInvoices(list(data))
        setTotal(data.count ?? list(data).length)
      } else if (tab === 'sotuvlar' && can(session, 'sales_view')) {
        const data = await api.sales({ client: clientId, page, page_size: 15, ordering: '-sold_date' })
        setSales(list(data))
        setTotal(data.count ?? list(data).length)
      } else if (tab === 'tolovlar' && can(session, 'cash_view')) {
        const data = await api.payments({ client: clientId, page, page_size: 15 })
        setPayments(list(data))
        setTotal(data.count ?? list(data).length)
      }
    } catch (err) {
      notify(err.message)
    } finally {
      setTabLoading(false)
    }
  }, [tab, clientId, page, session, notify])

  useEffect(() => {
    if (tab !== 'umumiy') {
      setPage(1)
    }
  }, [tab])

  useEffect(() => {
    if (tab !== 'umumiy' && client) loadTabData()
  }, [tab, client, page, loadTabData])

  const tabs = useMemo(() => (
    ['umumiy', 'buyurtmalar', 'sotuvlar', 'tolovlar'].filter((key) => {
      if (key === 'buyurtmalar') return can(session, 'einvoice_view')
      if (key === 'sotuvlar') return can(session, 'sales_view')
      if (key === 'tolovlar') return can(session, 'cash_view')
      return true
    })
  ), [session])

  if (loading) {
    return <div className="page client-detail-page"><div className="client-detail-loading"><SpinnerGap size={32} className="spin" /></div></div>
  }

  if (!client) {
    return (
      <div className="page client-detail-page">
        <button type="button" className="text-button" onClick={() => onNavigate(pathForPage('Mijozlar'))}><ArrowLeft size={16} />Mijozlar ro‘yxati</button>
        <p className="contract-detail-error">Mijoz topilmadi</p>
      </div>
    )
  }

  const name = clientDisplayName(client)

  return (
    <div className="page client-detail-page">
      <button type="button" className="text-button client-detail-back" onClick={() => onNavigate(pathForPage('Mijozlar'))}>
        <ArrowLeft size={16} />Mijozlar
      </button>

      <header className="client-detail-header">
        <div>
          <p className="eyebrow">MIJOZ</p>
          <h1>{name}</h1>
          <div className="client-detail-meta">
            {client.phone && <span>{client.phone}</span>}
            {client.inn && <span>STIR: {client.inn}</span>}
            <StatusBadge
              status={client.is_active ? 'active' : 'inactive'}
              label={client.is_active ? 'Faol' : 'Nofaol'}
              tone={client.is_active ? 'success' : 'neutral'}
            />
          </div>
        </div>
        <div className="client-detail-actions">
          {can(session, 'clients_manage') && (
            <button type="button" className="secondary-button" onClick={() => onEditClient?.(client)}>
              <PencilSimple size={18} />Tahrir
            </button>
          )}
          {can(session, 'einvoice_manage') && (
            <button type="button" className="secondary-button" onClick={() => onNewOrder?.(client)}>
              <Plus size={18} />Yangi buyurtma
            </button>
          )}
          {can(session, 'sales_manage') && (
            <button type="button" className="primary-button" onClick={() => onNewSale?.(client)}>
              <TrendUp size={18} />Yangi sotuv
            </button>
          )}
        </div>
      </header>

      <div className="section-tabs client-detail-tabs" role="tablist">
        {tabs.map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? 'section-tab is-active' : 'section-tab'}
            onClick={() => onNavigate(clientDetailPath(clientId, key))}
          >
            {TAB_LABELS[key]}
          </button>
        ))}
      </div>

      <section className="client-detail-panel">
        {tab === 'umumiy' && (
          <dl className="contract-detail-grid">
            <div><dt>Turi</dt><dd>{client.client_type === 'legal' ? 'Yuridik shaxs' : 'Jismoniy shaxs'}</dd></div>
            <div><dt>Telefon</dt><dd>{client.phone || '—'}</dd></div>
            <div><dt>Email</dt><dd>{client.email || '—'}</dd></div>
            <div><dt>Manzil</dt><dd>{client.address || '—'}</dd></div>
            <div><dt>Passport / STIR</dt><dd>{client.inn || client.passport_number || '—'}</dd></div>
            <div><dt>Ro‘yxatga olingan</dt><dd>{formatDate(client.created_at)}</dd></div>
            {client.comment && <div className="full-width"><dt>Izoh</dt><dd>{client.comment}</dd></div>}
          </dl>
        )}

        {tab === 'buyurtmalar' && (
          <>
            <DataTable
              loading={tabLoading}
              columns={[
                { key: 'contract_number', label: 'Shartnoma', render: (r) => r.contract_number || r.name || `#${r.id}` },
                { key: 'document_type', label: 'Turi', render: (r) => r.document_type_display || documentTypeLabels[r.document_type] || r.document_type || '—' },
                { key: 'total', label: 'Summa', render: (r) => `${money(r.grand_total ?? r.total ?? 0)} so‘m` },
                { key: 'created_at', label: 'Sana', render: (r) => formatDate(r.created_at || r.contract_date) },
              ]}
              rows={invoices}
              onRowClick={(row) => onNavigate(`/buyurtmalar/${row.id}`)}
              emptyLabel="Buyurtma yo‘q"
            />
            <TablePagination page={page} pageSize={15} total={total} onPageChange={setPage} />
          </>
        )}

        {tab === 'sotuvlar' && (
          <>
            <DataTable
              loading={tabLoading}
              columns={[
                { key: 'product_name', label: 'Mahsulot', render: (r) => r.product_name || r.product },
                { key: 'quantity', label: 'Miqdor' },
                { key: 'total_amount', label: 'Summa', render: (r) => `${money(r.total_amount)} so‘m` },
                { key: 'sold_date', label: 'Sana', render: (r) => formatDate(r.sold_date) },
              ]}
              rows={sales}
              emptyLabel="Sotuv yo‘q"
            />
            <TablePagination page={page} pageSize={15} total={total} onPageChange={setPage} />
          </>
        )}

        {tab === 'tolovlar' && (
          <>
            <DataTable
              loading={tabLoading}
              columns={[
                { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} label={r.status_display || r.status} tone={r.status === 'paid' ? 'success' : 'warning'} /> },
                { key: 'total_amount', label: 'Summa', render: (r) => `${money(r.total_amount)} ${r.currency || 'UZS'}` },
                { key: 'due_date', label: 'Muddat', render: (r) => formatDate(r.due_date) },
              ]}
              rows={payments}
              emptyLabel="To‘lov yo‘q"
            />
            <TablePagination page={page} pageSize={15} total={total} onPageChange={setPage} />
          </>
        )}
      </section>
    </div>
  )
}
