import { useCallback, useEffect, useState } from 'react'

export default function useDebounceSearch(delay = 300) {
  const [search, setSearch] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setSearchTerm(search.trim()), delay)
    return () => clearTimeout(timer)
  }, [search, delay])

  const submitSearch = useCallback((event) => {
    event?.preventDefault?.()
    setSearchTerm(search.trim())
  }, [search])

  const clearSearch = useCallback(() => {
    setSearch('')
    setSearchTerm('')
  }, [])

  return { search, setSearch, searchTerm, submitSearch, clearSearch }
}
