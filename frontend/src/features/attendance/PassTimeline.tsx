import type { GatePass, Visit } from '@/types/api'
import { useTranslation } from 'react-i18next'
import { DIRECTION_META, formatDuration } from '@/utils/attendance'
import { cn } from '@/utils/cn'

import { EmptyState } from '@/components/ui'

/**
 * The day at the gate: every pass the turnstile recorded, in order. This is the
 * raw record the rest of the report is derived from, so it is shown verbatim.
 */
export function PassTimeline({ passes }: { passes: GatePass[] | undefined }) {
  const { t } = useTranslation()
  if (!passes?.length) {
    return (
      <EmptyState
        title={t('attendance.noPasses')}
        description={t('attendance.noPassesHint')}
      />
    )
  }

  return (
    <ol className="divide-y divide-ink-100 border-t border-ink-100">
      {(passes ?? []).map((pass) => {
        const meta = DIRECTION_META[pass.direction] ?? DIRECTION_META.UNKNOWN
        return (
          <li key={pass.id} className="flex items-center gap-4 px-5 py-3.5">
            <span aria-hidden className="text-base">
              {meta.emoji}
            </span>
            <span className="w-14 shrink-0 text-[15px] font-semibold tabular-nums text-ink-800">
              {pass.time ?? '—'}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[15px] text-ink-800">{t(meta.labelKey)}</p>
              <p className="truncate text-xs text-ink-500">
                {pass.location || pass.terminal}
              </p>
            </div>
            <span
              className={cn(
                'shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset',
                meta.chip,
              )}
            >
              {t(meta.labelKey)}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

/** Entry→exit stretches: how long the pupil was inside on each visit. */
export function VisitList({ visits }: { visits: Visit[] | undefined }) {
  if (!visits?.length) return null

  return (
    <ul className="divide-y divide-ink-100 border-t border-ink-100">
      {visits.map((visit, index) => (
        <li key={`${visit.in}-${index}`} className="flex items-center gap-4 px-5 py-3">
          <span className="w-6 shrink-0 text-xs font-semibold tabular-nums text-ink-400">
            {index + 1}
          </span>
          <span className="text-[15px] tabular-nums text-ink-800">
            {visit.in ?? '—'}
            <span className="mx-2 text-ink-300">→</span>
            {visit.out ?? <span className="text-emerald-600">hozir maktabda</span>}
          </span>
          <span className="ml-auto text-sm tabular-nums text-ink-600">
            {formatDuration(visit.minutes)}
          </span>
        </li>
      ))}
    </ul>
  )
}
