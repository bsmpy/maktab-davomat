import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { catalogApi } from '@/api/catalogApi'
import { Button, ErrorState, Skeleton } from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { ClassGroup, Grade } from '@/types/api'
import { cn } from '@/utils/cn'

/**
 * Grades and class groups both come from the API — nothing about "1-A … 11-B"
 * is hardcoded in the frontend, so a school can add groups without a redeploy.
 */
export function ClassStep({
  onSelect,
}: {
  onSelect: (grade: Grade, group: ClassGroup) => void
}) {
  const { t } = useTranslation()
  const [grade, setGrade] = useState<Grade | null>(null)
  const grades = useAsyncData(() => catalogApi.grades(), [])
  const groups = useAsyncData(
    () => catalogApi.classGroups(grade!.id),
    [grade?.id],
    { enabled: Boolean(grade) },
  )

  useEffect(() => {
    // Auto-advance when a grade has exactly one group.
    if (grade && groups.data?.length === 1) {
      onSelect(grade, groups.data[0])
    }
  }, [grade, groups.data, onSelect])

  if (grades.initialLoading) {
    return (
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
        {Array.from({ length: 11 }).map((_, index) => (
          <Skeleton key={index} className="h-14 rounded-xl" />
        ))}
      </div>
    )
  }

  if (grades.error) {
    return <ErrorState error={grades.error} onRetry={grades.reload} />
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="label">{t('registration.pickGrade')}</p>
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
          {(grades.data ?? []).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setGrade(item)}
              className={cn(
                'flex h-14 flex-col items-center justify-center rounded-xl border text-sm font-semibold transition',
                grade?.id === item.id
                  ? 'border-brand-500 bg-brand-50 text-brand-700 ring-2 ring-brand-500/20'
                  : 'border-ink-200 bg-surface text-ink-700 hover:border-ink-300 hover:bg-ink-50',
              )}
            >
              {item.level}
              <span className="text-[11px] font-normal text-ink-400">sinf</span>
            </button>
          ))}
        </div>
      </div>

      {grade ? (
        <div className="animate-slide-up">
          <p className="label">{t('registration.pickGroup')}</p>
          {groups.initialLoading ? (
            <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
              {Array.from({ length: 3 }).map((_, index) => (
                <Skeleton key={index} className="h-14 rounded-xl" />
              ))}
            </div>
          ) : groups.error ? (
            <ErrorState error={groups.error} onRetry={groups.reload} />
          ) : groups.data && groups.data.length > 0 ? (
            <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
              {groups.data.map((group) => (
                <Button
                  key={group.id}
                  variant="secondary"
                  className="h-14 text-base font-semibold"
                  onClick={() => onSelect(grade, group)}
                >
                  {group.display_name}
                </Button>
              ))}
            </div>
          ) : (
            <p className="rounded-xl bg-ink-50 px-4 py-3 text-sm text-ink-500">
              {t('registration.noGroups')}
            </p>
          )}
        </div>
      ) : null}
    </div>
  )
}
