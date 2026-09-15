import { teachingApi } from '@/api/teachingApi'
import { useTranslation } from 'react-i18next'
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  SkeletonRows,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { cn } from '@/utils/cn'
import { formatLongDate } from '@/utils/date'

/**
 * One class on one day: its timetable, with the teacher's own lessons open for
 * marking and everybody else's shown but greyed out.
 *
 * When the school has not uploaded a timetable yet, the same screen lists the
 * teacher's subjects for that class instead — the register still has to work.
 */
export function ClassDay({
  classGroupId,
  date,
  onBack,
  onOpenLesson,
}: {
  classGroupId: string
  date: string
  onBack: () => void
  onOpenLesson: (subjectId: string) => void
}) {
  const { t } = useTranslation()
  const day = useAsyncData(
    () => teachingApi.classDay(classGroupId, date),
    [classGroupId, date],
  )
  const lessons = day.data?.lessons ?? []

  return (
    <Card>
      <CardHeader
        title={day.data?.class_group.display_name ?? 'Sinf'}
        description={
          day.data
            ? `${formatLongDate(date)} · ${
                day.data.has_timetable ? `${lessons.length} ta dars` : 'jadval yuklanmagan'
              }`
            : formatLongDate(date)
        }
        action={
          <Button variant="secondary" size="sm" onClick={onBack}>
            {t('actions.back')}
          </Button>
        }
      />

      {day.initialLoading ? (
        <SkeletonRows count={4} />
      ) : day.error ? (
        <ErrorState error={day.error} onRetry={day.reload} />
      ) : lessons.length === 0 ? (
        <CardBody>
          <EmptyState
            title={t('teacher.noLessonThatDay')}
            description={t('teacher.loadScheduleHint')}
          />
        </CardBody>
      ) : (
        <ul className="divide-y divide-ink-100">
          {lessons.map((lesson) => {
            const done =
              lesson.students_count > 0 && lesson.marked_count >= lesson.students_count
            return (
              <li
                key={`${lesson.subject}-${lesson.lesson_number}`}
                className={cn(
                  'flex flex-wrap items-center gap-3 px-5 py-3.5',
                  !lesson.is_mine && 'opacity-55',
                )}
              >
                <span className="w-7 shrink-0 text-sm font-semibold tabular-nums text-ink-400">
                  {lesson.lesson_number}.
                </span>
                {lesson.start_time ? (
                  <span className="w-32 shrink-0 text-sm font-medium tabular-nums text-ink-800">
                    {lesson.start_time} — {lesson.end_time}
                  </span>
                ) : null}

                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-medium text-ink-800">
                    {lesson.subject_name}
                  </p>
                  <p className="truncate text-xs text-ink-500">
                    {[lesson.teacher_name, lesson.room && `${lesson.room}-xona`]
                      .filter(Boolean)
                      .join(' · ') || 'o‘qituvchi ko‘rsatilmagan'}
                  </p>
                </div>

                {lesson.is_mine ? (
                  <>
                    <Badge
                      className={cn(
                        'shrink-0 ring-1 ring-inset',
                        done
                          ? 'bg-emerald-500/15 text-emerald-700 ring-emerald-600/20'
                          : 'bg-ink-100 text-ink-600 ring-ink-200',
                      )}
                    >
                      {lesson.marked_count} / {lesson.students_count}
                    </Badge>
                    {/* A lesson that has not started cannot be entered at all:
                        the roll call opens with the bell. */}
                    {lesson.can_mark ? null : (
                      <span className="shrink-0 text-xs text-amber-700">
                        {lesson.start_time} da ochiladi
                      </span>
                    )}
                    <Button
                      size="sm"
                      variant={lesson.can_mark ? 'primary' : 'secondary'}
                      disabled={!lesson.can_mark}
                      title={lesson.can_mark ? undefined : 'Dars hali boshlanmagan'}
                      onClick={() => onOpenLesson(lesson.subject)}
                    >
                      {t('nav.attendance')}
                    </Button>
                  </>
                ) : (
                  <span className="shrink-0 text-xs text-ink-400">boshqa o‘qituvchi</span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
