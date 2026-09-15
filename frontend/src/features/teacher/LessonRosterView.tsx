import { teachingApi } from '@/api/teachingApi'
import { useTranslation } from 'react-i18next'
import { rosterClosedMessage } from '@/features/attendance/lessons/rosterWindow'
import {
  Avatar,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  SkeletonRows,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { LessonRosterStudent, LessonStatus } from '@/types/api'
import { formatDuration } from '@/utils/attendance'
import { cn } from '@/utils/cn'
import { formatLongDate } from '@/utils/date'

/**
 * How a mark reads when it is only being looked at.
 *
 * Both kinds of absence are red — the pupil was not there either way; what
 * separates them is whether a reason was given, which is written out beside
 * the word rather than encoded in a second colour.
 */
function describe(student: LessonRosterStudent): { dot: string; text: string } {
  const status: LessonStatus = student.status
  if (status === 'PRESENT') return { dot: 'bg-emerald-500', text: 'Keldi' }
  if (status === 'LATE') {
    return {
      dot: 'bg-amber-500',
      text: `Kechikdi · ${formatDuration(student.late_minutes)}`,
    }
  }
  if (status === 'EXCUSED') {
    return {
      dot: 'bg-red-500',
      text: student.comment ? `Kelmadi · ${student.comment}` : 'Kelmadi · sababli',
    }
  }
  if (status === 'ABSENT') return { dot: 'bg-red-500', text: 'Kelmadi' }
  return { dot: 'bg-ink-300', text: 'Belgilanmagan' }
}

/** The register as a record: the class list and what each pupil was marked. */
export function LessonRosterView({
  subjectId,
  date,
  onBack,
}: {
  subjectId: string
  date: string
  onBack: () => void
}) {
  const { t } = useTranslation()
  const roster = useAsyncData(() => teachingApi.roster(subjectId, date), [subjectId, date])
  const students = roster.data?.students ?? []
  const marked = students.filter((student) => student.status).length

  return (
    <Card>
      <CardHeader
        title={roster.data?.subject.display_name ?? 'Davomat'}
        description={
          roster.data
            ? `${formatLongDate(date)} · ${marked} / ${students.length} belgilangan`
            : formatLongDate(date)
        }
        action={
          <Button variant="secondary" size="sm" onClick={onBack}>
            {t('actions.back')}
          </Button>
        }
      />

      {roster.initialLoading ? (
        <SkeletonRows count={5} />
      ) : rosterClosedMessage(roster.error) ? (
        // A lesson later today, or any day still to come: the roll call is
        // shut until the bell, so there is no list to show yet.
        <CardBody>
          <div className="rounded-xl border border-amber-200 bg-amber-500/15 px-4 py-3 text-sm text-amber-800">
            {rosterClosedMessage(roster.error)}
          </div>
        </CardBody>
      ) : roster.error ? (
        <ErrorState error={roster.error} onRetry={roster.reload} />
      ) : students.length === 0 ? (
        <CardBody>
          <EmptyState title={t('teacher.noPupilsInClass')} />
        </CardBody>
      ) : (
        <ul className="divide-y divide-ink-100">
          {students.map((student) => {
            const mark = describe(student)
            return (
              <li key={student.id} className="flex items-center gap-3 px-5 py-3">
                <Avatar
                  name={student.full_name}
                  initials={student.initials}
                  src={student.photo ?? undefined}
                  size="sm"
                />
                <p className="min-w-0 flex-1 basis-1/2 truncate text-[15px] font-medium text-ink-800">
                  {student.full_name}
                </p>
                <span className="flex min-w-0 shrink items-center gap-2 text-sm text-ink-600">
                  <span className={cn('h-2.5 w-2.5 shrink-0 rounded-full', mark.dot)} />
                  <span className="truncate">{mark.text}</span>
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
