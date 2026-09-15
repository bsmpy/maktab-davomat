import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { AbsenceReasonModal } from '@/features/attendance/AbsenceReasonModal'
import { DailyView } from '@/features/attendance/DailyView'
import { MonthlyView } from '@/features/attendance/MonthlyView'
import { WeeklyView } from '@/features/attendance/WeeklyView'
import { YearlyView } from '@/features/attendance/YearlyView'
import { ClassCards } from '@/features/attendance/lessons/ClassCards'
import { ClassDay } from '@/features/attendance/lessons/ClassDay'
import { LessonRoster } from '@/features/attendance/lessons/LessonRoster'
import { TeacherLessons } from '@/features/teacher/TeacherLessons'
import { ParentLessons } from '@/features/attendance/lessons/ParentLessons'
import { NoChildState } from '@/components/layout/NoChildState'
import { Button, SegmentedControl } from '@/components/ui'
import { marksLessons } from '@/components/layout/navigation'
import { useAuth } from '@/auth/permissions'
import { useChildStore } from '@/store/childStore'
import { now } from '@/utils/clock'
import {
  academicYearRange,
  formatLongDate,
  monthName,
  monthRange,
  todayISO,
  weekRange,
} from '@/utils/date'

type Period = 'daily' | 'weekly' | 'monthly' | 'yearly'
/** Which register is on screen: the school gate, or the lessons. */
type Kind = 'school' | 'lessons'

const KINDS: { value: Kind; label: string }[] = [
  { value: 'school', label: 'Maktab davomati' },
  { value: 'lessons', label: 'Dars davomati' },
]

const SEGMENTS: { value: Period; label: string }[] = [
  { value: 'daily', label: 'Kunlik' },
  { value: 'weekly', label: 'Haftalik' },
  { value: 'monthly', label: 'Oylik' },
  { value: 'yearly', label: 'Yillik' },
]

/**
 * One attendance module with two switches.
 *
 * *Maktab davomati* is the turnstile: when the pupil walked in and out. *Dars
 * davomati* is what the teacher marked lesson by lesson — the same page serves
 * both sides of it, the register for whoever fills it in and the read-only
 * report for the family.
 */
export function AttendancePage() {
  const { t } = useTranslation()
  const activeChildId = useChildStore((state) => state.activeChildId)
  const { user, isActing } = useAuth()
  const [params, setParams] = useSearchParams()
  const [reasonDate, setReasonDate] = useState<string | null>(null)

  const canMark = marksLessons(user)
  // A teacher's Davomat is only ever the lesson register: no gate report to
  // switch to, and no child of their own to report on.
  const isTeacher = isActing('TEACHER')
  const kind = isTeacher ? 'lessons' : ((params.get('kind') as Kind) ?? 'school')
  const period = (params.get('period') as Period) ?? 'daily'
  const date = params.get('date') ?? todayISO()
  // The teacher drills down: classes → one class's day → one lesson.
  const openClass = params.get('sinf')
  const openSubject = params.get('fan')
  const today = now()
  const year = Number(params.get('year')) || today.getFullYear()
  const month = Number(params.get('month')) || today.getMonth() + 1

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

  if (isTeacher) {
    return (
      <div className="space-y-5">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('nav.attendance')}</h1>
        {openSubject ? (
          <LessonRoster subjectId={openSubject} date={date} onBack={() => update({ fan: '' })} />
        ) : (
          <TeacherLessons
            date={date}
            onDateChange={(value) => update({ date: value })}
            onOpen={(subjectId) => update({ fan: subjectId })}
          />
        )}
      </div>
    )
  }

  // An administrator standing in for a teacher has no child of their own; only
  // the school register needs one.
  if (!activeChildId && !(kind === 'lessons' && canMark)) {
    return canMark ? (
      <div className="space-y-5">
        <Header
          kind={kind}
          canSubmitReason={false}
          onKindChange={(value) => update({ kind: value, sinf: '', fan: '' })}
          onSubmitReason={() => setReasonDate(todayISO())}
        />
        <NoChildState />
      </div>
    ) : (
      <NoChildState />
    )
  }

  /** The range the lesson report should cover for the chosen period. */
  const lessonRange =
    period === 'weekly'
      ? { ...weekRange(date), includeDays: true, title: 'Hafta bo‘yicha darslar' }
      : period === 'monthly'
        ? {
            ...monthRange(year, month),
            includeDays: true,
            title: `${monthName(month)} · darslar`,
          }
        : period === 'yearly'
          ? { ...academicYearRange(date), includeDays: false, title: "O'quv yili" }
          : { start: date, end: date, includeDays: true, title: formatLongDate(date) }

  return (
    <div className="space-y-5">
      <Header
        kind={kind}
        canSubmitReason={Boolean(activeChildId)}
        onKindChange={(value) => update({ kind: value, sinf: '', fan: '' })}
        onSubmitReason={() => setReasonDate(todayISO())}
      />

      {/* The teacher's register is per day, so the period switch only belongs
          to the reports. */}
      {kind === 'school' || !canMark ? (
        <SegmentedControl
          segments={SEGMENTS}
          value={period}
          onChange={(value) => update({ period: value })}
        />
      ) : null}

      {kind === 'lessons' && canMark ? (
        openSubject ? (
          <LessonRoster subjectId={openSubject} date={date} onBack={() => update({ fan: '' })} />
        ) : openClass ? (
          <ClassDay
            classGroupId={openClass}
            date={date}
            onBack={() => update({ sinf: '' })}
            onOpenLesson={(subjectId) => update({ fan: subjectId })}
          />
        ) : (
          <ClassCards
            date={date}
            onDateChange={(value) => update({ date: value })}
            onOpen={(classGroupId) => update({ sinf: classGroupId })}
          />
        )
      ) : null}

      {kind === 'lessons' && !canMark && activeChildId ? (
        <ParentLessons
          childId={activeChildId}
          start={lessonRange.start}
          end={lessonRange.end}
          includeDays={lessonRange.includeDays}
          title={lessonRange.title}
        />
      ) : null}

      {kind === 'school' && activeChildId ? (
        <>
          {period === 'daily' ? (
            <DailyView
              childId={activeChildId}
              date={date}
              onDateChange={(value) => update({ date: value })}
            />
          ) : null}

          {period === 'weekly' ? (
            <WeeklyView
              childId={activeChildId}
              date={date}
              onDateChange={(value) => update({ date: value })}
            />
          ) : null}

          {period === 'monthly' ? (
            <MonthlyView
              childId={activeChildId}
              year={year}
              month={month}
              onMonthChange={(nextYear, nextMonth) =>
                update({ year: String(nextYear), month: String(nextMonth) })
              }
              onSubmitReason={setReasonDate}
            />
          ) : null}

          {period === 'yearly' ? <YearlyView childId={activeChildId} /> : null}
        </>
      ) : null}

      {activeChildId ? (
        <AbsenceReasonModal
          childId={activeChildId}
          date={reasonDate}
          onClose={() => setReasonDate(null)}
        />
      ) : null}
    </div>
  )
}

function Header({
  kind,
  canSubmitReason,
  onKindChange,
  onSubmitReason,
}: {
  kind: Kind
  canSubmitReason: boolean
  onKindChange: (kind: Kind) => void
  onSubmitReason: () => void
}) {
  const { t } = useTranslation()
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('nav.attendance')}</h1>
        {canSubmitReason ? (
          <Button variant="secondary" size="sm" onClick={onSubmitReason}>
            {t('attendance.submitReason')}
          </Button>
        ) : null}
      </div>

      <SegmentedControl segments={KINDS} value={kind} onChange={onKindChange} />
    </>
  )
}
