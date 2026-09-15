import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { SubjectsPanel, TeachersPanel } from '@/features/admin/SchoolPanel'
import type { ManagedClassGroup, ManagedSubject, ManagedTeacher } from '@/types/api'

vi.mock('@/api/adminApi', () => ({
  adminApi: {
    subjects: vi.fn(),
    teachers: vi.fn(),
    createSubject: vi.fn(),
    deleteSubject: vi.fn(),
    createTeacher: vi.fn(),
    updateTeacher: vi.fn(),
    deleteTeacher: vi.fn(),
  },
}))

vi.mock('@/api/managementApi', () => ({
  managementApi: { classGroups: vi.fn() },
}))

const { adminApi } = await import('@/api/adminApi')
const { managementApi } = await import('@/api/managementApi')

function group(id: string, level: number, name: string): ManagedClassGroup {
  return {
    id,
    name,
    display_name: `${level}-${name}`,
    room: '',
    grade_id: `g${level}`,
    grade_level: level,
    students_count: 0,
  }
}

function subject(id: string, name: string, group: ManagedClassGroup): ManagedSubject {
  return {
    id,
    name,
    display_name: `${name} ${group.display_name}`,
    class_group: group.id,
    class_group_name: group.display_name,
    grade_level: group.grade_level,
    short_name: '',
    color: '',
    is_active: true,
  }
}

const GROUPS = [group('cg1a', 1, 'A'), group('cg1b', 1, 'B'), group('cg2a', 2, 'A')]

const SUBJECTS = [
  subject('m1', 'Matematika', GROUPS[0]),
  subject('m2', 'Matematika', GROUPS[1]),
  subject('m3', 'Matematika', GROUPS[2]),
  subject('geo', 'Geografiya', GROUPS[0]),
]

const TEACHER: ManagedTeacher = {
  id: 't1',
  full_name: 'Yusupov Sardor',
  first_name: 'Sardor',
  last_name: 'Yusupov',
  middle_name: '',
  passport_id: 'AA1234567',
  jshshir: '31234567890123',
  masked_jshshir: '**********0123',
  has_jshshir: true,
  birth_date: '1988-04-12',
  gender: 'MALE',
  gender_label: 'Erkak',
  phone: '+998901234567',
  email: '',
  photo: null,
  is_active: true,
  username: null,
  subjects: [],
}

async function renderPanel(teacher: ManagedTeacher = TEACHER) {
  vi.mocked(adminApi.subjects).mockResolvedValue(SUBJECTS)
  vi.mocked(adminApi.teachers).mockResolvedValue([teacher])
  vi.mocked(managementApi.classGroups).mockResolvedValue(GROUPS)
  vi.mocked(adminApi.updateTeacher).mockResolvedValue({ ...teacher })
  vi.mocked(adminApi.createSubject).mockResolvedValue(SUBJECTS[0])
  vi.mocked(adminApi.createTeacher).mockResolvedValue({ ...teacher })
  render(<TeachersPanel />)
  return screen.findByRole('combobox', { name: "O'qituvchi" })
}

/** The card that attaches subjects, told apart from the create form above it. */
function assignCard() {
  return screen.getByText("Fanlarni o'qituvchiga biriktirish").closest('div.card') as HTMLElement
}

/** The subject card, told apart from the attach card below it. */
function subjectCard() {
  return screen.getByText('Fanlar').closest('div.card') as HTMLElement
}

async function renderSubjects() {
  vi.mocked(adminApi.subjects).mockResolvedValue(SUBJECTS)
  vi.mocked(managementApi.classGroups).mockResolvedValue(GROUPS)
  vi.mocked(adminApi.createSubject).mockResolvedValue(SUBJECTS[0])
  render(<SubjectsPanel />)
  // The form only appears once the class groups have arrived.
  await screen.findByLabelText('Sinf')
}

describe('adding a subject', () => {
  it('takes the grade, then the group, then the name', async () => {
    const user = userEvent.setup()
    await renderSubjects()
    const card = subjectCard()

    // Nothing can be typed before a class group is chosen.
    expect(within(card).getByLabelText('Fan nomi')).toBeDisabled()
    expect(within(card).getByLabelText('Sinf guruhi')).toBeDisabled()

    await user.selectOptions(within(card).getByLabelText('Sinf'), '1')
    const groups = within(card).getByLabelText('Sinf guruhi')
    // Only the groups of the chosen grade are offered.
    expect(
      within(groups)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Tanlang…', '1-A', '1-B'])

    await user.selectOptions(groups, 'cg1a')
    await user.type(within(card).getByLabelText('Fan nomi'), 'Fizika')
    await user.click(within(card).getByRole('button', { name: "Qo'shish" }))

    await waitFor(() =>
      expect(adminApi.createSubject).toHaveBeenCalledWith({
        name: 'Fizika',
        class_group: 'cg1a',
      }),
    )
  })

  it('groups the subjects under a heading per class', async () => {
    await renderSubjects()
    const card = subjectCard()

    // One block per class group, in register order.
    const headings = within(card).getAllByRole('heading', { level: 3 })
    expect(headings.map((heading) => heading.textContent)).toEqual(['1-A', '1-B', '2-A'])

    // The chips inside a block carry the bare subject name; the class is the
    // heading above them.
    const first = headings[0]!.closest('section') as HTMLElement
    expect(within(first).getByText('Matematika')).toBeInTheDocument()
    expect(within(first).getByText('Geografiya')).toBeInTheDocument()
    expect(within(first).queryByText('Matematika 1-A')).toBeNull()
  })

  it('sends nobody to the form when there are no class groups yet', async () => {
    vi.mocked(adminApi.subjects).mockResolvedValue([])
    vi.mocked(managementApi.classGroups).mockResolvedValue([])
    render(<SubjectsPanel />)

    expect(await screen.findByText('Avval sinf guruhlarini yarating')).toBeInTheDocument()
    expect(screen.queryByLabelText('Fan nomi')).toBeNull()
  })
})

/** Opens the add-teacher modal and returns it. */
async function openTeacherForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: /O'qituvchi qo'shish/ }))
  return screen.getByRole('dialog')
}

describe('teacher credentials', () => {
  it('creates the teacher without an account when the fields are left empty', async () => {
    const user = userEvent.setup()
    await renderPanel()
    const form = await openTeacherForm(user)

    await user.type(within(form).getByLabelText('Ism'), 'Sardor')
    await user.type(within(form).getByLabelText('Familiya'), 'Yusupov')
    await user.click(within(form).getByRole('button', { name: "Qo'shish" }))

    await waitFor(() => expect(adminApi.createTeacher).toHaveBeenCalled())
    const payload = vi.mocked(adminApi.createTeacher).mock.calls[0][0]
    expect(payload).not.toHaveProperty('username')
    expect(payload).not.toHaveProperty('password')
  })

  it('sends the login and both passwords when they are filled in', async () => {
    const user = userEvent.setup()
    await renderPanel()
    const form = await openTeacherForm(user)

    await user.type(within(form).getByLabelText('Ism'), 'Sardor')
    await user.type(within(form).getByLabelText('Familiya'), 'Yusupov')
    // Typed in upper case, stored as the API expects it.
    await user.type(within(form).getByLabelText('Login'), 'S.Yusupov')
    await user.type(within(form).getByLabelText('Parol'), 'Maktab2026!')
    await user.type(within(form).getByLabelText('Parolni tasdiqlang'), 'Maktab2026!')
    await user.click(within(form).getByRole('button', { name: "Qo'shish" }))

    await waitFor(() =>
      expect(adminApi.createTeacher).toHaveBeenCalledWith(
        expect.objectContaining({
          username: 's.yusupov',
          password: 'Maktab2026!',
          password_confirm: 'Maktab2026!',
        }),
        null,
      ),
    )
  })

  it('refuses to submit while the two passwords differ', async () => {
    const user = userEvent.setup()
    await renderPanel()
    const form = await openTeacherForm(user)

    await user.type(within(form).getByLabelText('Ism'), 'Sardor')
    await user.type(within(form).getByLabelText('Familiya'), 'Yusupov')
    await user.type(within(form).getByLabelText('Login'), 's.yusupov')
    await user.type(within(form).getByLabelText('Parol'), 'Maktab2026!')
    await user.type(within(form).getByLabelText('Parolni tasdiqlang'), 'Maktab2027!')

    expect(within(form).getByText('Parollar mos kelmadi')).toBeInTheDocument()
    expect(within(form).getByRole('button', { name: "Qo'shish" })).toBeDisabled()
    expect(adminApi.createTeacher).not.toHaveBeenCalled()
  })

  it('refuses a login with no password behind it', async () => {
    const user = userEvent.setup()
    await renderPanel()
    const form = await openTeacherForm(user)

    await user.type(within(form).getByLabelText('Ism'), 'Sardor')
    await user.type(within(form).getByLabelText('Familiya'), 'Yusupov')
    await user.type(within(form).getByLabelText('Login'), 's.yusupov')

    expect(within(form).getByText('Kamida 8 ta belgi')).toBeInTheDocument()
    expect(within(form).getByRole('button', { name: "Qo'shish" })).toBeDisabled()
  })
})

describe('the order of the teacher blocks', () => {
  /**
   * The register of people first, then the action performed on one of them.
   * Asked for explicitly, and exactly the kind of thing a later edit reshuffles
   * without anyone noticing.
   */
  it('puts the teacher list above the attach-subjects card', async () => {
    await renderPanel()

    const headings = screen
      .getAllByRole('heading', { level: 2 })
      .map((node) => node.textContent)

    expect(headings.indexOf("O'qituvchilar")).toBeGreaterThanOrEqual(0)
    expect(headings.indexOf("O'qituvchilar")).toBeLessThan(
      headings.indexOf("Fanlarni o'qituvchiga biriktirish"),
    )
  })
})

describe('attaching subjects to a teacher', () => {
  /** Teacher, then class, then group — the cascade the register now needs. */
  async function openGroup(user: ReturnType<typeof userEvent.setup>, grade: string, group: string) {
    const card = assignCard()
    await user.selectOptions(within(card).getByLabelText('Sinf'), grade)
    await user.selectOptions(within(card).getByLabelText('Guruh'), group)
    return card
  }

  it('shows nothing until a group is chosen', async () => {
    const user = userEvent.setup()
    const picker = await renderPanel()
    await user.selectOptions(picker, 't1')

    const card = assignCard()
    // Six hundred subjects would be unreadable as a flat list, so the picker
    // waits to be told which group to draw.
    expect(within(card).getByText(/sinf va guruhni tanlang/i)).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: 'Matematika 1-A' })).toBeNull()
  })

  it('narrows the subjects to the chosen group', async () => {
    const user = userEvent.setup()
    const picker = await renderPanel()
    await user.selectOptions(picker, 't1')

    const card = await openGroup(user, '1', 'cg1a')

    expect(within(card).getByRole('button', { name: 'Matematika 1-A' })).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: 'Geografiya 1-A' })).toBeInTheDocument()
    // Another group's copy of the same subject stays out of the way.
    expect(within(card).queryByRole('button', { name: 'Matematika 1-B' })).toBeNull()
  })

  it('hands a whole group to one teacher in a single save', async () => {
    const user = userEvent.setup()
    const picker = await renderPanel()
    await user.selectOptions(picker, 't1')

    const card = await openGroup(user, '1', 'cg1a')
    await user.click(within(card).getByRole('button', { name: /Shu guruhdagi barchasini/ }))
    expect(within(card).getByText(/2 ta fan tanlandi/)).toBeInTheDocument()

    await user.click(within(card).getByRole('button', { name: 'Saqlash' }))
    await waitFor(() =>
      expect(adminApi.updateTeacher).toHaveBeenCalledWith('t1', {
        subjects: ['m1', 'geo'],
      }),
    )
  })

  /**
   * The tally counts every group, not only the one on screen — a teacher
   * carries Matematika across four years, and filtering to the fourth must not
   * look like it threw the first three away.
   */
  it('keeps what was ticked in another group while the filter moves', async () => {
    const user = userEvent.setup()
    const picker = await renderPanel()
    await user.selectOptions(picker, 't1')

    const card = await openGroup(user, '1', 'cg1a')
    await user.click(within(card).getByRole('button', { name: 'Matematika 1-A' }))

    await user.selectOptions(within(card).getByLabelText('Sinf'), '2')
    await user.selectOptions(within(card).getByLabelText('Guruh'), 'cg2a')
    await user.click(within(card).getByRole('button', { name: 'Matematika 2-A' }))

    expect(within(card).getByText(/2 ta fan tanlandi/)).toBeInTheDocument()
    expect(within(card).getByText(/boshqa guruhlarda/)).toBeInTheDocument()

    await user.click(within(card).getByRole('button', { name: 'Saqlash' }))
    await waitFor(() =>
      expect(adminApi.updateTeacher).toHaveBeenCalledWith('t1', { subjects: ['m1', 'm3'] }),
    )
  })

  it('starts from what the teacher already teaches', async () => {
    const user = userEvent.setup()
    const picker = await renderPanel({
      ...TEACHER,
      subjects: [{ id: 'm1', name: 'Matematika', display_name: 'Matematika 1-A' }],
    })

    await user.selectOptions(picker, 't1')
    const card = assignCard()
    expect(within(card).getByText(/1 ta fan tanlandi/)).toBeInTheDocument()

    // Adding a second one keeps the stored one.
    await openGroup(user, '1', 'cg1b')
    await user.click(within(card).getByRole('button', { name: 'Matematika 1-B' }))
    await user.click(within(card).getByRole('button', { name: 'Saqlash' }))
    await waitFor(() =>
      expect(adminApi.updateTeacher).toHaveBeenCalledWith('t1', { subjects: ['m1', 'm2'] }),
    )
  })

  it('lets a subject be detached again', async () => {
    const user = userEvent.setup()
    const picker = await renderPanel({
      ...TEACHER,
      subjects: [{ id: 'm1', name: 'Matematika', display_name: 'Matematika 1-A' }],
    })

    await user.selectOptions(picker, 't1')
    const card = await openGroup(user, '1', 'cg1a')
    await user.click(within(card).getByRole('button', { name: 'Matematika 1-A' }))
    await user.click(within(card).getByRole('button', { name: 'Saqlash' }))
    await waitFor(() =>
      expect(adminApi.updateTeacher).toHaveBeenCalledWith('t1', { subjects: [] }),
    )
  })
})
