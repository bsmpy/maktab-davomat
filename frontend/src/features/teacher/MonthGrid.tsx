import { teachingApi } from '@/api/teachingApi'
import { useTranslation } from 'react-i18next'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ErrorState,
  Skeleton,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { TeachingCalendarDay } from '@/types/api'
import { cn } from '@/utils/cn'
import { monthName, shiftMonth, todayISO } from '@/utils/date'

const WEEKDAYS = ['Du', 'Se', 'Chor', 'Pay', 'Ju', 'Sha', 'Yak']

/**
 * A compact month grid.
 *
 * Each square carries a dot: green when the timetable puts this teacher in
 * front of a class that day, red when it does not. Picking a day does not
 * navigate anywhere — the panel beside the calendar answers instead.
 */
export function MonthGrid({
  year,
  month,
  selected,
  onMonthChange,
  onSelect,
  onPickToday,
}: {
  year: number
  month: number
  selected: string | null
  onMonthChange: (year: number, month: number) => void
  onSelect: (date: string) => void
  /** Month and day in one write — two would race on the same query string. */
  onPickToday: (date: string) => void
}) {
  const { t } = useTranslation()
  const calendar = useAsyncData(() => teachingApi.calendar(year, month), [year, month])
  const data = calendar.data
  const today = data?.today ?? todayISO()

  return (
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

        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-ink-900 sm:text-base">
            {monthName(month)} {year}
          </h3>
          <button
            type="button"
            onClick={() => onPickToday(todayISO())}
            className="rounded-lg border border-ink-200 px-2 py-1 text-xs text-ink-500 transition hover:bg-ink-100 hover:text-ink-900"
          >
            {t('common.today')}
          </button>
        </div>

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

      {calendar.error ? (
        <ErrorState error={calendar.error} onRetry={calendar.reload} />
      ) : !data || data.year !== year || data.month !== month ? (
        // Six rows of `sm:min-h-[54px]` plus the gaps — the placeholder stands
        // in for the grid rather than collapsing the card while it loads.
        <Skeleton className="h-[228px] w-full rounded-xl sm:h-[354px]" />
      ) : (
        <div
          className={cn(
            'grid grid-cols-7 gap-1 transition-opacity sm:gap-1.5',
            calendar.loading && 'opacity-50',
          )}
        >
          {data.days.map((day) => (
            <DayCell
              key={day.date}
              day={day}
              isToday={day.date === today}
              isSelected={day.date === selected}
              onSelect={onSelect}
            />
          ))}
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
  )
}

function DayCell({
  day,
  isToday,
  isSelected,
  onSelect,
}: {
  day: TeachingCalendarDay
  isToday: boolean
  isSelected: boolean
  onSelect: (date: string) => void
}) {
  const { t } = useTranslation()
  return (
    <button
      type="button"
      onClick={() => onSelect(day.date)}
      title={day.holiday ?? undefined}
      aria-pressed={isSelected}
      className={cn(
        'relative flex aspect-square flex-col items-center justify-center rounded-xl border p-1 transition sm:aspect-auto sm:min-h-[54px] sm:items-start sm:justify-start sm:p-1.5',
        isSelected
          ? 'border-brand-500 bg-brand-50'
          : 'border-ink-200 bg-surface hover:border-brand-300 hover:bg-ink-50',
        !day.in_month && 'opacity-40',
      )}
    >
      <span
        aria-label={day.teaches ? t('attendance.hasLessons') : "Dars yo'q"}
        className={cn(
          'absolute right-1 top-1 h-1.5 w-1.5 rounded-full sm:right-1.5 sm:top-1.5',
          day.teaches ? 'bg-emerald-500' : 'bg-red-500',
        )}
      />
      <span
        className={cn(
          'flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold',
          isToday ? 'bg-brand-600 text-onbrand' : 'text-ink-800',
        )}
      >
        {Number(day.date.slice(-2))}
      </span>
      {day.in_month && day.groups_count > 0 ? (
        <span className="hidden text-[10px] text-ink-400 sm:mt-0.5 sm:block">
          {day.groups_count} sinf
        </span>
      ) : null}
    </button>
  )
}
