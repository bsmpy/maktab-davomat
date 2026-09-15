import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { UserMenu } from '@/components/layout/UserMenu'
import { navItemsFor } from '@/components/layout/navigation'
import { RequirePermission } from '@/routes/ProtectedRoute'
import i18n from '@/i18n'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import { useTeacherStore } from '@/store/teacherStore'
import type { Role } from '@/types/api'

import { makeUser } from './session'

vi.mock('@/api/authApi', () => ({
  authApi: { switchRole: vi.fn(), logout: vi.fn() },
}))

const { authApi } = await import('@/api/authApi')

beforeEach(async () => {
  await i18n.changeLanguage('uz')
  vi.clearAllMocks()
  useChildStore.setState({
    children: [],
    activeChildId: null,
    loading: false,
    error: null,
    load: () => Promise.resolve(),
  } as never)
  useTeacherStore.setState({ profile: null, load: () => Promise.resolve() } as never)
})

function signIn(active: Role, roles: Role[] = [active]) {
  useAuthStore.setState({
    status: 'authenticated',
    user: makeUser(active, { roles, full_name: 'Valiyev Ali' }),
  } as never)
}

function railFor(active: Role, roles: Role[] = [active]) {
  return navItemsFor({ user: makeUser(active, { roles }), hasChildren: false }).map(
    (item) => item.to,
  )
}

// --------------------------------------------------------------------------
// The rail follows the active role
// --------------------------------------------------------------------------
describe('the rail each role gets', () => {
  it('gives an administrator the register and not a curator cabinet', () => {
    const rail = railFor('ADMIN')
    expect(rail).toContain('/oquvchilar')
    expect(rail).toContain('/sozlamalar')
    expect(rail).toContain('/kuratorlar')
    expect(rail).toContain('/dars-jadvali')
    expect(rail).not.toContain('/guruhim')
    // Nobody's attendance but their own, which lives on Bosh sahifa.
    expect(rail).not.toContain('/davomat')
    expect(rail).not.toContain('/kalendar')
    // Accounts and the audit trail are not an administrator's.
    expect(rail).not.toContain('/foydalanuvchilar')
    expect(rail).not.toContain('/audit')
  })

  /**
   * A moderator reads the same register an administrator writes, so the rail
   * is nearly identical. What is missing is any page that only exists to make
   * changes — and every button on the pages they do get.
   */
  it('gives a moderator the register to read', () => {
    const rail = railFor('MODERATOR')
    expect(rail).toContain('/kuratorlar')
    expect(rail).not.toContain('/export')
    // Opened read-only, for the register sections that live inside it.
    expect(rail).toContain('/sozlamalar')
  })

  it('gives a teacher their own pages and no register at all', () => {
    const rail = railFor('TEACHER')
    expect(rail).toEqual(['/', '/davomat', '/kalendar', '/bildirishnomalar', '/profil'])
  })

  it('gives a curator their group and its pupils', () => {
    const rail = railFor('CURATOR')
    expect(rail).toContain('/guruhim')
    expect(rail).toContain('/guruhim/oquvchilar')
    expect(rail).toContain('/davomat')
    expect(rail).not.toContain('/oquvchilar')
  })

  it('gives an ordinary employee their own day and nothing else', () => {
    const rail = railFor('STAFF')
    expect(rail).toEqual(['/', '/xronologiya', '/bildirishnomalar', '/profil'])
  })

  it('gives a parent their children', () => {
    const rail = railFor('OTA-ONA')
    expect(rail).toContain('/farzandlarim')
    expect(rail).toContain('/xronologiya')
    expect(rail).not.toContain('/oquvchilar')
    expect(rail).not.toContain('/kuratorlar')
  })

  it('gives the platform owner everything', () => {
    const rail = railFor('DEVELOPER')
    for (const page of ['/maktab', '/foydalanuvchilar', '/audit', '/sozlamalar', '/kuratorlar']) {
      expect(rail).toContain(page)
    }
  })

  /** The order the school asked for, entry by entry, for a full-access account. */
  it('lays the rail out in the agreed order', () => {
    expect(railFor('DEVELOPER')).toEqual([
      '/',
      '/maktab',
      '/sinflar',
      '/fanlar',
      '/dars-jadvali',
      '/davomat',
      '/kalendar',
      '/foydalanuvchilar',
      '/oqituvchilar',
      '/xodimlar',
      '/kuratorlar',
      '/oquvchilar',
      '/export',
      '/audit',
      '/bildirishnomalar',
      '/sozlamalar',
      '/profil',
    ])
  })

  it('shows Farzandlarim to a parent and to nobody else', () => {
    expect(railFor('OTA-ONA')).toContain('/farzandlarim')
    for (const role of ['DEVELOPER', 'SUPER_ADMIN', 'ADMIN', 'TEACHER', 'STAFF'] as const) {
      expect(railFor(role)).not.toContain('/farzandlarim')
    }
  })

  /**
   * The whole point of the switcher: the same account, two rails. Nothing is
   * merged — working as a TEACHER is being a teacher, ADMIN or not.
   */
  it('redraws for the role in use, not for every role held', () => {
    const asAdmin = railFor('ADMIN', ['ADMIN', 'TEACHER'])
    const asTeacher = railFor('TEACHER', ['ADMIN', 'TEACHER'])

    expect(asAdmin).toContain('/maktab')
    expect(asTeacher).not.toContain('/maktab')
  })
})

// --------------------------------------------------------------------------
// Route guards
// --------------------------------------------------------------------------
describe('the route guard', () => {
  function renderGuarded(active: Role, permission: Parameters<typeof RequirePermission>[0]['all']) {
    signIn(active)
    return render(
      <MemoryRouter>
        <RequirePermission all={permission}>
          <p>secret page</p>
        </RequirePermission>
      </MemoryRouter>,
    )
  }

  it('opens a page the active role may see', () => {
    renderGuarded('ADMIN', ['students.manage'])
    expect(screen.getByText('secret page')).toBeInTheDocument()
  })

  it('closes one it may not, and names the role standing there', () => {
    renderGuarded('TEACHER', ['students.manage'])
    expect(screen.queryByText('secret page')).not.toBeInTheDocument()
    expect(screen.getByText(/TEACHER/)).toBeInTheDocument()
  })
})

// --------------------------------------------------------------------------
// The switcher in the navbar
// --------------------------------------------------------------------------
describe('the role switcher', () => {
  it('stays out of the way when there is only one role', async () => {
    signIn('TEACHER')
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { expanded: false }))
    expect(screen.queryByRole('menuitemradio')).not.toBeInTheDocument()
  })

  it('lists every role the person holds and marks the one in use', async () => {
    signIn('TEACHER', ['TEACHER', 'CURATOR', 'STAFF'])
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { expanded: false }))
    const options = screen.getAllByRole('menuitemradio')
    expect(options.map((row) => row.textContent?.trim())).toEqual([
      'TEACHER',
      'CURATOR',
      'STAFF',
    ])
    expect(options[0]).toHaveAttribute('aria-checked', 'true')
    expect(options[1]).toHaveAttribute('aria-checked', 'false')
  })

  /**
   * Switching is a request, not a local flag: the server writes the active
   * role onto the account and answers with a fresh session, which is why a
   * reload comes back in the same role.
   */
  it('asks the server and adopts the session it answers with', async () => {
    signIn('TEACHER', ['TEACHER', 'CURATOR'])
    vi.mocked(authApi.switchRole).mockResolvedValue({
      access: 'new-token',
      expires_in: 900,
      csrf: 'csrf',
      user: makeUser('CURATOR', { roles: ['TEACHER', 'CURATOR'] }),
    } as never)

    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { expanded: false }))
    await user.click(screen.getByRole('menuitemradio', { name: 'CURATOR' }))

    await waitFor(() => expect(authApi.switchRole).toHaveBeenCalledWith('CURATOR'))
    await waitFor(() =>
      expect(useAuthStore.getState().user?.active_role).toBe('CURATOR'),
    )
  })
})

// --------------------------------------------------------------------------
// What a read-only role is shown
// --------------------------------------------------------------------------
describe('a read-only role on a register page', () => {
  it('is told so, and is offered no way to change anything', async () => {
    const { StudentsPage } = await import('@/pages/RegisterPages')
    signIn('MODERATOR')

    render(
      <MemoryRouter>
        <StudentsPage />
      </MemoryRouter>,
    )

    expect(
      await screen.findByText(/faqat ko'rishingiz mumkin/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /qo'shish/i })).not.toBeInTheDocument()
  })

  it('says nothing of the sort to the role that runs the register', async () => {
    const { StudentsPage } = await import('@/pages/RegisterPages')
    signIn('ADMIN')

    render(
      <MemoryRouter>
        <StudentsPage />
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(screen.queryByText(/faqat ko'rishingiz mumkin/i)).not.toBeInTheDocument(),
    )
  })
})
