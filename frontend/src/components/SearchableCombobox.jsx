import { useEffect, useMemo, useRef, useState } from 'react'
import { CaretDown, MagnifyingGlass, SpinnerGap, X } from '@phosphor-icons/react'
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

function matchesNeedle(text, needle, compactNeedle) {
  const plain = String(text || '').toLowerCase()
  if (!plain) return false
  if (needle && plain.includes(needle)) return true
  if (compactNeedle && plain.replace(/\s+/g, '').includes(compactNeedle)) return true
  return false
}

export default function SearchableCombobox({
  id,
  label,
  value,
  onChange,
  options = [],
  selectedOption = null,
  getLabel = (item) => item.label ?? item.name ?? String(item),
  getSearchText,
  getValue = (item) => item.value ?? item.id,
  onSearch,
  minSearchLength = 2,
  searchDebounceMs = 400,
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
  const [asyncOptions, setAsyncOptions] = useState(null)
  const [searching, setSearching] = useState(false)
  const wrapRef = useRef(null)
  const inputRef = useRef(null)
  const debounceRef = useRef(null)

  const selected = useMemo(() => {
    if (selectedOption && String(getValue(selectedOption)) === String(value)) return selectedOption
    return options.find((item) => String(getValue(item)) === String(value))
  }, [options, selectedOption, value, getValue])

  const filtered = useMemo(() => {
    const source = onSearch && asyncOptions !== null ? asyncOptions : options
    const needle = query.trim().toLowerCase()
    const compactNeedle = needle.replace(/\s+/g, '')
    if (!needle || (onSearch && asyncOptions !== null)) return source
    const searchFn = getSearchText || getLabel
    return source.filter((item) => matchesNeedle(searchFn(item), needle, compactNeedle))
  }, [options, asyncOptions, query, getLabel, getSearchText, onSearch])

  const displayOptions = useMemo(() => {
    if (!selected || !value) return filtered
    if (filtered.some((item) => String(getValue(item)) === String(value))) return filtered
    return [selected, ...filtered]
  }, [filtered, selected, value, getValue])

  useEffect(() => {
    if (!onSearch || !open) return undefined
    const q = query.trim()
    if (q.length < minSearchLength) {
      setAsyncOptions(null)
      setSearching(false)
      return undefined
    }
    window.clearTimeout(debounceRef.current)
    setSearching(true)
    debounceRef.current = window.setTimeout(async () => {
      try {
        const results = await onSearch(q)
        setAsyncOptions(Array.isArray(results) ? results : [])
      } catch {
        setAsyncOptions([])
      } finally {
        setSearching(false)
      }
    }, searchDebounceMs)
    return () => window.clearTimeout(debounceRef.current)
  }, [query, onSearch, open, minSearchLength, searchDebounceMs])

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
    setAsyncOptions(null)
    inputRef.current?.focus()
  }

  const inputPlaceholder = loading || searching ? 'Qidirilmoqda...' : placeholder

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
          placeholder={inputPlaceholder}
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
            if (event.key === 'Enter' && open && displayOptions[0]) {
              event.preventDefault()
              pick(displayOptions[0])
            }
          }}
        />
        {searching && <SpinnerGap size={14} className="combobox-icon combobox-spinner spin" aria-hidden="true" />}
        {allowEmpty && value && !searching && (
          <button type="button" className="combobox-clear" onClick={clear} aria-label="Tozalash">
            <X size={14} />
          </button>
        )}
        <CaretDown size={14} className="combobox-caret" aria-hidden="true" />
        {open && !disabled && (
          <ul id={id ? `${id}-listbox` : undefined} className="combobox-list" role="listbox">
            {allowEmpty && (
              <li>
                <button type="button" className="combobox-option" onClick={() => { onChange(''); setQuery(''); setAsyncOptions(null); close() }}>
                  {emptyLabel}
                </button>
              </li>
            )}
            {onSearch && query.trim().length > 0 && query.trim().length < minSearchLength && (
              <li className="combobox-empty">Kamida {minSearchLength} ta belgi kiriting</li>
            )}
            {displayOptions.length ? displayOptions.map((item) => (
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
              !searching && !(onSearch && query.trim().length > 0 && query.trim().length < minSearchLength) && (
                <li className="combobox-empty">{onSearch && !query.trim() ? 'F.I.Sh, INN/STIR, JSHSHIR, passport, kompaniya yoki email kiriting' : 'Natija topilmadi'}</li>
              )
            )}
          </ul>
        )}
      </div>
      <FieldError message={error} />
    </div>
  )
}
