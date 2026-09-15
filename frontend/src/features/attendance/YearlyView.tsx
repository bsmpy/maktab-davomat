import { attendanceApi } from '@/api/attendanceApi'
import { useTranslation } from 'react-i18next'
import { AttendanceLineChart } from '@/components/charts/AttendanceLineChart'
import type { BarPoint } from '@/components/charts/AttendanceBarChart'
import {
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  ProgressBar,
  Skeleton,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { formatDuration, formatRate, RATE_TONE_CLASS, rateTone } from '@/utils/attendance'
import { cn } from '@/utils/cn'

import { StatCard } from '../dashboard/SummaryCards'

export function YearlyView({ childId }: { childId: string }) {
  const { t } = useTranslation()
  const report = useAsyncData(() => attendanceApi.yearly(childId), [childId])

  if (report.initialLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-80 w-full rounded-2xl" />
      </div>
    )
  }

  if (report.error) {
    return (
      <Card>
        <ErrorState error={report.error} onRetry={report.reload} />
      </Card>
    )
  }

  const data = report.data!
  const months = (data.months ?? []).filter((month) => month.summary.school_days > 0)
  const chart: BarPoint[] = months.map((month) => ({
    label: month.month_name.slice(0, 3),
    rate: month.summary.rate,
    attended: month.summary.entries,
    total: month.summary.exits,
  }))

  if (months.length === 0) {
    return (
      <Card>
        <EmptyState
          title={t('attendance.noYearData')}
          description={t('attendance.yearDataHint')}
        />
      </Card>
    )
  }

  const summary = data.summary

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <div className="card card-hover p-5 sm:col-span-2 xl:col-span-1">
          <p className="text-sm font-medium text-ink-500">{t('attendance.yearly')}</p>
          <p
            className={cn(
              'mt-2 text-3xl font-semibold tabular-nums tracking-tight',
              RATE_TONE_CLASS[rateTone(summary.rate)],
            )}
          >
            {formatRate(summary.rate)}
          </p>
          <ProgressBar value={summary.rate} className="mt-3" />
          <p className="mt-2 text-xs text-ink-500">{data.academic_year} o'quv yili</p>
        </div>
        <StatCard label={t('attendance.schoolDays')} value={summary.school_days} />
        <StatCard
          label={t('attendance.wasInside')}
          value={summary.days_present}
          tone="good"
          hint={`Jami ${formatDuration(summary.inside_minutes)}`}
        />
        <StatCard label={t('attendance.wasAbsent')} value={summary.days_absent} tone="bad" />
        <StatCard
          label={t('attendance.wasLate')}
          value={summary.days_late}
          tone="warn"
          hint={summary.late_minutes > 0 ? `${summary.late_minutes} daqiqa` : undefined}
        />
      </div>

      <Card>
        <CardHeader title={t('attendance.byMonth')} description={`${data.academic_year} o'quv yili`} />
        <CardBody className="pb-2">
          <AttendanceLineChart data={chart} />
        </CardBody>

        <ul className="divide-y divide-ink-100 border-t border-ink-100">
          {months.map((month) => (
            <li key={`${month.year}-${month.month}`} className="flex items-center gap-4 px-5 py-3.5">
              <span className="w-24 shrink-0 text-[15px] font-medium text-ink-800">
                {month.month_name}
              </span>
              <ProgressBar value={month.summary.rate} className="flex-1" />
              <span className="w-24 shrink-0 text-right text-xs tabular-nums text-ink-500">
                {month.summary.days_present}/{month.summary.school_days}
              </span>
              <span
                className={cn(
                  'w-14 shrink-0 text-right text-sm font-semibold tabular-nums',
                  RATE_TONE_CLASS[rateTone(month.summary.rate)],
                )}
              >
                {formatRate(month.summary.rate)}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
