import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { teachingApi } from '@/api/teachingApi'
import {
  ChartIcon,
  SearchIcon,
  Spinner,
  UserIcon,
  UsersIcon,
} from '@/components/ui'
import { useAuth } from '@/auth/permissions'
import { useChildStore } from '@/store/childStore'
import type { SearchHit } from '@/types/api'
import { cn } from '@/utils/cn'

import { navItemsFor } from './navigation'

const KIND_ICON = {
  class: UsersIcon,
  subject: ChartIcon,
  student: UserIcon,
  teacher: UserIcon,
} as const

/** Where a hit takes you. A pupil has no page of their own to open. */
function linkFor(hit: SearchHit): string | null {
  if (hit.kind === 'class') return `/kalendar?sinf=${hit.id}`
  if (hit.kind === 'subject') return `/davomat?fan=${hit.id}`
  return null
}

/**
 * One field for the whole cabinet.
 *
 * Pages match locally and appear instantly; classes, subjects, pupils and
 * colleagues come from `/teaching/search/`, scoped by the server to what this
 * user may already open. Staff only — a parent has no such surface, so for them
 * the field stays a page jumper.
 */
export function NavSearch({
  className,
  autoFocus = false,
  onNavigate,
}: {
  className?: string
  /** Set when the field is opened on purpose, as it is by the phone's search
   *  button — the keyboard should come up with it. */
  autoFocus?: boolean
  /** Fired once the field has taken the user somewhere, so a container that
   *  opened it on purpose can close itself again. */
  onNavigate?: () => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, can } = useAuth()
  const hasChildren = useChildStore((state) => state.children.length > 0)

  const [term, setTerm] = useState('')
  const [open, setOpen] = useState(false)
  const [cursor, setCursor] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const listId = useId()

  const [found, setFound] = useState<{ term: string; rows: SearchHit[] }>({
    term: '',
    rows: [],
  })
  const [searching, setSearching] = useState(false)
  const canSearchData = can('students.view')
  // Results belong to the term they were fetched for: a stale list must not sit
  // under a term the user has already changed.
  const hits = found.term === term.trim() ? found.rows : []

  const items = useMemo(() => navItemsFor({ user, hasChildren }), [user, hasChildren])
  const matches = useMemo(() => {
    const needle = term.trim().toLowerCase()
    if (!needle) return []
    // Matched against what is on screen: someone reading a Russian menu
    // searches for the Russian word.
    return items.filter((item) => t(item.labelKey).toLowerCase().includes(needle))
  }, [items, term, t])

  // A shrinking list must not leave the cursor pointing past its end.
  const active = matches.length ? Math.min(cursor, matches.length - 1) : 0

  // The record search is debounced; the page list needs no round trip.
  useEffect(() => {
    const needle = term.trim()
    if (!canSearchData || needle.length < 2) return
    const timer = setTimeout(() => {
      setSearching(true)
      let cancelled = false
      void teachingApi
        .search(needle)
        .then((rows) => {
          if (!cancelled) setFound({ term: needle, rows })
        })
        // A failed lookup must not take the page jumper down with it.
        .catch(() => setFound({ term: needle, rows: [] }))
        .finally(() => setSearching(false))
      return () => {
        cancelled = true
      }
    }, 250)
    return () => {
      clearTimeout(timer)
      setSearching(false)
    }
  }, [term, canSearchData])

  useEffect(() => {
    if (!open) return
    const onPointer = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    return () => document.removeEventListener('mousedown', onPointer)
  }, [open])

  function go(to: string) {
    navigate(to)
    setTerm('')
    setOpen(false)
    onNavigate?.()
  }

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <SearchIcon
        width={16}
        height={16}
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400"
      />
      <input
        type="search"
        role="combobox"
        autoFocus={autoFocus}
        aria-expanded={open && Boolean(term.trim())}
        aria-controls={`${listId}`}
        aria-autocomplete="list"
        aria-activedescendant={
          matches.length ? `${listId}-${active}` : undefined
        }
        value={term}
        placeholder={t('common.searchPlaceholder')}
        aria-label={t('common.search')}
        onChange={(event) => {
          setTerm(event.target.value)
          setOpen(true)
          setCursor(0)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') return setOpen(false)
          // Enter only acts on a list that is actually on screen.
          if (!open || !matches.length) return
          if (event.key === 'ArrowDown') {
            event.preventDefault()
            setCursor((value) => (value + 1) % matches.length)
          } else if (event.key === 'ArrowUp') {
            event.preventDefault()
            setCursor((value) => (value - 1 + matches.length) % matches.length)
          } else if (event.key === 'Enter') {
            event.preventDefault()
            go(matches[Math.min(cursor, matches.length - 1)]!.to)
          }
        }}
        // 16px on a phone keeps iOS from zooming the page in on focus.
        className="h-10 w-full rounded-xl border border-ink-200 bg-surface-2 pl-9 pr-3 text-base text-ink-800 placeholder:text-ink-400 transition focus:border-brand-400 focus:bg-surface focus:outline-none focus:ring-4 focus:ring-brand-500/10 md:h-9 md:text-sm"
      />

      {open && term.trim() ? (
        <div
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 z-40 mt-2 rounded-xl border border-ink-200 bg-surface p-1.5 shadow-pop"
        >
          {matches.length === 0 && hits.length === 0 ? (
            <p className="px-3 py-2 text-sm text-ink-500">
              {searching ? t('common.loading') : t('common.nothingFound')}
            </p>
          ) : (
            matches.map((item, index) => (
              <button
                key={item.to}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                type="button"
                onMouseEnter={() => setCursor(index)}
                onClick={() => go(item.to)}
                className={cn(
                  'flex min-h-[44px] w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition',
                  index === active ? 'bg-brand-50 text-brand-700' : 'text-ink-700',
                )}
              >
                <item.icon width={16} height={16} />
                {t(item.labelKey)}
              </button>
            ))
          )}

          {hits.length > 0 ? (
            <div className="mt-1 border-t border-ink-200 pt-1">
              {hits.map((hit) => {
                const Icon = KIND_ICON[hit.kind]
                const to = linkFor(hit)
                return (
                  <button
                    key={`${hit.kind}-${hit.id}`}
                    type="button"
                    role="option"
                    aria-selected={false}
                    disabled={!to}
                    onClick={() => to && go(to)}
                    className={cn(
                      'flex min-h-[44px] w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition',
                      to ? 'text-ink-700 hover:bg-ink-100' : 'cursor-default text-ink-600',
                    )}
                  >
                    <Icon width={16} height={16} className="shrink-0 text-ink-400" />
                    <span className="min-w-0 flex-1 truncate">{hit.title}</span>
                    {hit.subtitle ? (
                      <span className="shrink-0 text-xs text-ink-400">{hit.subtitle}</span>
                    ) : null}
                  </button>
                )
              })}
            </div>
          ) : null}

          {searching && matches.length > 0 ? (
            <p className="flex items-center gap-2 px-3 py-2 text-xs text-ink-400">
              <Spinner className="h-3 w-3" />
              {t('common.loading')}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
