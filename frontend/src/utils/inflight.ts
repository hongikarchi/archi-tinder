/**
 * Share one in-flight request per key (#493). Concurrent callers for the same
 * key get the same promise; once it settles the next call fetches again, so
 * nothing is cached past the request. invalidate() makes the next call start a
 * fresh request (used before a write that changes the answer).
 */
export function createInflight<V>() {
  const pending = new Map<string, Promise<V>>()
  return {
    run(key: string, fetcher: () => Promise<V>): Promise<V> {
      const existing = pending.get(key)
      if (existing) return existing
      const p = fetcher().finally(() => {
        if (pending.get(key) === p) pending.delete(key)
      })
      pending.set(key, p)
      return p
    },
    invalidate(key?: string) {
      if (key === undefined) pending.clear()
      else pending.delete(key)
    },
  }
}
