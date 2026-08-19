import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Funnel, MagnifyingGlass, X } from '@phosphor-icons/react'
import { api } from '../api'
import { MODULE_FILTER_FEATURES, MODULE_STATUS_OPTIONS, hasActiveListFilters } from '../listFilters'

const list = (data) => Array.isArray(data) ? data : data?.results || []

// Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
// // Kategoriya daraxtini tekis ro'yxatga aylantiradi (bosqich — `depth`)
// function flattenCategoryTree(nodes, depth = 0, acc = []) {
//   nodes.forEach((node) => {
//     acc.push({ id: node.id, name: node.name, depth })
//     if (node.children?.length) flattenCategoryTree(node.children, depth + 1, acc)
//   })
//   return acc
// }

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

export default function ListFiltersPanel({ title, filters, onChange }) {
  const [open, setOpen] = useState(false)
  const [clients, setClients] = useState([])
  const [clientsLoading, setClientsLoading] = useState(false)
  // Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
  // const [categories, setCategories] = useState([])
  // const [categoriesLoading, setCategoriesLoading] = useState(false)
  const ref = useRef(null)
  const features = MODULE_FILTER_FEATURES[title] || {}

  useEffect(() => {
    if (!open || !features.client) return undefined
    let cancelled = false
    setClientsLoading(true)
    api.clients({ page_size: 200 })
      .then((data) => { if (!cancelled) setClients(list(data)) })
      .catch(() => { if (!cancelled) setClients([]) })
      .finally(() => { if (!cancelled) setClientsLoading(false) })
    return () => { cancelled = true }
  }, [open, features.client])

  // Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
  // useEffect(() => {
  //   if (!open || !features.category) return undefined
  //   let cancelled = false
  //   setCategoriesLoading(true)
  //   api.categories({ page_size: 200 })
  //     .then((data) => { if (!cancelled) setCategories(flattenCategoryTree(list(data))) })
  //     .catch(() => { if (!cancelled) setCategories([]) })
  //     .finally(() => { if (!cancelled) setCategoriesLoading(false) })
  //   return () => { cancelled = true }
  // }, [open, features.category])

  useEffect(() => {
    const onPointer = (event) => {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', onPointer)
    return () => document.removeEventListener('mousedown', onPointer)
  }, [open])

  const statusOptions = MODULE_STATUS_OPTIONS[title] || []
  const active = hasActiveListFilters(filters)

  const clearAll = useCallback(() => {
    // Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi: category: '' olib tashlandi.
    onChange({ status: '', client: '', date_from: '', date_to: '' })
  }, [onChange])

  if (!features.status && !features.client && !features.date) return null

  return (
    <div className="list-filters" ref={ref}>
      <button
        type="button"
        className={`secondary-button list-filters-toggle${active ? ' is-active' : ''}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <Funnel size={18} />
        Filtr
        {active && <span className="list-filters-badge" aria-hidden="true" />}
      </button>
      {active && (
        <button type="button" className="filter-clear-inline" onClick={clearAll}>
          Filtrlarni tozalash
        </button>
      )}
      {open && (
        <div className="list-filters-panel">
          <div className="filter-group-fields">
            {features.status && (
              <div className="filter-field">
                <label className="filter-field-label" htmlFor={`${title}-status-filter`}>Status</label>
                <select
                  id={`${title}-status-filter`}
                  className="filter-select"
                  value={filters.status || ''}
                  onChange={(event) => onChange({ ...filters, status: event.target.value })}
                >
                  <option value="">Hammasi</option>
                  {statusOptions.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>
            )}
            {features.client && (
              <FilterSearchSelect
                id={`${title}-client-filter`}
                label="Mijoz"
                value={filters.client || ''}
                onChange={(value) => onChange({ ...filters, client: value })}
                options={clients}
                loading={clientsLoading}
                getLabel={(item) => item.company_name || item.full_name || '—'}
              />
            )}
            {/* Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi. */}
            {/* {features.category && (
              <FilterSearchSelect
                id={`${title}-category-filter`}
                label="Kategoriya"
                value={filters.category || ''}
                onChange={(value) => onChange({ ...filters, category: value })}
                options={categories}
                loading={categoriesLoading}
                getLabel={(item) => `${'— '.repeat(item.depth)}${item.name}`}
              />
            )} */}
            {features.date && (
              <>
                <div className="filter-field">
                  <label className="filter-field-label" htmlFor={`${title}-date-from`}>Sana (dan)</label>
                  <input
                    id={`${title}-date-from`}
                    type="date"
                    className="filter-select"
                    value={filters.date_from || ''}
                    onChange={(event) => onChange({ ...filters, date_from: event.target.value })}
                  />
                </div>
                <div className="filter-field">
                  <label className="filter-field-label" htmlFor={`${title}-date-to`}>Sana (gacha)</label>
                  <input
                    id={`${title}-date-to`}
                    type="date"
                    className="filter-select"
                    value={filters.date_to || ''}
                    onChange={(event) => onChange({ ...filters, date_to: event.target.value })}
                  />
                </div>
              </>
            )}
          </div>
          <div className="list-filters-panel-foot">
            <button type="button" className="primary-button" onClick={() => setOpen(false)}>Qo‘llash</button>
            {active && (
              <button type="button" className="secondary-button" onClick={clearAll}>
                <X size={16} />
                Tozalash
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
