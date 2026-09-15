import { attendanceApi } from '@/api/attendanceApi'
import { useTranslation } from 'react-i18next'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  EmptyState,
  ErrorState,
  Skeleton,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { LessonRow } from '@/types/api'
import { LESSON_STATUS_META, formatDuration } from '@/utils/attendance'
import { cn } from '@/utils/cn'
import { formatLongDate, monthName, monthRange, shiftMonth, todayISO } from '@/utils/date'

const WEEKDAYS = ['Du', 'Se', 'Chor', 'Pay', 'Ju', 'Sha', 'Yak']

/** A Monday-aligned 6×7 grid of ISO dates covering the month. */
function grid(year: number, month: number): string[] {
  const first = new Date(year, month - 1, 1)
  const offset = (first.getDay() + 6) % 7
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(year, month - 1, 1 - offset + index)
    const m = String(day.getMonth() + 1).padStart(2, '0')
    const d = String(day.getDate()).padStart(2, '0')
    return `${day.getFullYear()}-${m}-${d}`
  })
}

/** Green when the child had lessons that day, red when the register is empty. */
function dot(hasLessons: boolean): string {
  return hasLessons ? 'bg-emerald-500' : 'bg-red-500'
}

/**
 * The same calendar the staff see, scoped to one child.
 *
 * A parent has no school-wide register to browse, so the panel beside the month
 * lists that day's lessons and the mark their child got in each.
 */
export function ParentCalendar({
  childId,
  year,
  month,
  selected,
  onMonthChange,
  onSelect,
}: {
  childId: string
  year: number
  month: number
  selected: string | null
  onMonthChange: (year: number, month: number) => void
  onSelect: (date: string) => void
}) {
  const { t } = useTranslation()
  const span = monthRange(year, month)
  const report = useAsyncData(
    () => attendanceApi.lessons(childId, { start: span.start, end: span.end }),
    [childId, span.start, span.end],
  )

  const byDate = new Map<string, LessonRow[]>()
  for (const day of report.data?.days ?? []) byDate.set(day.date, day.lessons)
  const today = report.data?.today ?? todayISO()

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_380px] 2xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="rounded-2xl border border-ink-200 bg-surface p-3 sm:p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <button
            type="button"
            aria-label={t('attendance.prevMonth')}
            onClick={() => {
              const previous = shiftMonth(year, month, -1)
              onMonthChange(previous.year, previous.month)
            }}
            className="rounded-lg border border-ink-200 p-1.5 text-ink-500 transition hover:bg-ink-100 hover:text-ink-900"
          >
            <ChevronLeftIcon width={16} height={16} />
          </button>
          <h3 className="text-sm font-semibold text-ink-900 sm:text-base">
            {monthName(month)} {year}
          </h3>
          <button
            type="button"
            aria-label={t('attendance.nextMonth')}
            onClick={() => {
              const next = shiftMonth(year, month, 1)
              onMonthChange(next.year, next.month)
            }}
            className="rounded-lg border border-ink-200 p-1.5 text-ink-500 transition hover:bg-ink-100 hover:text-ink-900"
          >
            <ChevronRightIcon width={16} height={16} />
          </button>
        </div>

        <div className="mb-1 grid grid-cols-7 gap-1 sm:gap-1.5">
          {WEEKDAYS.map((weekday) => (
            <div key={weekday} className="py-1 text-center text-[11px] font-medium text-ink-400">
              {weekday}
            </div>
          ))}
        </div>

        {report.error ? (
          <ErrorState error={report.error} onRetry={report.reload} />
        ) : report.initialLoading ? (
          <Skeleton className="h-[228px] w-full rounded-xl sm:h-[354px]" />
        ) : (
          <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
            {grid(year, month).map((date) => {
              const lessons = byDate.get(date) ?? []
              const inMonth = Number(date.slice(5, 7)) === month
              return (
                <button
                  key={date}
                  type="button"
                  aria-pressed={date === selected}
                  onClick={() => onSelect(date)}
                  className={cn(
                    'relative flex aspect-square flex-col items-center justify-center rounded-xl border p-1 transition sm:aspect-auto sm:min-h-[54px] sm:items-start sm:justify-start sm:p-1.5',
                    date === selected
                      ? 'border-brand-500 bg-brand-50'
                      : 'border-ink-200 bg-surface hover:border-brand-300 hover:bg-ink-50',
                    !inMonth && 'opacity-40',
                  )}
                >
                  <span
                    aria-label={lessons.length ? t('attendance.hasLessons') : "Dars yo'q"}
                    className={cn(
                      'absolute right-1 top-1 h-1.5 w-1.5 rounded-full sm:right-1.5 sm:top-1.5',
                      dot(lessons.length > 0),
                    )}
                  />
                  <span
                    className={cn(
                      'flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold',
                      date === today ? 'bg-brand-600 text-onbrand' : 'text-ink-800',
                    )}
                  >
                    {Number(date.slice(-2))}
                  </span>
                </button>
              )
            })}
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-500">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            {t('attendance.hasLessons')}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            {t('attendance.noLessonsDot')}
          </span>
        </div>
      </div>

      <aside className="min-h-[320px] rounded-2xl border border-ink-200 bg-surface lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:overflow-y-auto">
        <div className="border-b border-ink-200 px-4 py-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-ink-400">
            {t('attendance.detail')}
          </p>
          <p className="mt-0.5 truncate text-[15px] font-semibold text-ink-900">
            {selected ? formatLongDate(selected) : 'Kun tanlanmagan'}
          </p>
        </div>

        <div className="px-4 py-3">
          {!selected ? (
            <div className="py-6">
              <EmptyState
                title={t('attendance.pickDay')}
                description={t('attendance.pickDayHint')}
              />
            </div>
          ) : (byDate.get(selected) ?? []).length === 0 ? (
            <EmptyState title={t('attendance.noLessonsThatDay')} />
          ) : (
            <ul className="space-y-1.5">
              {(byDate.get(selected) ?? []).map((lesson) => {
                const meta = LESSON_STATUS_META[lesson.status]
                return (
                  <li
                    key={lesson.id}
                    className="animate-fade-in flex items-center gap-2 rounded-xl border border-ink-200 px-3 py-2"
                  >
                    <span className={cn('h-2.5 w-2.5 shrink-0 rounded-full', meta.dot)} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink-800">
                        {lesson.subject_display}
                      </p>
                      <p className="truncate text-xs text-ink-500">
                        {lesson.status === 'LATE'
                          ? `${t(meta.shortKey)} · ${formatDuration(lesson.late_minutes)}`
                          : lesson.status === 'EXCUSED' && lesson.comment
                            ? `${t(meta.shortKey)} · ${lesson.comment}`
                            : t(meta.labelKey)}
                      </p>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </aside>
    </div>
  )
}
