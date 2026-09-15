import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/errors'
import { LessonRoster } from '@/features/attendance/lessons/LessonRoster'
import type { LessonRoster as LessonRosterData, LessonRosterStudent } from '@/types/api'

vi.mock('@/api/teachingApi', () => ({
  teachingApi: { roster: vi.fn(), saveMarks: vi.fn() },
}))

const { teachingApi } = await import('@/api/teachingApi')

function pupil(id: string, name: string, patch: Partial<LessonRosterStudent> = {}) {
  return {
    id,
    full_name: name,
    display_name: name,
    initials: name.slice(0, 2).toUpperCase(),
    photo: null,
    status: null,
    status_label: '',
    late_minutes: 0,
    comment: '',
    ...patch,
  } as LessonRosterStudent
}

function rosterData(
  students: LessonRosterStudent[],
  lock: { can_mark: boolean; opens_at: string | null } = { can_mark: true, opens_at: null },
): LessonRosterData {
  return {
    ...lock,
    subject: {
      id: 'subj-1',
      name: 'Matematika',
      display_name: 'Matematika 1-A',
      class_group: 'cg-1a',
      class_group_name: '1-A',
      grade_level: 1,
      students_count: students.length,
      marked_count: students.filter((row) => row.status).length,
      teachers: ['Rasulov Saodaddin'],
    },
    date: '2026-09-10',
    students,
  }
}

async function renderRoster(
  students: LessonRosterStudent[],
  lock?: { can_mark: boolean; opens_at: string | null },
) {
  vi.mocked(teachingApi.roster).mockResolvedValue(rosterData(students, lock))
  vi.mocked(teachingApi.saveMarks).mockResolvedValue(rosterData(students, lock))
  render(<LessonRoster subjectId="subj-1" date="2026-09-10" onBack={() => {}} />)
  return screen.findByText('Matematika 1-A')
}

function rowOf(name: string) {
  return screen.getByText(name).closest('li') as HTMLElement
}

describe('marking a lesson', () => {
  it('sends keldi with nothing else attached', async () => {
    const user = userEvent.setup()
    await renderRoster([pupil('s1', 'Valiyev Azizbek')])

    await user.click(within(rowOf('Valiyev Azizbek')).getByRole('button', { name: 'Keldi' }))
    await user.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() =>
      expect(teachingApi.saveMarks).toHaveBeenCalledWith('subj-1', '2026-09-10', [
        { student: 's1', status: 'PRESENT', late_minutes: 0, comment: '' },
      ]),
    )
  })

  it('asks how many minutes late, and refuses to save without them', async () => {
    const user = userEvent.setup()
    await renderRoster([pupil('s1', 'Valiyev Azizbek')])
    const row = rowOf('Valiyev Azizbek')

    await user.click(within(row).getByRole('button', { name: 'Kechikdi' }))
    expect(within(row).getByLabelText('Necha daqiqa kechikdi?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Saqlash' })).toBeDisabled()

    await user.type(within(row).getByLabelText('Necha daqiqa kechikdi?'), '12')
    await user.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() =>
      expect(teachingApi.saveMarks).toHaveBeenCalledWith('subj-1', '2026-09-10', [
        { student: 's1', status: 'LATE', late_minutes: 12, comment: '' },
      ]),
    )
  })

  it('splits kelmadi into sababli and sababsiz', async () => {
    const user = userEvent.setup()
    await renderRoster([pupil('s1', 'Valiyev Azizbek')])
    const row = rowOf('Valiyev Azizbek')

    await user.click(within(row).getByRole('button', { name: 'Kelmadi' }))
    expect(within(row).getByRole('button', { name: 'Sababli' })).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Sababsiz' })).toBeInTheDocument()
    // Sababsiz is the default, so the row is already complete.
    expect(screen.getByRole('button', { name: 'Saqlash' })).toBeEnabled()

    await user.click(within(row).getByRole('button', { name: 'Sababsiz' }))
    await user.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() =>
      expect(teachingApi.saveMarks).toHaveBeenCalledWith('subj-1', '2026-09-10', [
        { student: 's1', status: 'ABSENT', late_minutes: 0, comment: '' },
      ]),
    )
  })

  it('demands a written reason once sababli is chosen', async () => {
    const user = userEvent.setup()
    await renderRoster([pupil('s1', 'Valiyev Azizbek')])
    const row = rowOf('Valiyev Azizbek')

    await user.click(within(row).getByRole('button', { name: 'Kelmadi' }))
    await user.click(within(row).getByRole('button', { name: 'Sababli' }))

    expect(screen.getByRole('button', { name: 'Saqlash' })).toBeDisabled()
    await user.type(within(row).getByLabelText('Sababi'), 'Shifokorga bordi')
    await user.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() =>
      expect(teachingApi.saveMarks).toHaveBeenCalledWith('subj-1', '2026-09-10', [
        {
          student: 's1',
          status: 'EXCUSED',
          late_minutes: 0,
          comment: 'Shifokorga bordi',
        },
      ]),
    )
  })

  it('clears a mark when the same button is pressed again', async () => {
    const user = userEvent.setup()
    await renderRoster([pupil('s1', 'Valiyev Azizbek')])
    const row = rowOf('Valiyev Azizbek')

    await user.click(within(row).getByRole('button', { name: 'Keldi' }))
    await user.click(within(row).getByRole('button', { name: 'Keldi' }))
    await user.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() =>
      expect(teachingApi.saveMarks).toHaveBeenCalledWith('subj-1', '2026-09-10', [
        { student: 's1', status: '', late_minutes: 0, comment: '' },
      ]),
    )
  })

  it('starts from the marks already stored', async () => {
    await renderRoster([
      pupil('s1', 'Valiyev Azizbek', {
        status: 'EXCUSED',
        status_label: 'Sababli',
        comment: 'Kasal',
      }),
    ])
    const row = rowOf('Valiyev Azizbek')

    expect(within(row).getByText('Kelmadi · sababli')).toBeInTheDocument()
    expect(within(row).getByLabelText('Sababi')).toHaveValue('Kasal')
  })
})

describe('a lesson that has not started', () => {
  it('does not open the roll call at all when the server keeps it shut', async () => {
    vi.mocked(teachingApi.roster).mockRejectedValue(
      new ApiError(
        {
          code: 'LESSON_NOT_STARTED',
          message: 'Dars hali boshlanmadi. Davomatni 10:20 dan keyin belgilash mumkin.',
          fields: {},
        },
        409,
      ),
    )
    render(<LessonRoster subjectId="subj-1" date="2026-09-10" onBack={() => {}} />)

    expect(await screen.findByText(/10:20 dan keyin/)).toBeInTheDocument()
    // No pupils, no buttons to press, and no retry that can only fail again.
    expect(screen.queryByRole('button', { name: 'Keldi' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Saqlash' })).toBeNull()
    expect(screen.queryByRole('button', { name: /qayta/i })).toBeNull()
  })

  it('says when the register opens and leaves the buttons inert', async () => {
    const user = userEvent.setup()
    await renderRoster([pupil('s1', 'Valiyev Azizbek')], {
      can_mark: false,
      opens_at: '10:20',
    })
    const row = rowOf('Valiyev Azizbek')

    expect(screen.getByText(/Dars hali boshlanmadi/)).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Keldi' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Saqlash' })).toBeDisabled()

    await user.click(within(row).getByRole('button', { name: 'Keldi' }))
    expect(within(row).getByText('Belgilanmagan')).toBeInTheDocument()
    expect(teachingApi.saveMarks).not.toHaveBeenCalled()
  })

  it('leaves an existing mark visible but unchangeable', async () => {
    const user = userEvent.setup()
    await renderRoster(
      [pupil('s1', 'Valiyev Azizbek', { status: 'PRESENT', status_label: 'Keldi' })],
      { can_mark: false, opens_at: '10:20' },
    )
    const row = rowOf('Valiyev Azizbek')

    // The status line under the name still reads the stored mark.
    expect(within(row).getByRole('button', { name: 'Keldi' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    await user.click(within(row).getByRole('button', { name: 'Kelmadi' }))
    // Nothing moved: no sababli/sababsiz choice appeared.
    expect(within(row).queryByRole('button', { name: 'Sababli' })).toBeNull()
    expect(within(row).getByRole('button', { name: 'Keldi' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})
