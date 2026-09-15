import { attendanceApi } from '@/api/attendanceApi'
import { useTranslation } from 'react-i18next'
import { AttendanceBarChart, type BarPoint } from '@/components/charts/AttendanceBarChart'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  ChevronLeftIcon,
  ChevronRightIcon,
  ErrorState,
  Skeleton,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { DAY_STATE_META, formatDurationShort } from '@/utils/attendance'
import { addDays, formatShortDate, todayISO } from '@/utils/date'
import { cn } from '@/utils/cn'

import { SummaryCards } from '../dashboard/SummaryCards'

export function WeeklyView({
  childId,
  date,
  onDateChange,
}: {
  childId: string
  date: string
  onDateChange: (date: string) => void
}) {
  const { t } = useTranslation()
  const report = useAsyncData(() => attendanceApi.weekly(childId, date), [childId, date])

  if (report.initialLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-72 w-full rounded-2xl" />
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
  const days = data.days ?? []
  // Only school days belong on the chart; a Sunday is not a zero.
  const chart: BarPoint[] = days
    .filter((day) => day.is_school_day)
    .map((day) => ({
      label: day.weekday_short,
      // Hours in the building, which is what the bar actually encodes here.
      rate: Math.round((day.inside_minutes / 60) * 10) / 10,
      attended: day.entries,
      total: day.exits,
    }))

  return (
    <div className="space-y-4">
      <SummaryCards summary={data.summary} />

      <Card>
        <CardHeader
          title={t('attendance.byWeek')}
          description={`${formatShortDate(data.start_date)} — ${formatShortDate(data.end_date)}`}
          action={
            <div className="flex items-center gap-1">
              <Button
                variant="secondary"
                size="sm"
                aria-label={t('attendance.prevWeek')}
                onClick={() => onDateChange(addDays(date, -7))}
              >
                <ChevronLeftIcon width={18} height={18} />
              </Button>
              <Button variant="secondary" size="sm" onClick={() => onDateChange(todayISO())}>
                {t('attendance.thisWeek')}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                aria-label={t('attendance.nextWeek')}
                onClick={() => onDateChange(addDays(date, 7))}
              >
                <ChevronRightIcon width={18} height={18} />
              </Button>
            </div>
          }
        />

        {chart.length > 0 ? (
          <CardBody className="pb-2">
            <AttendanceBarChart data={chart} unit="soat" />
          </CardBody>
        ) : null}

        <ul className="divide-y divide-ink-100 border-t border-ink-100">
          {days.map((day) => {
            const meta = DAY_STATE_META[day.state] ?? DAY_STATE_META.NO_DATA
            return (
              <li key={day.date} className="flex items-center gap-4 px-5 py-3.5">
                <span className={cn('h-2 w-2 shrink-0 rounded-full', meta.dot)} />
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] font-medium text-ink-800">{day.weekday_name}</p>
                  <p className="text-xs text-ink-500">{formatShortDate(day.date)}</p>
                </div>
                {day.was_present ? (
                  <>
                    <span className="hidden text-sm tabular-nums text-ink-600 sm:inline">
                      {day.first_in ?? '—'}
                      <span className="mx-1.5 text-ink-300">→</span>
                      {day.is_inside ? 'hozir' : (day.last_out ?? '—')}
                    </span>
                    <span className="w-20 text-right text-sm font-semibold tabular-nums text-ink-800">
                      {formatDurationShort(day.inside_minutes)}
                    </span>
                  </>
                ) : day.arrived_too_late ? (
                  // Shown, but not counted: the arrival was past the cutoff.
                  <span className="text-sm text-amber-700">
                    {day.arrived_at} da kirdi · hisoblanmadi
                  </span>
                ) : (
                  <span className="text-sm text-ink-400">{t(meta.labelKey)}</span>
                )}
              </li>
            )
          })}
        </ul>
      </Card>
    </div>
  )
}
