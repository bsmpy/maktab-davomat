import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { adminApi } from '@/api/adminApi'
import { toApiError } from '@/api/errors'
import { managementApi } from '@/api/managementApi'
import {
  Avatar,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  JshshirInput,
  Modal,
  PassportIdInput,
  PhoneInput,
  Select,
  Skeleton,
} from '@/components/ui'
import { useAuth } from '@/auth/permissions'
import {
  PersonProfileModal,
  type ProfileTarget,
} from '@/features/management/PersonProfileModal'
import { stopCard } from '@/features/management/cardActions'
import { ProfileCard } from '@/features/management/ProfileCard'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { ManagedSchool, ManagedSubject } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatShortDate } from '@/utils/date'
import {
  isJshshir,
  isPassportId,
  isPhoneComplete,
  phoneDigits,
  phoneFromApi,
  phoneToApi,
} from '@/utils/masks'

/** The school phone: masked while typing, saved once the field loses focus. */
function SchoolPhoneField({ phone, onSave }: { phone: string; onSave: (phone: string) => void }) {
  const { t } = useTranslation()
  const [value, setValue] = useState(() => phoneFromApi(phone))
  return (
    <PhoneInput
      label={t('person.phone')}
      value={value}
      onChange={setValue}
      onBlur={() => {
        const next = phoneToApi(value)
        if (next !== phone) onSave(next)
      }}
    />
  )
}

/** Shown until a real face photo is uploaded — the same one pupils use. */
const PHOTO_PLACEHOLDER = '/shablon.png'

const WEEKDAYS = [
  { value: 1, label: 'Du' },
  { value: 2, label: 'Se' },
  { value: 3, label: 'Chor' },
  { value: 4, label: 'Pay' },
  { value: 5, label: 'Ju' },
  { value: 6, label: 'Sha' },
  { value: 7, label: 'Ya' },
]

/**
 * The school profile and the days it is shut.
 *
 * These three drive the arithmetic everywhere else: a day outside
 * `working_weekdays`, or listed as a holiday, is not a school day and never
 * enters an attendance denominator.
 */
export function SchoolPanel() {
  const { t } = useTranslation()
  // Creating a school is a platform action, not a school one.
  const { isActing } = useAuth()
  const schools = useAsyncData(() => adminApi.schools(), [])
  const holidays = useAsyncData(() => adminApi.holidays(), [])

  const [busy, setBusy] = useState(false)
  const [schoolName, setSchoolName] = useState('')
  const [holidayDate, setHolidayDate] = useState('')
  const [holidayName, setHolidayName] = useState('')

  async function run(action: () => Promise<unknown>, success: string, reload: () => void) {
    setBusy(true)
    try {
      await action()
      toast.success(success)
      reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  async function toggleWeekday(school: ManagedSchool, day: number) {
    const next = school.working_weekdays.includes(day)
      ? school.working_weekdays.filter((value) => value !== day)
      : [...school.working_weekdays, day].sort()
    if (next.length === 0) {
      toast.error(t('school.needOneWorkday'))
      return
    }
    await run(
      () => adminApi.updateSchool(school.id, { working_weekdays: next }),
      'Ish kunlari yangilandi',
      schools.reload,
    )
  }

  if (schools.initialLoading) return <Skeleton className="h-96 w-full rounded-2xl" />
  if (schools.error) {
    return (
      <Card>
        <ErrorState error={schools.error} onRetry={schools.reload} />
      </Card>
    )
  }

  const list = schools.data ?? []

  // Nothing exists yet: creating the school is the first step of setting the
  // platform up, and everything else (years, groups, pupils) hangs off it.
  if (list.length === 0) {
    return (
      <Card>
        {isActing('DEVELOPER') ? (
          <CardBody className="space-y-4">
            <EmptyState
              title={t('school.noSchoolYet')}
              description={t('school.noSchoolHint')}
            />
            <div className="mx-auto flex w-full max-w-md flex-wrap items-end justify-center gap-3">
              <Input
                label={t('school.name')}
                value={schoolName}
                placeholder={t('school.namePlaceholder')}
                className="flex-1"
                onChange={(event) => setSchoolName(event.target.value)}
              />
              <Button
                disabled={!schoolName.trim() || busy}
                onClick={() =>
                  run(
                    async () => {
                      await adminApi.createSchool({ name: schoolName.trim() })
                      setSchoolName('')
                    },
                    'Maktab yaratildi',
                    schools.reload,
                  )
                }
              >
                {t('users.create')}
              </Button>
            </div>
          </CardBody>
        ) : (
          <EmptyState
            title={t('school.noSchoolYet')}
            description={t('school.developerOnly')}
          />
        )}
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      {/* --- school --------------------------------------------------- */}
      {list.map((school) => (
        <Card key={school.id}>
          <CardHeader
            title={school.name}
            description={`${school.students_count} o'quvchi · ${school.class_groups_count} guruh`}
          />
          <CardBody className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label={t('school.shortName')}
                defaultValue={school.short_name}
                onBlur={(event) => {
                  if (event.target.value !== school.short_name) {
                    run(
                      () =>
                        adminApi.updateSchool(school.id, {
                          short_name: event.target.value,
                        }),
                      'Saqlandi',
                      schools.reload,
                    )
                  }
                }}
              />
              <SchoolPhoneField
                phone={school.phone}
                onSave={(phone) =>
                  run(() => adminApi.updateSchool(school.id, { phone }), 'Saqlandi', schools.reload)
                }
              />
            </div>

            <div>
              <p className="label">{t('school.workdays')}</p>
              <div className="flex flex-wrap gap-2">
                {WEEKDAYS.map((day) => {
                  const active = school.working_weekdays.includes(day.value)
                  return (
                    <button
                      key={day.value}
                      type="button"
                      disabled={busy}
                      onClick={() => toggleWeekday(school, day.value)}
                      className={
                        active
                          ? 'rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-onbrand'
                          : 'rounded-xl border border-ink-200 px-4 py-2 text-sm text-ink-600 hover:bg-ink-50'
                      }
                    >
                      {day.label}
                    </button>
                  )
                })}
              </div>
              <p className="mt-1.5 text-xs text-ink-500">
                {t('school.workdaysHint')}
              </p>
            </div>
          </CardBody>
        </Card>
      ))}

      {/* --- holidays --------------------------------------------------- */}
      <Card>
        <CardHeader
          title={t('school.holidays')}
          description={t('school.holidaysHint')}
        />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <Input
              label={t('school.date')}
              type="date"
              value={holidayDate}
              className="w-full sm:w-44"
              onChange={(event) => setHolidayDate(event.target.value)}
            />
            <Input
              label={t('school.name2')}
              value={holidayName}
              placeholder={t('school.holidayExample')}
              className="w-full sm:w-64"
              onChange={(event) => setHolidayName(event.target.value)}
            />
            <Button
              disabled={!holidayDate || !holidayName.trim() || busy}
              onClick={() =>
                run(
                  async () => {
                    await adminApi.createHoliday({
                      date: holidayDate,
                      name: holidayName.trim(),
                    })
                    setHolidayDate('')
                    setHolidayName('')
                  },
                  'Bayram qo‘shildi',
                  holidays.reload,
                )
              }
            >
              {t('actions.add')}
            </Button>
          </div>

          {(holidays.data ?? []).length === 0 ? (
            <EmptyState title={t('school.noHolidays')} />
          ) : (
            <ul className="divide-y divide-ink-100 rounded-xl border border-ink-100">
              {(holidays.data ?? []).map((holiday) => (
                <li key={holiday.id} className="flex items-center gap-3 px-4 py-3">
                  <span className="w-28 text-sm font-medium tabular-nums text-ink-800">
                    {formatShortDate(holiday.date)}
                  </span>
                  <span className="flex-1 text-sm text-ink-700">{holiday.name}</span>
                  {holiday.is_working_day ? (
                    <Badge className="bg-amber-500/15 text-amber-700 ring-1 ring-inset ring-amber-600/20">
                      {t('school.workday')}
                    </Badge>
                  ) : null}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-600 hover:bg-red-500/15"
                    disabled={busy}
                    onClick={() =>
                      run(() => adminApi.deleteHoliday(holiday.id), "O'chirildi", holidays.reload)
                    }
                  >
                    {t('actions.delete')}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

/** Kept alongside the school screen: both describe the timetable's vocabulary. */
/**
 * Multi-select over the subject register.
 *
 * A school carries the same subject once per year — Matematika 1 … 11 — so the
 * filter exists to narrow a long list down to one family and take it in one go.
 */
function SubjectPicker({
  subjects,
  selected,
  onChange,
  bulkActions = false,
}: {
  /** Already narrowed by the caller — this only draws and toggles. */
  subjects: ManagedSubject[]
  selected: string[]
  onChange: (ids: string[]) => void
  /** Adds "select all" / "clear", which only the attach flow wants. */
  bulkActions?: boolean
}) {
  const { t } = useTranslation()
  const visible = subjects

  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id])
  }

  return (
    <div className="space-y-3">
      {bulkActions ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={visible.length === 0}
            onClick={() =>
              onChange([...new Set([...selected, ...visible.map((subject) => subject.id)])])
            }
          >
            {t('school.selectAllInGroup')}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={selected.length === 0}
            onClick={() => onChange([])}
          >
            {t('school.clearSelection')}
          </Button>
        </div>
      ) : null}

      {visible.length === 0 ? (
        <p className="text-sm text-ink-500">{t('school.groupHasNoSubjects')}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {visible.map((subject) => {
            const active = selected.includes(subject.id)
            return (
              <button
                key={subject.id}
                type="button"
                aria-pressed={active}
                onClick={() => toggle(subject.id)}
                className={cn(
                  'rounded-xl border px-3 py-1.5 text-sm transition',
                  active
                    ? 'border-brand-600 bg-brand-50 text-brand-700'
                    : 'border-ink-200 text-ink-600 hover:bg-ink-50',
                )}
              >
                {subject.display_name}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

/** Blank teacher form state; also what "Tozalash" resets to. */
const EMPTY_TEACHER = {
  first_name: '',
  last_name: '',
  middle_name: '',
  passport_id: '',
  jshshir: '',
  birth_date: '',
  gender: '',
  phone: '',
  email: '',
  username: '',
  password: '',
  password_confirm: '',
}

type TeacherForm = typeof EMPTY_TEACHER

/** Same shape the API enforces, so the form can say no before the round trip. */
const USERNAME_RE = /^[a-z0-9][a-z0-9._-]{1,48}[a-z0-9]$/

/**
 * Subjects and teachers, each behind its own menu entry.
 *
 * The two halves share the form state helpers, so they stay in one file and one
 * component with a `show` switch rather than being copied apart.
 */
export function SubjectsPanel() {
  return <SubjectsTeachersPanel show="subjects" />
}

export function TeachersPanel() {
  return <SubjectsTeachersPanel show="teachers" />
}

function SubjectsTeachersPanel({ show }: { show: 'subjects' | 'teachers' }) {
  const { t } = useTranslation()
  const subjects = useAsyncData(() => adminApi.subjects(), [])
  // The subjects half has no use for the staff list; only ask for what the
  // page on screen actually shows.
  const teachers = useAsyncData(() => adminApi.teachers(), [show], {
    enabled: show === 'teachers',
  })
  // A subject belongs to one class group, so the register is needed to add one.
  const classGroups = useAsyncData(() => managementApi.classGroups(), [])

  const [busy, setBusy] = useState(false)
  //: Whose profile is open, when a teacher card has been pressed.
  const [profile, setProfile] = useState<ProfileTarget | null>(null)
  const [subjectGrade, setSubjectGrade] = useState('')
  const [subjectGroup, setSubjectGroup] = useState('')
  const [subjectName, setSubjectName] = useState('')
  const [form, setForm] = useState<TeacherForm>(EMPTY_TEACHER)
  const [chosenSubjects, setChosenSubjects] = useState<string[]>([])
  // The face the turnstile will learn: uploaded with the teacher, not later.
  const [addOpen, setAddOpen] = useState(false)
  const [photo, setPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const photoInput = useRef<HTMLInputElement>(null)
  // The attach-subjects block below works on an existing teacher, so it keeps
  // its own selection: the one already stored, until it is saved again.
  const [assignTeacherId, setAssignTeacherId] = useState('')
  const [assignSubjects, setAssignSubjects] = useState<string[]>([])
  // Teacher → class → group. With six hundred subjects in the register, a flat
  // list is unreadable; narrowing to one group at a time is the only way to
  // find "Matematika 7-B" without scrolling past everything else.
  const [assignGrade, setAssignGrade] = useState('')
  const [assignGroup, setAssignGroup] = useState('')

  function set<K extends keyof TeacherForm>(field: K, value: TeacherForm[K]) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function run(action: () => Promise<unknown>, success: string, reload: () => void) {
    setBusy(true)
    try {
      await action()
      toast.success(success)
      reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  // Each optional identifier is either empty or complete — half a passport
  // number is worse than none, so the form refuses to send one.
  const passportError =
    form.passport_id && !isPassportId(form.passport_id)
      ? t('validation.passportFormat')
      : undefined
  const jshshirError = form.jshshir && !isJshshir(form.jshshir) ? t('validation.jshshirFormat') : undefined
  const phoneError =
    phoneDigits(form.phone).length > 0 && !isPhoneComplete(form.phone)
      ? t('validation.phoneIncomplete')
      : undefined

  // Credentials are optional, but partial ones are not: a login with no
  // password would create an account nobody can sign in to.
  const wantsAccount = Boolean(form.username.trim() || form.password || form.password_confirm)
  const usernameError =
    wantsAccount && !USERNAME_RE.test(form.username.trim().toLowerCase())
      ? t('validation.usernameFormat')
      : undefined
  const passwordError = wantsAccount && form.password.length < 8 ? t('validation.passwordShort') : undefined
  const confirmError =
    wantsAccount && form.password_confirm !== form.password ? t('validation.passwordMismatch') : undefined

  const canSubmit =
    Boolean(form.first_name.trim()) &&
    Boolean(form.last_name.trim()) &&
    !passportError &&
    !jshshirError &&
    !phoneError &&
    !usernameError &&
    !passwordError &&
    !confirmError &&
    !busy

  function closeAdd() {
    setAddOpen(false)
    resetForm()
  }

  function resetForm() {
    setForm(EMPTY_TEACHER)
    setChosenSubjects([])
    setPhoto(null)
    setPhotoPreview(null)
  }

  function submit() {
    return run(
      async () => {
        await adminApi.createTeacher(
          {
            first_name: form.first_name.trim(),
            last_name: form.last_name.trim(),
            middle_name: form.middle_name.trim(),
            passport_id: form.passport_id,
            jshshir: form.jshshir,
            birth_date: form.birth_date || null,
            gender: form.gender,
            phone: phoneToApi(form.phone),
            email: form.email.trim(),
            subjects: chosenSubjects,
            ...(wantsAccount
              ? {
                  username: form.username.trim().toLowerCase(),
                  password: form.password,
                  password_confirm: form.password_confirm,
                }
              : {}),
          },
          photo,
        )
        closeAdd()
      },
      'O‘qituvchi qo‘shildi',
      teachers.reload,
    )
  }

  const subjectList = subjects.data ?? []
  const teacherList = teachers.data ?? []
  const groupList = classGroups.data ?? []
  // Grades come from the class groups themselves — no separate request, and
  // a grade with no groups yet could not carry a subject anyway.
  const gradeLevels = [...new Set(groupList.map((group) => group.grade_level))].sort(
    (a, b) => a - b,
  )
  const groupsInGrade = groupList.filter((group) => String(group.grade_level) === subjectGrade)
  const canAddSubject = Boolean(subjectGroup) && Boolean(subjectName.trim()) && !busy

  // The list reads as the register does: a class, then everything taught in it.
  // Grouped by name rather than by adjacency, so a payload that arrives in a
  // different order still produces one block per class.
  const subjectsByGroup = Object.values(
    subjectList.reduce<
      Record<string, { name: string; level: number; subjects: typeof subjectList }>
    >((groups, subject) => {
      const name = subject.class_group_name || 'Sinf biriktirilmagan'
      groups[name] = groups[name] ?? {
        name,
        level: subject.grade_level ?? Number.MAX_SAFE_INTEGER,
        subjects: [],
      }
      groups[name].subjects.push(subject)
      return groups
    }, {}),
  ).sort((a, b) => a.level - b.level || a.name.localeCompare(b.name))

  function addSubject() {
    return run(
      async () => {
        await adminApi.createSubject({
          name: subjectName.trim(),
          class_group: subjectGroup,
        })
        // The class group stays picked: the next subject is usually for the
        // same class.
        setSubjectName('')
      },
      'Fan qo‘shildi',
      subjects.reload,
    )
  }
  const assignTeacher = teacherList.find((teacher) => teacher.id === assignTeacherId) ?? null

  // The cascade, derived rather than stored: the register is the only source of
  // which classes exist and which groups sit under them.
  const assignGradeLevels = [...new Set(groupList.map((group) => group.grade_level))].sort(
    (a, b) => a - b,
  )
  const assignGroupOptions = groupList
    .filter((group) => String(group.grade_level) === assignGrade)
    .sort((a, b) => a.name.localeCompare(b.name))
  const assignVisibleSubjects = subjectList.filter(
    (subject) => subject.class_group === assignGroup,
  )
  //: Ticked, but belonging to a group other than the one on screen.
  const assignChosenElsewhere = assignSubjects.filter(
    (id) => !assignVisibleSubjects.some((subject) => subject.id === id),
  ).length

  function pickTeacherToAssign(id: string) {
    setAssignTeacherId(id)
    const teacher = teacherList.find((row) => row.id === id)
    // Start from what the teacher already teaches, so saving adds rather than
    // silently wipes the subjects somebody attached earlier.
    setAssignSubjects(teacher ? teacher.subjects.map((subject) => subject.id) : [])
  }

  function saveAssignment() {
    if (!assignTeacher) return
    return run(
      () => adminApi.updateTeacher(assignTeacher.id, { subjects: assignSubjects }),
      'Fanlar biriktirildi',
      () => {
        teachers.reload()
      },
    )
  }

  return (
    <div className="space-y-5">
      {show === 'subjects' ? (
        <>
          {/* Sinf → sinf guruhi → fan nomi. The three together make the label the
          rest of the console shows: "Matematika 1-A". */}
          <Card>
            <CardHeader
              title={t('nav.subjects')}
              description={t('school.subjectsHint')}
            />
            <CardBody className="space-y-4">
              {groupList.length === 0 ? (
                <EmptyState
                  title={t('school.createGroupsFirst')}
                  description={t('school.subjectNeedsGroup')}
                />
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
                  <Select
                    label={t('register.grade')}
                    value={subjectGrade}
                    onChange={(event) => {
                      setSubjectGrade(event.target.value)
                      // The old group belongs to the old grade.
                      setSubjectGroup('')
                    }}
                  >
                    <option value="">{t('person.select')}</option>
                    {gradeLevels.map((level) => (
                      <option key={level} value={String(level)}>
                        {level}-sinf
                      </option>
                    ))}
                  </Select>
                  <Select
                    label={t('student.classGroup')}
                    value={subjectGroup}
                    disabled={!subjectGrade}
                    onChange={(event) => setSubjectGroup(event.target.value)}
                  >
                    <option value="">{subjectGrade ? t('person.select') : 'Avval sinfni tanlang'}</option>
                    {groupsInGrade.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.display_name}
                      </option>
                    ))}
                  </Select>
                  <Input
                    label={t('school.subjectName')}
                    value={subjectName}
                    placeholder={t('school.subjectExample')}
                    disabled={!subjectGroup}
                    onChange={(event) => setSubjectName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && canAddSubject) void addSubject()
                    }}
                  />
                  <Button disabled={!canAddSubject} onClick={addSubject}>
                    {t('actions.add')}
                  </Button>
                </div>
              )}

              {subjectList.length === 0 ? (
                <EmptyState title={t('school.noSubjects')} />
              ) : (
                <div className="space-y-5">
                  {subjectsByGroup.map((group) => (
                    <section key={group.name}>
                      <div className="mb-2 flex items-baseline gap-2">
                        <h3 className="text-xl font-semibold tracking-tight text-ink-900">
                          {group.name}
                        </h3>
                        <span className="text-xs text-ink-400">
                          {group.subjects.length} ta fan
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {group.subjects.map((subject) => (
                          <span
                            key={subject.id}
                            className="flex items-center gap-2 rounded-xl border border-ink-200 px-3 py-1.5 text-sm text-ink-700"
                          >
                            {subject.name}
                            <button
                              type="button"
                              aria-label={`${subject.display_name} — o'chirish`}
                              className="text-red-600 hover:text-red-700"
                              disabled={busy}
                              onClick={() =>
                                run(
                                  () => adminApi.deleteSubject(subject.id),
                                  "O'chirildi",
                                  subjects.reload,
                                )
                              }
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </>
      ) : (
        <>
          <Card>
            <CardHeader
              title={t('nav.teachers')}
              description={t('school.homeroomHint')}
              action={
                <Button onClick={() => setAddOpen(true)}>{t('school.addTeacher')}</Button>
              }
            />
            {teacherList.length === 0 ? (
              <CardBody>
                <EmptyState
                  title={t('school.noTeachers')}
                  description={t('school.noTeachersHint')}
                />
              </CardBody>
            ) : (
              <CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {teacherList.map((teacher) => (
                  <ProfileCard
                    key={teacher.id}
                    label={t('personProfile.open', { name: teacher.full_name })}
                    onOpen={() =>
                      setProfile({ kind: 'teacher', id: teacher.id, name: teacher.full_name })
                    }
                  >
                    <div className="flex items-center gap-3">
                      <Avatar name={teacher.full_name} src={teacher.photo ?? undefined} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[15px] font-medium text-ink-900">
                          {teacher.last_name} {teacher.first_name} {teacher.middle_name}
                        </p>
                        <p className="truncate text-xs text-ink-500">
                          {phoneFromApi(teacher.phone) || 'telefon yo‘q'}
                        </p>
                      </div>
                    </div>

                    <p className="mt-3 line-clamp-2 min-h-[2.5rem] text-xs text-ink-500">
                      {teacher.subjects.map((item) => item.display_name).join(', ') ||
                        'Fan biriktirilmagan'}
                    </p>

                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {teacher.username ? (
                        <Badge className="bg-brand-500/15 text-brand-700 ring-1 ring-inset ring-brand-600/20">
                          {teacher.username}
                        </Badge>
                      ) : (
                        <Badge className="bg-ink-100 text-ink-600 ring-ink-400/20">
                          {t('school.noAccount')}
                        </Badge>
                      )}
                      {teacher.has_jshshir ? (
                        <Badge className="bg-ink-100 text-ink-600 ring-ink-400/20">
                          JSHSHIR {teacher.jshshir || teacher.masked_jshshir}
                        </Badge>
                      ) : null}
                    </div>

                    <div className="mt-auto pt-4" onClick={stopCard}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:bg-red-500/15"
                        disabled={busy}
                        onClick={() =>
                          run(
                            () => adminApi.deleteTeacher(teacher.id),
                            "O'chirildi",
                            teachers.reload,
                          )
                        }
                      >
                        {t('actions.delete')}
                      </Button>
                    </div>
                  </ProfileCard>
                ))}
              </CardBody>
            )}
          </Card>

          <PersonProfileModal target={profile} onClose={() => setProfile(null)} />

          {addOpen ? (
            <Modal
              open
              onClose={closeAdd}
              title={t('school.addTeacher')}
              description={t('school.addTeacherHint')}
              footer={
                <>
                  <Button variant="secondary" disabled={busy} onClick={closeAdd}>
                    {t('actions.cancel')}
                  </Button>
                  <Button disabled={!canSubmit} onClick={submit}>
                    {t('actions.add')}
                  </Button>
                </>
              }
            >
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-4">
                <img
                  src={photoPreview ?? PHOTO_PLACEHOLDER}
                  alt=""
                  className="h-20 w-20 shrink-0 rounded-2xl border border-ink-200 object-cover"
                />
                <div>
                  <input
                    ref={photoInput}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(event) => {
                      const file = event.target.files?.[0]
                      if (!file) return
                      setPhoto(file)
                      setPhotoPreview(URL.createObjectURL(file))
                    }}
                  />
                  <Button variant="secondary" size="sm" onClick={() => photoInput.current?.click()}>
                    {t('school.pickPhoto')}
                  </Button>
                  <p className="mt-1.5 text-xs text-ink-500">
                    {t('school.photoAutoSent')}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                <Input
                  label={t('person.firstName')}
                  value={form.first_name}
                  onChange={(event) => set('first_name', event.target.value)}
                />
                <Input
                  label={t('person.lastName')}
                  value={form.last_name}
                  onChange={(event) => set('last_name', event.target.value)}
                />
                <Input
                  label={t('person.middleName')}
                  value={form.middle_name}
                  onChange={(event) => set('middle_name', event.target.value)}
                />
                <PassportIdInput
                  label={t('person.passportId')}
                  value={form.passport_id}
                  error={passportError}
                  onChange={(value) => set('passport_id', value)}
                />
                <JshshirInput
                  label={t('person.jshshir')}
                  value={form.jshshir}
                  error={jshshirError}
                  onChange={(value) => set('jshshir', value)}
                />
                <Input
                  label={t('person.birthDate')}
                  type="date"
                  value={form.birth_date}
                  onChange={(event) => set('birth_date', event.target.value)}
                />
                <Select
                  label={t('person.gender')}
                  value={form.gender}
                  onChange={(event) => set('gender', event.target.value)}
                >
                  <option value="">{t('teacher.notSet')}</option>
                  <option value="MALE">{t('person.male')}</option>
                  <option value="FEMALE">{t('person.female')}</option>
                </Select>
                <PhoneInput
                  label={t('person.phone')}
                  value={form.phone}
                  error={phoneError}
                  onChange={(value) => set('phone', value)}
                />
                <Input
                  label={t('person.email')}
                  type="email"
                  value={form.email}
                  placeholder={t('school.emailExample')}
                  onChange={(event) => set('email', event.target.value)}
                />
              </div>

              {subjectList.length > 0 ? (
                <div>
                  <p className="label">{t('school.subjectsOf')}</p>
                  <SubjectPicker
                    subjects={subjectList}
                    selected={chosenSubjects}
                    onChange={setChosenSubjects}
                  />
                </div>
              ) : null}

              {/* Cabinet credentials, last in the form: an account is only made
              when all three are filled in. */}
              <div className="border-t border-ink-100 pt-4">
                <p className="label">{t('school.cabinetAccess')}</p>
                <p className="mb-3 text-sm text-ink-500">
                  To'ldirilsa, o'qituvchi uchun akkaunt yaratiladi. Bo'sh qoldirsangiz, o'qituvchi
                  faqat ro'yxatda qoladi.
                </p>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                  <Input
                    label={t('person.login')}
                    value={form.username}
                    placeholder={t('school.loginExample')}
                    autoComplete="off"
                    spellCheck={false}
                    error={usernameError}
                    onChange={(event) => set('username', event.target.value.toLowerCase())}
                  />
                  <Input
                    label={t('person.password')}
                    type="password"
                    value={form.password}
                    autoComplete="new-password"
                    error={passwordError}
                    onChange={(event) => set('password', event.target.value)}
                  />
                  <Input
                    label={t('person.passwordConfirm')}
                    type="password"
                    value={form.password_confirm}
                    autoComplete="new-password"
                    error={confirmError}
                    onChange={(event) => set('password_confirm', event.target.value)}
                  />
                </div>
              </div>

            </div>
            </Modal>
          ) : null}

          {/* Attaching several subjects at once: one teacher usually carries the
          same subject across every year — Matematika 1, 2, 3, 4. */}
          <Card>
            <CardHeader
              title={t('school.assignSubjects')}
              description={t('school.assignHint')}
            />
            <CardBody className="space-y-4">
              {teacherList.length === 0 || subjectList.length === 0 ? (
                <EmptyState
                  title={t('school.needSubjectAndTeacher')}
                  description={t('school.needBothHint')}
                />
              ) : (
                <>
                  <Select
                    label={t('school.teacher')}
                    value={assignTeacherId}
                    className="sm:max-w-sm"
                    onChange={(event) => pickTeacherToAssign(event.target.value)}
                  >
                    <option value="">{t('person.select')}</option>
                    {teacherList.map((teacher) => (
                      <option key={teacher.id} value={teacher.id}>
                        {teacher.last_name} {teacher.first_name}
                      </option>
                    ))}
                  </Select>

                  {assignTeacher ? (
                    <>
                      <div className="grid gap-3 sm:grid-cols-2 lg:max-w-lg">
                        <Select
                          label={t('register.grade')}
                          value={assignGrade}
                          onChange={(event) => {
                            // A group belongs to one class, so changing the
                            // class cannot leave the old group selected.
                            setAssignGrade(event.target.value)
                            setAssignGroup('')
                          }}
                        >
                          <option value="">{t('person.select')}</option>
                          {assignGradeLevels.map((level) => (
                            <option key={level} value={String(level)}>
                              {level}-{t('register.grade').toLowerCase()}
                            </option>
                          ))}
                        </Select>

                        <Select
                          label={t('register.group')}
                          value={assignGroup}
                          disabled={!assignGrade}
                          onChange={(event) => setAssignGroup(event.target.value)}
                        >
                          <option value="">{t('person.select')}</option>
                          {assignGroupOptions.map((group) => (
                            <option key={group.id} value={group.id}>
                              {group.display_name}
                            </option>
                          ))}
                        </Select>
                      </div>

                      {assignGroup ? (
                        <SubjectPicker
                          bulkActions
                          subjects={assignVisibleSubjects}
                          selected={assignSubjects}
                          onChange={setAssignSubjects}
                        />
                      ) : (
                        <p className="text-sm text-ink-500">{t('school.pickGroupFirst')}</p>
                      )}

                      <div className="flex flex-wrap items-center gap-3">
                        <Button disabled={busy} onClick={saveAssignment}>
                          {t('actions.save')}
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={busy}
                          onClick={() => pickTeacherToAssign(assignTeacher.id)}
                        >
                          {t('actions.cancel')}
                        </Button>
                        {/* The tally counts every group, not just the one on
                            screen — otherwise filtering to 3-B looks like it
                            threw away what was ticked in 1-A. */}
                        <span className="text-sm text-ink-500">
                          {assignSubjects.length > 0
                            ? t('school.subjectsChosen', { count: assignSubjects.length })
                            : t('school.noSubjectsChosen')}
                          {assignChosenElsewhere > 0
                            ? ` · ${t('school.chosenElsewhere', { count: assignChosenElsewhere })}`
                            : ''}
                        </span>
                      </div>
                    </>
                  ) : null}
                </>
              )}
            </CardBody>
          </Card>

        </>
      )}
    </div>
  )
}
