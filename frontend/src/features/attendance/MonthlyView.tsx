import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { attendanceApi } from '@/api/attendanceApi'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  ChevronLeftIcon,
  ChevronRightIcon,
  ErrorState,
  Skeleton,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { CalendarDay } from '@/types/api'
import { shiftMonth } from '@/utils/date'

import { SummaryCards } from '../dashboard/SummaryCards'

import { CalendarGrid, CalendarLegend } from './CalendarGrid'
import { DayDetailModal } from './DayDetailModal'

export function MonthlyView({
  childId,
  year,
  month,
  onMonthChange,
  useCalendarEndpoint = false,
  onSubmitReason,
}: {
  childId: string
  year: number
  month: number
  onMonthChange: (year: number, month: number) => void
  /** The Kalendar page needs holiday + reason annotations; Davomat does not. */
  useCalendarEndpoint?: boolean
  onSubmitReason?: (date: string) => void
}) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<CalendarDay | null>(null)
  const report = useAsyncData(
    () =>
      useCalendarEndpoint
        ? attendanceApi.calendar(childId, year, month)
        : attendanceApi.monthly(childId, year, month),
    [childId, year, month, useCalendarEndpoint],
  )

  if (report.initialLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-[420px] w-full rounded-2xl" />
      </div>
    )
  }

  if (report.error) {
    return (
      <Card>
        <ErrorState error={report.error} onRetry={report.reload} />
      </Card>
    )
  }

  const data = report.data!

  return (
    <div className="space-y-4">
      <SummaryCards summary={data.summary} />

      <Card>
        <CardHeader
          title={`${data.month_name} ${data.year}`}
          description={t('attendance.clickDay')}
          action={
            <div className="flex items-center gap-1">
              <Button
                variant="secondary"
                size="sm"
                aria-label={t('attendance.prevMonth')}
                onClick={() => {
                  const next = shiftMonth(year, month, -1)
                  onMonthChange(next.year, next.month)
                }}
              >
                <ChevronLeftIcon width={18} height={18} />
              </Button>
              <Button
                variant="secondary"
                size="sm"
                aria-label={t('attendance.nextMonth')}
                onClick={() => {
                  const next = shiftMonth(year, month, 1)
                  onMonthChange(next.year, next.month)
                }}
              >
                <ChevronRightIcon width={18} height={18} />
              </Button>
            </div>
          }
        />
        <CardBody>
          <CalendarGrid
            report={data}
            selectedDate={selected?.date}
            onSelectDay={(day) => setSelected(day)}
          />
          <div className="mt-5 border-t border-ink-100 pt-4">
            <CalendarLegend />
          </div>
        </CardBody>
      </Card>

      <DayDetailModal
        childId={childId}
        day={selected}
        onClose={() => setSelected(null)}
        onSubmitReason={
          onSubmitReason
            ? (date) => {
                setSelected(null)
                onSubmitReason(date)
              }
            : undefined
        }
      />
    </div>
  )
}
