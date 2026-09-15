import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { MobileNav } from '@/components/layout/MobileNav'
import { MOBILE_TAB_LIMIT, mobileNavSplit, navItemsFor } from '@/components/layout/navigation'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import type { Role } from '@/types/api'

import { makeUser } from './session'

function signIn(role: Role) {
  useAuthStore.setState({ user: makeUser(role) } as never)
  useChildStore.setState({ children: [], activeChildId: null } as never)
}

/** The nav context a role's session produces. */
function ctx(role: Role, hasChildren: boolean) {
  return { user: makeUser(role), hasChildren }
}

beforeEach(() => {
  useChildStore.setState({ children: [], activeChildId: null } as never)
})

describe('splitting the nav for a phone', () => {
  /**
   * The reason the split exists: a developer's rail is long enough that laying
   * it out as tabs gives each one about 25px on a 360px screen.
   *
   * The invariant is the width of the bar, not the number of tabs — five slots,
   * counting the overflow button when there is one.
   */
  it('never asks the bar for more than five slots', () => {
    for (const role of ['DEVELOPER', 'SUPER_ADMIN', 'ADMIN', 'TEACHER', 'CURATOR', 'STAFF', 'OTA-ONA'] as const) {
      const { tabs, overflow } = mobileNavSplit(ctx(role, true))
      const slots = tabs.length + (overflow.length > 0 ? 1 : 0)
      expect(slots).toBeLessThanOrEqual(MOBILE_TAB_LIMIT + 1)
      // Once anything is hidden, the tabs themselves are capped.
      if (overflow.length > 0) expect(tabs.length).toBe(MOBILE_TAB_LIMIT)
    }
  })

  it('keeps every entry reachable — the bar plus the sheet is the whole rail', () => {
    const all = navItemsFor(ctx('DEVELOPER', true)).map((item) => item.to)
    const { tabs, overflow } = mobileNavSplit(ctx('DEVELOPER', true))

    expect([...tabs, ...overflow].map((item) => item.to).sort()).toEqual([...all].sort())
    // Nothing is in both halves.
    expect(tabs.filter((tab) => overflow.some((row) => row.to === tab.to))).toHaveLength(0)
  })

  it('spends the slots on the pages people open daily', () => {
    const { tabs } = mobileNavSplit(ctx('DEVELOPER', true))
    expect(tabs.map((item) => item.to)).toContain('/')
    expect(tabs.map((item) => item.to)).toContain('/davomat')
    expect(tabs.map((item) => item.to)).toContain('/kalendar')
  })

  /**
   * A short menu fits as it is, and should not be broken up for nothing.
   *
   * An ordinary employee's rail is the shortest there is: their own day, their
   * chronology, their profile and their notifications.
   */
  it('leaves a short menu whole', () => {
    const { tabs, overflow } = mobileNavSplit(ctx('STAFF', true))
    expect(overflow).toHaveLength(0)
    expect(tabs.length).toBe(navItemsFor(ctx('STAFF', true)).length)
  })

  it('keeps the rail order rather than the priority order', () => {
    const all = navItemsFor(ctx('ADMIN', false)).map((item) => item.to)
    const { tabs } = mobileNavSplit(ctx('ADMIN', false))
    const positions = tabs.map((item) => all.indexOf(item.to))
    expect(positions).toEqual([...positions].sort((a, b) => a - b))
  })
})

describe('the phone tab bar', () => {
  function renderNav(role: Role, unread = 0) {
    signIn(role)
    return render(
      <MemoryRouter>
        <MobileNav unreadCount={unread} />
      </MemoryRouter>,
    )
  }

  it('offers the rest of the menu behind Yana', async () => {
    const user = userEvent.setup()
    renderNav('DEVELOPER')

    const bar = screen.getByRole('navigation', { name: 'Asosiy menyu' })
    expect(within(bar).getAllByRole('link').length).toBeLessThanOrEqual(MOBILE_TAB_LIMIT)

    await user.click(within(bar).getByRole('button', { name: /Yana/ }))
    const sheet = await screen.findByRole('dialog', { name: 'Menyu' })
    expect(within(sheet).getByRole('link', { name: /Administratsiya/ })).toBeInTheDocument()
  })

  it('closes the sheet on Escape', async () => {
    const user = userEvent.setup()
    renderNav('DEVELOPER')

    await user.click(screen.getByRole('button', { name: /Yana/ }))
    expect(await screen.findByRole('dialog', { name: 'Menyu' })).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Menyu' })).not.toBeInTheDocument()
  })

  /**
   * When the notifications entry lives in the sheet, the count has to show on
   * the button that opens it — otherwise a phone user has no sign that anything
   * arrived. A curator's menu is long enough to push it there; an
   * administrator's now keeps it on the bar itself.
   */
  it('carries the unread mark onto Yana when notifications are hidden', () => {
    renderNav('CURATOR', 3)
    const { overflow } = mobileNavSplit(ctx('CURATOR', false))
    expect(overflow.some((item) => item.badge === 'notifications')).toBe(true)

    const yana = screen.getByRole('button', { name: /Yana/ })
    expect(yana.querySelector('.bg-red-500')).not.toBeNull()
  })

  it('does not draw a Yana button for a menu that fits', () => {
    renderNav('STAFF')
    expect(screen.queryByRole('button', { name: /Yana/ })).not.toBeInTheDocument()
  })
})
