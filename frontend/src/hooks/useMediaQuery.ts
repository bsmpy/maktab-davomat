import { useCallback, useSyncExternalStore } from 'react'

/**
 * Subscribes to a media query without a state-syncing effect: React reads the
 * current value during render and re-subscribes when the query changes.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    [query],
  )

  const getSnapshot = useCallback(() => window.matchMedia(query).matches, [query])
  // Server/prerender has no viewport — assume the mobile-first layout.
  const getServerSnapshot = useCallback(() => false, [])

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}

export const useIsDesktop = () => useMediaQuery('(min-width: 1024px)')
