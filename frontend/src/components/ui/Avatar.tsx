import { cn } from '@/utils/cn'

/** Deterministic tint so a person always gets the same colour.
 *
 * The tints are opacities of the two themed ramps rather than fixed pale
 * palettes: a stock `bg-rose-100` is a light wash that only works on a light
 * page, and would sit as a bright blob on the four dark themes.
 */
const TINTS = [
  'bg-brand-500/15 text-brand-700',
  'bg-brand-400/20 text-brand-700',
  'bg-accent-500/15 text-accent-700',
  'bg-ink-400/15 text-ink-700',
  'bg-brand-600/15 text-brand-700',
  'bg-accent-400/20 text-accent-700',
]

function tintFor(seed: string): string {
  let hash = 0
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) >>> 0
  }
  return TINTS[hash % TINTS.length]
}

export function Avatar({
  name,
  initials,
  src,
  size = 'md',
  className,
}: {
  name: string
  initials?: string
  /** Photo URL. Falls back to the tinted initials when absent. */
  src?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}) {
  const label =
    initials ??
    name
      .split(' ')
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('')

  if (src) {
    return (
      <img
        src={src}
        alt={name}
        loading="lazy"
        className={cn(
          'shrink-0 rounded-xl object-cover',
          size === 'sm' && 'h-8 w-8',
          size === 'md' && 'h-10 w-10',
          size === 'lg' && 'h-12 w-12',
          className,
        )}
      />
    )
  }

  return (
    <span
      aria-hidden="true"
      className={cn(
        'grid shrink-0 place-items-center rounded-xl font-semibold',
        size === 'sm' && 'h-8 w-8 text-xs',
        size === 'md' && 'h-10 w-10 text-sm',
        size === 'lg' && 'h-12 w-12 text-base',
        tintFor(name),
        className,
      )}
    >
      {label}
    </span>
  )
}
