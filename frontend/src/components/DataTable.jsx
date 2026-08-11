import { CaretDown, CaretUp, CaretUpDown } from '@phosphor-icons/react'
import EmptyState from './EmptyState'
import StatusBadge from './StatusBadge'

function SortIcon({ active, direction }) {
  if (!active) return <CaretUpDown size={14} className="sort-icon sort-icon-idle" aria-hidden="true" />
  return direction === 'asc'
    ? <CaretUp size={14} className="sort-icon" aria-hidden="true" />
    : <CaretDown size={14} className="sort-icon" aria-hidden="true" />
}

export default function DataTable({
  columns,
  rows,
  rowKey = (row, index) => row.id ?? index,
  sortKey,
  sortDir,
  onSort,
  onRowClick,
  loading,
  emptyLabel = 'Yozuv topilmadi',
  emptyCta,
  renderActions,
  selectable = false,
  selectedIds = [],
  onSelectionChange,
}) {
  const allSelected = rows.length > 0 && rows.every((row, index) => selectedIds.includes(rowKey(row, index)))
  const someSelected = rows.some((row, index) => selectedIds.includes(rowKey(row, index)))

  const toggleAll = () => {
    if (!onSelectionChange) return
    if (allSelected) onSelectionChange([])
    else onSelectionChange(rows.map((row, index) => rowKey(row, index)))
  }

  const toggleRow = (id) => {
    if (!onSelectionChange) return
    if (selectedIds.includes(id)) onSelectionChange(selectedIds.filter((item) => item !== id))
    else onSelectionChange([...selectedIds, id])
  }

  if (loading && !rows.length) {
    return (
      <div className="data-table-wrap">
        <div className="data-table-skeleton"><i /><i /><i /><i /></div>
      </div>
    )
  }

  if (!rows.length) {
    if (emptyCta) {
      return (
        <EmptyState
          label={emptyCta.label || emptyLabel}
          ctaLabel={emptyCta.ctaLabel}
          onCta={emptyCta.onCta}
        />
      )
    }
    return <div className="data-table-empty">{emptyLabel}</div>
  }

  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {selectable && (
              <th scope="col" className="data-table-check-col">
                <input
                  type="checkbox"
                  aria-label="Hammasini tanlash"
                  checked={allSelected}
                  ref={(node) => { if (node) node.indeterminate = someSelected && !allSelected }}
                  onChange={toggleAll}
                />
              </th>
            )}
            {columns.map((col) => (
              <th key={col.key} scope="col" className={col.className || ''}>
                {col.sortable ? (
                  <button
                    type="button"
                    className="data-table-sort"
                    onClick={() => onSort?.(col.key)}
                    aria-sort={sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    {col.label}
                    <SortIcon active={sortKey === col.key} direction={sortDir} />
                  </button>
                ) : col.label}
              </th>
            ))}
            {renderActions && <th scope="col" className="data-table-actions-col">Amallar</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const id = rowKey(row, index)
            const checked = selectedIds.includes(id)
            return (
              <tr
                key={id}
                className={[
                  'data-table-row',
                  onRowClick ? 'is-clickable' : '',
                  checked ? 'is-selected' : '',
                ].filter(Boolean).join(' ')}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={onRowClick ? (event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onRowClick(row)
                  }
                } : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                role={onRowClick ? 'button' : undefined}
              >
                {selectable && (
                  <td className="data-table-check-col" onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label="Qatorni tanlash"
                      checked={checked}
                      onChange={() => toggleRow(id)}
                    />
                  </td>
                )}
                {columns.map((col) => (
                  <td key={col.key} className={col.className || ''}>
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
                {renderActions && (
                  <td className="data-table-actions-col" onClick={(event) => event.stopPropagation()}>
                    <div className="row-actions">{renderActions(row)}</div>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function BulkActionsBar({ count, onClear, children }) {
  if (!count) return null
  return (
    <div className="bulk-actions-bar">
      <span><b>{count}</b> ta tanlandi</span>
      <div className="bulk-actions-buttons">{children}</div>
      <button type="button" className="secondary-button" onClick={onClear}>Tanlovni bekor qilish</button>
    </div>
  )
}

export function TablePagination({ page, pageSize, total, onPageChange }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)

  return (
    <div className="table-pagination">
      <span>{from}–{to} / {total} ta</span>
      <div className="table-pagination-controls">
        <button type="button" className="secondary-button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Oldingi</button>
        <span>{page} / {totalPages}</span>
        <button type="button" className="secondary-button" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>Keyingi</button>
      </div>
    </div>
  )
}

export { StatusBadge }
