import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import { AttendancePage } from '@/pages/AttendancePage'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import type { Role } from '@/types/api'

import { makeUser } from './session'

vi.mock('@/api/teachingApi', () => ({
  teachingApi: {
    classes: vi.fn(),
    classDay: vi.fn(),
    myLessons: vi.fn(),
    roster: vi.fn(),
    saveMarks: vi.fn(),
  },
}))
vi.mock('@/api/attendanceApi', () => ({
  attendanceApi: {
    daily: vi.fn(),
    weekly: vi.fn(),
    monthly: vi.fn(),
    yearly: vi.fn(),
    lessons: vi.fn(),
    reasons: vi.fn(),
    absenceRequests: vi.fn(),
    submitAbsenceReason: vi.fn(),
  },
}))

const { teachingApi } = await import('@/api/teachingApi')
const { attendanceApi } = await import('@/api/attendanceApi')

const SUBJECT = {
  id: 'subj-1',
  name: 'Matematika',
  display_name: 'Matematika 1-A',
  class_group: 'cg-1a',
  class_group_name: '1-A',
  grade_level: 1,
  students_count: 12,
  marked_count: 4,
  teachers: ['Rasulov Saodaddin'],
}

const CLASS = {
  id: 'cg-1a',
  display_name: '1-A',
  grade_level: 1,
  students_count: 12,
  marked_count: 4,
  schedule_state: 'TODAY' as const,
  subjects: [{ id: 'subj-1', name: 'Matematika', display_name: 'Matematika 1-A' }],
}

const LESSON = {
  subject: 'subj-1',
  subject_name: 'Matematika',
  class_group_name: '1-A',
  grade_level: 1,
  lesson_number: 1,
  start_time: '10:00',
  end_time: '10:45',
  room: '101',
  can_mark: true,
  opens_at: null,
}

const CLASS_DAY = {
  class_group: {
    id: 'cg-1a',
    display_name: '1-A',
    grade_level: 1,
    students_count: 12,
  },
  date: '2026-09-10',
  weekday: 4,
  has_timetable: true,
  lessons: [
    {
      id: 'sch-1',
      lesson_number: 1,
      start_time: '08:00',
      end_time: '08:40',
      room: '101',
      subject: 'subj-1',
      subject_name: 'Matematika',
      subject_display: 'Matematika 1-A',
      teacher: 't1',
      teacher_name: 'Rasulov Saodaddin',
      is_mine: true,
      marked_count: 4,
      students_count: 12,
      can_mark: true,
    },
  ],
}

function signIn(role: Role, childId: string | null) {
  useAuthStore.setState({
    user: makeUser(role) as never,
  })
  useChildStore.setState({ activeChildId: childId } as never)
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AttendancePage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(teachingApi.classes).mockResolvedValue([CLASS])
  vi.mocked(teachingApi.classDay).mockResolvedValue(CLASS_DAY as never)
  vi.mocked(teachingApi.myLessons).mockResolvedValue([LESSON] as never)
  vi.mocked(attendanceApi.daily).mockResolvedValue({
    date: '2026-09-10',
    was_present: false,
    entries: 0,
    exits: 0,
    inside_minutes: 0,
    outside_minutes: 0,
    late_minutes: 0,
    is_inside: false,
    visits: [],
    passes: [],
    state: 'NO_DATA',
  } as never)
  vi.mocked(attendanceApi.lessons).mockResolvedValue({
    start_date: '2026-09-10',
    end_date: '2026-09-10',
    summary: {
      lessons: 2,
      present: 1,
      late: 1,
      absent: 0,
      excused: 0,
      attended: 2,
      rate: 100,
    },
    subjects: [
      {
        id: 'subj-1',
        name: 'Matematika',
        display_name: 'Matematika 1-A',
        teacher: 'Rasulov Saodaddin',
        lessons: 2,
        present: 1,
        late: 1,
        absent: 0,
        excused: 0,
        attended: 2,
        rate: 100,
      },
    ],
    days: [
      {
        date: '2026-09-10',
        lessons: [
          {
            id: 'a1',
            date: '2026-09-10',
            lesson_number: 1,
            subject: 'Matematika',
            subject_display: 'Matematika 1-A',
            subject_id: 'subj-1',
            teacher: 'Rasulov Saodaddin',
            status: 'LATE',
            status_label: 'Kechikdi',
            late_minutes: 7,
            comment: '',
            is_canceled: false,
          },
        ],
      },
    ],
    today: '2026-09-10',
  } as never)
})

describe('the Davomat switch', () => {
  it('offers both registers', async () => {
    signIn('OTA-ONA', 'child-1')
    renderPage()

    expect(screen.getByRole('tab', { name: 'Maktab davomati' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Dars davomati' })).toBeInTheDocument()
    // The gate register is what opens first.
    await waitFor(() => expect(attendanceApi.daily).toHaveBeenCalled())
  })

  it('shows a parent their child’s lessons', async () => {
    const user = userEvent.setup()
    signIn('OTA-ONA', 'child-1')
    renderPage()

    await user.click(screen.getByRole('tab', { name: 'Dars davomati' }))

    await waitFor(() => expect(attendanceApi.lessons).toHaveBeenCalled())
    // Once in the per-subject table, once in the day-by-day list.
    expect(await screen.findAllByText('Matematika 1-A')).toHaveLength(2)
    expect(screen.getByText('Kechikdi · 7 daqiqa')).toBeInTheDocument()
    // A parent reads the register; they never get the teacher's cards.
    expect(teachingApi.classes).not.toHaveBeenCalled()
  })

  it('shows an administrator the classes, flagged for today', async () => {
    const user = userEvent.setup()
    signIn('SUPER_ADMIN', null)
    renderPage()

    await user.click(screen.getByRole('tab', { name: 'Dars davomati' }))

    expect(await screen.findByText('1-A')).toBeInTheDocument()
    expect(screen.getByLabelText('Bugun dars bor')).toBeInTheDocument()
    expect(attendanceApi.lessons).not.toHaveBeenCalled()
  })

  it('marks tomorrow in amber and the rest in grey', async () => {
    const user = userEvent.setup()
    vi.mocked(teachingApi.classes).mockResolvedValue([
      { ...CLASS, id: 'cg-1a', display_name: '1-A', schedule_state: 'TOMORROW' },
      { ...CLASS, id: 'cg-2b', display_name: '2-B', schedule_state: 'NONE' },
    ] as never)
    signIn('SUPER_ADMIN', null)
    renderPage()

    await user.click(screen.getByRole('tab', { name: 'Dars davomati' }))

    expect(await screen.findByLabelText('Ertaga dars bor')).toBeInTheDocument()
    expect(screen.getByLabelText('Yaqin kunlarda dars yo‘q')).toBeInTheDocument()
  })

  it('drills down class → day → register', async () => {
    const user = userEvent.setup()
    vi.mocked(teachingApi.roster).mockResolvedValue({
      subject: SUBJECT,
      date: '2026-09-10',
      students: [],
    } as never)
    signIn('SUPER_ADMIN', null)
    renderPage()

    await user.click(screen.getByRole('tab', { name: 'Dars davomati' }))
    await user.click(await screen.findByText('1-A'))

    // The class's day, with the timetable on it.
    await waitFor(() => expect(teachingApi.classDay).toHaveBeenCalled())
    expect(await screen.findByText('08:00 — 08:40')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Davomat' }))
    await waitFor(() => expect(teachingApi.roster).toHaveBeenCalled())
  })

  it('keeps the roll call shut until the lesson starts', async () => {
    const user = userEvent.setup()
    vi.mocked(teachingApi.roster).mockClear()
    vi.mocked(teachingApi.classDay).mockResolvedValue({
      ...CLASS_DAY,
      lessons: [{ ...CLASS_DAY.lessons[0], can_mark: false }],
    } as never)
    signIn('SUPER_ADMIN', null)
    renderPage()

    await user.click(screen.getByRole('tab', { name: 'Dars davomati' }))
    await user.click(await screen.findByText('1-A'))

    const open = await screen.findByRole('button', { name: 'Davomat' })
    expect(open).toBeDisabled()
    expect(screen.getByText('08:00 da ochiladi')).toBeInTheDocument()
    await user.click(open)
    expect(teachingApi.roster).not.toHaveBeenCalled()
  })

  it('does not block an administrator with no child of their own', async () => {
    signIn('SUPER_ADMIN', null)
    renderPage()

    // The gate register needs a pupil, but the page itself still loads.
    expect(screen.getByRole('tab', { name: 'Dars davomati' })).toBeInTheDocument()
  })
})

describe("a teacher's Davomat", () => {
  it('opens straight on their lessons, with no switches at all', async () => {
    signIn('TEACHER', null)
    renderPage()

    expect(await screen.findByText('Matematika')).toBeInTheDocument()
    expect(screen.getByText('1-A')).toBeInTheDocument()
    expect(screen.getByText('10:00 - 10:45')).toBeInTheDocument()

    // Neither switch is on the page.
    expect(screen.queryByRole('tab', { name: 'Maktab davomati' })).toBeNull()
    expect(screen.queryByRole('tab', { name: 'Dars davomati' })).toBeNull()
    expect(screen.queryByRole('tab', { name: 'Kunlik' })).toBeNull()
  })

  it('greys out a lesson that has not started', async () => {
    vi.mocked(teachingApi.myLessons).mockResolvedValue([
      { ...LESSON, can_mark: false, opens_at: '10:00' },
    ] as never)
    signIn('TEACHER', null)
    renderPage()

    expect(await screen.findByRole('button', { name: 'Davomat' })).toBeDisabled()
    expect(screen.getByText('10:00 da ochiladi')).toBeInTheDocument()
  })

  it('opens the register when the lesson has begun', async () => {
    const user = userEvent.setup()
    vi.mocked(teachingApi.roster).mockResolvedValue({
      subject: SUBJECT,
      date: '2026-09-10',
      can_mark: true,
      opens_at: null,
      students: [],
    } as never)
    signIn('TEACHER', null)
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Davomat' }))
    await waitFor(() => expect(teachingApi.roster).toHaveBeenCalled())
  })
})
