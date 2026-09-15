import { teachingApi } from '@/api/teachingApi'
import { useTranslation } from 'react-i18next'
import { PresenceTimeline } from '@/features/teacher/PresenceTimeline'
import {
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Skeleton,
  SkeletonCards,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { CuratorGroupToday, TodayLesson } from '@/types/api'
import { formatDuration } from '@/utils/attendance'
import { cn } from '@/utils/cn'
import { formatShortDate } from '@/utils/date'

/** One headline number from the week. */
function StatCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string
  hint?: string
  tone: 'good' | 'warn' | 'bad'
}) {
  const toneClass = {
    good: 'text-emerald-600',
    warn: 'text-amber-600',
    bad: 'text-red-600',
  }[tone]
  return (
    <div className="rounded-2xl border border-ink-100 bg-surface p-4">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className={cn('mt-1 text-2xl font-semibold tracking-tight', toneClass)}>{value}</p>
      {hint ? <p className="mt-0.5 text-[11px] text-ink-400">{hint}</p> : null}
    </div>
  )
}

/** One of the three readings under the timeline. */
function TimeFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-ink-100 bg-surface p-4">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-ink-900">{value}</p>
    </div>
  )
}

/**
 * A teacher's lessons today — only the ones the timetable gives *them*, in bell
 * order, each with whether its register has been filled in yet.
 */
function TodayLessons({ lessons }: { lessons: TodayLesson[] }) {
  const { t } = useTranslation()
  return (
    <Card>
      <CardHeader
        title={t('teacher.todayLessons')}
        description={t('teacher.lessonsCount', { count: lessons.length })}
      />
      {lessons.length === 0 ? (
        <CardBody>
          <EmptyState title={t('teacher.noLessonsToday')} />
        </CardBody>
      ) : (
        <ul className="divide-y divide-ink-100">
          {lessons.map((lesson) => (
            <li key={lesson.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <span className="w-28 shrink-0 font-mono text-sm tabular-nums text-ink-500">
                {lesson.start_time}–{lesson.end_time}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[15px] font-medium text-ink-800">
                  {lesson.subject_name}
                </p>
                <p className="truncate text-xs text-ink-500">
                  {lesson.class_group_name}
                  {lesson.room ? ` · ${lesson.room}` : ''}
                </p>
              </div>
              <span
                className={cn(
                  'shrink-0 rounded-full px-2.5 py-1 text-xs font-medium',
                  lesson.marked_count > 0
                    ? 'bg-emerald-500/15 text-emerald-700'
                    : 'bg-ink-100 text-ink-500',
                )}
              >
                {lesson.marked_count > 0
                  ? t('teacher.markedOf', {
                      marked: lesson.marked_count,
                      total: lesson.students_count,
                    })
                  : t('teacher.notMarked')}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/** A curator's groups today — theirs and nobody else's. */
function CuratorGroups({ groups }: { groups: CuratorGroupToday[] }) {
  const { t } = useTranslation()
  return (
    <div>
      <h2 className="mb-3 text-[15px] font-semibold text-ink-800">{t('teacher.myGroupsToday')}</h2>
      {groups.length === 0 ? (
        <Card>
          <CardBody>
            <EmptyState title={t('teacher.noCuratorGroups')} />
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => (
            <Card key={group.id}>
              <CardHeader
                title={group.display_name}
                description={t('home.rate', { rate: group.pupils.rate })}
              />
              <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard
                  label={t('home.arrived')}
                  value={String(group.pupils.arrived)}
                  hint={t('home.ofTotal', { total: group.pupils.total })}
                  tone="good"
                />
                <StatCard
                  label={t('home.absent')}
                  value={String(group.pupils.absent)}
                  tone={group.pupils.absent > 0 ? 'bad' : 'good'}
                />
                <StatCard
                  label={t('home.late')}
                  value={String(group.pupils.late)}
                  tone={group.pupils.late > 0 ? 'warn' : 'good'}
                />
                <StatCard
                  label={t('home.insideNow')}
                  value={String(group.pupils.inside)}
                  tone="good"
                />
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * The employee's home screen. What sits on top follows the hat being worn: a
 * teacher's lessons today, a curator's groups today. Below it, always, their own
 * week at school, today's movements at the gate, and the last few passes.
 * Everything arrives in one request.
 */
export function TeacherDashboardPage() {
  const { t } = useTranslation()
  const dashboard = useAsyncData(() => teachingApi.dashboard(), [])

  if (dashboard.initialLoading) {
    return (
      <div className="space-y-5">
        <SkeletonCards />
        <Skeleton className="h-48 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
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
  const { teacher, week, timeline, recent_passes: passes } = data
  const range = `${formatShortDate(week.start_date)} — ${formatShortDate(week.end_date)}`

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm text-ink-500">{t('home.greeting')}</p>
        <h1 className="mt-0.5 text-2xl font-semibold tracking-tight text-ink-900">
          {teacher.full_name}
        </h1>
      </div>

      {data.lessons_today ? <TodayLessons lessons={data.lessons_today} /> : null}
      {data.groups_today ? <CuratorGroups groups={data.groups_today} /> : null}

      <div>
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="text-[15px] font-semibold text-ink-800">{t('attendance.thisWeek')}</h2>
          <span className="text-xs text-ink-500">{range}</span>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard
            label={t('teacher.activeAtSchool')}
            value={formatDuration(week.active_minutes)}
            hint={`${week.school_days} ta ish kuni`}
            tone="good"
          />
          <StatCard
            label={t('teacher.inactiveAtSchool')}
            value={formatDuration(week.inactive_minutes)}
            hint={t('teacher.outsideHours')}
            tone="warn"
          />
          <StatCard
            label={t('attendance.daysLate')}
            value={`${week.late_days} kun`}
            hint={t('teacher.lateDaysHint')}
            tone={week.late_days > 0 ? 'bad' : 'good'}
          />
        </div>
      </div>

      <Card>
        <CardHeader
          title={t('teacher.todayTimeline')}
          description={
            timeline.is_inside
              ? `Hozir maktabdasiz · ${formatDuration(timeline.inside_minutes)}`
              : formatDuration(timeline.inside_minutes)
          }
        />
        <CardBody className="space-y-5">
          <PresenceTimeline timeline={timeline} />

          <div className="grid gap-3 sm:grid-cols-3">
            <TimeFact
              label={t('teacher.firstInOut')}
              value={
                timeline.first_in
                  ? `${timeline.first_in} - ${timeline.last_out ?? '—'}`
                  : '—'
              }
            />
            <TimeFact label={t('teacher.firstInTime')} value={timeline.first_in ?? '—'} />
            <TimeFact label={t('teacher.lastOutTime')} value={timeline.last_out ?? '—'} />
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={t('teacher.gateHistory')} description={t('teacher.recentPasses')} />
        {passes.length === 0 ? (
          <CardBody>
            <EmptyState title={t('teacher.noGateData')} />
          </CardBody>
        ) : (
          <ul className="divide-y divide-ink-100">
            {passes.map((pass) => (
              <li key={pass.id} className="flex items-center gap-3 px-5 py-3">
                <span
                  className={cn(
                    'h-2.5 w-2.5 shrink-0 rounded-full',
                    pass.direction === 'IN' ? 'bg-emerald-500' : 'bg-red-500',
                  )}
                />
                <span className="flex-1 text-[15px] font-medium text-ink-800">
                  {pass.label}
                </span>
                <span className="shrink-0 text-sm tabular-nums text-ink-500">
                  {formatShortDate(pass.date)}, {pass.time}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
