import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAuth } from '@/auth/permissions'
import { Card, EmptyState, LockIcon, Spinner } from '@/components/ui'
import { useAuthStore } from '@/store/authStore'
import type { Permission, Role } from '@/types/api'

function Loading() {
  return (
    <div className="grid min-h-dvh place-items-center text-ink-400">
      <Spinner className="h-7 w-7" />
    </div>
  )
}

/** Gate for the signed-in area. Server-side permissions are the real guard. */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const status = useAuthStore((state) => state.status)
  const location = useLocation()

  if (status === 'unknown' || status === 'authenticating') return <Loading />

  if (status === 'anonymous') {
    return <Navigate to="/kirish" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}

/** Inverse gate: keeps signed-in users off the login/registration screens. */
export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const status = useAuthStore((state) => state.status)

  if (status === 'unknown' || status === 'authenticating') return <Loading />

  if (status === 'authenticated') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

/**
 * A page the active role may not open.
 *
 * Not an error screen: a role that cannot see a section has not gone wrong,
 * and switching roles is how you get to it. Saying which role you are standing
 * in is the useful part — somebody who switched to CURATOR and then clicked an
 * old bookmark needs to be told that, not shown a lock and left guessing.
 */
export function NoAccess({ role }: { role?: Role | null }) {
  const { t } = useTranslation()
  return (
    <Card>
      <EmptyState
        icon={<LockIcon width={28} height={28} />}
        title={t('access.denied')}
        description={t('access.deniedHint', { role: role ?? '—' })}
      />
    </Card>
  )
}

/**
 * Wraps a route in the permission it needs.
 *
 * One place decides this for every page, so a section is never gated in two
 * ways that can drift apart. The guard re-evaluates when the active role
 * changes, which is what makes switching roles redraw the routing without a
 * reload — and what sends somebody standing on a page their new role cannot
 * open back to their own home rather than leaving them on a dead screen.
 */
export function RequirePermission({
  children,
  all,
  any,
  roles,
}: {
  children: ReactNode
  /** Every one of these is required. */
  all?: Permission[]
  /** Any one of these is enough. */
  any?: Permission[]
  /** Or gate on the active role itself, for a role's own cabinet. */
  roles?: Role[]
}) {
  const { activeRole, can, canAny, isActing } = useAuth()

  const allowed =
    (!all || can(...all)) &&
    (!any || canAny(...any)) &&
    (!roles || isActing(...roles))

  if (!allowed) return <NoAccess role={activeRole} />

  return <>{children}</>
}
