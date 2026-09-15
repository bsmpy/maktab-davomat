import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { Sidebar } from '@/components/layout/Sidebar'
import { navItemsFor } from '@/components/layout/navigation'
import i18n from '@/i18n'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import type { Role } from '@/types/api'

import { makeUser } from './session'

function renderRail(role: Role, open: boolean) {
  useAuthStore.setState({ user: makeUser(role) } as never)
  return render(
    <MemoryRouter>
      <Sidebar unreadCount={0} open={open} onClose={() => {}} />
    </MemoryRouter>,
  )
}

beforeEach(async () => {
  await i18n.changeLanguage('uz')
  useChildStore.setState({ children: [], activeChildId: null } as never)
})

describe('the cabinet rail', () => {
  /**
   * Collapsing used to take the rail off the screen entirely, which left a
   * 900px tablet with no navigation at all but the burger. Collapsed now means
   * a column of icons, so every entry is still one tap away.
   */
  it('keeps every entry when it is collapsed', () => {
    const expected = navItemsFor({ user: makeUser('ADMIN'), hasChildren: false }).map((item) =>
      i18n.t(item.labelKey),
    )

    const { unmount } = renderRail('ADMIN', true)
    const openRail = screen.getByRole('complementary')
    expect(within(openRail).getAllByRole('link').map((a) => a.textContent)).toEqual(expected)
    unmount()

    renderRail('ADMIN', false)
    const shutRail = screen.getByRole('complementary')
    // Same links, same order — the labels are read out rather than drawn.
    expect(
      within(shutRail)
        .getAllByRole('link')
        .map((a) => a.getAttribute('title')),
    ).toEqual(expected)
  })

  it('names each icon for the pointer and the screen reader alike', () => {
    renderRail('TEACHER', false)
    const rail = screen.getByRole('complementary')
    const home = within(rail).getByRole('link', { name: 'Bosh sahifa' })
    expect(home).toHaveAttribute('title', 'Bosh sahifa')
  })

  it('drops the tooltips once the labels are on screen', () => {
    renderRail('TEACHER', true)
    const rail = screen.getByRole('complementary')
    expect(within(rail).getByRole('link', { name: 'Bosh sahifa' })).not.toHaveAttribute('title')
  })

  /** The child card is a parent's, and only when the rail is wide enough. */
  it('shows the child switcher only to a parent with the rail open', () => {
    useChildStore.setState({
      children: [
        {
          id: 'c1',
          full_name: 'Samir Hasanov',
          display_name: 'Samir',
          initials: 'SH',
          class_group: '1-A',
        },
      ],
      activeChildId: 'c1',
    } as never)

    const { unmount } = renderRail('OTA-ONA', true)
    expect(screen.getByText('Samir')).toBeInTheDocument()
    unmount()

    renderRail('OTA-ONA', false)
    expect(screen.queryByText('Samir')).not.toBeInTheDocument()
  })
})
