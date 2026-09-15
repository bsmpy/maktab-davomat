import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { attendanceApi } from '@/api/attendanceApi'
import { AbsenceReasonModal } from '@/features/attendance/AbsenceReasonModal'
import { MonthlyView } from '@/features/attendance/MonthlyView'
import { ParentCalendar } from '@/features/attendance/ParentCalendar'
import { Badge, Card, CardHeader, EmptyState, Skeleton } from '@/components/ui'
import { NoChildState } from '@/components/layout/NoChildState'
import { DayDetailPanel } from '@/features/teacher/DayDetailPanel'
import { LessonRosterView } from '@/features/teacher/LessonRosterView'
import { MonthGrid } from '@/features/teacher/MonthGrid'
import { useAsyncData } from '@/hooks'
import { useAuth } from '@/auth/permissions'
import { useChildStore } from '@/store/childStore'
import { now } from '@/utils/clock'
import { formatShortDate } from '@/utils/date'

const STATUS_LABEL = {
  PENDING: { text: "Ko'rib chiqilmoqda", chip: 'bg-amber-500/15 text-amber-700 ring-amber-600/20' },
  APPROVED: { text: 'Tasdiqlangan', chip: 'bg-emerald-500/15 text-emerald-700 ring-emerald-600/20' },
  REJECTED: { text: 'Rad etilgan', chip: 'bg-red-500/15 text-red-700 ring-red-600/20' },
} as const

export function CalendarPage() {
  const { t } = useTranslation()
  const activeChildId = useChildStore((state) => state.activeChildId)
  const { isActing } = useAuth()
  const [params, setParams] = useSearchParams()
  const [reasonDate, setReasonDate] = useState<string | null>(null)

  const today = now()
  const year = Number(params.get('year')) || today.getFullYear()
  const month = Number(params.get('month')) || today.getMonth() + 1
  // Staff share one calendar; the server decides how wide it reaches — a
  // teacher sees the classes they teach, a curator their groups, an
  // administrator the whole school.
  const isStaff = !isActing('OTA-ONA')

  const requests = useAsyncData(
    () => attendanceApi.absenceRequests(activeChildId!),
    [activeChildId],
    { enabled: Boolean(activeChildId) && !isStaff },
  )

  function update(next: Record<string, string>) {
    const merged = new URLSearchParams(params)
    Object.entries(next).forEach(([key, value]) => {
      if (value) merged.set(key, value)
      else merged.delete(key)
    })
    // Push rather than replace: every step the user takes is its own history
    // entry, so the browser's Back button undoes exactly one of them.
    setParams(merged)
  }

  // The staff calendar is the month beside a detail panel: the day chooses what
  // the panel shows, and the panel walks groups → subjects in place.
  if (isStaff) {
    const day = params.get('kun')
    const group = params.get('sinf')
    const subject = params.get('fan')

    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('nav.calendar')}</h1>

        {subject && day ? (
          <LessonRosterView
            subjectId={subject}
            date={day}
            onBack={() => update({ fan: '' })}
          />
        ) : (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_380px] 2xl:grid-cols-[minmax(0,1fr)_420px]">
            <MonthGrid
              year={year}
              month={month}
              selected={day}
              onMonthChange={(nextYear, nextMonth) =>
                update({
                  year: String(nextYear),
                  month: String(nextMonth),
                  kun: '',
                  sinf: '',
                  fan: '',
                })
              }
              onSelect={(date) => update({ kun: date, sinf: '', fan: '' })}
              onPickToday={(date) => {
                const [nextYear, nextMonth] = date.split('-')
                update({ year: nextYear!, month: String(Number(nextMonth)), kun: date, sinf: '', fan: '' })
              }}
            />
            <DayDetailPanel
              date={day}
              classGroupId={group}
              onPickClass={(id) => update({ sinf: id })}
              onBack={() => update({ sinf: '' })}
              onOpenSubject={(subjectId) => update({ fan: subjectId })}
            />
          </div>
        )}
      </div>
    )
  }

  if (!activeChildId) {
    return <NoChildState />
  }

  const parentDay = params.get('kun')

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('nav.calendar')}</h1>

      {/* The same month-plus-panel the staff see, scoped to this child. */}
      <ParentCalendar
        childId={activeChildId}
        year={year}
        month={month}
        selected={parentDay}
        onMonthChange={(nextYear, nextMonth) =>
          update({ year: String(nextYear), month: String(nextMonth), kun: '' })
        }
        onSelect={(date) => update({ kun: date })}
      />

      <MonthlyView
        childId={activeChildId}
        year={year}
        month={month}
        useCalendarEndpoint
        onMonthChange={(nextYear, nextMonth) =>
          update({ year: String(nextYear), month: String(nextMonth) })
        }
        onSubmitReason={setReasonDate}
      />

      <Card>
        <CardHeader
          title={t('attendance.sentReasons')}
          description={t('attendance.sentReasonsHint')}
        />
        {requests.initialLoading ? (
          <div className="space-y-3 p-5">
            <Skeleton className="h-14 w-full rounded-xl" />
            <Skeleton className="h-14 w-full rounded-xl" />
          </div>
        ) : (requests.data?.length ?? 0) === 0 ? (
          <EmptyState
            title={t('attendance.noReasons')}
            description={t('attendance.noReasonsHint')}
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {requests.data!.map((request) => {
              const label = STATUS_LABEL[request.status]
              return (
                <li key={request.id} className="flex items-start gap-4 px-5 py-3.5">
                  <div className="min-w-0 flex-1">
                    <p className="text-[15px] font-medium text-ink-800">
                      {formatShortDate(request.date)} · {request.reason_name}
                    </p>
                    {request.comment ? (
                      <p className="mt-0.5 text-sm text-ink-500">{request.comment}</p>
                    ) : null}
                    {request.review_comment ? (
                      <p className="mt-1 text-sm text-ink-500">Javob: {request.review_comment}</p>
                    ) : null}
                  </div>
                  <Badge className={label.chip}>{label.text}</Badge>
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      <AbsenceReasonModal
        childId={activeChildId}
        date={reasonDate}
        onClose={() => setReasonDate(null)}
        onSubmitted={requests.reload}
      />
    </div>
  )
}
