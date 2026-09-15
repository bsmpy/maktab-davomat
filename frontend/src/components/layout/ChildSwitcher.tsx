import { useEffect, useRef, useState } from 'react'

import { useChildStore } from '@/store/childStore'
import { formatRate, RATE_TONE_CLASS, rateTone } from '@/utils/attendance'
import { cn } from '@/utils/cn'

import { Avatar, CheckIcon, ChevronDownIcon } from '../ui'

/**
 * Top-of-page child selector. Switching updates the shared store, and every
 * page reads `activeChildId` from it — so the whole cabinet follows along.
 */
export function ChildSwitcher({ className }: { className?: string }) {
  const children = useChildStore((state) => state.children)
  const activeChildId = useChildStore((state) => state.activeChildId)
  const setActiveChild = useChildStore((state) => state.setActiveChild)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const active = children.find((child) => child.id === activeChildId)
  if (!active) return null

  const single = children.length === 1

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <button
        type="button"
        onClick={() => !single && setOpen((value) => !value)}
        aria-haspopup={single ? undefined : 'listbox'}
        aria-expanded={open}
        className={cn(
          'flex w-full items-center gap-3 rounded-xl border border-ink-200 bg-surface px-3 py-2 text-left transition',
          !single && 'hover:border-ink-300 hover:shadow-sm',
          single && 'cursor-default',
        )}
      >
        <Avatar name={active.full_name} initials={active.initials} size="sm" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-ink-800">
            {active.display_name}
          </span>
          <span className="block truncate text-xs text-ink-500">
            {active.class_group} sinf
            {active.relation_label ? ` · ${active.relation_label}` : ''}
          </span>
        </span>
        {!single ? (
          <ChevronDownIcon
            width={18}
            height={18}
            className={cn('shrink-0 text-ink-400 transition-transform', open && 'rotate-180')}
          />
        ) : null}
      </button>

      {open ? (
        <div
          role="listbox"
          className="absolute left-0 right-0 z-40 mt-2 animate-slide-up overflow-hidden rounded-xl border border-ink-200 bg-surface p-1.5 shadow-pop"
        >
          {children.map((child) => {
            const selected = child.id === active.id
            const rate = child.current_month?.rate ?? 0
            return (
              <button
                key={child.id}
                role="option"
                aria-selected={selected}
                type="button"
                onClick={() => {
                  setActiveChild(child.id)
                  setOpen(false)
                }}
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition',
                  selected ? 'bg-brand-50' : 'hover:bg-ink-50',
                )}
              >
                <Avatar name={child.full_name} initials={child.initials} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink-800">
                    {child.display_name}
                  </span>
                  <span className="block text-xs text-ink-500">{child.class_group} sinf</span>
                </span>
                {child.current_month ? (
                  <span
                    className={cn(
                      'shrink-0 text-xs font-semibold tabular-nums',
                      RATE_TONE_CLASS[rateTone(rate)],
                    )}
                  >
                    {formatRate(rate)}
                  </span>
                ) : null}
                {selected ? (
                  <CheckIcon width={16} height={16} className="shrink-0 text-brand-600" />
                ) : null}
              </button>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
