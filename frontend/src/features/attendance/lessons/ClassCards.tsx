import { teachingApi } from '@/api/teachingApi'
import { useTranslation } from 'react-i18next'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  ChevronLeftIcon,
  ChevronRightIcon,
  EmptyState,
  ErrorState,
  SkeletonCards,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { ScheduleState } from '@/types/api'
import { cn } from '@/utils/cn'
import { addDays, formatLongDate, todayISO } from '@/utils/date'

const STATE_META: Record<ScheduleState, { dot: string; ring: string; label: string }> = {
  TODAY: { dot: 'bg-emerald-500', ring: 'bg-emerald-500', label: 'Bugun dars bor' },
  TOMORROW: { dot: 'bg-amber-500', ring: 'bg-amber-500', label: 'Ertaga dars bor' },
  NONE: { dot: 'bg-ink-300', ring: '', label: 'Yaqin kunlarda dars yo‘q' },
}

/**
 * The marker in the corner of a class card.
 *
 * Green means the teacher is in that class today and it breathes, so the eye
 * finds it across a grid; amber means tomorrow; grey means neither, and stays
 * still.
 */
function StateDot({ state }: { state: ScheduleState }) {
  const meta = STATE_META[state]
  return (
    <span className="relative flex h-2.5 w-2.5" title={meta.label} aria-label={meta.label}>
      {state === 'TODAY' ? (
        <span
          className={cn(
            'absolute inset-0 rounded-full motion-safe:animate-live-ring',
            meta.ring,
          )}
        />
      ) : null}
      <span
        className={cn(
          'relative inline-flex h-2.5 w-2.5 rounded-full',
          meta.dot,
          state === 'TODAY' && 'motion-safe:animate-live-dot',
        )}
      />
    </span>
  )
}

/**
 * A teacher's cabinet opens on classes, not subjects: "am I in 1-A today?" is
 * the question they actually arrive with.
 */
export function ClassCards({
  date,
  onDateChange,
  onOpen,
}: {
  date: string
  onDateChange: (date: string) => void
  onOpen: (classGroupId: string) => void
}) {
  const { t } = useTranslation()
  const classes = useAsyncData(() => teachingApi.classes(date), [date])
  const isToday = date === todayISO()

  return (
    <Card>
      <CardHeader
        title={t('teacher.myClasses')}
        description={formatLongDate(date)}
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

      <CardBody>
        {classes.initialLoading ? (
          <SkeletonCards />
        ) : classes.error ? (
          <ErrorState error={classes.error} onRetry={classes.reload} />
        ) : (classes.data ?? []).length === 0 ? (
          <EmptyState
            title={t('teacher.noClasses')}
            description={t('teacher.noClassesHint')}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {(classes.data ?? []).map((row) => (
              <button
                key={row.id}
                type="button"
                onClick={() => onOpen(row.id)}
                className="relative rounded-2xl border border-ink-200 bg-surface p-4 pl-6 text-left transition hover:border-brand-400 hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                <span className="absolute left-3 top-3.5">
                  <StateDot state={row.schedule_state} />
                </span>

                <p className="text-lg font-semibold text-ink-900">{row.display_name}</p>
                <p className="mt-0.5 text-xs text-ink-500">
                  {row.students_count} o'quvchi · {STATE_META[row.schedule_state].label}
                </p>

                <p className="mt-3 line-clamp-2 text-sm text-ink-600">
                  {row.subjects.map((subject) => subject.name).join(', ')}
                </p>
              </button>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
