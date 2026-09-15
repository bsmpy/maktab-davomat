import { attendanceApi } from '@/api/attendanceApi'
import { useTranslation } from 'react-i18next'
import { Button, ErrorState, Modal, SkeletonRows } from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { CalendarDay } from '@/types/api'
import { formatDuration, formatLateMinutes } from '@/utils/attendance'
import { formatLongDate } from '@/utils/date'

import { PassTimeline, VisitList } from './PassTimeline'

/** Clicking a calendar day opens that day's full gate record. */
export function DayDetailModal({
  childId,
  day,
  onClose,
  onSubmitReason,
}: {
  childId: string
  day: CalendarDay | null
  onClose: () => void
  onSubmitReason?: (date: string) => void
}) {
  const { t } = useTranslation()
  const report = useAsyncData(
    () => attendanceApi.daily(childId, day!.date),
    [childId, day?.date],
    { enabled: Boolean(day) },
  )

  if (!day) return null

  // A reason is worth submitting for a day the pupil missed or came late to.
  const canExplain =
    onSubmitReason &&
    day.is_school_day &&
    (!day.was_present || day.late_minutes > 0) &&
    day.absence_request?.status !== 'PENDING'

  return (
    <Modal
      open
      onClose={onClose}
      title={formatLongDate(day.date)}
      description={
        day.holiday ??
        (day.arrived_too_late
          ? `${day.arrived_at} da kirdi — hisoblanmadi`
          : day.was_present
            ? `${day.first_in ?? '—'} → ${day.is_inside ? 'hozir maktabda' : (day.last_out ?? '—')} · ${formatDuration(day.inside_minutes)}`
            : undefined)
      }
      footer={
        canExplain ? (
          <>
            <Button variant="secondary" onClick={onClose}>
              {t('common.close')}
            </Button>
            <Button onClick={() => onSubmitReason?.(day.date)}>{t('attendance.submitReason')}</Button>
          </>
        ) : (
          <Button variant="secondary" onClick={onClose}>
            {t('common.close')}
          </Button>
        )
      }
    >
      {day.absence_request ? (
        <div className="mb-4 rounded-xl bg-ink-50 px-4 py-3 text-sm">
          <p className="font-medium text-ink-700">
            Sabab: {day.absence_request.reason} ·{' '}
            <span
              className={
                day.absence_request.status === 'APPROVED'
                  ? 'text-emerald-600'
                  : day.absence_request.status === 'REJECTED'
                    ? 'text-red-600'
                    : 'text-amber-600'
              }
            >
              {day.absence_request.status === 'APPROVED'
                ? 'Tasdiqlangan'
                : day.absence_request.status === 'REJECTED'
                  ? 'Rad etilgan'
                  : "Ko'rib chiqilmoqda"}
            </span>
          </p>
          {day.absence_request.comment ? (
            <p className="mt-1 text-ink-500">{day.absence_request.comment}</p>
          ) : null}
        </div>
      ) : null}

      {day.arrived_too_late ? (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-500/15 px-4 py-3 text-sm text-amber-800">
          <b>{day.arrived_at}</b> da kirdi, lekin davomat uchun juda kech —
          kun <b>kelmagan</b> deb hisoblandi.
        </div>
      ) : null}

      {day.late_minutes > 0 && !day.arrived_too_late ? (
        <div className="mb-4 rounded-xl bg-ink-50 px-4 py-3 text-sm text-ink-700">
          {formatLateMinutes(day.late_minutes)}
        </div>
      ) : null}

      {day.was_present ? (
        <dl className="mb-4 grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-xl border border-ink-100 p-3">
            <dt className="text-xs text-ink-500">{t('attendance.inOut')}</dt>
            <dd className="mt-0.5 font-semibold tabular-nums text-ink-800">
              {day.entries} / {day.exits}
            </dd>
          </div>
          <div className="rounded-xl border border-ink-100 p-3">
            <dt className="text-xs text-ink-500">{t('attendance.outside')}</dt>
            <dd className="mt-0.5 font-semibold tabular-nums text-ink-800">
              {formatDuration(day.outside_minutes)}
            </dd>
          </div>
        </dl>
      ) : null}

      <div className="-mx-5">
        {report.initialLoading ? (
          <SkeletonRows count={4} />
        ) : report.error ? (
          <ErrorState error={report.error} onRetry={report.reload} />
        ) : (
          <>
            <VisitList visits={report.data?.visits} />
            <PassTimeline passes={report.data?.passes} />
          </>
        )}
      </div>
    </Modal>
  )
}
