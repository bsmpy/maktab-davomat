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
import { addDays, formatLongDate, todayISO } from '@/utils/date'

import { LessonCard, LessonGrid } from './LessonCard'

/**
 * The teacher's Davomat page: their lessons for the day, as cards.
 *
 * No tabs and no period switch — a teacher comes here to open one register,
 * and the only thing they need to know is whether it is open yet.
 */
export function TeacherLessons({
  date,
  onDateChange,
  onOpen,
}: {
  date: string
  onDateChange: (date: string) => void
  onOpen: (subjectId: string) => void
}) {
  const { t } = useTranslation()
  const lessons = useAsyncData(() => teachingApi.myLessons(date), [date])
  const isToday = date === todayISO()
  const rows = lessons.data ?? []

  return (
    <Card>
      <CardHeader
        title={t('teacher.myLessons')}
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
        {lessons.initialLoading ? (
          <SkeletonCards />
        ) : lessons.error ? (
          <ErrorState error={lessons.error} onRetry={lessons.reload} />
        ) : rows.length === 0 ? (
          <EmptyState
            title={t('teacher.noLessonsToday')}
            description={t('teacher.scheduleLoadedBy')}
          />
        ) : (
          <LessonGrid>
            {rows.map((lesson) => (
              <LessonCard
                key={`${lesson.subject}-${lesson.lesson_number}`}
                subject={lesson.subject_name}
                classGroup={lesson.class_group_name}
                startTime={lesson.start_time}
                endTime={lesson.end_time}
                room={lesson.room}
                action="Davomat"
                disabled={!lesson.can_mark}
                disabledTitle="Dars hali boshlanmagan"
                hint={
                  lesson.can_mark ? null : (
                    <span className="text-xs text-amber-700">
                      {lesson.opens_at} da ochiladi
                    </span>
                  )
                }
                onAction={() => onOpen(lesson.subject)}
              />
            ))}
          </LessonGrid>
        )}
      </CardBody>
    </Card>
  )
}
