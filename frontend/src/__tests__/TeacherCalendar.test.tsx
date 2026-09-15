import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CalendarPage } from '@/pages/CalendarPage'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import type { LessonRosterStudent } from '@/types/api'

vi.mock('@/api/teachingApi', () => ({
  teachingApi: { calendar: vi.fn(), calendarDay: vi.fn(), roster: vi.fn() },
}))
vi.mock('@/api/attendanceApi', () => ({
  attendanceApi: { absenceRequests: vi.fn(), reasons: vi.fn(), submitAbsenceReason: vi.fn() },
}))

const { teachingApi } = await import('@/api/teachingApi')

function day(date: string, teaches: boolean, groups = teaches ? 1 : 0) {
  return {
    date,
    weekday: 1,
    in_month: true,
    is_school_day: true,
    holiday: null,
    teaches,
    groups_count: groups,
  }
}

function pupil(
  id: string,
  name: string,
  patch: Partial<LessonRosterStudent> = {},
): LessonRosterStudent {
  return {
    id,
    full_name: name,
    display_name: name,
    initials: 'XX',
    photo: null,
    status: null,
    status_label: '',
    late_minutes: 0,
    comment: '',
    ...patch,
  }
}

function lesson(subject: string, name: string, start: string, number: number) {
  return {
    subject,
    subject_name: name,
    lesson_number: number,
    start_time: start,
    end_time: '08:40',
    room: '101',
    marked_count: 0,
    students_count: 12,
  }
}

/** Only the classes this teacher actually taught that day. */
const DAY = {
  date: '2026-09-14',
  weekday: 1,
  holiday: null,
  groups: [
    {
      id: 'cg-1a',
      display_name: '1-A',
      grade_level: 1,
      students_count: 12,
      lessons: [lesson('subj-3', 'Fizika', '08:00', 1)],
    },
    {
      id: 'cg-3b',
      display_name: '3-B',
      grade_level: 3,
      students_count: 10,
      lessons: [
        lesson('subj-1', 'Matematika', '09:00', 2),
        lesson('subj-2', 'Ingliz tili', '10:00', 3),
      ],
    },
  ],
}

beforeEach(() => {
  useChildStore.setState({ children: [], activeChildId: null } as never)
  useAuthStore.setState({
    user: { id: 1, username: 't', full_name: 'T', role: 'TEACHER' } as never,
  })

  vi.mocked(teachingApi.calendar).mockResolvedValue({
    year: 2026,
    month: 9,
    start_date: '2026-08-31',
    end_date: '2026-10-04',
    today: '2026-09-14',
    days: [day('2026-09-14', true, 2), day('2026-09-15', false), day('2026-09-16', true)],
  } as never)

  vi.mocked(teachingApi.calendarDay).mockResolvedValue(DAY as never)

  vi.mocked(teachingApi.roster).mockResolvedValue({
    subject: {
      id: 'subj-1',
      name: 'Matematika',
      display_name: 'Matematika 3-B',
      class_group: 'cg-3b',
      class_group_name: '3-B',
      grade_level: 3,
      students_count: 4,
      marked_count: 4,
      teachers: [],
    },
    date: '2026-09-14',
    can_mark: true,
    opens_at: null,
    students: [
      pupil('s1', 'Valiyev Azizbek', { status: 'PRESENT' }),
      pupil('s2', 'Karimov Sardor', { status: 'LATE', late_minutes: 12 }),
      pupil('s3', 'Rustamov Bobur', { status: 'ABSENT' }),
      pupil('s4', 'Aliyeva Madina', { status: 'EXCUSED', comment: 'Shifokorga bordi' }),
    ],
  } as never)
})

function renderCalendar() {
  return render(
    <MemoryRouter initialEntries={['/kalendar?year=2026&month=9']}>
      <CalendarPage />
    </MemoryRouter>,
  )
}

describe('the month grid', () => {
  it('marks teaching days green and the rest red', async () => {
    renderCalendar()

    await waitFor(() => expect(teachingApi.calendar).toHaveBeenCalledWith(2026, 9))
    expect(screen.getAllByLabelText('Dars bor')).toHaveLength(2)
    expect(screen.getAllByLabelText("Dars yo'q")).toHaveLength(1)
    expect(screen.getAllByLabelText('Dars bor')[0].className).toContain('bg-emerald-500')
    expect(screen.getAllByLabelText("Dars yo'q")[0].className).toContain('bg-red-500')
  })

  it('walks months without leaving the page', async () => {
    const user = userEvent.setup()
    renderCalendar()

    await user.click(await screen.findByLabelText('Keyingi oy'))
    await waitFor(() => expect(teachingApi.calendar).toHaveBeenCalledWith(2026, 10))
  })
})

describe('the detail panel', () => {
  it('asks for a day before it shows anything', async () => {
    renderCalendar()
    expect(await screen.findByText('Kunni tanlang')).toBeInTheDocument()
    expect(teachingApi.calendarDay).not.toHaveBeenCalled()
  })

  it('lists only the groups this teacher taught that day', async () => {
    const user = userEvent.setup()
    renderCalendar()

    await user.click(await screen.findByText('14'))

    // The chosen date heads the panel.
    expect(await screen.findByText('14 Sentabr 2026')).toBeInTheDocument()
    await waitFor(() => expect(teachingApi.calendarDay).toHaveBeenCalledWith('2026-09-14'))

    const panel = screen.getByText('Guruhlar').closest('div') as HTMLElement
    expect(
      within(panel)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual(['1-A', '3-B'])
  })

  it('opens that day\'s lessons of the group in the same panel', async () => {
    const user = userEvent.setup()
    renderCalendar()

    await user.click(await screen.findByText('14'))
    await user.click(await screen.findByRole('button', { name: '3-B' }))

    expect(await screen.findByText('Fanlar')).toBeInTheDocument()
    expect(screen.getByText('Matematika')).toBeInTheDocument()
    expect(screen.getByText('Ingliz tili')).toBeInTheDocument()
    // A class the teacher did not teach that day is not offered at all.
    expect(screen.queryByText('Geografiya')).toBeNull()
    // The calendar never left the screen.
    expect(screen.getByLabelText('Keyingi oy')).toBeInTheDocument()
  })

  it('goes back from subjects to groups', async () => {
    const user = userEvent.setup()
    renderCalendar()

    await user.click(await screen.findByText('14'))
    await user.click(await screen.findByRole('button', { name: '3-B' }))
    await user.click(await screen.findByRole('button', { name: 'Guruhlar' }))

    expect(await screen.findByRole('button', { name: '1-A' })).toBeInTheDocument()
    expect(screen.queryByText('Ingliz tili')).toBeNull()
  })

  it('says so on a day with no lessons at all', async () => {
    const user = userEvent.setup()
    vi.mocked(teachingApi.calendarDay).mockResolvedValue({
      ...DAY,
      groups: [],
    } as never)
    renderCalendar()

    await user.click(await screen.findByText('14'))
    expect(await screen.findByText("Bu kuni darsingiz yo'q")).toBeInTheDocument()
  })

  it('shows the time and the marked count on each lesson', async () => {
    const user = userEvent.setup()
    renderCalendar()

    await user.click(await screen.findByText('14'))
    await user.click(await screen.findByRole('button', { name: '3-B' }))

    const rows = await screen.findAllByRole('listitem')
    const maths = rows.find((row) => within(row).queryByText('Matematika')) as HTMLElement
    expect(within(maths).getByText(/09:00 — 08:40/)).toBeInTheDocument()
    expect(within(maths).getByText('0 / 12')).toBeInTheDocument()
    expect(within(maths).getByRole('button', { name: "Ko'rish" })).toBeInTheDocument()
  })
})

describe('the register behind a subject', () => {
  async function openRegister(user: ReturnType<typeof userEvent.setup>) {
    renderCalendar()
    await user.click(await screen.findByText('14'))
    await user.click(await screen.findByRole('button', { name: '3-B' }))
    // Two lessons that day; open the first.
    await user.click((await screen.findAllByRole('button', { name: "Ko'rish" }))[0]!)
    await waitFor(() => expect(teachingApi.roster).toHaveBeenCalled())
  }

  it('shows every mark with its own dot and wording', async () => {
    const user = userEvent.setup()
    await openRegister(user)

    const rows = await screen.findAllByRole('listitem')
    const read = (name: string) =>
      rows.find((row) => within(row).queryByText(name)) as HTMLElement

    expect(within(read('Valiyev Azizbek')).getByText('Keldi')).toBeInTheDocument()
    expect(
      within(read('Karimov Sardor')).getByText('Kechikdi · 12 daqiqa'),
    ).toBeInTheDocument()
    expect(within(read('Rustamov Bobur')).getByText('Kelmadi')).toBeInTheDocument()
    expect(
      within(read('Aliyeva Madina')).getByText('Kelmadi · Shifokorga bordi'),
    ).toBeInTheDocument()
  })

  it('paints both kinds of absence red and lateness amber', async () => {
    const user = userEvent.setup()
    await openRegister(user)

    const rows = await screen.findAllByRole('listitem')
    const dotOf = (name: string) =>
      (rows.find((row) => within(row).queryByText(name)) as HTMLElement).querySelector(
        'span.rounded-full',
      )?.className ?? ''

    expect(dotOf('Valiyev Azizbek')).toContain('bg-emerald-500')
    expect(dotOf('Karimov Sardor')).toContain('bg-amber-500')
    expect(dotOf('Rustamov Bobur')).toContain('bg-red-500')
    expect(dotOf('Aliyeva Madina')).toContain('bg-red-500')
  })
})

describe('the browser Back button', () => {
  /** A harness with a real history stack and a button that steps back once. */
  function Harness() {
    const navigate = useNavigate()
    return (
      <>
        <button type="button" onClick={() => navigate(-1)}>
          browser-back
        </button>
        <CalendarPage />
      </>
    )
  }

  it('undoes exactly one step of the panel', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/kalendar?year=2026&month=9']}>
        <Harness />
      </MemoryRouter>,
    )
    const back = () => user.click(screen.getByRole('button', { name: 'browser-back' }))

    await user.click(await screen.findByText('14'))
    await user.click(await screen.findByRole('button', { name: '3-B' }))
    await user.click((await screen.findAllByRole('button', { name: "Ko'rish" }))[0]!)
    expect(await screen.findByText('Valiyev Azizbek')).toBeInTheDocument()

    await back()
    expect(await screen.findByText('Ingliz tili')).toBeInTheDocument()

    await back()
    expect(await screen.findByRole('button', { name: '1-A' })).toBeInTheDocument()

    await back()
    expect(await screen.findByText('Kunni tanlang')).toBeInTheDocument()
  })
})

describe('the calendar for the other roles', () => {
  it('gives an administrator the same month and panel', async () => {
    const user = userEvent.setup()
    useAuthStore.setState({
      user: { id: 1, username: 'a', full_name: 'A', role: 'ADMIN' } as never,
    })
    render(
      <MemoryRouter initialEntries={['/kalendar?year=2026&month=9']}>
        <CalendarPage />
      </MemoryRouter>,
    )

    // Same endpoints as a teacher: the server decides how wide the scope is.
    await waitFor(() => expect(teachingApi.calendar).toHaveBeenCalledWith(2026, 9))
    await user.click(await screen.findByText('14'))
    await waitFor(() => expect(teachingApi.calendarDay).toHaveBeenCalledWith('2026-09-14'))
    expect(await screen.findByRole('button', { name: '3-B' })).toBeInTheDocument()
  })
})
