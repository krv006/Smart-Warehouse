import { useEffect, useMemo, useRef, useState } from 'react'
import { CaretDown, MagnifyingGlass, X } from '@phosphor-icons/react'
import FieldError from './FieldError'

function useClickOutside(ref, handler, active) {
  useEffect(() => {
    if (!active) return undefined
    const onPointer = (event) => {
      if (ref.current && !ref.current.contains(event.target)) handler()
    }
    document.addEventListener('mousedown', onPointer)
    return () => document.removeEventListener('mousedown', onPointer)
  }, [ref, handler, active])
}

export default function SearchableCombobox({
  id,
  label,
  value,
  onChange,
  options = [],
  getLabel = (item) => item.label ?? item.name ?? String(item),
  getValue = (item) => item.value ?? item.id,
  placeholder = 'Qidirish...',
  emptyLabel = 'Tanlanmagan',
  required = false,
  error,
  disabled = false,
  allowEmpty = true,
  loading = false,
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const wrapRef = useRef(null)
  const inputRef = useRef(null)

  const selected = useMemo(
    () => options.find((item) => String(getValue(item)) === String(value)),
    [options, value, getValue],
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return options
    return options.filter((item) => getLabel(item).toLowerCase().includes(needle))
  }, [options, query, getLabel])

  useEffect(() => {
    if (!value) setQuery('')
    else if (selected) setQuery(getLabel(selected))
  }, [value, selected, getLabel])

  const close = () => setOpen(false)

  useClickOutside(wrapRef, close, open)

  const pick = (item) => {
    onChange(getValue(item))
    setQuery(getLabel(item))
    close()
  }

  const clear = (event) => {
    event.stopPropagation()
    onChange('')
    setQuery('')
    inputRef.current?.focus()
  }

  return (
    <div className="combobox-field" ref={wrapRef}>
      {label && (
        <label className="combobox-label" htmlFor={id}>
          {label}
          {required && <span className="required-mark" aria-hidden="true"> *</span>}
        </label>
      )}
      <div className={`combobox${open ? ' is-open' : ''}${error ? ' has-error' : ''}`}>
        <MagnifyingGlass size={16} className="combobox-icon" aria-hidden="true" />
        <input
          ref={inputRef}
          id={id}
          type="text"
          className="combobox-input"
          value={query}
          placeholder={loading ? 'Yuklanmoqda...' : placeholder}
          disabled={disabled || loading}
          required={required && !value}
          autoComplete="off"
          role="combobox"
          aria-expanded={open}
          aria-controls={id ? `${id}-listbox` : undefined}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
            if (!event.target.value.trim() && value) onChange('')
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') close()
            if (event.key === 'Enter' && open && filtered[0]) {
              event.preventDefault()
              pick(filtered[0])
            }
          }}
        />
        {allowEmpty && value && (
          <button type="button" className="combobox-clear" onClick={clear} aria-label="Tozalash">
            <X size={14} />
          </button>
        )}
        <CaretDown size={14} className="combobox-caret" aria-hidden="true" />
        {open && !disabled && (
          <ul id={id ? `${id}-listbox` : undefined} className="combobox-list" role="listbox">
            {allowEmpty && (
              <li>
                <button type="button" className="combobox-option" onClick={() => { onChange(''); setQuery(''); close() }}>
                  {emptyLabel}
                </button>
              </li>
            )}
            {filtered.length ? filtered.map((item) => (
              <li key={getValue(item)}>
                <button
                  type="button"
                  className={`combobox-option${String(getValue(item)) === String(value) ? ' is-selected' : ''}`}
                  role="option"
                  aria-selected={String(getValue(item)) === String(value)}
                  onClick={() => pick(item)}
                >
                  {getLabel(item)}
                </button>
              </li>
            )) : (
              <li className="combobox-empty">Natija topilmadi</li>
            )}
          </ul>
        )}
      </div>
      <FieldError message={error} />
    </div>
  )
}
