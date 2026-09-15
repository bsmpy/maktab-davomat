import { useTranslation } from 'react-i18next'

import { adminApi } from '@/api/adminApi'
import { Card, CardBody, CardHeader, ErrorState, Skeleton, SkeletonCards } from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { useAuthStore } from '@/store/authStore'
import type { AttendanceToday } from '@/types/api'
import { formatDuration } from '@/utils/attendance'
import { cn } from '@/utils/cn'
import { formatLongDate } from '@/utils/date'

/** One headline figure. */
function Stat({
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
    <div className="rounded-2xl border border-ink-200 bg-surface p-4">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className={cn('mt-1 text-2xl font-semibold tracking-tight tabular-nums', toneClass)}>
        {value}
      </p>
      {hint ? <p className="mt-0.5 text-[11px] text-ink-400">{hint}</p> : null}
    </div>
  )
}

/**
 * One group's day at the gate: came, late, did not come, inside right now.
 *
 * The teachers and the pupils are asked the same four questions and laid out
 * the same way, so the two rows can be read against each other at a glance.
 */
function AttendanceRow({ title, data }: { title: string; data: AttendanceToday }) {
  const { t } = useTranslation()
  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-[15px] font-semibold text-ink-800">{title}</h2>
        <span className="text-xs text-ink-500">{t('home.ofTotal', { total: data.total })}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <Stat
          label={t('home.arrived')}
          value={data.arrived}
          hint={t('home.rate', { rate: data.rate })}
          tone="good"
        />
        <Stat label={t('home.late')} value={data.late} tone={data.late ? 'warn' : 'neutral'} />
        <Stat
          label={t('home.absent')}
          value={data.absent}
          tone={data.absent ? 'bad' : 'neutral'}
        />
        <Stat label={t('home.insideNow')} value={data.inside} />
      </div>
    </section>
  )
}

/**
 * The three averages beside a group's day.
 *
 * Each is averaged over the people it describes — time inside over those who
 * came, lateness over those who were late — so a register full of people who
 * stayed home does not quietly drag them towards zero.
 */
function AveragesCard({ title, data }: { title: string; data: AttendanceToday }) {
  const { t } = useTranslation()
  return (
    <Card>
      <CardHeader title={title} />
      <CardBody className="grid grid-cols-1 gap-3 xs:grid-cols-3">
        <Stat
          label={t('home.avgActive')}
          value={formatDuration(data.avg_active_minutes)}
          tone="good"
        />
        <Stat
          label={t('home.avgInactive')}
          value={formatDuration(data.avg_inactive_minutes)}
          tone={data.avg_inactive_minutes ? 'warn' : 'neutral'}
        />
        <Stat
          label={t('home.avgLate')}
          value={formatDuration(data.avg_late_minutes)}
          tone={data.avg_late_minutes ? 'bad' : 'neutral'}
        />
      </CardBody>
    </Card>
  )
}

/**
 * The administrator's home screen.
 *
 * Read top to bottom: how big the school is, then how its two halves turned up
 * today — the teachers first, then the pupils, each answering the same four
 * questions — and finally how long each half actually spent inside.
 */
export function AdminHomePage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const overview = useAsyncData(() => adminApi.overview(), [])

  if (overview.initialLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-16 w-full rounded-2xl" />
        <SkeletonCards />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    )
  }

  if (overview.error) {
    return (
      <Card>
        <ErrorState error={overview.error} onRetry={overview.reload} />
      </Card>
    )
  }

  const data = overview.data!
  const { register, teachers_today: teachers, students_today: students } = data

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-ink-500">{t('home.greeting')}</p>
        <h1 className="mt-0.5 text-2xl font-semibold tracking-tight text-ink-900">
          {user?.first_name || user?.full_name}
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          {data.school} · {formatLongDate(data.date)}
        </p>
      </div>

      {/* How big the school is, before anything about today. */}
      <section>
        <h2 className="mb-3 text-[15px] font-semibold text-ink-800">{t('home.register')}</h2>
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <Stat label={t('home.teachers')} value={register.teachers} />
          <Stat label={t('home.staff')} value={register.staff} />
          <Stat label={t('home.students')} value={register.students} />
          <Stat label={t('home.groups')} value={register.class_groups} />
        </div>
      </section>

      <AttendanceRow title={t('home.teacherAttendance')} data={teachers} />
      <AttendanceRow title={t('home.studentAttendance')} data={students} />

      {/* The two halves side by side, three figures each. */}
      <div className="grid gap-4 lg:grid-cols-2">
        <AveragesCard title={t('home.teachers')} data={teachers} />
        <AveragesCard title={t('home.students')} data={students} />
      </div>
    </div>
  )
}
