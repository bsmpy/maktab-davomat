import { useTranslation } from 'react-i18next'

import { Badge } from '@/components/ui'
import type { Choice, Role } from '@/types/api'
import { cn } from '@/utils/cn'

import { ROLE_CHIP } from './roleChips'

/**
 * One role, shown the way roles are always shown: the code itself.
 *
 * Role names are not translated — TEACHER reads as TEACHER on a Russian screen
 * as much as an Uzbek one — so there is no label lookup here on purpose.
 */
export function RoleBadge({ role, className }: { role: Role | string; className?: string }) {
  return (
    <Badge className={cn('shrink-0 ring-1 ring-inset', ROLE_CHIP[role] ?? ROLE_CHIP.STAFF, className)}>
      {role}
    </Badge>
  )
}

/** Every role a person holds, most privileged first. */
export function RoleBadges({ roles }: { roles: (Role | string)[] | undefined }) {
  if (!roles?.length) return null
  return (
    <span className="flex flex-wrap gap-1">
      {roles.map((role) => (
        <RoleBadge key={role} role={role} />
      ))}
    </span>
  )
}

/**
 * The role picker: checkboxes, because one person is often several things.
 *
 * A teacher who also curates 7-A and is on the payroll as staff ticks three
 * boxes and gets one account. The list offered is whatever the server said
 * this operator may hand out, so a box that would be refused is never drawn.
 */
export function RolePicker({
  available,
  value,
  onChange,
  label,
  hint,
  disabled,
  locked = [],
}: {
  available: Choice[]
  value: string[]
  onChange: (roles: string[]) => void
  label?: string
  hint?: string
  disabled?: boolean
  /** Roles that stay ticked and cannot be cleared — your own highest one. */
  locked?: string[]
}) {
  const { t } = useTranslation()

  function toggle(role: string) {
    if (locked.includes(role)) return
    onChange(value.includes(role) ? value.filter((row) => row !== role) : [...value, role])
  }

  return (
    <fieldset disabled={disabled} className="space-y-2">
      <legend className="mb-1.5 block text-sm font-medium text-ink-700">
        {label ?? t('users.roles')}
      </legend>
      <div className="flex flex-wrap gap-2">
        {available.map((role) => {
          const isLocked = locked.includes(role.value)
          const checked = isLocked || value.includes(role.value)
          return (
            <label
              key={role.value}
              title={isLocked ? t('users.lockedRole') : undefined}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition',
                checked
                  ? 'border-brand-300 bg-brand-50 text-brand-700'
                  : 'border-ink-200 text-ink-600 hover:bg-ink-50',
                (disabled || isLocked) && 'cursor-not-allowed opacity-60',
              )}
            >
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
                checked={checked}
                disabled={isLocked}
                onChange={() => toggle(role.value)}
              />
              {role.value}
            </label>
          )
        })}
      </div>
      <p className="text-xs text-ink-400">{hint ?? t('users.rolesHint')}</p>
    </fieldset>
  )
}
