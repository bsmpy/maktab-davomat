import { attendanceApi } from '@/api/attendanceApi'
import { useTranslation } from 'react-i18next'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  ChevronLeftIcon,
  ChevronRightIcon,
  ErrorState,
  SkeletonRows,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { DAY_STATE_META, formatDuration, formatLateMinutes } from '@/utils/attendance'
import { addDays, formatLongDate, formatWeekday, todayISO } from '@/utils/date'
import { cn } from '@/utils/cn'

import { PassTimeline, VisitList } from './PassTimeline'

/** One number from the day, rendered as a compact tile. */
function DayStat({
  label,
  value,
  hint,
  tone = 'neutral',
}: {
  label: string
  value: string | number
  hint?: string
  tone?: 'neutral' | 'good' | 'warn' | 'bad'
}) {
  const toneClass = {
    neutral: 'text-ink-900',
    good: 'text-emerald-600',
    warn: 'text-amber-600',
    bad: 'text-red-600',
  }[tone]
  return (
    <div className="rounded-xl border border-ink-100 bg-surface p-4">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className={cn('mt-1 text-xl font-semibold tabular-nums tracking-tight', toneClass)}>
        {value}
      </p>
      {hint ? <p className="mt-0.5 text-[11px] text-ink-400">{hint}</p> : null}
    </div>
  )
}

export function DailyView({
  childId,
  date,
  onDateChange,
}: {
  childId: string
  date: string
  onDateChange: (date: string) => void
}) {
  const { t } = useTranslation()
  const report = useAsyncData(() => attendanceApi.daily(childId, date), [childId, date])
  const isToday = date === todayISO()
  const data = report.data

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={
            <span className="flex flex-wrap items-baseline gap-x-2">
              {formatLongDate(date)}
              <span className="text-sm font-normal text-ink-500">{formatWeekday(date)}</span>
            </span>
          }
          description={
            data
              ? data.holiday
                ? data.holiday
                : data.arrived_too_late
                  ? `${data.arrived_at} da kirdi — davomatga hisoblanmadi`
                  : data.was_present
                    ? `${t('attendance.cameAt', { time: data.first_in ?? '—' })} · ${
                        data.is_inside
                          ? t('attendance.insideNow')
                          : t('attendance.leftAt', { time: data.last_out ?? '—' })
                      }`
                    : t(DAY_STATE_META[data.state]?.labelKey ?? '')
              : undefined
          }
          action={
            <div className="flex items-center gap-1">
              <Button
                variant="secondary"
                size="sm"
                aria-label={t('attendance.prevDay')}
                onClick={() => onDateChange(addDays(date, -1))}
              >
                <ChevronLeftIcon width={18} height={18} />
              </Button>
              {!isToday ? (
                <Button variant="secondary" size="sm" onClick={() => onDateChange(todayISO())}>
                  {t('common.today')}
                </Button>
              ) : null}
              <Button
                variant="secondary"
                size="sm"
                aria-label={t('attendance.nextDay')}
                disabled={isToday}
                onClick={() => onDateChange(addDays(date, 1))}
              >
                <ChevronRightIcon width={18} height={18} />
              </Button>
            </div>
          }
        />

        {report.initialLoading ? (
          <SkeletonRows count={4} />
        ) : report.error ? (
          <ErrorState error={report.error} onRetry={report.reload} />
        ) : data ? (
          <>
            {data.arrived_too_late ? (
              <div className="mx-5 mt-1 rounded-xl border border-amber-200 bg-amber-500/15 px-4 py-3 text-sm text-amber-800">
                <b>{data.arrived_at}</b> da maktabga kirdi, lekin bu vaqt davomat
                uchun juda kech — kun <b>kelmagan</b> deb hisoblandi.
              </div>
            ) : null}

            <CardBody className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <DayStat
              label={t('attendance.firstIn')}
              value={data.first_in ?? '—'}
              hint={
                data.arrived_too_late
                  ? 'Juda kech — hisoblanmadi'
                  : data.late_minutes > 0
                    ? formatLateMinutes(data.late_minutes)
                    : 'Vaqtida'
              }
              tone={
                data.arrived_too_late
                  ? 'bad'
                  : data.late_minutes > 0
                    ? 'warn'
                    : data.was_present
                      ? 'good'
                      : 'neutral'
              }
            />
            <DayStat
              label={t('attendance.lastOut')}
              value={data.is_inside ? 'Maktabda' : (data.last_out ?? '—')}
              hint={data.left_early ? 'Erta ketgan' : undefined}
              tone={data.is_inside ? 'good' : 'neutral'}
            />
            <DayStat
              label={t('attendance.inOut')}
              value={`${data.entries} / ${data.exits}`}
              hint={t('attendance.passCount')}
            />
            <DayStat
              label={t('attendance.timeInside')}
              value={formatDuration(data.inside_minutes)}
              hint={
                data.outside_minutes > 0
                  ? `Tashqarida ${formatDuration(data.outside_minutes)}`
                  : undefined
              }
            />
            </CardBody>
          </>
        ) : null}
      </Card>

      {data?.visits?.length ? (
        <Card>
          <CardHeader
            title={t('attendance.timesInside')}
            description={
              data.outside_minutes > 0
                ? `Kun davomida ${formatDuration(data.outside_minutes)} tashqarida bo'lgan`
                : 'Kun davomida maktabdan chiqmagan'
            }
          />
          <VisitList visits={data.visits} />
        </Card>
      ) : null}

      <Card>
        <CardHeader title={t('attendance.gateLog')} description={t('attendance.allPasses')} />
        {report.initialLoading ? (
          <SkeletonRows count={3} />
        ) : (
          <PassTimeline passes={data?.passes ?? []} />
        )}
      </Card>
    </div>
  )
}
