import { useTranslation } from 'react-i18next'

import { cn } from '@/utils/cn'

import { CheckIcon } from '@/components/ui'

export function StepIndicator({
  steps,
  current,
}: {
  /** Translation keys, not words — the wizard is read in three languages. */
  steps: string[]
  current: number
}) {
  const { t } = useTranslation()
  return (
    <div className="mb-6">
      <ol className="flex items-center gap-1.5">
        {steps.map((key, index) => {
          const done = index < current
          const active = index === current
          return (
            <li key={key} className="flex flex-1 items-center gap-1.5">
              <span
                className={cn(
                  'grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold transition',
                  done && 'bg-brand-600 text-onbrand',
                  active && 'bg-brand-100 text-brand-700 ring-2 ring-brand-500/30',
                  !done && !active && 'bg-ink-100 text-ink-400',
                )}
                aria-current={active ? 'step' : undefined}
              >
                {done ? <CheckIcon width={13} height={13} /> : index + 1}
              </span>
              {index < steps.length - 1 ? (
                <span
                  className={cn(
                    'h-0.5 flex-1 rounded-full transition',
                    done ? 'bg-brand-500' : 'bg-ink-200',
                  )}
                />
              ) : null}
            </li>
          )
        })}
      </ol>
      <p className="mt-3 text-sm font-medium text-ink-600">
        {t('registration.stepOf', {
          index: current + 1,
          name: t(steps[current] ?? ''),
        })}
      </p>
    </div>
  )
}
