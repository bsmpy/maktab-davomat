import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { ProgressBar } from '@/components/ui'
import type { AttendanceSummary } from '@/types/api'
import {
  formatDuration,
  formatRate,
  RATE_TONE_CLASS,
  rateTone,
} from '@/utils/attendance'
import { cn } from '@/utils/cn'

export function StatCard({
  label,
  value,
  hint,
  tone = 'neutral',
  icon,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'info'
  icon?: ReactNode
}) {
  const toneClass = {
    neutral: 'text-ink-900',
    good: 'text-emerald-600',
    warn: 'text-amber-600',
    bad: 'text-red-600',
    info: 'text-brand-600',
  }[tone]

  return (
    <div className="card card-hover p-5">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-ink-500">{label}</p>
        {icon ? <span className="text-ink-300">{icon}</span> : null}
      </div>
      <p className={cn('mt-2 text-2xl font-semibold tabular-nums tracking-tight', toneClass)}>
        {value}
      </p>
      {hint ? <div className="mt-1 text-xs text-ink-500">{hint}</div> : null}
    </div>
  )
}

/** The numbers a parent actually looks for: days at school, and time inside. */
export function SummaryCards({ summary }: { summary: AttendanceSummary }) {
  const { t } = useTranslation()
  return (
    <div className="grid gap-3 grid-cols-2 sm:gap-4 xl:grid-cols-4">
      <div className="card card-hover p-5 sm:col-span-2 xl:col-span-1">
        <p className="text-sm font-medium text-ink-500">{t('attendance.rate')}</p>
        <p
          className={cn(
            'mt-2 text-3xl font-semibold tabular-nums tracking-tight',
            RATE_TONE_CLASS[rateTone(summary.rate)],
          )}
        >
          {formatRate(summary.rate)}
        </p>
        <ProgressBar value={summary.rate} className="mt-3" />
        <p className="mt-2 text-xs text-ink-500">
          {summary.days_present} / {summary.school_days} kun maktabda bo'lgan
        </p>
      </div>

      <StatCard
        label={t('attendance.inSchool')}
        value={formatDuration(summary.inside_minutes)}
        tone="info"
        hint={
          summary.days_present > 0
            ? `Kuniga o'rtacha ${formatDuration(summary.avg_inside_minutes)}`
            : undefined
        }
      />
      <StatCard
        label={t('attendance.daysAbsent')}
        value={summary.days_absent}
        tone="bad"
        hint={`${summary.entries} kirish · ${summary.exits} chiqish`}
      />
      <StatCard
        label={t('attendance.daysLate')}
        value={summary.days_late}
        tone="warn"
        hint={summary.late_minutes > 0 ? `Jami ${summary.late_minutes} daqiqa` : undefined}
      />
    </div>
  )
}
