import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/adminApi', () => ({ adminApi: { overview: vi.fn() } }))

const { adminApi } = await import('@/api/adminApi')
const { AdminHomePage } = await import('@/pages/AdminHomePage')
const { useAuthStore } = await import('@/store/authStore')
const i18n = (await import('@/i18n')).default

function day(overrides: Record<string, number> = {}) {
  return {
    total: 10,
    arrived: 8,
    absent: 2,
    inside: 6,
    late: 3,
    rate: 80,
    avg_active_minutes: 300,
    avg_inactive_minutes: 120,
    avg_late_minutes: 15,
    ...overrides,
  }
}

function overview() {
  return {
    school: '15-maktab',
    date: '2026-09-15',
    register: {
      students: 842,
      teachers: 57,
      staff: 12,
      positions: 4,
      class_groups: 33,
      subjects: 128,
      guardians: 913,
      lessons_scheduled: 264,
    },
    today: day(),
    students_today: day(),
    teachers_today: day({ total: 57, arrived: 50, absent: 7, inside: 44, late: 2 }),
    lessons: { marked: 0, absent: 0, excused: 0 },
    terminals: { total: 0, online: 0, offline: 0 },
  }
}

beforeEach(async () => {
  await i18n.changeLanguage('uz')
  useAuthStore.setState({
    user: { role: 'DEVELOPER', first_name: 'Behruz', full_name: 'Behruz S' } as never,
  })
  vi.mocked(adminApi.overview).mockResolvedValue(overview() as never)
})

describe("the developer's home screen", () => {
  /**
   * The order was asked for explicitly: how big the school is, then the
   * teachers' day, then the pupils' day, then the averages. A test on the
   * order is the only thing that keeps a later edit from quietly reshuffling
   * it.
   */
  it('reads register → teachers → pupils → averages, top to bottom', async () => {
    render(<AdminHomePage />)

    const headings = (await screen.findAllByRole('heading', { level: 2 })).map(
      (node) => node.textContent,
    )
    expect(headings).toEqual([
      'Reyestr',
      "O'qituvchilar davomati",
      "O'quvchilar davomati",
      "O'qituvchilar",
      "O'quvchilar",
    ])
  })

  it('opens on the four register counts', async () => {
    render(<AdminHomePage />)

    await screen.findByText('Reyestr')
    for (const [label, value] of [
      ["O'qituvchilar", '57'],
      ['Staff xodimlar', '12'],
      ["O'quvchilar", '842'],
      ['Guruhlar', '33'],
    ]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
      expect(screen.getAllByText(value).length).toBeGreaterThan(0)
    }
  })

  it('asks the teachers and the pupils the same four questions', async () => {
    render(<AdminHomePage />)
    await screen.findByText("O'qituvchilar davomati")

    for (const label of ['Keldi', 'Kechikdi', 'Kelmadi', 'Hozir maktabda']) {
      // Once for the teachers, once for the pupils.
      expect(screen.getAllByText(label)).toHaveLength(2)
    }
  })

  it('shows each half its own three averages', async () => {
    render(<AdminHomePage />)
    await screen.findByText("O'qituvchilar davomati")

    for (const label of [
      "Aktiv o'rtacha vaqt",
      "Noaktiv o'rtacha vaqt",
      "Kechikkan o'rtacha vaqt",
    ]) {
      expect(screen.getAllByText(label)).toHaveLength(2)
    }
  })

  it('reads the teachers from their own figures, not the pupils', async () => {
    render(<AdminHomePage />)

    const teachers = (await screen.findByText("O'qituvchilar davomati")).closest('section')!
    expect(within(teachers).getByText('50')).toBeInTheDocument()
    expect(within(teachers).getByText('57 tadan')).toBeInTheDocument()
  })

  /** Everything on the screen is a translation key, not a hardcoded string. */
  it('renders in Russian when the interface is in Russian', async () => {
    await i18n.changeLanguage('ru')
    render(<AdminHomePage />)

    expect(await screen.findByText('Реестр')).toBeInTheDocument()
    expect(screen.getByText('Посещаемость учителей')).toBeInTheDocument()
    expect(screen.getAllByText('Пришли')).toHaveLength(2)
    await i18n.changeLanguage('uz')
  })
})
