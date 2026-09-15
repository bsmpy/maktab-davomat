import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, useLocation } from 'react-router-dom'

import { MenuIcon } from '@/components/ui'
import { cn } from '@/utils/cn'

import { useAuth } from '@/auth/permissions'
import { useChildStore } from '@/store/childStore'

import { mobileNavSplit, type NavItem } from './navigation'

/**
 * The phone's navigation: a bottom tab bar, plus a sheet for what does not fit.
 *
 * The bar holds four tabs at most. An administrator's menu is fourteen entries
 * long, and fourteen tabs on a 360px screen are 25px each — unreadable and
 * unhittable. The rest live behind "Yana", which opens a sheet of full-size
 * targets. From `md` up the icon rail takes over and this is gone.
 */
export function MobileNav({ unreadCount }: { unreadCount: number }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const hasChildren = useChildStore((state) => state.children.length > 0)
  const { tabs, overflow } = mobileNavSplit({ user, hasChildren })
  const [sheetOpen, setSheetOpen] = useState(false)
  const { pathname } = useLocation()

  // Escape shuts the sheet, the same contract every other overlay in the
  // cabinet keeps. Navigating shuts it too, from the link's own click — the
  // tabs behind it are under the scrim, so a link in the sheet is the only way
  // out that changes the page.
  useEffect(() => {
    if (!sheetOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSheetOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [sheetOpen])

  // A page reached from the sheet still has to look reached, so the button
  // lights up when the current page is one of the hidden ones.
  const overflowActive = overflow.some((item) =>
    item.to === '/' ? pathname === '/' : pathname.startsWith(item.to),
  )
  // The unread badge follows the notifications entry into the sheet.
  const overflowUnread =
    unreadCount > 0 && overflow.some((item) => item.badge === 'notifications')

  const slots = tabs.length + (overflow.length > 0 ? 1 : 0)

  return (
    <>
      {sheetOpen ? (
        <div
          className="fixed inset-0 z-50 bg-scrim/50 animate-fade-in md:hidden"
          onClick={() => setSheetOpen(false)}
          aria-hidden="true"
        />
      ) : null}

      {sheetOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t('common.menu')}
          className="pb-safe fixed inset-x-0 bottom-0 z-50 max-h-[70dvh] animate-slide-up overflow-y-auto rounded-t-2xl border-t border-ink-200 bg-surface shadow-pop md:hidden"
        >
          <div className="sticky top-0 flex items-center justify-between gap-3 border-b border-ink-100 bg-surface px-5 py-3.5">
            <h2 className="text-base font-semibold text-ink-900">{t('common.menu')}</h2>
            <button
              type="button"
              onClick={() => setSheetOpen(false)}
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-ink-500 transition hover:bg-ink-100 hover:text-ink-900"
            >
              {t('common.close')}
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2 p-4">
            {overflow.map((item) => (
              <SheetLink
                key={item.to}
                item={item}
                unreadCount={unreadCount}
                onNavigate={() => setSheetOpen(false)}
              />
            ))}
          </div>
        </div>
      ) : null}

      <nav
        aria-label={t('common.mainMenu')}
        className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-ink-200 bg-surface/95 backdrop-blur md:hidden"
      >
        <div
          className="mx-auto grid max-w-lg"
          style={{ gridTemplateColumns: `repeat(${slots}, minmax(0, 1fr))` }}
        >
          {tabs.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/' || item.end}
              className={({ isActive }) =>
                cn(
                  // `min-h-[56px]` keeps every tab a comfortable thumb target
                  // however short its label is.
                  'relative flex min-h-[56px] flex-col items-center justify-center gap-1 px-0.5 py-2 text-[11px] font-medium transition',
                  isActive ? 'text-brand-600' : 'text-ink-400 active:bg-ink-100',
                )
              }
            >
              <span className="relative">
                <item.icon width={22} height={22} />
                {item.badge === 'notifications' && unreadCount > 0 ? (
                  <span className="absolute -right-2 -top-1 grid h-4 min-w-[16px] place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                ) : null}
              </span>
              <span className="max-w-full truncate">{shortLabel(t(item.labelKey))}</span>
            </NavLink>
          ))}

          {overflow.length > 0 ? (
            <button
              type="button"
              aria-haspopup="dialog"
              aria-expanded={sheetOpen}
              onClick={() => setSheetOpen((value) => !value)}
              className={cn(
                'relative flex min-h-[56px] flex-col items-center justify-center gap-1 px-0.5 py-2 text-[11px] font-medium transition',
                sheetOpen || overflowActive
                  ? 'text-brand-600'
                  : 'text-ink-400 active:bg-ink-100',
              )}
            >
              <span className="relative">
                <MenuIcon width={22} height={22} />
                {overflowUnread ? (
                  <span
                    aria-hidden
                    className="absolute -right-1.5 -top-0.5 h-2 w-2 rounded-full bg-red-500 ring-2 ring-surface"
                  />
                ) : null}
              </span>
              <span>{t('common.more')}</span>
            </button>
          ) : null}
        </div>
      </nav>
    </>
  )
}

/** One entry in the "Yana" sheet: a full-width row, not a cramped tab. */
function SheetLink({
  item,
  unreadCount,
  onNavigate,
}: {
  item: NavItem
  unreadCount: number
  onNavigate: () => void
}) {
  const { t } = useTranslation()
  return (
    <NavLink
      to={item.to}
      end={item.to === '/' || item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'flex min-h-[52px] items-center gap-3 rounded-xl border px-3 py-2.5 text-sm font-medium transition',
          isActive
            ? 'border-brand-200 bg-brand-50 text-brand-700'
            : 'border-ink-200 text-ink-700 active:bg-ink-100',
        )
      }
    >
      <item.icon width={20} height={20} className="shrink-0" />
      <span className="min-w-0 flex-1 truncate">{t(item.labelKey)}</span>
      {item.badge === 'notifications' && unreadCount > 0 ? (
        <span className="grid h-5 min-w-[20px] shrink-0 place-items-center rounded-full bg-red-500 px-1.5 text-[11px] font-semibold text-white">
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      ) : null}
    </NavLink>
  )
}

/**
 * Tab labels are one word wide. "Sinf va guruhlar" becomes "Sinf" — the icon
 * carries the rest, and the full name is a tap away in the sheet.
 */
function shortLabel(label: string): string {
  return label.split(' ')[0] ?? label
}
