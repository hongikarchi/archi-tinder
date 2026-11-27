/**
 * In-flight request registry (#493). Each pending request is stored with a
 * `meta` value captured when it STARTED (e.g. the block-seq token), so a caller
 * that joins later can judge staleness by the request's start, not its own.
 *
 * start() always sends a fresh request and publishes it; join() reuses a pending
 * one for the key or starts one. Nothing is kept after a request settles.
 * invalidate() makes the next join() start fresh.
 */
export type InflightEntry<V, M> = { promise: Promise<V>, meta: M }

export function createInflight<V, M = undefined>() {
  const pending = new Map<string, InflightEntry<V, M>>()

  function start(key: string, fetcher: () => Promise<V>, meta: M): InflightEntry<V, M> {
    const promise = fetcher().finally(() => {
      if (pending.get(key)?.promise === promise) pending.delete(key)
    })
    const entry = { promise, meta }
    pending.set(key, entry)
    return entry
  }

  return {
    start,
    join(key: string, fetcher: () => Promise<V>, meta: M): InflightEntry<V, M> {
      return pending.get(key) ?? start(key, fetcher, meta)
    },
    invalidate(key?: string) {
      if (key === undefined) pending.clear()
      else pending.delete(key)
    },
  }
}
