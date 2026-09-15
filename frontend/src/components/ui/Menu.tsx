import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'

import { cn } from '@/utils/cn'

/**
 * A dropdown panel anchored to a trigger.
 *
 * The navbar grew three of these — account, language, theme — and each one
 * needs the same three behaviours: close on a second click, on a click outside,
 * and on Escape. They live here once rather than three times.
 */
export function Menu({
  trigger,
  children,
  align = 'right',
  width = 'w-52',
  label,
}: {
  /** Receives the open state so the trigger can show a caret, a ring, etc. */
  trigger: (state: { open: boolean; toggle: () => void; id: string }) => ReactNode
  children: (state: { close: () => void }) => ReactNode
  align?: 'left' | 'right'
  width?: string
  label?: string
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const id = useId()

  const close = useCallback(() => setOpen(false), [])

  /* Closing must not drop focus on <body>. Restoring it belongs in an effect:
     the panel is still mounted while the click that closed it is handled, and
     only focus that was inside the menu is ours to move back. */
  const wasOpen = useRef(false)
  useEffect(() => {
    const container = containerRef.current
    const focus = document.activeElement
    const ours = focus === document.body || (!!container && container.contains(focus))
    if (wasOpen.current && !open && ours) {
      container?.querySelector<HTMLElement>('[aria-haspopup]')?.focus()
    }
    wasOpen.current = open
  }, [open])

  useEffect(() => {
    if (!open) return
    const onPointer = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, close])

  return (
    <div ref={containerRef} className="relative">
      {trigger({ open, toggle: () => setOpen((value) => !value), id })}

      <div
        role="menu"
        id={id}
        aria-label={label}
        hidden={!open}
        className={cn(
          'absolute z-40 mt-2 rounded-xl border border-ink-200 bg-surface p-1.5 shadow-pop transition duration-150',
          width,
          align === 'right' ? 'right-0 origin-top-right' : 'left-0 origin-top-left',
          open
            ? 'pointer-events-auto translate-y-0 opacity-100'
            : 'pointer-events-none -translate-y-1 opacity-0',
        )}
      >
        {children({ close })}
      </div>
    </div>
  )
}

/** One row of a menu. `active` marks the current choice rather than a hover. */
export function MenuItem({
  onSelect,
  active = false,
  tone = 'default',
  icon,
  children,
}: {
  onSelect: () => void
  active?: boolean
  tone?: 'default' | 'danger'
  icon?: ReactNode
  children: ReactNode
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onSelect}
      className={cn(
        'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition',
        tone === 'danger'
          ? 'text-red-600 hover:bg-red-500/10'
          : 'text-ink-700 hover:bg-ink-100',
        active && tone === 'default' && 'bg-brand-50 text-brand-700',
      )}
    >
      {icon}
      <span className="flex-1 text-left">{children}</span>
    </button>
  )
}
