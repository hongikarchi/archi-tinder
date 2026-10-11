import { useEffect, useState } from 'react'

/**
 * useNow — current time as a Date, refreshed every `intervalMs` (default 60s)
 * so a page left open flips D-day / closed state at the right moment.
 */
export function useNow(intervalMs = 60_000) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])
  return now
}
