import { cn } from '@/utils/cn'

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
  className,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label?: string
  description?: string
  disabled?: boolean
  className?: string
}) {
  return (
    <label
      className={cn(
        'flex items-start gap-3',
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
        className,
      )}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={cn(
          'relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition',
          checked ? 'bg-brand-600' : 'bg-ink-300',
          !disabled && 'hover:opacity-90',
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-all',
            checked ? 'left-[22px]' : 'left-0.5',
          )}
        />
      </button>
      {label || description ? (
        <span className="min-w-0">
          {label ? (
            <span className="block text-sm font-medium text-ink-800">{label}</span>
          ) : null}
          {description ? (
            <span className="block text-sm text-ink-500">{description}</span>
          ) : null}
        </span>
      ) : null}
    </label>
  )
}
