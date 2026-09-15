import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { UsersPanel } from '@/features/management/UsersPanel'
import i18n from '@/i18n'
import { useAuthStore } from '@/store/authStore'
import type { StaffUser } from '@/types/api'

vi.mock('@/api/managementApi', () => ({
  userApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    resetPassword: vi.fn(),
  },
}))

const { userApi } = await import('@/api/managementApi')

function row(overrides: Partial<StaffUser>): StaffUser {
  return {
    id: 1,
    username: 'bsm',
    full_name: 'Bosh Dasturchi',
    first_name: 'Dasturchi',
    last_name: 'Bosh',
    middle_name: '',
    role: 'DEVELOPER',
    active_role: 'DEVELOPER',
    roles: ['DEVELOPER'],
    role_label: 'DEVELOPER',
    phone: '',
    is_active: true,
    must_change_password: false,
    last_login: null,
    created_at: '2026-09-01T08:00:00Z',
    school: null,
    can_manage: false,
    is_self: true,
    can_edit: true,
    locked_role: 'DEVELOPER',
    ...overrides,
  }
}

const ME = row({})
const COLLEAGUE = row({
  id: 2,
  username: 'n.usmonova',
  full_name: 'Usmonova Nodira',
  first_name: 'Nodira',
  last_name: 'Usmonova',
  role: 'TEACHER',
  active_role: 'TEACHER',
  roles: ['TEACHER'],
  is_self: false,
  can_manage: true,
  locked_role: null,
})

const ROLES = ['DEVELOPER', 'SUPER_ADMIN', 'ADMIN', 'TEACHER', 'STAFF'].map((value) => ({
  value,
  label: value,
}))

function itemFor(name: string) {
  return screen.getByText(name).closest('li') as HTMLElement
}

beforeEach(async () => {
  await i18n.changeLanguage('uz')
  vi.mocked(userApi.list).mockResolvedValue({ assignable_roles: ROLES, results: [ME, COLLEAGUE] })
  vi.mocked(userApi.update).mockResolvedValue(ME)
})

describe('Administratsiya: your own account', () => {
  it('lets you edit yourself but not delete, reset or switch yourself off', async () => {
    render(<UsersPanel />)
    const mine = await waitFor(() => itemFor('Bosh Dasturchi'))

    expect(within(mine).getByText('Siz')).toBeInTheDocument()
    expect(within(mine).getByRole('button', { name: 'Tahrirlash' })).toBeInTheDocument()
    expect(within(mine).queryByRole('button', { name: /o'chirish/i })).not.toBeInTheDocument()
    expect(within(mine).queryByRole('switch')).not.toBeInTheDocument()

    // A colleague's row keeps every action.
    const theirs = itemFor('Usmonova Nodira')
    expect(within(theirs).getByRole('button', { name: 'Tahrirlash' })).toBeInTheDocument()
    expect(within(theirs).queryByText('Siz')).not.toBeInTheDocument()
  })

  it('keeps your highest role locked and re-reads the session after saving', async () => {
    const refreshProfile = vi.fn().mockResolvedValue(undefined)
    useAuthStore.setState({ refreshProfile } as never)
    const user = userEvent.setup()

    render(<UsersPanel />)
    const mine = await waitFor(() => itemFor('Bosh Dasturchi'))
    await user.click(within(mine).getByRole('button', { name: 'Tahrirlash' }))

    const dialog = await screen.findByRole('dialog')
    const locked = within(dialog).getByRole('checkbox', { name: 'DEVELOPER' })
    expect(locked).toBeChecked()
    expect(locked).toBeDisabled()

    await user.clear(within(dialog).getByLabelText('Ism'))
    await user.type(within(dialog).getByLabelText('Ism'), 'Yangi')
    await user.click(within(dialog).getByRole('checkbox', { name: 'TEACHER' }))
    await user.click(within(dialog).getByRole('button', { name: 'Saqlash' }))

    await waitFor(() => expect(userApi.update).toHaveBeenCalled())
    const [id, payload] = vi.mocked(userApi.update).mock.calls[0]
    expect(id).toBe(1)
    expect(payload.first_name).toBe('Yangi')
    expect(payload.roles).toEqual(expect.arrayContaining(['DEVELOPER', 'TEACHER']))
    await waitFor(() => expect(refreshProfile).toHaveBeenCalled())
  })
})
