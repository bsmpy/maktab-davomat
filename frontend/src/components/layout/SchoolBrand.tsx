import { Logo } from '@/components/ui'
import { useTeacherStore } from '@/store/teacherStore'
import { cn } from '@/utils/cn'

/**
 * The school at the head of the sidebar: its logo and its full name.
 *
 * Both come from the school record. A school that has not uploaded a logo
 * falls back to the product mark rather than to an empty box.
 *
 * `compact` is the collapsed rail: the mark alone, centred, with the name kept
 * for screen readers and as a tooltip rather than dropped.
 */
export function SchoolBrand({
  className,
  compact = false,
}: {
  className?: string
  compact?: boolean
}) {
  const school = useTeacherStore((state) => state.profile?.school)
  const name = school?.name ?? 'Maktab davomati'

  return (
    <div
      className={cn('flex items-center gap-3', compact && 'justify-center gap-0', className)}
      title={compact ? name : undefined}
    >
      {school?.logo ? (
        <img
          src={school.logo}
          alt=""
          aria-hidden="true"
          className="h-10 w-10 shrink-0 rounded-xl object-contain"
          draggable={false}
        />
      ) : (
        <Logo size="md" />
      )}

      {compact ? (
        <span className="sr-only">{name}</span>
      ) : (
        <div className="min-w-0">
          <p className="line-clamp-2 text-[13px] font-semibold leading-snug text-ink-900">
            {name}
          </p>
          {school?.short_name ? (
            <p className="truncate text-xs text-ink-500">{school.short_name}</p>
          ) : null}
        </div>
      )}
    </div>
  )
}
