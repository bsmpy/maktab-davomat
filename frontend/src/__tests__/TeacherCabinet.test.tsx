import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PresenceTimeline } from '@/features/teacher/PresenceTimeline'
import { TeacherProfile } from '@/features/teacher/TeacherProfile'
import { TeacherDashboardPage } from '@/pages/TeacherDashboardPage'
import { useTeacherStore } from '@/store/teacherStore'
import type { TeacherProfile as Profile, TeacherTimeline } from '@/types/api'

vi.mock('@/api/teachingApi', () => ({
  teachingApi: {
    dashboard: vi.fn(),
    profile: vi.fn(),
    saveProfile: vi.fn(),
    uploadPhoto: vi.fn(),
  },
}))

const { teachingApi } = await import('@/api/teachingApi')

const TEACHER = {
  id: 't1',
  first_name: 'Samir',
  last_name: 'Hasanov',
  middle_name: 'Xayrilloyevich',
  full_name: 'Hasanov Samir Xayrilloyevich',
  photo: null,
  email: 'samir@maktab.uz',
  school: {
    id: 's1',
    name: "23-sonli umumiy o'rta ta'lim maktabi",
    short_name: '23-maktab',
    logo: null,
  },
}

const TIMELINE: TeacherTimeline = {
  date: '2026-09-14',
  start_hour: 6,
  end_hour: 24,
  segments: [
    { state: 'OUT', start: '06:00', end: '08:12', minutes: 132, left: 0, width: 12.2 },
    { state: 'IN', start: '08:12', end: '13:40', minutes: 328, left: 12.2, width: 30.4 },
    { state: 'OUT', start: '13:40', end: '14:20', minutes: 40, left: 42.6, width: 3.7 },
    { state: 'IN', start: '14:20', end: '17:55', minutes: 215, left: 46.3, width: 19.9 },
    { state: 'OUT', start: '17:55', end: '00:00', minutes: 365, left: 66.2, width: 33.8 },
  ],
  first_in: '08:12',
  last_out: '17:55',
  is_inside: false,
  inside_minutes: 543,
}

const PROFILE: Profile = {
  ...TEACHER,
  birth_date: '1990-03-04',
  passport_id: 'AA1234567',
  jshshir: '31234567890123',
  masked_jshshir: '**********0123',
  has_jshshir: true,
  gender: 'MALE',
  gender_label: 'Erkak',
  phone: '+998901234567',
  username: 's.hasanov',
  role_label: "O'qituvchi",
  subjects: [
    { id: 'm1', name: 'Matematika', display_name: 'Matematika 1-A', class_group_name: '1-A' },
    { id: 'm2', name: 'Matematika', display_name: 'Matematika 2-A', class_group_name: '2-A' },
  ],
  genders: [
    { value: 'MALE', label: 'Erkak' },
    { value: 'FEMALE', label: 'Ayol' },
  ],
}

beforeEach(() => {
  useTeacherStore.setState({ profile: null, loading: false, error: null })
  vi.mocked(teachingApi.dashboard).mockResolvedValue({
    teacher: TEACHER,
    week: {
      start_date: '2026-09-14',
      end_date: '2026-09-20',
      school_days: 1,
      active_minutes: 543,
      inactive_minutes: 120,
      late_days: 1,
    },
    timeline: TIMELINE,
    recent_passes: [
      {
        id: 'p1',
        direction: 'OUT',
        label: 'Chiqdi',
        at: '2026-09-14T17:55:00+05:00',
        time: '17:55',
        date: '2026-09-14',
        terminal: 'Asosiy',
      },
      {
        id: 'p2',
        direction: 'IN',
        label: 'Kirdi',
        at: '2026-09-14T14:20:00+05:00',
        time: '14:20',
        date: '2026-09-14',
        terminal: 'Asosiy',
      },
    ],
  } as never)
  vi.mocked(teachingApi.profile).mockResolvedValue(PROFILE)
  vi.mocked(teachingApi.saveProfile).mockResolvedValue(PROFILE)
})

describe('the presence timeline', () => {
  function segments() {
    return screen.getAllByRole('button')
  }

  it('paints one block per visit, not one from first to last', () => {
    render(<PresenceTimeline timeline={TIMELINE} />)
    expect(segments()).toHaveLength(5)
    // Green for time inside, red for time outside — solid, not washed out.
    expect(segments()[1].className).toContain('bg-emerald-500')
    expect(segments()[2].className).toContain('bg-red-500')
  })

  it('runs from 06:00 to 00:00', () => {
    render(<PresenceTimeline timeline={TIMELINE} />)
    expect(screen.getByText('06:00')).toBeInTheDocument()
    expect(screen.getByText('00:00')).toBeInTheDocument()
  })

  it('names the very block under the pointer, green or red', async () => {
    const user = userEvent.setup()
    render(<PresenceTimeline timeline={TIMELINE} />)

    // Nothing is claimed until something is hovered.
    expect(screen.queryByRole('status')).toBeNull()

    await user.hover(segments()[1])
    let tip = screen.getByRole('status')
    expect(tip).toHaveTextContent('Maktabda')
    expect(tip).toHaveTextContent('08:12 - 13:40')
    expect(tip).toHaveTextContent('5 soat 28 daqiqa')

    // The next block replaces the reading rather than adding to it.
    await user.hover(segments()[2])
    tip = screen.getByRole('status')
    expect(tip).toHaveTextContent('Maktabda emas')
    expect(tip).toHaveTextContent('13:40 - 14:20')
    expect(tip).not.toHaveTextContent('08:12')

    await user.hover(segments()[3])
    tip = screen.getByRole('status')
    expect(tip).toHaveTextContent('14:20 - 17:55')
  })

  it('drops the reading when the pointer leaves the band', async () => {
    const user = userEvent.setup()
    render(<PresenceTimeline timeline={TIMELINE} />)

    await user.hover(segments()[0])
    expect(screen.getByRole('status')).toHaveTextContent('06:00 - 08:12')

    await user.unhover(segments()[0])
    expect(screen.queryByRole('status')).toBeNull()
  })
})

describe('the teacher dashboard', () => {
  it('shows the week, not a pupil', async () => {
    render(<TeacherDashboardPage />)

    expect(await screen.findByText('Joriy hafta')).toBeInTheDocument()
    expect(screen.getByText('Maktabda aktiv')).toBeInTheDocument()
    expect(screen.getByText('Maktabda noaktiv')).toBeInTheDocument()
    expect(screen.getByText('Kechikkan kunlar')).toBeInTheDocument()
    expect(screen.getByText('Hasanov Samir Xayrilloyevich')).toBeInTheDocument()
    expect(screen.queryByText('Joriy oy')).toBeNull()
  })

  it('reports the first entry and last exit under the timeline', async () => {
    render(<TeacherDashboardPage />)

    expect(await screen.findByText('Birinchi kirish-chiqish vaqti')).toBeInTheDocument()
    expect(screen.getByText('08:12 - 17:55')).toBeInTheDocument()
    expect(screen.getAllByText('08:12').length).toBeGreaterThan(0)
    expect(screen.getAllByText('17:55').length).toBeGreaterThan(0)
  })

  it('lists the turnstile log newest first', async () => {
    render(<TeacherDashboardPage />)

    expect(await screen.findByText('Turniket tarixi')).toBeInTheDocument()
    const rows = screen.getAllByRole('listitem')
    expect(within(rows[0]).getByText('Chiqdi')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Kirdi')).toBeInTheDocument()
  })

  it('says so when the gate has nothing', async () => {
    vi.mocked(teachingApi.dashboard).mockResolvedValue({
      teacher: TEACHER,
      week: {
        start_date: '2026-09-14',
        end_date: '2026-09-20',
        school_days: 0,
        active_minutes: 0,
        inactive_minutes: 0,
        late_days: 0,
      },
      timeline: { ...TIMELINE, segments: [], first_in: null, last_out: null },
      recent_passes: [],
    } as never)
    render(<TeacherDashboardPage />)

    expect(await screen.findByText("Turniket ma'lumotlari mavjud emas")).toBeInTheDocument()
    // Missing times read as a dash, never as an invented clock.
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3)
  })
})

describe('the teacher profile', () => {
  function renderProfile() {
    return render(
      <MemoryRouter>
        <TeacherProfile />
      </MemoryRouter>,
    )
  }

  it('fills the fields from the record', async () => {
    renderProfile()

    expect(await screen.findByLabelText('Ism')).toHaveValue('Samir')
    expect(screen.getByLabelText('Familiya')).toHaveValue('Hasanov')
    expect(screen.getByLabelText('Otasining ismi')).toHaveValue('Xayrilloyevich')
    expect(screen.getByLabelText("Tug'ilgan sana")).toHaveValue('1990-03-04')
    expect(screen.getByLabelText('Passport ID')).toHaveValue('AA1234567')
    expect(screen.getByLabelText('Telefon')).toHaveValue('+998(90)123-45-67')
    expect(screen.getByLabelText('Login')).toHaveValue('s.hasanov')
  })

  it('never loads a password into the form', async () => {
    renderProfile()

    const password = await screen.findByLabelText('Parol')
    expect(password).toHaveValue('')
    expect(password).toBeDisabled()
    expect(screen.getByLabelText('Parolni tasdiqlang')).toBeDisabled()
  })

  it('unlocks both password fields only when the box is ticked', async () => {
    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByLabelText("Parolni o'zgartirish"))
    expect(screen.getByLabelText('Parol')).toBeEnabled()
    expect(screen.getByLabelText('Parolni tasdiqlang')).toBeEnabled()
  })

  it('sends no password when the box is left alone', async () => {
    const user = userEvent.setup()
    renderProfile()

    await user.clear(await screen.findByLabelText('Ism'))
    await user.type(screen.getByLabelText('Ism'), 'Samirbek')
    await user.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() => expect(teachingApi.saveProfile).toHaveBeenCalled())
    const payload = vi.mocked(teachingApi.saveProfile).mock.calls[0][0]
    expect(payload.first_name).toBe('Samirbek')
    expect(payload).not.toHaveProperty('password')
  })

  it('refuses to save while the two passwords differ', async () => {
    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByLabelText("Parolni o'zgartirish"))
    await user.type(screen.getByLabelText('Parol'), 'Maktab2026!')
    await user.type(screen.getByLabelText('Parolni tasdiqlang'), 'boshqa')

    expect(screen.getByText('Parollar mos kelmadi')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Saqlash' })).toBeDisabled()
  })

  it('sends both fields once they match', async () => {
    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByLabelText("Parolni o'zgartirish"))
    await user.type(screen.getByLabelText('Parol'), 'Maktab2026!')
    await user.type(screen.getByLabelText('Parolni tasdiqlang'), 'Maktab2026!')
    await user.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() =>
      expect(teachingApi.saveProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          password: 'Maktab2026!',
          password_confirm: 'Maktab2026!',
        }),
      ),
    )
  })

  it('shows the stored JSHSHIR in full and sends it back unchanged', async () => {
    const user = userEvent.setup()
    renderProfile()

    expect(await screen.findByLabelText('JSHSHIR')).toHaveValue('31234567890123')

    await user.click(screen.getByRole('button', { name: 'Saqlash' }))
    await waitFor(() => expect(teachingApi.saveProfile).toHaveBeenCalled())
    expect(vi.mocked(teachingApi.saveProfile).mock.calls[0][0].jshshir).toBe('31234567890123')
  })

  it('leaves the stored JSHSHIR alone when the field is cleared', async () => {
    const user = userEvent.setup()
    renderProfile()

    await user.clear(await screen.findByLabelText('JSHSHIR'))
    await user.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() => expect(teachingApi.saveProfile).toHaveBeenCalled())
    expect(vi.mocked(teachingApi.saveProfile).mock.calls[0][0]).not.toHaveProperty('jshshir')
  })

  it('groups the subjects under a heading per class', async () => {
    renderProfile()

    expect(await screen.findByText('Sizga biriktirilgan fanlar')).toBeInTheDocument()

    // One block per class group, the group as its heading.
    const headings = screen.getAllByRole('heading', { level: 3 })
    expect(headings.map((heading) => heading.textContent)).toEqual(['1-A', '2-A'])

    // The subject cards sit under their own class, not in one flat list.
    const first = headings[0]!.closest('section') as HTMLElement
    expect(within(first).getByText('Matematika')).toBeInTheDocument()
  })
})
