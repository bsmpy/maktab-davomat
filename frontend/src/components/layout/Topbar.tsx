import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'

import { CloseIcon, SearchIcon } from '@/components/ui'
import { cn } from '@/utils/cn'

import { LanguageMenu } from './LanguageMenu'
import { NavBackButton } from './NavBackButton'
import { NavBurgerButton } from './NavBurgerButton'
import { NavSearch } from './NavSearch'
import { ThemeMenu } from './ThemeMenu'
import { UserMenu } from './UserMenu'
import { NAV_ITEMS } from './navigation'

function titleKeyForPath(pathname: string): string {
  // The *longest* match, so `/guruhim/oquvchilar` reads as "O'quvchilar"
  // rather than borrowing its parent's name.
  const match = NAV_ITEMS.filter((item) =>
    item.to === '/' ? pathname === '/' : pathname.startsWith(item.to),
  ).sort((a, b) => b.to.length - a.to.length)[0]
  return match?.labelKey ?? 'nav.attendance'
}

/**
 * The bar above the content.
 *
 * Left: the sidebar toggle and a back button, in that order. Right: search, the
 * language and theme pickers, and the account menu.
 *
 * The search is a field from `md` up, where there is width for one, and a
 * button below that: a phone's navbar is already four controls wide, and a
 * field parked permanently on a second row costs a row of content on every
 * page to save one tap on the few where it is used.
 */
export function Topbar({
  sidebarOpen,
  onToggleSidebar,
}: {
  sidebarOpen: boolean
  onToggleSidebar: () => void
}) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const [searchOpen, setSearchOpen] = useState(false)

  return (
    <header
      className="sticky top-0 z-30 border-b border-ink-200 bg-surface/90 backdrop-blur"
      style={{ paddingTop: 'env(safe-area-inset-top)' }}
    >
      <div className="flex items-center gap-2 px-3 py-2.5 sm:px-4 lg:px-6">
        <NavBurgerButton open={sidebarOpen} onToggle={onToggleSidebar} />
        <NavBackButton />

        {/* The page's own name, at every width. The school's mark and name are
            the rail's job — on a phone a brand that never changes tells the
            user less than the page they are standing on, and it was the first
            thing to be squeezed out when the bar filled up. */}
        <h1 className="min-w-0 flex-1 truncate text-[15px] font-semibold text-ink-900 sm:text-base">
          {t(titleKeyForPath(pathname))}
        </h1>

        <div className="flex shrink-0 items-center gap-1 sm:gap-2">
          <NavSearch className="hidden w-56 lg:block xl:w-72" />

          <button
            type="button"
            aria-label={searchOpen ? t('common.closeSearch') : t('common.search')}
            aria-expanded={searchOpen}
            onClick={() => setSearchOpen((value) => !value)}
            className={cn(
              'grid h-9 w-9 shrink-0 place-items-center rounded-xl border transition lg:hidden',
              searchOpen
                ? 'border-brand-200 bg-brand-50 text-brand-700'
                : 'border-ink-200 text-ink-600 active:bg-ink-100',
            )}
          >
            {searchOpen ? (
              <CloseIcon width={18} height={18} />
            ) : (
              <SearchIcon width={18} height={18} />
            )}
          </button>

          <LanguageMenu />
          <ThemeMenu />
          <UserMenu />
        </div>
      </div>

      {/* Asked for: the field takes the width of the bar for as long as it is
          being used, then gives the row back. */}
      {searchOpen ? (
        <div className="animate-slide-up px-3 pb-2.5 sm:px-4 lg:hidden">
          {/* Arriving somewhere gives the row back — the field is a way to get
              to a page, not a fixture of the page you land on. */}
          <NavSearch autoFocus onNavigate={() => setSearchOpen(false)} />
        </div>
      ) : null}
    </header>
  )
}
