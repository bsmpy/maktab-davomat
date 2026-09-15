import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, toApiError } from '@/api/errors'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: ApiError | null
  /** True only for the very first load — used to pick skeleton vs. spinner. */
  initialLoading: boolean
  reload: () => void
  setData: (value: T) => void
}

/**
 * Small data-fetching primitive: loading / error / retry in one place, so
 * every page gets the same skeleton → error → empty → content lifecycle
 * without repeating the plumbing.
 *
 * `deps` behaves like a `useEffect` dependency list.
 */
export function useAsyncData<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: { enabled?: boolean } = {},
): AsyncState<T> {
  const enabled = options.enabled ?? true
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<ApiError | null>(null)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [tick, setTick] = useState(0)

  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)

    fetcherRef
      .current()
      .then((result) => {
        if (cancelled) return
        setData(result)
        setHasLoaded(true)
      })
      .catch((caught) => {
        if (cancelled) return
        setError(toApiError(caught))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled])

  const reload = useCallback(() => setTick((value) => value + 1), [])

  return {
    data,
    loading,
    error,
    initialLoading: loading && !hasLoaded,
    reload,
    setData,
  }
}
