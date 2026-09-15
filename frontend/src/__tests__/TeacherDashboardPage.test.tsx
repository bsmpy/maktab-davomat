import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '@/i18n'
import { TeacherDashboardPage } from '@/pages/TeacherDashboardPage'
import type { TeacherDashboard } from '@/types/api'

vi.mock('@/api/teachingApi', () => ({
  teachingApi: { dashboard: vi.fn() },
}))

const { teachingApi } = await import('@/api/teachingApi')

const BASE: TeacherDashboard = {
  teacher: {
    id: 't-1',
    first_name: 'Nodira',
    last_name: 'Usmonova',
    middle_name: '',
    full_name: 'Usmonova Nodira',
    photo: null,
    email: '',
    school: { id: 's-1', name: '1-maktab' } as never,
  },
  week: {
    start_date: '2026-09-14',
    end_date: '2026-09-19',
    school_days: 1,
    active_minutes: 0,
    inactive_minutes: 0,
    late_days: 0,
  },
  timeline: {
    date: '2026-09-14',
    start_hour: 6,
    end_hour: 24,
    segments: [],
    first_in: null,
    last_out: null,
    is_inside: false,
    inside_minutes: 0,
  },
  recent_passes: [],
  lessons_today: null,
  groups_today: null,
}

beforeEach(async () => {
  await i18n.changeLanguage('uz')
  vi.clearAllMocks()
})

describe('the employee home screen', () => {
  it("shows a teacher only today's lessons and no group figures", async () => {
    vi.mocked(teachingApi.dashboard).mockResolvedValue({
      ...BASE,
      lessons_today: [
        {
          id: 'l-1',
          subject: 'subj-1',
          subject_name: 'Matematika',
          class_group: 'cg-7a',
          class_group_name: '7-A',
          lesson_number: 2,
          start_time: '08:50',
          end_time: '09:35',
          room: '204',
          students_count: 25,
          marked_count: 0,
        },
      ],
    })
    render(<TeacherDashboardPage />)

    expect(await screen.findByText('Bugungi darslarim')).toBeInTheDocument()
    expect(screen.getByText('Matematika')).toBeInTheDocument()
    expect(screen.getByText('7-A · 204')).toBeInTheDocument()
    expect(screen.getByText('Davomat qilinmagan')).toBeInTheDocument()
    expect(screen.queryByText('Guruhlarim · bugun')).not.toBeInTheDocument()
  })

  it('shows a curator their own groups and no lesson list', async () => {
    vi.mocked(teachingApi.dashboard).mockResolvedValue({
      ...BASE,
      groups_today: [
        {
          id: 'cg-7b',
          display_name: '7-B',
          grade_level: 7,
          pupils: {
            total: 24,
            arrived: 21,
            absent: 3,
            inside: 20,
            late: 2,
            rate: 87.5,
            avg_active_minutes: 0,
            avg_inactive_minutes: 0,
            avg_late_minutes: 0,
          },
          lessons: { marked: 0, absent: 0, excused: 0 },
        },
      ],
    })
    render(<TeacherDashboardPage />)

    expect(await screen.findByText('Guruhlarim · bugun')).toBeInTheDocument()
    expect(screen.getByText('7-B')).toBeInTheDocument()
    expect(screen.getByText('87.5% davomat')).toBeInTheDocument()
    expect(screen.getByText('21')).toBeInTheDocument()
    expect(screen.queryByText('Bugungi darslarim')).not.toBeInTheDocument()
  })

  it('shows an administrator only their own day', async () => {
    vi.mocked(teachingApi.dashboard).mockResolvedValue(BASE)
    render(<TeacherDashboardPage />)

    expect(await screen.findByText('Usmonova Nodira')).toBeInTheDocument()
    expect(screen.queryByText('Bugungi darslarim')).not.toBeInTheDocument()
    expect(screen.queryByText('Guruhlarim · bugun')).not.toBeInTheDocument()
  })
})
