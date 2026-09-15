import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { AttendanceStatus } from '@/types/api'
import { STATUS_META } from '@/utils/attendance'
import { cn } from '@/utils/cn'

export function Badge({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset',
        'bg-ink-50 text-ink-600 ring-ink-200',
        className,
      )}
    >
      {children}
    </span>
  )
}

export function StatusBadge({
  status,
  lateMinutes = 0,
  className,
}: {
  status: AttendanceStatus | null
  lateMinutes?: number
  className?: string
}) {
  const { t } = useTranslation()
  if (!status) {
    return (
      <Badge className={cn('bg-ink-50 text-ink-400 ring-ink-200', className)}>
        {t('status.unmarked')}
      </Badge>
    )
  }
  const meta = STATUS_META[status]
  return (
    <Badge className={cn(meta.chip, className)}>
      <span className={cn('h-1.5 w-1.5 rounded-full', meta.dot)} />
      {t(meta.labelKey)}
      {status === 'LATE' && lateMinutes > 0 ? (
        <span className="font-normal opacity-80">
          · {lateMinutes} {t('common.minutesShort')}
        </span>
      ) : null}
    </Badge>
  )
}
