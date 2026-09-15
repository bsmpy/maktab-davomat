import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

import { useAuth } from '@/auth/permissions'
import { useChildStore } from '@/store/childStore'
import { cn } from '@/utils/cn'

import { ChildSwitcher } from './ChildSwitcher'
import { SchoolBrand } from './SchoolBrand'
import { navItemsFor } from './navigation'

/**
 * The cabinet's rail, in three shapes for three sizes of screen.
 *
 * * **Phone** (`< md`) — no rail at all until the burger asks for one, and then
 *   it slides over the content with a scrim. The bottom tab bar is the everyday
 *   navigation there.
 * * **Tablet** (`md`–`lg`) — always present, but as a column of icons 76px wide,
 *   so an 820px screen keeps most of its width for the content. The burger
 *   widens it in place.
 * * **Laptop and desktop** (`lg+`) — the full 264px rail, open by default; the
 *   burger collapses it to the same icon column rather than hiding it, so the
 *   navigation never disappears on a screen that has room for it.
 *
 * Signing out lives in the navbar menu, not here.
 */
export function Sidebar({
  unreadCount,
  open,
  onClose,
}: {
  unreadCount: number
  open: boolean
  onClose: () => void
}) {
  const { t } = useTranslation()
  const { user, isActing } = useAuth()
  const children = useChildStore((state) => state.children)
  const items = navItemsFor({ user, hasChildren: children.length > 0 })
  // Only a parent's cabinet is about a particular child. Staff accounts can
  // have a child of their own attached, which is not what this rail is for.
  const showChild = isActing('OTA-ONA') && children.length > 0

  return (
    <>
      {/* Only the phone's drawer overlays the content, so only it needs a
          scrim: from `md` up the rail sits in the layout and pushes. */}
      <div
        hidden={!open}
        onClick={onClose}
        className={cn(
          'fixed inset-0 z-40 bg-scrim/50 transition-opacity md:hidden',
          open ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      />

      <aside
        id="cabinet-sidebar"
        // No `aria-hidden`: the collapsed rail is real navigation from `md` up.
        // The `invisible` class below is what takes the phone's off-canvas
        // drawer out of the accessibility tree, and `md:visible` puts the icon
        // rail back into it.
        className={cn(
          'z-40 flex h-dvh shrink-0 flex-col overflow-y-auto overflow-x-hidden border-r border-ink-200 bg-surface/95 backdrop-blur',
          'fixed inset-y-0 left-0 transition-[width,transform] duration-200 md:sticky md:top-0 md:translate-x-0',
          open
            ? 'w-[264px] translate-x-0'
            : // Off-canvas on a phone — and `invisible` matters as much as the
              // transform, because a translated-away rail is still focusable and
              // still read out. From `md` it is simply narrower, never gone.
              'w-[264px] -translate-x-full invisible md:visible md:w-[76px]',
        )}
      >
        <div className={cn('py-5', open ? 'px-5' : 'px-4')}>
          <SchoolBrand compact={!open} />
        </div>

        {showChild && open ? (
          <div className="px-4 pb-4">
            <ChildSwitcher />
          </div>
        ) : null}

        <nav className="flex-1 space-y-1 px-3 pb-5">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/' || item.end}
              onClick={onClose}
              // Collapsed the label is gone, so the icon needs to name itself.
              title={open ? undefined : t(item.labelKey)}
              className={({ isActive }) =>
                cn(
                  'relative flex items-center rounded-xl text-sm font-medium transition',
                  open ? 'gap-3 px-3 py-2.5' : 'justify-center px-0 py-3',
                  isActive
                    ? 'bg-brand-50 text-brand-700 before:absolute before:left-0 before:top-1/2 before:h-6 before:w-1 before:-translate-y-1/2 before:rounded-r-full before:bg-brand-600'
                    : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900',
                )
              }
            >
              <span className="relative shrink-0">
                <item.icon width={20} height={20} />
                {/* Collapsed there is no room for a count, so the badge
                    shrinks to a dot on the icon itself. */}
                {!open && item.badge === 'notifications' && unreadCount > 0 ? (
                  <span
                    aria-hidden
                    className="absolute -right-1 -top-0.5 h-2 w-2 rounded-full bg-red-500 ring-2 ring-surface"
                  />
                ) : null}
              </span>

              {open ? (
                <>
                  <span className="flex-1 truncate">{t(item.labelKey)}</span>
                  {item.badge === 'notifications' && unreadCount > 0 ? (
                    <span className="grid h-5 min-w-[20px] shrink-0 place-items-center rounded-full bg-red-500 px-1.5 text-[11px] font-semibold text-white">
                      {unreadCount > 99 ? '99+' : unreadCount}
                    </span>
                  ) : null}
                </>
              ) : (
                <span className="sr-only">{t(item.labelKey)}</span>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  )
}
