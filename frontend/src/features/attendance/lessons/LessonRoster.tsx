import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { toApiError } from '@/api/errors'
import { teachingApi } from '@/api/teachingApi'
import {
  Avatar,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  SkeletonRows,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type {
  LessonMark,
  LessonRoster as LessonRosterData,
  LessonRosterStudent,
  LessonStatus,
} from '@/types/api'
import { cn } from '@/utils/cn'
import { LESSON_STATUS_META } from '@/utils/attendance'
import { formatLongDate } from '@/utils/date'

import { rosterClosedMessage } from './rosterWindow'

/** The four buttons on every row, in the order a teacher reaches for them. */
const CHOICES: { value: Exclude<LessonStatus, null>; label: string }[] = [
  { value: 'PRESENT', label: 'Keldi' },
  { value: 'LATE', label: 'Kechikdi' },
  { value: 'ABSENT', label: 'Kelmadi' },
]

type Draft = {
  status: LessonStatus
  late_minutes: number
  comment: string
  /** Kelmadi splits in two, and the choice decides which status is sent. */
  excused: boolean
}

function draftOf(student: LessonRosterStudent): Draft {
  return {
    status: student.status,
    late_minutes: student.late_minutes,
    comment: student.comment,
    excused: student.status === 'EXCUSED',
  }
}

/** What the row means once "kelmadi" has been split into sababli/sababsiz. */
function resolved(draft: Draft): LessonStatus {
  if (draft.status === 'ABSENT' || draft.status === 'EXCUSED') {
    return draft.excused ? 'EXCUSED' : 'ABSENT'
  }
  return draft.status
}

function isComplete(draft: Draft): boolean {
  const status = resolved(draft)
  if (status === 'LATE') return draft.late_minutes > 0
  if (status === 'EXCUSED') return draft.comment.trim().length > 0
  return true
}

/**
 * One subject on one day: the class list, and a mark for each pupil.
 *
 * Everything is edited locally and saved in one request — a teacher goes down
 * the register in a few seconds and should not wait for the network between
 * two names.
 */
export function LessonRoster({
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
  const [loaded, setLoaded] = useState<LessonRosterData | null>(null)
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [saving, setSaving] = useState(false)

  // Whenever a different day or subject arrives, the working copy starts again
  // from what the server holds. Adjusting during render (rather than in an
  // effect) means the list never paints one frame with the previous marks.
  if (roster.data && roster.data !== loaded) {
    setLoaded(roster.data)
    setDrafts(Object.fromEntries(roster.data.students.map((row) => [row.id, draftOf(row)])))
  }

  function update(id: string, patch: Partial<Draft>) {
    if (locked) return
    setDrafts((current) => ({ ...current, [id]: { ...current[id], ...patch } }))
  }

  function choose(id: string, value: Exclude<LessonStatus, null>) {
    if (locked) return
    const current = drafts[id]
    // Tapping the same button again clears the mark.
    if (current && resolved(current) === value && value !== 'ABSENT') {
      update(id, { status: null, late_minutes: 0, comment: '' })
      return
    }
    if (value === 'ABSENT') {
      if (current?.status === 'ABSENT' || current?.status === 'EXCUSED') {
        update(id, { status: null, late_minutes: 0, comment: '', excused: false })
        return
      }
      update(id, { status: 'ABSENT', late_minutes: 0, excused: false })
      return
    }
    update(id, {
      status: value,
      comment: '',
      late_minutes: value === 'LATE' ? current?.late_minutes || 0 : 0,
    })
  }

  const students = roster.data?.students ?? []
  // Before the lesson starts there is nothing to record, so the register is
  // read-only: the buttons are visible but inert, and Saqlash is off.
  const locked = roster.data ? !roster.data.can_mark : false
  const opensAt = roster.data?.opens_at ?? null
  const rows = students.map((student) => ({ student, draft: drafts[student.id] }))
  const incomplete = rows.filter(({ draft }) => draft && draft.status && !isComplete(draft))
  const markedCount = rows.filter(({ draft }) => draft?.status).length

  async function save() {
    setSaving(true)
    try {
      const marks: LessonMark[] = rows.map(({ student, draft }) => ({
        student: student.id,
        status: draft?.status ? (resolved(draft) ?? '') : '',
        late_minutes: draft?.late_minutes ?? 0,
        comment: draft?.comment ?? '',
      }))
      await teachingApi.saveMarks(subjectId, date, marks)
      toast.success(t('teacher.marksSaved'))
      roster.reload()
    } catch (error) {
      toast.error(t('teacher.saveFailed'), toApiError(error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title={roster.data?.subject.display_name ?? 'Dars davomati'}
        description={`${formatLongDate(date)} · ${markedCount} / ${students.length} belgilandi`}
        action={
          <Button variant="secondary" size="sm" onClick={onBack}>
            {t('actions.back')}
          </Button>
        }
      />

      {roster.initialLoading ? (
        <SkeletonRows count={5} />
      ) : rosterClosedMessage(roster.error) ? (
        // Reached by a link or an old tab before the bell: the server does not
        // hand the list out, and this says when it will instead of offering a
        // retry that can only fail again.
        <CardBody>
          <div className="rounded-xl border border-amber-200 bg-amber-500/15 px-4 py-3 text-sm text-amber-800">
            {rosterClosedMessage(roster.error)}
          </div>
        </CardBody>
      ) : roster.error ? (
        <ErrorState error={roster.error} onRetry={roster.reload} />
      ) : students.length === 0 ? (
        <CardBody>
          <EmptyState
            title={t('teacher.noPupilsInClass')}
            description={t('teacher.addPupilsHint')}
          />
        </CardBody>
      ) : (
        <>
          {locked ? (
            <div className="mx-5 mb-1 rounded-xl border border-amber-200 bg-amber-500/15 px-4 py-3 text-sm text-amber-800">
              {t('teacher.notStartedYet')} <b>{opensAt}</b> dan keyin belgilash mumkin.
            </div>
          ) : null}

          <ul className="divide-y divide-ink-100">
            {rows.map(({ student, draft }) => {
              const status = draft ? resolved(draft) : null
              const meta = status ? LESSON_STATUS_META[status] : null
              return (
                <li key={student.id} className="px-4 py-3.5 sm:px-5">
                  <div className="flex flex-wrap items-center gap-3">
                    <Avatar
                      name={student.full_name}
                      initials={student.initials}
                      src={student.photo ?? undefined}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[15px] font-medium text-ink-800">
                        {student.full_name}
                      </p>
                      <p className="text-xs text-ink-500">
                        {meta ? t(meta.labelKey) : 'Belgilanmagan'}
                      </p>
                    </div>

                    {/* A phone puts the three choices on their own row, one
                        third each and tall enough to hit; from `sm` they sit
                        inline beside the name as before. */}
                    <div className="grid w-full grid-cols-3 gap-1.5 sm:flex sm:w-auto sm:flex-wrap">
                      {CHOICES.map((choice) => {
                        const active =
                          choice.value === 'ABSENT'
                            ? status === 'ABSENT' || status === 'EXCUSED'
                            : status === choice.value
                        return (
                          <button
                            key={choice.value}
                            type="button"
                            aria-pressed={active}
                            disabled={locked}
                            onClick={() => choose(student.id, choice.value)}
                            className={cn(
                              'min-h-[44px] rounded-xl border px-2 py-1.5 text-sm font-medium transition sm:min-h-0 sm:px-3',
                              active
                                ? LESSON_STATUS_META[choice.value].chip
                                : 'border-ink-200 text-ink-600 hover:bg-ink-50',
                              locked && 'cursor-not-allowed opacity-50 hover:bg-transparent',
                            )}
                          >
                            {choice.label}
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  {/* Kechikdi asks how long; kelmadi asks whether there was a
                      reason, and then for the reason itself. */}
                  {draft && status === 'LATE' ? (
                    <div className="mt-3 flex flex-wrap items-end gap-3 sm:pl-1">
                      <Input
                        label={t('teacher.lateMinutes')}
                        inputMode="numeric"
                        disabled={locked}
                        className="w-full sm:w-44"
                        value={draft.late_minutes ? String(draft.late_minutes) : ''}
                        placeholder="0"
                        error={draft.late_minutes > 0 ? undefined : 'Daqiqani kiriting'}
                        onChange={(event) =>
                          update(student.id, {
                            late_minutes: Math.min(
                              Number(event.target.value.replace(/\D/g, '')) || 0,
                              600,
                            ),
                          })
                        }
                      />
                    </div>
                  ) : null}

                  {draft && (status === 'ABSENT' || status === 'EXCUSED') ? (
                    <div className="mt-3 space-y-3 pl-1">
                      <div className="grid grid-cols-2 gap-1.5 sm:flex sm:flex-wrap">
                        {[
                          { value: true, label: 'Sababli' },
                          { value: false, label: 'Sababsiz' },
                        ].map((option) => (
                          <button
                            key={String(option.value)}
                            type="button"
                            aria-pressed={draft.excused === option.value}
                            disabled={locked}
                            onClick={() =>
                              update(student.id, {
                                excused: option.value,
                                comment: option.value ? draft.comment : '',
                              })
                            }
                            className={cn(
                              'min-h-[44px] rounded-xl border px-3 py-1.5 text-sm transition sm:min-h-0',
                              draft.excused === option.value
                                ? option.value
                                  ? LESSON_STATUS_META.EXCUSED.chip
                                  : LESSON_STATUS_META.ABSENT.chip
                                : 'border-ink-200 text-ink-600 hover:bg-ink-50',
                            )}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>

                      {draft.excused ? (
                        <Input
                          label={t('teacher.reason')}
                          disabled={locked}
                          value={draft.comment}
                          placeholder={t('teacher.reasonExample')}
                          maxLength={255}
                          error={draft.comment.trim() ? undefined : 'Sababini yozing'}
                          onChange={(event) =>
                            update(student.id, { comment: event.target.value })
                          }
                        />
                      ) : null}
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ul>

          {/* Sticky on a phone: a class of thirty is far longer than a screen,
              and Saqlash has to stay in reach of the row being marked. */}
          <CardBody className="sticky bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-10 flex flex-wrap items-center gap-2 rounded-b-2xl border-t border-ink-100 bg-surface/95 backdrop-blur sm:static sm:gap-3 sm:bg-transparent sm:backdrop-blur-none">
            <Button
              className="flex-1 sm:flex-none"
              loading={saving}
              disabled={locked || incomplete.length > 0}
              onClick={save}
            >
              {t('actions.save')}
            </Button>
            <Button
              className="flex-1 sm:flex-none"
              variant="secondary"
              disabled={locked || saving}
              onClick={() =>
                setDrafts(Object.fromEntries(students.map((row) => [row.id, draftOf(row)])))
              }
            >
              {t('actions.cancel')}
            </Button>
            {locked ? (
              <span className="text-sm text-amber-700">
                Dars {opensAt} da boshlanadi
              </span>
            ) : incomplete.length > 0 ? (
              <span className="text-sm text-amber-700">
                {incomplete.length} ta qatorni to‘ldiring
              </span>
            ) : null}
          </CardBody>
        </>
      )}
    </Card>
  )
}
