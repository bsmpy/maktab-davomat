import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { UserMenu } from '@/components/layout/UserMenu'
import { useAuthStore } from '@/store/authStore'
import { useTeacherStore } from '@/store/teacherStore'

const logout = vi.fn()

beforeEach(() => {
  logout.mockClear()
  useTeacherStore.setState({ profile: null, loading: false, error: null })
  useAuthStore.setState({
    user: {
      id: 1,
      username: 's.hasanov',
      full_name: 'Hasanov Samir Xayrilloyevich',
      first_name: 'Samir',
      last_name: 'Hasanov',
      middle_name: 'Xayrilloyevich',
      role: 'TEACHER',
      role_label: "O'qituvchi",
      phone: '',
      is_phone_verified: false,
      must_change_password: false,
    },
    logout,
  } as never)
})

function renderMenu() {
  return render(
    <MemoryRouter>
      <UserMenu />
    </MemoryRouter>,
  )
}

describe('the account menu', () => {
  it('shows the full name next to the photo, the same one every page shows', () => {
    renderMenu()
    expect(screen.getAllByText('Hasanov Samir Xayrilloyevich').length).toBeGreaterThan(0)
    // Never an abbreviation: one screen must not disagree with the next.
    expect(screen.queryByText('H.X.SAMIR')).toBeNull()
  })

  it('opens and closes on the button', async () => {
    const user = userEvent.setup()
    renderMenu()
    const button = screen.getByRole('button', { expanded: false })

    await user.click(button)
    expect(screen.getByRole('menu')).toBeVisible()

    await user.click(screen.getByRole('button', { expanded: true }))
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
  })

  it('closes on a click outside it', async () => {
    const user = userEvent.setup()
    renderMenu()

    await user.click(screen.getByRole('button', { expanded: false }))
    expect(screen.getByRole('menu')).toBeVisible()

    await user.click(document.body)
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
  })

  it('offers only the profile and signing out', async () => {
    const user = userEvent.setup()
    renderMenu()

    await user.click(screen.getByRole('button', { expanded: false }))
    const items = screen.getAllByRole('menuitem')
    expect(items.map((item) => item.textContent)).toEqual(['Profil', 'Chiqish'])
  })

  it('signs the user out', async () => {
    const user = userEvent.setup()
    renderMenu()

    await user.click(screen.getByRole('button', { expanded: false }))
    await user.click(screen.getByRole('menuitem', { name: 'Chiqish' }))

    expect(logout).toHaveBeenCalled()
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
  })
})
