import { useTranslation } from 'react-i18next'

import type { IntegrationStatus } from '@/types/api'
import { cn } from '@/utils/cn'

const META: Record<IntegrationStatus, { labelKey: string; chip: string; dot: string }> = {
  OK: {
    labelKey: 'settings.working',
    chip: 'bg-emerald-500/15 text-emerald-700 ring-emerald-600/20',
    dot: 'bg-emerald-500',
  },
  ERROR: {
    labelKey: 'common.error',
    chip: 'bg-red-500/15 text-red-700 ring-red-600/20',
    dot: 'bg-red-500',
  },
  DISABLED: {
    labelKey: 'settings.off',
    chip: 'bg-ink-100 text-ink-500 ring-ink-200',
    dot: 'bg-ink-400',
  },
  UNKNOWN: {
    labelKey: 'settings.unchecked',
    chip: 'bg-amber-500/15 text-amber-700 ring-amber-600/20',
    dot: 'bg-amber-500',
  },
}

export function StatusPill({
  status,
  className,
}: {
  status: IntegrationStatus
  className?: string
}) {
  const { t } = useTranslation()
  const meta = META[status] ?? META.UNKNOWN
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset',
        meta.chip,
        className,
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', meta.dot)} />
      {t(meta.labelKey)}
    </span>
  )
}
