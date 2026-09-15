import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { TeacherTimeline, TimelineSegment } from '@/types/api'
import { formatDuration } from '@/utils/attendance'
import { cn } from '@/utils/cn'

/** The hour marks under the band — kept sparse so they fit on a phone. */
function ticks(startHour: number, endHour: number, step: number): number[] {
  const marks: number[] = []
  for (let hour = startHour; hour <= endHour; hour += step) marks.push(hour)
  return marks
}

function label(hour: number): string {
  return `${String(hour % 24).padStart(2, '0')}:00`
}

/**
 * The day as one horizontal band, 06:00 to 00:00.
 *
 * Green is time inside the school and red is time outside it, segment by
 * segment — a teacher who steps out at noon and comes back gets two green
 * blocks with a red gap, not one block from the first entry to the last exit.
 *
 * Hovering a block names that block alone: its own from–to, and how long it
 * lasted. Moving to the next one swaps the reading rather than adding to it.
 */
export function PresenceTimeline({ timeline }: { timeline: TeacherTimeline }) {
  const { t } = useTranslation()
  const { start_hour: from, end_hour: to, segments } = timeline
  const [active, setActive] = useState<number | null>(null)
  const marks = ticks(from, to, 3)
  const hovered: TimelineSegment | undefined =
    active === null ? undefined : segments[active]

  // Keep the bubble on screen at the two ends of the band.
  const centre = hovered ? hovered.left + hovered.width / 2 : 0
  const anchor = centre < 12 ? 'left' : centre > 88 ? 'right' : 'centre'

  return (
    <div className="space-y-2">
      <div className="relative">
        {hovered ? (
          <div
            role="status"
            style={
              anchor === 'left'
                ? { left: 0 }
                : anchor === 'right'
                  ? { right: 0 }
                  : { left: `${centre}%` }
            }
            className={cn(
              'pointer-events-none absolute bottom-full z-10 mb-2 w-max max-w-[220px] rounded-xl border border-ink-200 bg-surface px-3 py-2 shadow-lg',
              anchor === 'centre' && '-translate-x-1/2',
            )}
          >
            <p className="flex items-center gap-1.5 text-xs font-semibold text-ink-800">
              <span
                className={cn(
                  'h-2 w-2 rounded-full',
                  hovered.state === 'IN' ? 'bg-emerald-500' : 'bg-red-500',
                )}
              />
              {hovered.state === 'IN' ? t('teacher.atSchool') : t('teacher.notAtSchool')}
            </p>
            <p className="mt-0.5 text-sm font-medium tabular-nums text-ink-900">
              {hovered.start} - {hovered.end}
            </p>
            <p className="text-xs text-ink-500">{formatDuration(hovered.minutes)}</p>
          </div>
        ) : null}

        <div
          className="flex h-4 w-full overflow-hidden rounded-full bg-ink-100"
          onMouseLeave={() => setActive(null)}
        >
          {segments.map((segment, index) => (
            <button
              key={`${segment.state}-${segment.start}-${segment.left}`}
              type="button"
              tabIndex={-1}
              aria-label={`${segment.state === 'IN' ? t('teacher.atSchool') : t('teacher.notAtSchool')} ${segment.start} - ${segment.end}`}
              style={{ width: `${segment.width}%` }}
              onMouseEnter={() => setActive(index)}
              onFocus={() => setActive(index)}
              // A tap on a phone reads the same block the mouse would.
              onClick={() => setActive(active === index ? null : index)}
              className={cn(
                'h-full cursor-default transition-opacity',
                segment.state === 'IN' ? 'bg-emerald-500' : 'bg-red-500',
                active !== null && active !== index && 'opacity-45',
              )}
            />
          ))}
        </div>
      </div>

      <div className="relative h-4">
        {marks.map((hour) => {
          const position = ((hour - from) / (to - from)) * 100
          return (
            <span
              key={hour}
              style={{ left: `${position}%` }}
              className={cn(
                'absolute text-[11px] tabular-nums text-ink-400',
                position === 0 && 'translate-x-0',
                position === 100 && '-translate-x-full',
                position > 0 && position < 100 && '-translate-x-1/2',
              )}
            >
              {label(hour)}
            </span>
          )
        })}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          {t('teacher.atSchool')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-red-500" />
          {t('teacher.notAtSchool')}
        </span>
      </div>
    </div>
  )
}
