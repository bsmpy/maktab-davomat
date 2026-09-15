import { cn } from '@/utils/cn'

export interface Segment<T extends string> {
  value: T
  label: string
}

export function SegmentedControl<T extends string>({
  segments,
  value,
  onChange,
  className,
}: {
  segments: Segment<T>[]
  value: T
  onChange: (value: T) => void
  className?: string
}) {
  return (
    <div
      role="tablist"
      className={cn(
        // On a narrow screen the tabs scroll and snap rather than squeezing
        // into unreadable slivers; from `sm` the control is only as wide as
        // its labels.
        'rail-x w-full gap-1 rounded-xl bg-ink-100 p-1 sm:inline-flex sm:w-auto sm:overflow-visible',
        className,
      )}
    >
      {segments.map((segment) => {
        const active = segment.value === value
        return (
          <button
            key={segment.value}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onChange(segment.value)}
            className={cn(
              'min-h-[40px] flex-1 whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-medium transition sm:flex-none',
              active
                ? 'bg-surface text-ink-900 shadow-sm'
                : 'text-ink-500 hover:text-ink-700',
            )}
          >
            {segment.label}
          </button>
        )
      })}
    </div>
  )
}
