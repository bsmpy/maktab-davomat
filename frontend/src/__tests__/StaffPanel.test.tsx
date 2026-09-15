import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/adminApi', () => ({
  adminApi: {
    staff: vi.fn(),
    positions: vi.fn(),
    createStaff: vi.fn(),
    updateStaff: vi.fn(),
    deleteStaff: vi.fn(),
  },
}))

const { adminApi } = await import('@/api/adminApi')
const { StaffPanel } = await import('@/features/admin/StaffPanel')
const i18n = (await import('@/i18n')).default

const POSITION = {
  id: 'p1',
  title_uz: 'Hisobchi',
  title_ru: 'Бухгалтер',
  title_en: 'Accountant',
  titles: { uz: 'Hisobchi', ru: 'Бухгалтер', en: 'Accountant' },
  staff_count: 0,
}

function person(over: Record<string, unknown> = {}) {
  return {
    id: 's1',
    full_name: 'Karimov Aziz',
    first_name: 'Aziz',
    last_name: 'Karimov',
    middle_name: '',
    passport_id: '',
    jshshir: '',
    masked_jshshir: '',
    has_jshshir: false,
    birth_date: null,
    gender: '' as const,
    gender_label: '',
    phone: '',
    email: '',
    photo: null,
    is_active: true,
    username: null,
    position: null,
    role: null,
    roles: [],
    role_label: null,
    ...over,
  }
}

/** What the server offers: everything the caller may hand out, never DEVELOPER. */
const ROLES = [
  { value: 'ADMIN', label: 'ADMIN' },
  { value: 'TEACHER', label: 'TEACHER' },
  { value: 'CURATOR', label: 'CURATOR' },
  { value: 'STAFF', label: 'STAFF' },
]

beforeEach(async () => {
  await i18n.changeLanguage('uz')
  vi.clearAllMocks()
  vi.mocked(adminApi.positions).mockResolvedValue([POSITION] as never)
  vi.mocked(adminApi.staff).mockResolvedValue({
    results: [],
    assignable_roles: ROLES,
  } as never)
  vi.mocked(adminApi.createStaff).mockResolvedValue(person() as never)
  vi.mocked(adminApi.updateStaff).mockResolvedValue(person() as never)
})

describe('adding a staff member', () => {
  /**
   * The register holds people; what they are called and what their account may
   * do are separate questions, asked later or never. Requiring a position up
   * front meant nobody could be entered until the office had decided one.
   */
  it('takes a name and nothing else', async () => {
    const user = userEvent.setup()
    render(<StaffPanel />)

    await user.click(await screen.findByRole('button', { name: /Xodim qo'shish/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Ism'), 'Aziz')
    await user.type(within(dialog).getByLabelText('Familiya'), 'Karimov')

    const save = within(dialog).getByRole('button', { name: 'Saqlash' })
    expect(save).toBeEnabled()
    await user.click(save)

    await waitFor(() => expect(adminApi.createStaff).toHaveBeenCalled())
    const [payload] = vi.mocked(adminApi.createStaff).mock.calls[0]!
    expect(payload.first_name).toBe('Aziz')
    // Neither was answered, so neither is claimed. An account created with no
    // role at all becomes STAFF — the server decides that, not this form.
    expect(payload.position).toBeNull()
    expect(payload.roles).toEqual([])
  })

  it('can be opened with no position on the books at all', async () => {
    vi.mocked(adminApi.positions).mockResolvedValue([] as never)
    const user = userEvent.setup()
    render(<StaffPanel />)

    const add = await screen.findByRole('button', { name: /Xodim qo'shish/ })
    expect(add).toBeEnabled()
    await user.click(add)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('never offers DEVELOPER as a role', async () => {
    const user = userEvent.setup()
    render(<StaffPanel />)

    await user.click(await screen.findByRole('button', { name: /Xodim qo'shish/ }))
    const dialog = await screen.findByRole('dialog')

    // Checkboxes, because one person is often several things at once.
    const offered = within(dialog)
      .getAllByRole('checkbox')
      .map((box) => box.closest('label')?.textContent?.trim())
    expect(offered).not.toContain('DEVELOPER')
    expect(offered).toContain('ADMIN')
    expect(offered).toContain('CURATOR')
  })

  it('sends every role that was ticked', async () => {
    const user = userEvent.setup()
    render(<StaffPanel />)

    await user.click(await screen.findByRole('button', { name: /Xodim qo'shish/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Ism'), 'Ali')
    await user.type(within(dialog).getByLabelText('Familiya'), 'Valiyev')
    await user.click(within(dialog).getByRole('checkbox', { name: 'TEACHER' }))
    await user.click(within(dialog).getByRole('checkbox', { name: 'CURATOR' }))
    await user.click(within(dialog).getByRole('button', { name: 'Saqlash' }))

    await waitFor(() => expect(adminApi.createStaff).toHaveBeenCalled())
    const [payload] = vi.mocked(adminApi.createStaff).mock.calls[0]!
    expect(payload.roles).toEqual(['TEACHER', 'CURATOR'])
  })
})

describe('attaching afterwards', () => {
  it('shows what a bare row is still missing', async () => {
    vi.mocked(adminApi.staff).mockResolvedValue({
      results: [person()],
      assignable_roles: ROLES,
    } as never)
    render(<StaffPanel />)

    expect(await screen.findByText('Lavozim belgilanmagan')).toBeInTheDocument()
    expect(screen.getByText('Rol berilmagan')).toBeInTheDocument()
  })

  it('attaches a position to somebody already in the register', async () => {
    vi.mocked(adminApi.staff).mockResolvedValue({
      results: [person()],
      assignable_roles: ROLES,
    } as never)
    const user = userEvent.setup()
    render(<StaffPanel />)

    await user.click(await screen.findByRole('button', { name: 'Tahrirlash' }))
    const dialog = await screen.findByRole('dialog')
    await user.selectOptions(within(dialog).getByLabelText(/Lavozim/), 'p1')
    await user.click(within(dialog).getByRole('button', { name: 'Saqlash' }))

    await waitFor(() => expect(adminApi.updateStaff).toHaveBeenCalled())
    const [, payload] = vi.mocked(adminApi.updateStaff).mock.calls[0]!
    expect(payload.position).toBe('p1')
  })

  /**
   * A role is something an account holds. Without an account there is nothing
   * to put it on, so the field says so rather than failing on save.
   */
  it('will not offer a role to somebody with no account', async () => {
    vi.mocked(adminApi.staff).mockResolvedValue({
      results: [person()],
      assignable_roles: ROLES,
    } as never)
    const user = userEvent.setup()
    render(<StaffPanel />)

    await user.click(await screen.findByRole('button', { name: 'Tahrirlash' }))
    const dialog = await screen.findByRole('dialog')

    expect(within(dialog).getByRole('checkbox', { name: 'ADMIN' })).toBeDisabled()
    expect(
      within(dialog).getByText('Rol berish uchun avval kabinet akkaunti kerak.'),
    ).toBeInTheDocument()
  })

  it('changes the roles of somebody who does have an account', async () => {
    vi.mocked(adminApi.staff).mockResolvedValue({
      results: [
        person({ username: 'a.karimov', role: 'TEACHER', roles: ['TEACHER'] }),
      ],
      assignable_roles: ROLES,
    } as never)
    const user = userEvent.setup()
    render(<StaffPanel />)

    await user.click(await screen.findByRole('button', { name: 'Tahrirlash' }))
    const dialog = await screen.findByRole('dialog')
    // The boxes open on what they already hold; ticking another adds to it.
    expect(within(dialog).getByRole('checkbox', { name: 'TEACHER' })).toBeChecked()
    await user.click(within(dialog).getByRole('checkbox', { name: 'CURATOR' }))
    await user.click(within(dialog).getByRole('button', { name: 'Saqlash' }))

    await waitFor(() => expect(adminApi.updateStaff).toHaveBeenCalled())
    const [, payload] = vi.mocked(adminApi.updateStaff).mock.calls[0]!
    expect(payload.roles).toEqual(['TEACHER', 'CURATOR'])
  })
})
