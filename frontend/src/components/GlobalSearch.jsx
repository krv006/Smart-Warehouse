import { useCallback, useEffect, useRef, useState } from 'react'
import { FileText, MagnifyingGlass, Package, SpinnerGap, Truck, Users, X } from '@phosphor-icons/react'
import { api } from '../api'
import { clientDetailPath, orderDetailPath, pathForPage } from '../routes'

const list = (data) => (Array.isArray(data) ? data : data?.results || [])

const SECTIONS = [
  { id: 'clients', label: 'Mijozlar', icon: Users, ability: 'clients_view', load: (q) => api.clients({ search: q, page_size: 6 }) },
  { id: 'invoices', label: 'Buyurtmalar', icon: FileText, ability: 'einvoice_view', load: (q) => api.invoices({ search: q, page_size: 6 }) },
  { id: 'products', label: 'Mahsulotlar', icon: Package, ability: 'warehouse_view', load: (q) => api.products({ search: q, page_size: 6 }) },
  { id: 'contracts', label: 'Shartnomalar', icon: Truck, ability: 'contracts_view', load: (q) => api.contracts({ search: q, page_size: 6 }) },
]

function can(session, ability) {
  if (!ability) return true
  if (session?.is_superuser) return true
  return Boolean(session?.abilities?.[ability])
}

function resultHref(section, row) {
  if (section === 'clients') return clientDetailPath(row.id)
  if (section === 'invoices') return orderDetailPath(row.id)
  if (section === 'products') return pathForPage('Ombor')
  if (section === 'contracts') return pathForPage('Shartnomalar')
  return '/'
}

function resultTitle(section, row) {
  if (section === 'clients') return row.company_name || row.full_name || `Mijoz #${row.id?.slice?.(0, 8)}`
  if (section === 'invoices') return row.client_name || row.contract_number || row.name || `Buyurtma #${row.id}`
  if (section === 'products') return row.name || row.serial_number || `Mahsulot #${row.id}`
  if (section === 'contracts') return row.contract_number || `Shartnoma #${row.id}`
  return 'Yozuv'
}

function resultMeta(section, row) {
  if (section === 'clients') {
    return [row.phone, row.inn, row.pinfl, row.passport_number, row.director_jshshr].filter(Boolean).join(' · ')
  }
  if (section === 'invoices') return [row.document_type_display || row.document_type, row.contract_number].filter(Boolean).join(' · ')
  if (section === 'products') return row.serial_number || row.barcode || ''
  if (section === 'contracts') return row.product_name || row.asos || ''
  return ''
}

export default function GlobalSearch({ open, onClose, session, onNavigate }) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState({})
  const inputRef = useRef(null)
  const debounceRef = useRef(null)

  useEffect(() => {
    if (open) {
      setQuery('')
      setResults({})
      window.setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [open])

  const runSearch = useCallback(async (term) => {
    const q = term.trim()
    if (q.length < 2) {
      setResults({})
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const sections = SECTIONS.filter((item) => can(session, item.ability))
      const entries = await Promise.all(
        sections.map(async (section) => {
          try {
            const data = await section.load(q)
            return [section.id, list(data)]
          } catch {
            return [section.id, []]
          }
        }),
      )
      setResults(Object.fromEntries(entries))
    } finally {
      setLoading(false)
    }
  }, [session])

  useEffect(() => {
    if (!open) return undefined
    window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => runSearch(query), 280)
    return () => window.clearTimeout(debounceRef.current)
  }, [query, open, runSearch])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const hasResults = Object.values(results).some((rows) => rows.length > 0)

  return (
    <div className="modal-backdrop omnibox-backdrop" role="presentation" onClick={onClose}>
      <div
        className="omnibox"
        role="dialog"
        aria-modal="true"
        aria-label="Global qidiruv"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="omnibox-head">
          <MagnifyingGlass size={20} />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="F.I.Sh, INN, JSHSHIR, passport, buyurtma…"
            aria-label="Qidiruv"
          />
          <kbd className="omnibox-kbd">Esc</kbd>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Yopish"><X size={18} /></button>
        </div>
        <div className="omnibox-body">
          {loading && <div className="omnibox-loading"><SpinnerGap size={22} className="spin" />Qidirilmoqda…</div>}
          {!loading && query.trim().length < 2 && (
            <p className="omnibox-hint">Kamida 2 ta belgi kiriting. Tezkor ochish: <kbd>Ctrl</kbd>+<kbd>K</kbd></p>
          )}
          {!loading && query.trim().length >= 2 && !hasResults && (
            <p className="omnibox-hint">Natija topilmadi</p>
          )}
          {!loading && SECTIONS.filter((s) => can(session, s.ability)).map((section) => {
            const rows = results[section.id] || []
            if (!rows.length) return null
            const Icon = section.icon
            return (
              <div key={section.id} className="omnibox-section">
                <p className="omnibox-section-title"><Icon size={16} />{section.label}</p>
                <ul>
                  {rows.map((row) => (
                    <li key={`${section.id}-${row.id}`}>
                      <button
                        type="button"
                        onClick={() => {
                          onNavigate(resultHref(section.id, row))
                          onClose()
                        }}
                      >
                        <b>{resultTitle(section.id, row)}</b>
                        {resultMeta(section.id, row) && <span>{resultMeta(section.id, row)}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export function useGlobalSearchHotkey(onOpen) {
  useEffect(() => {
    const handler = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        onOpen()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onOpen])
}
