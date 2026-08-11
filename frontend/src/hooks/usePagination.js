import { useCallback, useState } from 'react'

export default function usePagination({ pageSize = 25, initialPage = 1 } = {}) {
  const [page, setPage] = useState(initialPage)
  const [totalCount, setTotalCount] = useState(0)

  const resetPage = useCallback(() => setPage(1), [])

  return {
    page,
    pageSize,
    totalCount,
    setPage,
    setTotalCount,
    resetPage,
  }
}
