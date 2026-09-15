import { teachingApi } from '@/api/teachingApi'
import { useTranslation } from 'react-i18next'
import {
  ArrowLeftIcon,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Skeleton,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { TeachingDay } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatLongDate } from '@/utils/date'

/**
 * The panel beside the calendar: a date, the classes this teacher stood in
 * front of that day, and the lessons of one of them.
 *
 * Both steps read a single request. The groups are the ones with a lesson of
 * this teacher's on that date — not the school's whole register, which would
 * say nothing about the day that was picked.
 */
export function DayDetailPanel({
  date,
  classGroupId,
  onPickClass,
  onBack,
  onOpenSubject,
}: {
  date: string | null
  classGroupId: string | null
  onPickClass: (id: string) => void
  onBack: () => void
  onOpenSubject: (subjectId: string) => void
}) {
  const { t } = useTranslation()
  const day = useAsyncData(() => teachingApi.calendarDay(date!), [date], {
    enabled: Boolean(date),
  })
  const groups = day.data?.groups ?? []
  const group = groups.find((row) => row.id === classGroupId) ?? null

  return (
    <aside className="min-h-[320px] rounded-2xl border border-ink-200 bg-surface lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:overflow-y-auto">
      <div className="border-b border-ink-200 px-4 py-3">
        <p className="text-[11px] font-medium uppercase tracking-wide text-ink-400">
          {t('attendance.detail')}
        </p>
        <p className="mt-0.5 truncate text-[15px] font-semibold text-ink-900">
          {date ? formatLongDate(date) : 'Kun tanlanmagan'}
        </p>
      </div>

      {!date ? (
        <div className="px-4 py-8">
          <EmptyState
            title={t('attendance.pickDay')}
            description={t('attendance.pickDayHint')}
          />
        </div>
      ) : day.error ? (
        <div className="px-4 py-3">
          <ErrorState error={day.error} onRetry={day.reload} />
        </div>
      ) : day.initialLoading ? (
        <Placeholder />
      ) : group ? (
        <SubjectList group={group} onBack={onBack} onOpenSubject={onOpenSubject} />
      ) : (
        <ClassList groups={groups} onPick={onPickClass} />
      )}
    </aside>
  )
}

function Placeholder() {
  return (
    <div className="grid grid-cols-3 gap-2 px-4 py-3 sm:grid-cols-4 xl:grid-cols-3">
      {Array.from({ length: 6 }, (_, index) => (
        <Skeleton key={index} className="h-10 rounded-xl" />
      ))}
    </div>
  )
}

/** The classes this teacher taught that day. */
function ClassList({
  groups,
  onPick,
}: {
  groups: TeachingDay['groups']
  onPick: (id: string) => void
}) {
  const { t } = useTranslation()
  return (
    <div className="px-4 py-3">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-400">
        {t('teacher.groups')}
      </p>

      {groups.length === 0 ? (
        <EmptyState
          title={t('teacher.noLessonForYou')}
          description={t('teacher.noClassThatDay')}
        />
      ) : (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 xl:grid-cols-3">
          {groups.map((group) => (
            <button
              key={group.id}
              type="button"
              onClick={() => onPick(group.id)}
              className="animate-fade-in rounded-xl border border-ink-200 py-2.5 text-sm font-semibold text-ink-800 transition hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700 active:bg-brand-100"
            >
              {group.display_name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/** That day's lessons for the chosen class, with a way back. */
function SubjectList({
  group,
  onBack,
  onOpenSubject,
}: {
  group: TeachingDay['groups'][number]
  onBack: () => void
  onOpenSubject: (subjectId: string) => void
}) {
  const { t } = useTranslation()
  return (
    <div className="px-4 py-3">
      <div className="mb-3 flex items-center gap-2">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 rounded-lg px-1.5 py-1 text-xs font-medium text-ink-500 transition hover:bg-ink-100 hover:text-ink-900"
        >
          <ArrowLeftIcon width={14} height={14} />
          {t('teacher.groups')}
        </button>
        <Badge className="bg-brand-500/15 text-brand-700 ring-1 ring-inset ring-brand-600/20">
          {group.display_name}
        </Badge>
      </div>

      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-400">
        {t('teacher.subjects')}
      </p>

      {group.lessons.length === 0 ? (
        <EmptyState title={t('teacher.noSubjectsForGroup')} />
      ) : (
        <ul className="space-y-1.5">
          {group.lessons.map((lesson) => {
            const done =
              lesson.students_count > 0 && lesson.marked_count >= lesson.students_count
            return (
              <li
                key={`${lesson.subject}-${lesson.lesson_number}`}
                className="animate-fade-in flex items-center gap-2 rounded-xl border border-ink-200 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink-800">
                    {lesson.subject_name}
                  </p>
                  <p className="truncate text-xs text-ink-500">
                    {lesson.start_time} — {lesson.end_time} ·{' '}
                    <span className={cn(done && 'text-emerald-600')}>
                      {lesson.marked_count} / {lesson.students_count}
                    </span>
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onOpenSubject(lesson.subject)}
                >
                  {t('actions.view')}
                </Button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
