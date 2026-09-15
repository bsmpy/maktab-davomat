import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { attendanceApi } from '@/api/attendanceApi'
import { ApiError } from '@/api/errors'
import { Button, Modal, Select } from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import { formatLongDate } from '@/utils/date'

/** "Sabab bildirish" — a parent explains a missed day; staff review it. */
export function AbsenceReasonModal({
  childId,
  date,
  onClose,
  onSubmitted,
}: {
  childId: string
  date: string | null
  onClose: () => void
  onSubmitted?: () => void
}) {
  const { t } = useTranslation()
  const reasons = useAsyncData(() => attendanceApi.reasons(), [], { enabled: Boolean(date) })
  const [reasonId, setReasonId] = useState('')
  const [comment, setComment] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!date) return null

  const selected = reasons.data?.find((item) => item.id === reasonId)
  const commentRequired = selected?.requires_comment ?? false

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!date) return
    setSubmitting(true)
    setError(null)
    try {
      await attendanceApi.submitAbsenceReason(childId, {
        date,
        reason: reasonId,
        comment: comment.trim(),
      })
      toast.success(t('attendance.sent'), "Sabab maktab ma'muriyatiga yuborildi.")
      onSubmitted?.()
      onClose()
      setReasonId('')
      setComment('')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t('attendance.submitReason')}
      description={formatLongDate(date)}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('actions.cancel')}
          </Button>
          <Button
            type="submit"
            form="absence-reason-form"
            loading={submitting}
            disabled={!reasonId || (commentRequired && comment.trim().length === 0)}
          >
            {t('attendance.send')}
          </Button>
        </>
      }
    >
      <form id="absence-reason-form" onSubmit={onSubmit} className="space-y-4" noValidate>
        {error ? (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700"
          >
            {error.message}
          </div>
        ) : null}

        <Select
          name="reason"
          label={t('attendance.reasonType')}
          value={reasonId}
          onChange={(event) => setReasonId(event.target.value)}
          required
        >
          <option value="" disabled>
            {t('person.select')}
          </option>
          {(reasons.data ?? []).map((reason) => (
            <option key={reason.id} value={reason.id}>
              {reason.name}
            </option>
          ))}
        </Select>

        <div>
          <label className="label" htmlFor="comment">
            Izoh {commentRequired ? <span className="text-red-500">*</span> : '(ixtiyoriy)'}
          </label>
          <textarea
            id="comment"
            className="input min-h-[104px] resize-y"
            placeholder={t('attendance.reasonHint')}
            maxLength={1000}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
          />
          {selected?.requires_document ? (
            <p className="mt-1.5 text-sm text-amber-600">
              {t('attendance.documentNeeded')}
            </p>
          ) : null}
        </div>
      </form>
    </Modal>
  )
}
