import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui'
import { cn } from '@/utils/cn'

/**
 * One lesson, as a card.
 *
 * Davomat and the calendar show the same thing — a subject, its class and when
 * it runs — so they show it the same way; only the button on the bottom differs
 * (mark it, or look at it).
 */
export function LessonCard({
  subject,
  classGroup,
  startTime,
  endTime,
  room,
  action,
  disabled = false,
  disabledTitle,
  hint,
  onAction,
}: {
  subject: string
  classGroup: string
  startTime: string | null
  endTime: string | null
  room?: string
  action: string
  disabled?: boolean
  disabledTitle?: string
  hint?: ReactNode
  onAction: () => void
}) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col rounded-2xl border border-ink-200 bg-surface p-4">
      <p className="truncate text-[15px] font-semibold text-ink-900">{subject}</p>
      <p className="mt-0.5 text-sm text-ink-500">{classGroup}</p>

      <p className="mt-3 text-sm font-medium tabular-nums text-ink-700">
        {startTime ? (
          <>
            {startTime} - {endTime}
            {room ? <span className="ml-2 font-normal text-ink-400">{room}-xona</span> : null}
          </>
        ) : (
          <span className="font-normal text-ink-400">{t('teacher.noLessonTime')}</span>
        )}
      </p>

      <div className="mt-4 flex items-center gap-2">
        <Button
          size="sm"
          disabled={disabled}
          title={disabled ? disabledTitle : undefined}
          className={cn(disabled && 'cursor-not-allowed')}
          onClick={onAction}
        >
          {action}
        </Button>
        {hint}
      </div>
    </div>
  )
}

/** The grid both lists sit in, so the columns match at every width. */
export function LessonGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">{children}</div>
}
