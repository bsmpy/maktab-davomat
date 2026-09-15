import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/errors'
import { StudentStep } from '@/features/registration/steps/StudentStep'
import type { ClassGroup, StudentSearchResult } from '@/types/api'

vi.mock('@/api/registrationApi', () => ({
  registrationApi: { searchStudents: vi.fn(), relations: vi.fn(), identify: vi.fn() },
}))

const { registrationApi } = await import('@/api/registrationApi')

const CLASS_GROUP: ClassGroup = {
  id: 'cg-7a',
  name: 'A',
  display_name: '7-A',
  grade: 'g7',
  grade_level: 7,
  school: 'school-1',
  room: '701',
}

const RESULT: StudentSearchResult = {
  id: 'st-1',
  display_name: 'Valiyev A.',
  full_name: 'Valiyev A.',
  class_group: '7-A',
  birth_year: 2013,
  photo: 'http://192.168.0.100/media/students/photos/st-1.jpg',
  has_registered_guardian: false,
}

function renderStep(onSelect = vi.fn(), onBack = vi.fn()) {
  render(<StudentStep classGroup={CLASS_GROUP} onSelect={onSelect} onBack={onBack} />)
  return { onSelect, onBack }
}

describe('registration · pupil search', () => {
  it('does not query the API until the term is long enough', async () => {
    renderStep()
    await userEvent.type(screen.getByLabelText(/ism-familiyasi/i), 'Va')
    await new Promise((resolve) => setTimeout(resolve, 600))
    expect(registrationApi.searchStudents).not.toHaveBeenCalled()
  })

  it('searches within the chosen class group and shows masked names', async () => {
    vi.mocked(registrationApi.searchStudents).mockResolvedValue([RESULT])
    renderStep()

    await userEvent.type(screen.getByLabelText(/ism-familiyasi/i), 'Valiyev')

    expect(await screen.findByText('Valiyev A.')).toBeInTheDocument()
    expect(registrationApi.searchStudents).toHaveBeenCalledWith({
      class_group: 'cg-7a',
      query: 'Valiyev',
    })
    // The masked name is all the public endpoint returns — no full name, no id.
    expect(screen.queryByText(/Azizbek/)).not.toBeInTheDocument()
  })

  it('hands the chosen pupil back to the wizard', async () => {
    vi.mocked(registrationApi.searchStudents).mockResolvedValue([RESULT])
    const { onSelect } = renderStep()

    await userEvent.type(screen.getByLabelText(/ism-familiyasi/i), 'Valiyev')
    await userEvent.click(await screen.findByText('Valiyev A.'))

    expect(onSelect).toHaveBeenCalledWith(RESULT)
  })

  it('tells the user when nothing matched', async () => {
    vi.mocked(registrationApi.searchStudents).mockResolvedValue([])
    renderStep()

    await userEvent.type(screen.getByLabelText(/ism-familiyasi/i), 'Nomavjud')
    expect(await screen.findByText(/Hech narsa topilmadi/)).toBeInTheDocument()
  })

  it('surfaces a rate-limit message from the server', async () => {
    vi.mocked(registrationApi.searchStudents).mockRejectedValue(
      new ApiError(
        { code: 'TOO_MANY_REQUESTS', message: 'Juda ko\'p urinish.', fields: {} },
        429,
      ),
    )
    renderStep()

    await userEvent.type(screen.getByLabelText(/ism-familiyasi/i), 'Valiyev')
    expect(await screen.findByText("Juda ko'p urinish.")).toBeInTheDocument()
  })

  it('never shows results from a superseded query', async () => {
    vi.mocked(registrationApi.searchStudents).mockImplementation(async ({ query }) => {
      if (query === 'Valiyev') {
        await new Promise((resolve) => setTimeout(resolve, 300))
        return [RESULT]
      }
      return [{ ...RESULT, id: 'st-2', display_name: 'Karimov B.' }]
    })

    renderStep()
    const input = screen.getByLabelText(/ism-familiyasi/i)
    await userEvent.type(input, 'Valiyev')
    await userEvent.clear(input)
    await userEvent.type(input, 'Karimov')

    expect(await screen.findByText('Karimov B.')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('Valiyev A.')).not.toBeInTheDocument())
  })

  it('shows the photo so namesakes can be told apart', async () => {
    vi.mocked(registrationApi.searchStudents).mockResolvedValue([RESULT])
    renderStep()

    await userEvent.type(screen.getByLabelText(/ism-familiyasi/i), 'Valiyev')
    const photo = await screen.findByRole('img', { name: 'Valiyev A.' })
    expect(photo).toHaveAttribute('src', RESULT.photo)
  })

  it('falls back to initials for a pupil with no photo', async () => {
    vi.mocked(registrationApi.searchStudents).mockResolvedValue([
      { ...RESULT, photo: null },
    ])
    renderStep()

    await userEvent.type(screen.getByLabelText(/ism-familiyasi/i), 'Valiyev')
    expect(await screen.findByText('Valiyev A.')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
