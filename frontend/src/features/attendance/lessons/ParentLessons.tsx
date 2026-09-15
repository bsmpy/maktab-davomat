import { attendanceApi } from '@/api/attendanceApi'
import { useTranslation } from 'react-i18next'
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
import type { LessonRow, LessonTotals } from '@/types/api'
import { LESSON_STATUS_META, formatDuration } from '@/utils/attendance'
import { cn } from '@/utils/cn'
import { formatLongDate, formatShortDate } from '@/utils/date'

/** The four counts, so a parent sees the shape of the term at a glance. */
function Totals({ summary }: { summary: LessonTotals }) {
  const cells = [
    { label: 'Keldi', value: summary.present, tone: 'text-emerald-600' },
    { label: 'Kechikdi', value: summary.late, tone: 'text-amber-600' },
    { label: 'Sababli', value: summary.excused, tone: 'text-blue-600' },
    { label: 'Sababsiz', value: summary.absent, tone: 'text-red-600' },
  ]
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {cells.map((cell) => (
        <div key={cell.label} className="rounded-xl border border-ink-100 bg-surface p-4">
          <p className="text-xs font-medium text-ink-500">{cell.label}</p>
          <p className={cn('mt-1 text-xl font-semibold tabular-nums', cell.tone)}>
            {cell.value}
          </p>
        </div>
      ))}
    </div>
  )
}

function LessonLine({ lesson }: { lesson: LessonRow }) {
  const { t } = useTranslation()
  const meta = LESSON_STATUS_META[lesson.status]
  return (
    <li className="flex flex-wrap items-center gap-3 px-5 py-3">
      <span className={cn('h-2 w-2 shrink-0 rounded-full', meta.dot)} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink-800">{lesson.subject_display}</p>
        <p className="truncate text-xs text-ink-500">
          {lesson.teacher || "o'qituvchi ko'rsatilmagan"}
          {lesson.status === 'EXCUSED' && lesson.comment ? ` · ${lesson.comment}` : ''}
        </p>
      </div>
      <span className={cn('shrink-0 rounded-lg border px-2.5 py-1 text-xs font-medium', meta.chip)}>
        {lesson.status === 'LATE'
          ? `${t(meta.shortKey)} · ${formatDuration(lesson.late_minutes)}`
          : t(meta.shortKey)}
      </span>
    </li>
  )
}

/**
 * Dars davomati as a parent reads it.
 *
 * The range comes from the period switch above, so the same component serves
 * the day, the week, the month and the year; only the year drops the day-by-day
 * list, which would otherwise be a thousand rows nobody scrolls.
 */
export function ParentLessons({
  childId,
  start,
  end,
  includeDays = true,
  title,
}: {
  childId: string
  start: string
  end: string
  includeDays?: boolean
  title: string
}) {
  const { t } = useTranslation()
  const report = useAsyncData(
    () => attendanceApi.lessons(childId, { start, end, includeDays }),
    [childId, start, end, includeDays],
  )

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
  const subjects = data.subjects ?? []

  if (data.summary.lessons === 0) {
    return (
      <Card>
        <CardHeader title={title} />
        <CardBody>
          <EmptyState
            title={t('attendance.notMarked')}
            description={t('attendance.notMarkedHint')}
          />
        </CardBody>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Totals summary={data.summary} />

      <Card>
        <CardHeader
          title={t('attendance.bySubject')}
          description={`${data.summary.attended} / ${data.summary.lessons} darsda qatnashdi`}
        />
        <ul className="divide-y divide-ink-100 border-t border-ink-100">
          {subjects.map((subject) => (
            <li key={subject.id} className="px-5 py-3.5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-[15px] font-medium text-ink-800">{subject.display_name}</p>
                <p className="text-sm font-semibold tabular-nums text-ink-700">
                  {subject.rate}%
                </p>
              </div>
              <ProgressBar value={subject.rate} className="mt-2" />
              <p className="mt-1.5 text-xs text-ink-500">
                {subject.present} keldi · {subject.late} kechikdi · {subject.excused} sababli
                · {subject.absent} sababsiz
              </p>
            </li>
          ))}
        </ul>
      </Card>

      {includeDays && days.length > 0 ? (
        <Card>
          <CardHeader title={title} />
          <div className="border-t border-ink-100">
            {days.map((day) => (
              <div key={day.date}>
                <p className="bg-ink-50/60 px-5 py-2 text-xs font-medium uppercase tracking-wide text-ink-500">
                  {days.length === 1 ? formatLongDate(day.date) : formatShortDate(day.date)}
                </p>
                <ul className="divide-y divide-ink-100">
                  {day.lessons.map((lesson) => (
                    <LessonLine key={lesson.id} lesson={lesson} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  )
}
