import type { KeyboardEvent, ReactNode } from 'react'

import { cn } from '@/utils/cn'

/**
 * A card that opens a profile when it is pressed.
 *
 * Not a `<button>`: the card holds buttons of its own — edit, delete — and a
 * button inside a button is invalid HTML that browsers "repair" unpredictably.
 * So it is a `role="button"` region that answers Enter and Space like a real
 * one, and the actions inside it stop the click from reaching the card.
 */
export function ProfileCard({
  onOpen,
  label,
  className,
  children,
}: {
  onOpen: () => void
  /** What a screen reader announces: "Open the profile of …". */
  label: string
  className?: string
  children: ReactNode
}) {
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    // Only the card itself: Enter on an inner button is that button's business.
    if (event.target !== event.currentTarget) return
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onOpen()
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={label}
      onClick={onOpen}
      onKeyDown={onKeyDown}
      className={cn(
        'flex cursor-pointer flex-col rounded-2xl border border-ink-200 bg-surface p-4 text-left transition',
        'hover:border-brand-300 hover:shadow-sm',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-surface',
        className,
      )}
    >
      {children}
    </div>
  )
}
