import { useMemo } from 'react'

import { useAuthStore } from '@/store/authStore'
import type { Permission, Role, SessionScope, User } from '@/types/api'

/**
 * The cabinet's single source of "may I?".
 *
 * Nothing in the app compares roles by hand any more. A page asks for the
 * permission it needs — `can('students.manage')` — and the answer comes from
 * the list the server sent for the **active** role. That matters twice over:
 * roles are not summed, so somebody who holds ADMIN but is working as a
 * TEACHER gets a teacher's answers; and adding a role is a server change, not
 * a sweep through components.
 *
 * None of this is security. Every one of these questions is asked again on the
 * server, on the endpoint behind the button. This decides what to *draw*.
 */

const EMPTY_SCOPE: SessionScope = {
  teacher_subjects: [],
  teacher_groups: [],
  curator_groups: [],
  children: [],
}

/** Most privileged first — the order roles are listed in. */
export const ROLE_ORDER: Role[] = [
  'DEVELOPER',
  'SUPER_ADMIN',
  'MODERATOR',
  'ADMIN',
  'TEACHER',
  'CURATOR',
  'STAFF',
  'OTA-ONA',
]

export function sortRoles(roles: Role[] | undefined): Role[] {
  return [...(roles ?? [])].sort(
    (a, b) => ROLE_ORDER.indexOf(a) - ROLE_ORDER.indexOf(b),
  )
}

/** Does this user's active role carry every one of these permissions? */
export function userCan(
  user: Pick<User, 'permissions'> | null | undefined,
  ...permissions: Permission[]
): boolean {
  if (!user?.permissions) return false
  return permissions.every((permission) => user.permissions.includes(permission))
}

/** Does the active role carry *any* of these? Use for "show the section" checks. */
export function userCanAny(
  user: Pick<User, 'permissions'> | null | undefined,
  ...permissions: Permission[]
): boolean {
  if (!user?.permissions) return false
  return permissions.some((permission) => user.permissions.includes(permission))
}

/** Is this role granted to the account — whether or not it is the active one? */
export function userHasRole(
  user: Pick<User, 'roles'> | null | undefined,
  ...roles: Role[]
): boolean {
  if (!user?.roles) return false
  return roles.some((role) => user.roles.includes(role))
}

export interface AuthContext {
  user: User | null
  /** True once the session is known and signed in. */
  isAuthenticated: boolean
  /** The role currently being worked through. */
  activeRole: Role | null
  /** Every role granted, most privileged first. */
  roles: Role[]
  /** True when there is more than one role to switch between. */
  canSwitchRole: boolean
  scope: SessionScope
  /** Every permission the active role carries. */
  permissions: Permission[]
  can: (...permissions: Permission[]) => boolean
  canAny: (...permissions: Permission[]) => boolean
  /** Role membership — not "is working as", which is `activeRole`. */
  hasRole: (...roles: Role[]) => boolean
  /** "Am I working as this right now?" */
  isActing: (...roles: Role[]) => boolean
}

/**
 * Who is signed in and what they may do, in one hook.
 *
 * Subscribes to the user object only, so a component re-renders when the role
 * is switched (which replaces it) and not when anything else in the store moves.
 */
export function useAuth(): AuthContext {
  const user = useAuthStore((state) => state.user) as User | null

  return useMemo(() => {
    const roles = sortRoles(user?.roles)
    const permissions = user?.permissions ?? []
    const activeRole = (user?.active_role ?? user?.role ?? null) as Role | null

    return {
      user,
      isAuthenticated: Boolean(user),
      activeRole,
      roles,
      canSwitchRole: roles.length > 1,
      scope: user?.scope ?? EMPTY_SCOPE,
      permissions,
      can: (...wanted: Permission[]) => userCan(user, ...wanted),
      canAny: (...wanted: Permission[]) => userCanAny(user, ...wanted),
      hasRole: (...wanted: Role[]) => userHasRole(user, ...wanted),
      isActing: (...wanted: Role[]) =>
        Boolean(activeRole && wanted.includes(activeRole)),
    }
  }, [user])
}

/**
 * Just the permission half, for components that do not need the rest.
 *
 * ```tsx
 * const { can } = usePermissions()
 * {can('students.manage') ? <Button>+ O'quvchi</Button> : null}
 * ```
 */
export function usePermissions(): Pick<
  AuthContext,
  'can' | 'canAny' | 'hasRole' | 'isActing' | 'permissions' | 'activeRole'
> {
  const { can, canAny, hasRole, isActing, permissions, activeRole } = useAuth()
  return { can, canAny, hasRole, isActing, permissions, activeRole }
}
