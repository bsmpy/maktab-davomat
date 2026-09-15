import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Outlet } from 'react-router-dom'

import { notificationApi } from '@/api/notificationApi'
import { MobileNav } from '@/components/layout/MobileNav'
import { Particles } from '@/components/layout/Particles'
import { Sidebar } from '@/components/layout/Sidebar'
import { Topbar } from '@/components/layout/Topbar'
import { Button, EmptyState, ErrorState, Spinner, UserIcon } from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { useAuth } from '@/auth/permissions'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import { useAppearanceStore } from '@/store/appearanceStore'
import { useTeacherStore } from '@/store/teacherStore'

/**
 * Shell for the signed-in cabinet. It owns the two pieces of state that every
 * page needs — the child list and the unread badge — so pages stay focused on
 * their own data.
 */
export function AppLayout() {
  const { t } = useTranslation()
  const children = useChildStore((state) => state.children)
  const loadChildren = useChildStore((state) => state.load)
  const loading = useChildStore((state) => state.loading)
  const error = useChildStore((state) => state.error)
  const logout = useAuthStore((state) => state.logout)
  const { user, isActing } = useAuth()
  // Only a parent's cabinet is *about* children; everybody else works here.
  const isStaff = Boolean(user) && !isActing('OTA-ONA')

  useEffect(() => {
    void loadChildren()
  }, [loadChildren])

  // The sidebar's school and the navbar's photo come from the teacher's own
  // record; nobody else has one, so nobody else asks for it.
  const loadTeacher = useTeacherStore((state) => state.load)
  const activeRole = user?.active_role
  useEffect(() => {
    // Every employee has one of these rows — a teacher's or a staff member's —
    // and the navbar photo and the rail's school come out of it. A parent has
    // none, so a parent never asks.
    if (activeRole && activeRole !== 'OTA-ONA') void loadTeacher({ force: true })
  }, [loadTeacher, activeRole])

  const unread = useAsyncData(() => notificationApi.unreadCount(), [])

  // The appearance switches belong to the installation, not to this browser:
  // whatever a DEVELOPER or SUPER_ADMIN last set is what everyone gets, so the
  // shell asks the server on every mount rather than trusting the cache.
  const particles = useAppearanceStore((state) => state.particles)
  const loadAppearance = useAppearanceStore((state) => state.load)
  useEffect(() => {
    void loadAppearance()
  }, [loadAppearance])
  /**
   * What "open" means depends on the screen, and the rail renders all three
   * shapes from this one flag: a laptop starts with the full rail open, a
   * tablet with the icon rail, a phone with the drawer shut.
   */
  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window === 'undefined' || window.innerWidth >= 1024,
  )

  // Crossing into desktop width opens the full rail and leaving it collapses
  // back to icons; Escape shuts the drawer the way it shuts every other overlay.
  useEffect(() => {
    const wide = window.matchMedia('(min-width: 1024px)')
    const onChange = (event: MediaQueryListEvent) => setSidebarOpen(event.matches)
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !wide.matches) setSidebarOpen(false)
    }
    wide.addEventListener('change', onChange)
    document.addEventListener('keydown', onKey)
    return () => {
      wide.removeEventListener('change', onChange)
      document.removeEventListener('keydown', onKey)
    }
  }, [])
  const reloadChildren = useCallback(() => void loadChildren({ force: true }), [loadChildren])

  if (loading && children.length === 0) {
    return (
      <div className="grid min-h-dvh place-items-center text-ink-400">
        <Spinner className="h-7 w-7" />
      </div>
    )
  }

  if (error && children.length === 0) {
    return (
      <div className="grid min-h-dvh place-items-center p-6">
        <div className="card w-full max-w-md">
          <ErrorState error={error} onRetry={reloadChildren} />
        </div>
      </div>
    )
  }

  // Only a parent's cabinet is *about* children. Locking staff out when the
  // list is empty is a bootstrapping deadlock: on a fresh install nobody could
  // reach the admin console to add the first pupil.
  if (children.length === 0 && !isStaff) {
    return (
      <div className="grid min-h-dvh place-items-center p-6">
        <div className="card w-full max-w-md">
          <EmptyState
            icon={<UserIcon width={26} height={26} />}
            title={t('common.noChildLinked')}
            description={t('common.noChildLinkedHint')}
            action={
              <Button variant="secondary" onClick={() => void logout()}>
                {t('common.logout')}
              </Button>
            }
          />
        </div>
      </div>
    )
  }

  const unreadCount = unread.data ?? 0

  return (
    <>
      {particles ? <Particles /> : null}
      <div className="relative z-10 flex min-h-dvh">
        <Sidebar
          unreadCount={unreadCount}
          open={sidebarOpen}
          onClose={() => {
            if (window.innerWidth < 1024) setSidebarOpen(false)
          }}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar
            sidebarOpen={sidebarOpen}
            onToggleSidebar={() => setSidebarOpen((value) => !value)}
          />
          {/* Full width: the content runs from the sidebar to the right edge
            rather than sitting in a centred column. The deep bottom padding is
            for the phone's tab bar, which floats over the page; from `md` the
            icon rail replaces it and the padding goes back to normal. */}
          <main className="w-full min-w-0 flex-1 px-4 pb-28 pt-5 sm:px-6 md:pb-10 lg:px-8 lg:pt-6">
            <Outlet context={{ reloadUnread: unread.reload, unreadCount }} />
          </main>
        </div>
        <MobileNav unreadCount={unreadCount} />
      </div>
    </>
  )
}
