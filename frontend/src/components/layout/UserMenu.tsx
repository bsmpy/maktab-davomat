import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { toApiError } from '@/api/errors'
import { useAuth } from '@/auth/permissions'
import {
  Avatar,
  CheckIcon,
  ChevronDownIcon,
  LogoutIcon,
  Menu,
  MenuItem,
  Spinner,
  UserIcon,
} from '@/components/ui'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import { useTeacherStore } from '@/store/teacherStore'
import { toast } from '@/store/toastStore'
import type { Role } from '@/types/api'
import { cn } from '@/utils/cn'

/**
 * The account button: photo, short name, and the three things that belong to
 * the person rather than to a page — which of their roles they are working
 * through, their profile, and signing out.
 *
 * The role list is the interesting part. One person is often several things at
 * once — a teacher who also curates 7-A and is on the payroll as staff — and
 * picking one here changes the whole cabinet: the rail, the home page, the
 * routes, the buttons and what the API answers. No sign-out, no reload, and a
 * refresh comes back in the same role, because the choice is stored on the
 * account rather than in this tab.
 */
export function UserMenu() {
  const { user, activeRole, roles, canSwitchRole } = useAuth()
  const logout = useAuthStore((state) => state.logout)
  const switchRole = useAuthStore((state) => state.switchRole)
  const reloadChildren = useChildStore((state) => state.load)
  const loadTeacher = useTeacherStore((state) => state.load)
  const teacher = useTeacherStore((state) => state.profile)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [switching, setSwitching] = useState<Role | null>(null)

  if (!user) return null

  // The same full name the profile and every list shows. It was initials here
  // before, which made one screen disagree with the next about who you are.
  const label = teacher?.full_name ?? user.full_name

  async function choose(role: Role, close: () => void) {
    if (role === activeRole) return close()
    setSwitching(role)
    try {
      await switchRole(role)
      // The two caches that are *about* the role: the child list a parent's
      // cabinet is built on, and the register row the navbar photo comes from.
      // Everything else re-renders from the user object itself.
      await Promise.all([reloadChildren({ force: true }), loadTeacher({ force: true })])
      toast.success(t('roles.switched', { role }))
      close()
      // Back to the landing page: the one being looked at may not exist for
      // the new role, and its own home is where that role starts.
      navigate('/')
    } catch (error) {
      toast.error(t('roles.switchFailed'), toApiError(error).message)
    } finally {
      setSwitching(null)
    }
  }

  return (
    <Menu
      label={t('common.account')}
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={id}
          onClick={toggle}
          className="flex items-center gap-2.5 rounded-xl px-1.5 py-1.5 transition hover:bg-ink-100 sm:px-2"
        >
          <Avatar
            name={teacher?.full_name ?? user.full_name}
            src={teacher?.photo ?? undefined}
            size="sm"
          />
          <span className="hidden max-w-[200px] truncate text-sm font-semibold text-ink-800 lg:block xl:max-w-[280px]">
            {label}
          </span>
          <ChevronDownIcon
            width={16}
            height={16}
            className={cn('hidden text-ink-400 transition-transform sm:block', open && 'rotate-180')}
          />
        </button>
      )}
    >
      {({ close }) => (
        <>
          <div role="presentation" className="border-b border-ink-200 px-3 pb-2 pt-1.5">
            <p className="truncate text-sm font-medium text-ink-800">
              {teacher?.full_name ?? user.full_name}
            </p>
            <p className="truncate text-xs text-ink-500">@{user.username}</p>
            {/* The role is named, not translated: TEACHER reads the same in
                every language, and that is what the school calls it. */}
            <p className="mt-1 truncate text-xs font-semibold text-brand-600">
              {activeRole}
            </p>
          </div>

          {canSwitchRole ? (
            <div role="group" aria-label={t('roles.switchTo')} className="border-b border-ink-200 py-1">
              <p className="px-3 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-ink-400">
                {t('roles.switchTo')}
              </p>
              {roles.map((role) => {
                const isActive = role === activeRole
                return (
                  <button
                    key={role}
                    type="button"
                    role="menuitemradio"
                    aria-checked={isActive}
                    disabled={switching !== null}
                    onClick={() => void choose(role, close)}
                    className={cn(
                      'flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition',
                      isActive
                        ? 'font-semibold text-brand-700'
                        : 'text-ink-700 hover:bg-ink-50',
                      switching !== null && 'opacity-70',
                    )}
                  >
                    <span className="grid h-4 w-4 shrink-0 place-items-center">
                      {switching === role ? (
                        <Spinner className="h-3.5 w-3.5" />
                      ) : isActive ? (
                        <CheckIcon width={16} height={16} />
                      ) : null}
                    </span>
                    {role}
                  </button>
                )
              })}
            </div>
          ) : null}

          <MenuItem
            icon={<UserIcon width={18} height={18} />}
            onSelect={() => {
              close()
              navigate('/profil')
            }}
          >
            {t('nav.profile')}
          </MenuItem>
          <MenuItem
            tone="danger"
            icon={<LogoutIcon width={18} height={18} />}
            onSelect={() => {
              close()
              void logout()
            }}
          >
            {t('common.logout')}
          </MenuItem>
        </>
      )}
    </Menu>
  )
}
