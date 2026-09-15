import { RATE_BAR_CLASS, rateTone } from '@/utils/attendance'
import { cn } from '@/utils/cn'

export function ProgressBar({
  value,
  className,
  tone,
}: {
  value: number
  className?: string
  tone?: 'good' | 'warn' | 'bad'
}) {
  const resolved = tone ?? rateTone(value)
  return (
    <div className={cn('h-2 w-full overflow-hidden rounded-full bg-ink-100', className)}>
      <div
        className={cn('h-full rounded-full transition-all duration-500', RATE_BAR_CLASS[resolved])}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  )
}
