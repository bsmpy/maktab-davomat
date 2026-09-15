import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { adminApi } from '@/api/adminApi'
import { toApiError } from '@/api/errors'
import { managementApi } from '@/api/managementApi'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  Input,
  Select,
  SkeletonRows,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'

/** ISO weekdays, in the order the school week runs. */
const WEEKDAYS = [
  { value: 1, label: 'Dushanba' },
  { value: 2, label: 'Seshanba' },
  { value: 3, label: 'Chorshanba' },
  { value: 4, label: 'Payshanba' },
  { value: 5, label: 'Juma' },
  { value: 6, label: 'Shanba' },
]

/** `08:00` + 40 minutes → `08:40`, so the next slot fills itself in. */
function addMinutes(time: string, minutes: number): string {
  const [hours, mins] = time.split(':').map(Number)
  const total = (hours * 60 + mins + minutes) % (24 * 60)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

const LESSON_MINUTES = 40
const BREAK_MINUTES = 10

/**
 * Dars jadvali: sinf → sinf guruhi → kun, then the lessons in order.
 *
 * Each row is "from — to — which subject", and the next row starts where the
 * last one left off, so a whole day is entered by typing the subject and
 * pressing add.
 */
export function SchedulePanel() {
  const { t } = useTranslation()
  const classGroups = useAsyncData(() => managementApi.classGroups(), [])
  const [grade, setGrade] = useState('')
  const [group, setGroup] = useState('')
  const [weekday, setWeekday] = useState(String(WEEKDAYS[0].value))

  const schedule = useAsyncData(
    () => adminApi.schedule(group, Number(weekday)),
    [group, weekday],
    { enabled: Boolean(group) },
  )
  const subjects = useAsyncData(() => adminApi.subjects(), [])

  const [start, setStart] = useState('08:00')
  const [end, setEnd] = useState(addMinutes('08:00', LESSON_MINUTES))
  const [subject, setSubject] = useState('')
  const [room, setRoom] = useState('')
  const [busy, setBusy] = useState(false)

  const groupList = classGroups.data ?? []
  const gradeLevels = [...new Set(groupList.map((row) => row.grade_level))].sort((a, b) => a - b)
  const groupsInGrade = groupList.filter((row) => String(row.grade_level) === grade)
  // Only the chosen class's own subjects can be timetabled for it.
  const groupSubjects = (subjects.data ?? []).filter((row) => row.class_group === group)
  const entries = schedule.data ?? []

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true)
    try {
      await action()
      toast.success(success)
      schedule.reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  function add() {
    return run(async () => {
      await adminApi.addScheduleEntry({
        class_group: group,
        weekday: Number(weekday),
        subject,
        start_time: start,
        end_time: end,
        room: room.trim(),
      })
      // Line up the next lesson right after the break.
      const nextStart = addMinutes(end, BREAK_MINUTES)
      setStart(nextStart)
      setEnd(addMinutes(nextStart, LESSON_MINUTES))
      setSubject('')
    }, 'Dars qo‘shildi')
  }

  const canAdd = Boolean(group && subject && start && end && !busy)

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={t('nav.schedule')}
          description={t('schedule.hint')}
        />
        <CardBody className="space-y-4">
          {groupList.length === 0 ? (
            <EmptyState
              title={t('schedule.noGroupsFirst')}
              description={t('schedule.noGroupsHint')}
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-3">
              <Select
                label={t('register.grade')}
                value={grade}
                onChange={(event) => {
                  setGrade(event.target.value)
                  setGroup('')
                }}
              >
                <option value="">{t('person.select')}</option>
                {gradeLevels.map((level) => (
                  <option key={level} value={String(level)}>
                    {level}-sinf
                  </option>
                ))}
              </Select>
              <Select
                label={t('student.classGroup')}
                value={group}
                disabled={!grade}
                onChange={(event) => setGroup(event.target.value)}
              >
                <option value="">{grade ? t('person.select') : 'Avval sinfni tanlang'}</option>
                {groupsInGrade.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.display_name}
                  </option>
                ))}
              </Select>
              <Select
                label={t('schedule.weekday')}
                value={weekday}
                disabled={!group}
                onChange={(event) => setWeekday(event.target.value)}
              >
                {WEEKDAYS.map((day) => (
                  <option key={day.value} value={String(day.value)}>
                    {day.label}
                  </option>
                ))}
              </Select>
            </div>
          )}
        </CardBody>
      </Card>

      {group ? (
        <Card>
          <CardHeader
            title={`${groupsInGrade.find((row) => row.id === group)?.display_name ?? ''} · ${
              WEEKDAYS.find((day) => String(day.value) === weekday)?.label ?? ''
            }`}
            description={`${entries.length} ta dars`}
          />

          <CardBody className="space-y-4">
            {groupSubjects.length === 0 ? (
              <EmptyState
                title={t('schedule.noSubjects')}
                description={t('schedule.noSubjectsHint')}
              />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
                <Input
                  label={t('schedule.startsAt')}
                  type="time"
                  value={start}
                  onChange={(event) => {
                    setStart(event.target.value)
                    setEnd(addMinutes(event.target.value, LESSON_MINUTES))
                  }}
                />
                <Input
                  label={t('schedule.endsAt')}
                  type="time"
                  value={end}
                  onChange={(event) => setEnd(event.target.value)}
                />
                <Select
                  label={t('schedule.subject')}
                  value={subject}
                  className="lg:col-span-2"
                  onChange={(event) => setSubject(event.target.value)}
                >
                  <option value="">{t('person.select')}</option>
                  {groupSubjects.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.display_name}
                    </option>
                  ))}
                </Select>
                <Button disabled={!canAdd} onClick={add}>
                  {t('actions.add')}
                </Button>
                <Input
                  label={t('schedule.room')}
                  value={room}
                  placeholder={t('schedule.optional')}
                  className="lg:col-span-2"
                  onChange={(event) => setRoom(event.target.value)}
                />
              </div>
            )}
          </CardBody>

          {schedule.initialLoading ? (
            <SkeletonRows count={3} />
          ) : entries.length === 0 ? (
            <CardBody>
              <EmptyState title={t('teacher.noLessonThatDay')} />
            </CardBody>
          ) : (
            <ul className="divide-y divide-ink-100 border-t border-ink-100">
              {entries.map((entry) => (
                <li key={entry.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                  <span className="w-7 shrink-0 text-sm font-semibold tabular-nums text-ink-400">
                    {entry.lesson_number}.
                  </span>
                  <span className="w-32 shrink-0 text-sm font-medium tabular-nums text-ink-800">
                    {entry.start_time} — {entry.end_time}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[15px] text-ink-800">{entry.subject_display}</p>
                    <p className="truncate text-xs text-ink-500">
                      {[entry.teacher_name, entry.room && `${entry.room}-xona`]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-600 hover:bg-red-500/15"
                    disabled={busy}
                    onClick={() =>
                      run(() => adminApi.deleteScheduleEntry(entry.id), "O'chirildi")
                    }
                  >
                    {t('actions.delete')}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}
    </div>
  )
}
