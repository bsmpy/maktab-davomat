import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { attendanceApi } from '@/api/attendanceApi'
import { childrenApi } from '@/api/childrenApi'
import { teachingApi } from '@/api/teachingApi'
import { useAuth } from '@/auth/permissions'
import { PassTimeline, VisitList } from '@/features/attendance/PassTimeline'
import { PresenceTimeline } from '@/features/teacher/PresenceTimeline'
import { NoChildState } from '@/components/layout/NoChildState'
import {
  Avatar,
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Skeleton,
  SkeletonCards,
  SkeletonRows,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { useChildStore } from '@/store/childStore'
import { formatDuration } from '@/utils/attendance'
import { cn } from '@/utils/cn'
import { todayISO } from '@/utils/date'

/**
 * The pages that belong to one role's own cabinet.
 *
 * Each is deliberately thin: the scoping is the server's, so these render what
 * comes back rather than filtering anything themselves. A curator's group list
 * is "the groups the API returned", which is the same list the API will accept
 * an id from.
 */

/** One number in a row of them. */
function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-ink-100 bg-surface p-4">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight text-ink-900">{value}</p>
      {hint ? <p className="mt-0.5 text-[11px] text-ink-400">{hint}</p> : null}
    </div>
  )
}

/** One "label — value" line inside a summary card. */
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-ink-500">{label}</span>
      <span className="font-semibold tabular-nums text-ink-900">{value}</span>
    </div>
  )
}

function PageTitle({ title, hint }: { title: string; hint?: string }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{title}</h1>
      {hint ? <p className="mt-1 text-sm text-ink-500">{hint}</p> : null}
    </div>
  )
}

// --------------------------------------------------------------------------
// CURATOR — Guruhim
// --------------------------------------------------------------------------
/**
 * The groups this curator was put in charge of.
 *
 * It reads the same endpoint the teacher's class cards come from: the server
 * already answers it with "the classes you may open", which for a curator is
 * their assignments and nothing else.
 */
export function MyGroupsPage() {
  const { t } = useTranslation()
  const { scope } = useAuth()
  const classes = useAsyncData(() => teachingApi.classes(todayISO()), [])

  const rows = classes.data ?? []

  return (
    <div className="space-y-5">
      <PageTitle title={t('nav.myGroups')} hint={t('curator.groupsHint')} />

      {classes.initialLoading ? (
        <SkeletonCards />
      ) : classes.error ? (
        <Card>
          <ErrorState error={classes.error} onRetry={classes.reload} />
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            title={t('curator.noGroups')}
            description={t('curator.noGroupsHint')}
          />
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {rows.map((group) => (
            <Card key={group.id}>
              <CardBody className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xl font-semibold tracking-tight text-ink-900">
                    {group.display_name}
                  </span>
                  <Badge className="bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-600/20">
                    {group.students_count} {t('curators.pupils')}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  {group.subjects.map((subject) => (
                    <span
                      key={subject.id}
                      className="rounded-lg bg-ink-50 px-2 py-1 text-xs text-ink-600"
                    >
                      {subject.name}
                    </span>
                  ))}
                </div>
                <Link
                  to="/guruhim/oquvchilar"
                  className="inline-block text-sm font-medium text-brand-600 hover:text-brand-700"
                >
                  {t('curator.openPupils')} →
                </Link>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {scope.curator_groups.length > 0 ? (
        <p className="text-xs text-ink-400">
          {t('curator.assignedTo')}:{' '}
          {scope.curator_groups.map((group) => group.display_name).join(', ')}
        </p>
      ) : null}
    </div>
  )
}

// --------------------------------------------------------------------------
// CURATOR / OTA-ONA — a list of pupils
// --------------------------------------------------------------------------
function PupilCard({
  child,
  to,
}: {
  child: {
    id: string
    full_name: string
    class_group: string
    initials: string
    photo?: string | null
    current_month?: { rate: number; days_present: number; school_days: number }
  }
  to?: string
}) {
  const { t } = useTranslation()
  const month = child.current_month
  const body = (
    <CardBody className="flex items-center gap-4">
      <Avatar name={child.full_name} src={child.photo ?? undefined} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[15px] font-medium text-ink-800">{child.full_name}</p>
        <p className="truncate text-xs text-ink-500">{child.class_group}</p>
      </div>
      {month ? (
        <div className="shrink-0 text-right">
          <p
            className={cn(
              'text-lg font-semibold tabular-nums',
              month.rate >= 0.9
                ? 'text-emerald-600'
                : month.rate >= 0.75
                  ? 'text-amber-600'
                  : 'text-red-600',
            )}
          >
            {Math.round(month.rate * 100)}%
          </p>
          <p className="text-[11px] text-ink-400">
            {month.days_present}/{month.school_days} {t('attendance.schoolDays')}
          </p>
        </div>
      ) : null}
    </CardBody>
  )

  return to ? (
    <Card className="transition hover:border-brand-200">
      <Link to={to}>{body}</Link>
    </Card>
  ) : (
    <Card>{body}</Card>
  )
}

/** The pupils of the groups this curator watches. */
export function MyGroupPupilsPage() {
  const { t } = useTranslation()
  const pupils = useAsyncData(() => childrenApi.list(), [])
  const rows = pupils.data ?? []

  return (
    <div className="space-y-5">
      <PageTitle title={t('nav.students')} hint={t('curator.pupilsHint')} />

      {pupils.initialLoading ? (
        <SkeletonRows count={6} />
      ) : pupils.error ? (
        <Card>
          <ErrorState error={pupils.error} onRetry={pupils.reload} />
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState title={t('curator.noPupils')} description={t('curator.noPupilsHint')} />
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((child) => (
            <PupilCard key={child.id} child={child} />
          ))}
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------
// OTA-ONA — Farzandlarim
// --------------------------------------------------------------------------
/**
 * A parent's children, with this month's figure on each.
 *
 * Choosing one here is the same act as choosing one in the rail's switcher —
 * both write the active child, and every pupil-scoped page follows it.
 */
export function MyChildrenPage() {
  const { t } = useTranslation()
  const children = useChildStore((state) => state.children)
  const loading = useChildStore((state) => state.loading)
  const activeChildId = useChildStore((state) => state.activeChildId)
  const setActiveChild = useChildStore((state) => state.setActiveChild)

  if (loading && children.length === 0) return <SkeletonRows count={3} />
  if (children.length === 0) return <NoChildState />

  return (
    <div className="space-y-5">
      <PageTitle title={t('nav.children')} hint={t('profile.myChildrenHint')} />

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {children.map((child) => (
          <button
            key={child.id}
            type="button"
            onClick={() => setActiveChild(child.id)}
            className={cn(
              'rounded-2xl text-left transition',
              child.id === activeChildId
                ? 'ring-2 ring-brand-500 ring-offset-2 ring-offset-surface'
                : '',
            )}
          >
            <PupilCard child={child} />
          </button>
        ))}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------
// Xronologiya — the day at the gate, hour by hour
// --------------------------------------------------------------------------
/**
 * One day, laid out as it happened.
 *
 * The same page for two kinds of viewer, because it answers the same question
 * for both: an employee sees their own passes, a parent sees the child they
 * are looking at. Which of the two is decided by what the session may read —
 * not by a flag the browser sets.
 */
export function ChronologyPage() {
  const { t } = useTranslation()
  const { isActing } = useAuth()
  const isParent = isActing('OTA-ONA')
  const activeChildId = useChildStore((state) => state.activeChildId)

  const mine = useAsyncData(() => teachingApi.dashboard(), [], { enabled: !isParent })
  // The three spans the page shows side by side, in one request.
  const stats = useAsyncData(() => teachingApi.stats(), [], { enabled: !isParent })
  const child = useAsyncData(
    () => attendanceApi.daily(activeChildId!),
    [activeChildId],
    { enabled: isParent && Boolean(activeChildId) },
  )

  if (isParent && !activeChildId) return <NoChildState />

  const loading = isParent ? child.initialLoading : mine.initialLoading
  const error = isParent ? child.error : mine.error
  const reload = isParent ? child.reload : mine.reload

  if (loading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-72 w-full rounded-2xl" />
      </div>
    )
  }

  if (error) {
    return (
      <Card>
        <ErrorState error={error} onRetry={reload} />
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <PageTitle title={t('nav.chronology')} hint={t('chronology.hint')} />

      {isParent ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat
              label={t('attendance.firstIn')}
              value={child.data?.first_in ?? '—'}
            />
            <Stat label={t('attendance.lastOut')} value={child.data?.last_out ?? '—'} />
            <Stat
              label={t('attendance.timeInside')}
              value={formatDuration(child.data?.inside_minutes ?? 0)}
            />
          </div>

          <Card>
            <CardHeader title={t('attendance.inSchool')} />
            <VisitList visits={child.data?.visits} />
          </Card>

          <Card>
            <CardHeader title={t('attendance.gateLog')} />
            <PassTimeline passes={child.data?.passes} />
          </Card>
        </>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat
              label={t('teacher.firstInTime')}
              value={mine.data?.timeline.first_in ?? '—'}
            />
            <Stat
              label={t('teacher.lastOutTime')}
              value={mine.data?.timeline.last_out ?? '—'}
            />
            <Stat
              label={t('attendance.timeInside')}
              value={formatDuration(mine.data?.timeline.inside_minutes ?? 0)}
            />
          </div>

          {mine.data ? (
            <Card>
              <CardHeader title={t('teacher.todayTimeline')} />
              <CardBody>
                <PresenceTimeline timeline={mine.data.timeline} />
              </CardBody>
            </Card>
          ) : null}

          {stats.data ? (
            <div className="grid gap-4 lg:grid-cols-3">
              {(
                [
                  ['attendance.weekly', stats.data.week],
                  ['attendance.monthly', stats.data.month],
                  ['attendance.yearly', stats.data.year],
                ] as const
              ).map(([labelKey, summary]) => (
                <Card key={labelKey}>
                  <CardHeader title={t(labelKey)} />
                  <CardBody className="space-y-1.5 text-sm">
                    <Row
                      label={t('attendance.schoolDays')}
                      value={String(summary.school_days)}
                    />
                    <Row
                      label={t('attendance.wasInside')}
                      value={String(summary.days_present)}
                    />
                    <Row
                      label={t('attendance.wasAbsent')}
                      value={String(summary.days_absent)}
                    />
                    <Row label={t('attendance.daysLate')} value={String(summary.late_days)} />
                    <Row
                      label={t('teacher.activeAtSchool')}
                      value={formatDuration(summary.active_minutes)}
                    />
                    <Row
                      label={t('attendance.rate')}
                      value={`${Math.round(summary.rate * 100)}%`}
                    />
                  </CardBody>
                </Card>
              ))}
            </div>
          ) : null}

          <Card>
            <CardHeader title={t('teacher.gateHistory')} />
            {mine.data?.recent_passes?.length ? (
              <ul className="divide-y divide-ink-100 border-t border-ink-100">
                {mine.data.recent_passes.map((pass) => (
                  <li key={pass.id} className="flex items-center gap-4 px-5 py-3">
                    <Badge
                      className={cn(
                        'shrink-0 ring-1 ring-inset',
                        pass.direction === 'OUT'
                          ? 'bg-ink-100 text-ink-600 ring-ink-400/20'
                          : 'bg-emerald-500/15 text-emerald-700 ring-emerald-600/20',
                      )}
                    >
                      {pass.label}
                    </Badge>
                    <span className="flex-1 text-sm text-ink-700">{pass.terminal}</span>
                    <span className="tabular-nums text-sm text-ink-500">
                      {pass.date} · {pass.time}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <CardBody>
                <EmptyState
                  title={t('teacher.noGateData')}
                  description={t('attendance.noPassesHint')}
                />
              </CardBody>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
