import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { StaffPanel } from '@/features/admin/StaffPanel'
import i18n from '@/i18n'
import type { PersonProfile } from '@/types/api'

vi.mock('@/api/adminApi', () => ({
  adminApi: {
    staff: vi.fn(),
    positions: vi.fn(),
    staffProfile: vi.fn(),
    teacherProfile: vi.fn(),
    createStaff: vi.fn(),
    updateStaff: vi.fn(),
    deleteStaff: vi.fn(),
  },
}))

const { adminApi } = await import('@/api/adminApi')

const PERSON = {
  id: 'staff-1',
  full_name: 'Umarova Zilola',
  first_name: 'Zilola',
  last_name: 'Umarova',
  middle_name: 'Rustamovna',
  passport_id: 'AD7654321',
  jshshir: '41503199012345',
  masked_jshshir: '**********2345',
  has_jshshir: true,
  birth_date: '1990-03-15',
  gender: 'FEMALE' as const,
  gender_label: 'Ayol',
  phone: '+998901112233',
  email: 'z.umarova@maktab.uz',
  photo: null,
  is_active: true,
  username: 'z.umarova',
  position: null,
  role: 'STAFF' as const,
  roles: ['STAFF' as const],
  role_label: 'STAFF',
}

const PROFILE: PersonProfile = {
  ...PERSON,
  kind: 'staff',
  school: '1-maktab',
  account: {
    id: 7,
    username: 'z.umarova',
    roles: ['STAFF'],
    active_role: 'STAFF',
    is_active: true,
    must_change_password: true,
    last_login: null,
    created_at: '2026-09-12T08:00:00Z',
  },
  position: null,
  subjects: [],
  subjects_count: 0,
  curator_groups: [],
  homeroom_groups: [],
  timetable: { lessons_per_week: 0, days: [] },
  week: null,
}

beforeEach(async () => {
  await i18n.changeLanguage('uz')
  vi.clearAllMocks()
  vi.mocked(adminApi.positions).mockResolvedValue([] as never)
  vi.mocked(adminApi.staff).mockResolvedValue({
    results: [PERSON],
    assignable_roles: [{ value: 'STAFF', label: 'STAFF' }],
  } as never)
  vi.mocked(adminApi.staffProfile).mockResolvedValue(PROFILE)
})

describe('a person card', () => {
  it('sits in a grid of at most three columns', async () => {
    render(<StaffPanel />)
    const card = await screen.findByRole('button', { name: /Umarova Zilola profilini ochish/ })
    expect(card.parentElement?.className).toContain('lg:grid-cols-3')
    expect(card.parentElement?.className).not.toContain('grid-cols-4')
  })

  it('opens the whole profile when it is pressed', async () => {
    const user = userEvent.setup()
    render(<StaffPanel />)

    await user.click(
      await screen.findByRole('button', { name: /Umarova Zilola profilini ochish/ }),
    )

    await waitFor(() => expect(adminApi.staffProfile).toHaveBeenCalledWith('staff-1'))
    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByText('AD7654321')).toBeInTheDocument()
    expect(within(dialog).getByText('z.umarova@maktab.uz')).toBeInTheDocument()
    expect(within(dialog).getByText('Hali kirmagan')).toBeInTheDocument()
  })

  it('opens from the keyboard too', async () => {
    const user = userEvent.setup()
    render(<StaffPanel />)

    const card = await screen.findByRole('button', { name: /Umarova Zilola profilini ochish/ })
    card.focus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(adminApi.staffProfile).toHaveBeenCalledTimes(1))
  })

  it('does not open the profile when an action inside the card is pressed', async () => {
    const user = userEvent.setup()
    render(<StaffPanel />)

    await user.click(await screen.findByRole('button', { name: 'Tahrirlash' }))

    expect(adminApi.staffProfile).not.toHaveBeenCalled()
  })
})
