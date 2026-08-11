import { useEffect } from 'react'

export default function useClickOutside(ref, onClose, active) {
  useEffect(() => {
    if (!active) return undefined
    const handler = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [ref, onClose, active])
}
