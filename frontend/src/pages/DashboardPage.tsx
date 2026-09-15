import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { childrenApi } from '@/api/childrenApi'
import { PassTimeline, VisitList } from '@/features/attendance/PassTimeline'
import { SummaryCards } from '@/features/dashboard/SummaryCards'
import {
  Avatar,
  Badge,
  Card,
  CardBody,
  CardHeader,
  ErrorState,
  Skeleton,
  SkeletonCards,
  SkeletonRows,
} from '@/components/ui'
import { NoChildState } from '@/components/layout/NoChildState'
import { useAsyncData } from '@/hooks'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import {
  DAY_STATE_META,
  formatDuration,
  formatDurationShort,
  formatLateMinutes,
} from '@/utils/attendance'
import { cn } from '@/utils/cn'
import { formatLongDate, formatShortDate, monthName } from '@/utils/date'

export function DashboardPage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const activeChildId = useChildStore((state) => state.activeChildId)

  const dashboard = useAsyncData(
    () => childrenApi.dashboard(activeChildId!),
    [activeChildId],
    { enabled: Boolean(activeChildId) },
  )

  if (!activeChildId) {
    return <NoChildState />
  }

  if (dashboard.initialLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-24 w-full rounded-2xl" />
        <SkeletonCards />
        <Skeleton className="h-80 w-full rounded-2xl" />
      </div>
    )
  }

  if (dashboard.error) {
    return (
      <Card>
        <ErrorState error={dashboard.error} onRetry={dashboard.reload} />
      </Card>
    )
  }

  const data = dashboard.data!
  const today = data.today
  // A deployed API that is a version behind sends a different shape; render the
  // empty state rather than crashing the whole page on a missing collection.
  const recentDays = data.recent_days ?? []
  const visits = today.visits ?? []
  const passes = today.passes ?? []
  const todayMeta = DAY_STATE_META[today.state] ?? DAY_STATE_META.NO_DATA
  const month = data.current_month

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm text-ink-500">{t('home.greeting')}</p>
        <h1 className="mt-0.5 text-2xl font-semibold tracking-tight text-ink-900">
          {user?.first_name || user?.full_name}
        </h1>
      </div>

      {/* Child card + today's status */}
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
          <Avatar
            name={data.student.full_name}
            initials={data.student.initials}
            src={data.student.photo ?? undefined}
            size="lg"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-semibold text-ink-900">
              {data.student.display_name}
            </p>
            <p className="text-sm text-ink-500">
              {data.student.class_group} sinf · {data.student.school}
            </p>
          </div>
          <div className="flex flex-col items-start gap-1.5 sm:items-end">
            <span className="text-xs font-medium uppercase tracking-wide text-ink-400">{t('common.today')}</span>
            <span className="flex items-center gap-2">
              <span className={cn('h-2 w-2 rounded-full', todayMeta.dot)} />
              <span className="text-[15px] font-semibold text-ink-800">
                {today.arrived_too_late
                  ? 'Juda kech keldi'
                  : today.is_inside
                    ? 'Maktabda'
                    : t(todayMeta.labelKey)}
              </span>
            </span>
            <span className="text-xs text-ink-500">{formatLongDate(today.date)}</span>
          </div>
        </div>

        {today.arrived_too_late ? (
          <div className="border-t border-ink-100 bg-amber-500/15 px-5 py-3 text-sm text-amber-800">
            <b>{today.arrived_at}</b> da maktabga kirdi, lekin bu vaqt davomat uchun
            juda kech — kun <b>kelmagan</b> deb hisoblandi.
          </div>
        ) : null}

        {today.was_present || data.pending_absence_requests > 0 ? (
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-ink-100 bg-ink-50/60 px-5 py-3 text-sm">
            {today.was_present ? (
              <>
                <span className="text-ink-600">
                  Kirdi:{' '}
                  <span className="font-semibold tabular-nums text-ink-800">
                    {today.first_in ?? '—'}
                  </span>
                </span>
                <span className="text-ink-600">
                  {today.is_inside ? (
                    'Hozir maktabda'
                  ) : (
                    <>
                      Chiqdi:{' '}
                      <span className="font-semibold tabular-nums text-ink-800">
                        {today.last_out ?? '—'}
                      </span>
                    </>
                  )}
                </span>
                <span className="text-ink-600">
                  Maktabda:{' '}
                  <span className="font-semibold tabular-nums text-ink-800">
                    {formatDuration(today.inside_minutes)}
                  </span>
                </span>
                {today.late_minutes > 0 ? (
                  <span className="font-medium text-amber-700">
                    {formatLateMinutes(today.late_minutes)}
                  </span>
                ) : null}
                <span className="text-ink-600">
                  Kirish/chiqish:{' '}
                  <span className="font-semibold tabular-nums text-ink-800">
                    {today.entries}/{today.exits}
                  </span>
                </span>
              </>
            ) : null}
            {data.pending_absence_requests > 0 ? (
              <Badge className="ml-auto bg-amber-500/15 text-amber-700 ring-amber-600/20">
                {data.pending_absence_requests} ta sabab ko'rib chiqilmoqda
              </Badge>
            ) : null}
          </div>
        ) : null}
      </Card>

      {/* Month summary */}
      <div>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-[15px] font-semibold text-ink-800">
            Joriy oy · {monthName(month.month)}
          </h2>
          <Link to="/davomat" className="text-sm font-medium text-brand-600 hover:text-brand-700">
            {t('attendance.details')}
          </Link>
        </div>
        <SummaryCards summary={month.summary} />
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        {/* Today at the gate */}
        <Card className="lg:col-span-3">
          <CardHeader
            title={t('attendance.todayAtGate')}
            description={formatLongDate(today.date)}
            action={
              <Link
                to="/davomat"
                className="text-sm font-medium text-brand-600 hover:text-brand-700"
              >
                {t('attendance.dailyTitle')}
              </Link>
            }
          />
          {dashboard.loading ? (
            <SkeletonRows count={4} />
          ) : (
            <>
              <VisitList visits={visits} />
              <PassTimeline passes={passes} />
            </>
          )}
        </Card>

        {/* Recent days */}
        <Card className="lg:col-span-2">
          <CardHeader title={t('common.recentDays')} description={t('attendance.last7')} />
          {recentDays.length === 0 ? (
            <CardBody>
              <p className="py-6 text-center text-sm text-ink-500">{t('attendance.noRecords')}</p>
            </CardBody>
          ) : (
            <ul className="divide-y divide-ink-100">
              {recentDays.map((day) => {
                const meta = DAY_STATE_META[day.state] ?? DAY_STATE_META.NO_DATA
                return (
                  <li key={day.date} className="flex items-center gap-3 px-5 py-3">
                    <span className={cn('h-2 w-2 shrink-0 rounded-full', meta.dot)} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink-800">
                        {formatShortDate(day.date)}
                      </p>
                      <p className="text-xs text-ink-500">
                        {day.was_present
                          ? `${day.first_in ?? '—'} → ${day.is_inside ? 'hozir' : (day.last_out ?? '—')}`
                          : t(meta.labelKey)}
                      </p>
                    </div>
                    {day.was_present ? (
                      <span className="shrink-0 text-sm font-semibold tabular-nums text-ink-700">
                        {formatDurationShort(day.inside_minutes)}
                      </span>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
