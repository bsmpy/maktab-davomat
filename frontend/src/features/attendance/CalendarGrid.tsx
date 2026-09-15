import type { CalendarDay, MonthlyReport } from '@/types/api'
import { useTranslation } from 'react-i18next'
import { DAY_STATE_META, formatDurationShort } from '@/utils/attendance'
import { cn } from '@/utils/cn'

/**
 * Month grid. Colour encodes the day's state exactly as the backend computed
 * it — the frontend never re-derives whether a pupil was at school.
 */
export function CalendarGrid({
  report,
  onSelectDay,
  selectedDate,
}: {
  report: MonthlyReport
  onSelectDay: (day: CalendarDay) => void
  selectedDate?: string
}) {
  const { t } = useTranslation()
  return (
    <div>
      <div className="mb-2 grid grid-cols-7 gap-1.5">
        {(report.weekday_labels ?? []).map((label) => (
          <div
            key={label}
            className="py-1 text-center text-[11px] font-semibold uppercase tracking-wide text-ink-400"
          >
            {label}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1.5">
        {(report.days ?? []).map((day) => {
          const meta = DAY_STATE_META[day.state] ?? DAY_STATE_META.NO_DATA
          const interactive = day.in_month && day.is_school_day
          return (
            <button
              key={day.date}
              type="button"
              disabled={!interactive}
              onClick={() => onSelectDay(day)}
              title={day.holiday ?? t(meta.labelKey)}
              className={cn(
                'relative flex aspect-square flex-col items-center justify-center rounded-xl border text-sm transition',
                day.in_month ? meta.cell : 'border-transparent bg-transparent text-ink-300',
                interactive && 'hover:scale-[1.04] hover:shadow-sm',
                !interactive && 'cursor-default',
                day.is_today && 'ring-2 ring-brand-500 ring-offset-1 ring-offset-surface',
                selectedDate === day.date && 'ring-2 ring-ink-800 ring-offset-1 ring-offset-surface',
              )}
            >
              <span className={cn('font-semibold tabular-nums', !day.in_month && 'opacity-40')}>
                {day.day}
              </span>
              {day.in_month && day.was_present ? (
                <span className="mt-0.5 text-[10px] tabular-nums opacity-70">
                  {formatDurationShort(day.inside_minutes)}
                </span>
              ) : null}
              {day.absence_request?.status === 'PENDING' ? (
                <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-amber-500" />
              ) : null}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function CalendarLegend() {
  const items: { state: keyof typeof DAY_STATE_META; label: string }[] = [
    { state: 'PRESENT', label: 'Keldi' },
    { state: 'ABSENT', label: 'Kelmadi' },
    { state: 'LATE', label: 'Kechikdi' },
    { state: 'HOLIDAY', label: 'Bayram' },
    { state: 'NO_DATA', label: 'Hali kelmagan' },
  ]
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2">
      {items.map((item) => (
        <span key={item.state} className="flex items-center gap-1.5 text-xs text-ink-500">
          <span className={cn('h-2.5 w-2.5 rounded-full', DAY_STATE_META[item.state].dot)} />
          {item.label}
        </span>
      ))}
    </div>
  )
}
