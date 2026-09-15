import { useEffect, useState } from 'react'
import { BrowserRouter } from 'react-router-dom'

import { clockApi } from '@/api/clockApi'
import { Toaster } from '@/components/ui'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { AppRoutes } from '@/routes/AppRoutes'
import { useAuthStore } from '@/store/authStore'
import { setClockOffset } from '@/utils/clock'

/**
 * Root shell: restores the session once, then hands off to the router.
 * All real screens live under `src/pages` — nothing is implemented here.
 */
export function App() {
  const bootstrap = useAuthStore((state) => state.bootstrap)
  // Nothing renders until the app knows which day the server thinks it is;
  // normally that is simply today, and the request takes a few milliseconds.
  const [clockReady, setClockReady] = useState(false)

  useEffect(() => {
    void clockApi
      .read()
      .then((clock) => setClockOffset(clock.offset_seconds))
      // A clock we cannot read is not worth blocking the cabinet for: fall
      // back to the browser's own time.
      .catch(() => setClockOffset(0))
      .finally(() => setClockReady(true))
  }, [])

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  if (!clockReady) return null

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
      <Toaster />
    </ErrorBoundary>
  )
}
