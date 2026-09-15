import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { managementApi } from '@/api/managementApi'
import { toApiError } from '@/api/errors'
import { Button, Input, JshshirInput, Modal, PhoneInput, Select } from '@/components/ui'
import { toast } from '@/store/toastStore'
import type { GuardianInput, ManagedClassGroup, ManagedStudent, Relation } from '@/types/api'
import { cn } from '@/utils/cn'
import { isJshshir, isPhoneComplete, phoneFromApi, phoneToApi } from '@/utils/masks'

/** The four kinships the school register recognises. */
const RELATIONS: { value: Relation; label: string }[] = [
  { value: 'FATHER', label: 'Otasi' },
  { value: 'MOTHER', label: 'Onasi' },
  { value: 'GUARDIAN', label: 'Vasiysi' },
  { value: 'OTHER', label: 'Boshqa' },
]

/** Shown until a real face photo is uploaded. */
const PHOTO_PLACEHOLDER = '/shablon.png'

function emptyGuardian(): GuardianInput {
  return {
    last_name: '',
    first_name: '',
    middle_name: '',
    relation: 'FATHER',
    phone: '',
    jshshir: '',
    is_primary: false,
  }
}

/**
 * Add / edit a pupil.
 *
 * The photo is uploaded in a second request, after the pupil exists — it needs
 * an id to attach to, and the backend pushes it to the turnstiles from there.
 */
export function StudentFormModal({
  student,
  classGroups,
  defaultClassGroup,
  onClose,
  onSaved,
}: {
  /** Null when adding; the pupil being edited otherwise. */
  student: ManagedStudent | null
  classGroups: ManagedClassGroup[]
  defaultClassGroup?: string
  onClose: () => void
  onSaved: () => void
}) {
  const { t } = useTranslation()
  // Initialised from props on mount. The caller keys this component on the
  // pupil being edited, so opening a different one remounts it with fresh
  // state instead of syncing props into state from an effect.
  const [lastName, setLastName] = useState(student?.last_name ?? '')
  const [firstName, setFirstName] = useState(student?.first_name ?? '')
  const [middleName, setMiddleName] = useState(student?.middle_name ?? '')
  const [classGroup, setClassGroup] = useState(
    student?.class_group_id ?? defaultClassGroup ?? classGroups[0]?.id ?? '',
  )
  const [birthDate, setBirthDate] = useState(student?.birth_date ?? '')
  const [gender, setGender] = useState(student?.gender ?? '')
  const [guardians, setGuardians] = useState<GuardianInput[]>(() =>
    student
      ? student.guardians.map((guardian) => ({
          id: guardian.id,
          last_name: guardian.last_name,
          first_name: guardian.first_name,
          middle_name: guardian.middle_name,
          relation: guardian.relation,
          phone: phoneFromApi(guardian.phone),
          // The stored JSHSHIR never reaches the browser; the `id` identifies
          // the guardian instead, and a blank field leaves it untouched.
          jshshir: '',
          is_primary: guardian.is_primary,
        }))
      : [],
  )
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(student?.photo ?? null)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const fileInput = useRef<HTMLInputElement>(null)

  function updateGuardian(index: number, patch: Partial<GuardianInput>) {
    setGuardians((rows) =>
      rows.map((row, position) => (position === index ? { ...row, ...patch } : row)),
    )
  }

  function pickPhoto(file: File | undefined) {
    if (!file) return
    setPhotoFile(file)
    setPhotoPreview(URL.createObjectURL(file))
  }

  function validate(): boolean {
    const next: Record<string, string> = {}
    if (!lastName.trim()) next.last_name = 'Familiyani kiriting.'
    if (!firstName.trim()) next.first_name = 'Ismni kiriting.'
    if (!classGroup) next.class_group = 'Sinf guruhini tanlang.'
    guardians.forEach((guardian, index) => {
      if (!guardian.last_name.trim() || !guardian.first_name.trim()) {
        next[`guardian-${index}`] = 'Yaqinining ism-familiyasini kiriting.'
      } else if (!guardian.id && !isJshshir(guardian.jshshir)) {
        next[`guardian-${index}`] = 'JSHSHIR 14 ta raqamdan iborat bo‘lishi kerak.'
      } else if (guardian.jshshir && !isJshshir(guardian.jshshir)) {
        next[`guardian-${index}`] = 'JSHSHIR 14 ta raqamdan iborat bo‘lishi kerak.'
      } else if (!isPhoneComplete(guardian.phone)) {
        next[`guardian-${index}`] = 'Telefon raqamini to‘liq kiriting.'
      }
    })
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function submit() {
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        last_name: lastName.trim(),
        first_name: firstName.trim(),
        middle_name: middleName.trim(),
        class_group: classGroup,
        birth_date: birthDate || null,
        gender,
        // The masked value is for the eye; the API wants plain E.164.
        guardians: guardians.map((guardian) => ({
          ...guardian,
          phone: phoneToApi(guardian.phone),
        })),
      }

      const saved = student
        ? await managementApi.updateStudent(student.id, payload)
        : await managementApi.createStudent(payload)

      if (photoFile) {
        await managementApi.uploadPhoto(saved.id, photoFile)
      }

      toast.success(
        student ? "O'quvchi yangilandi" : "O'quvchi qo'shildi",
        photoFile ? 'Rasm terminallarga yuborildi.' : undefined,
      )
      onSaved()
      onClose()
    } catch (error) {
      const apiError = toApiError(error)
      toast.error(t('teacher.saveFailed'), apiError.message)
      setErrors(
        Object.fromEntries(
          Object.entries(apiError.fields ?? {}).map(([key, value]) => [
            key,
            Array.isArray(value) ? value[0] : String(value),
          ]),
        ),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={student ? "O'quvchini tahrirlash" : "Yangi o'quvchi"}
      description={t('student.formHint')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            {t('actions.cancel')}
          </Button>
          <Button onClick={submit} loading={saving}>
            {t('actions.save')}
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        {/* --- pupil ---------------------------------------------------- */}
        <section className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Input
              label={t('person.lastName')}
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
              error={errors.last_name}
              autoComplete="off"
            />
            <Input
              label={t('person.firstName')}
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
              error={errors.first_name}
              autoComplete="off"
            />
            <Input
              label={t('person.middleName')}
              value={middleName}
              onChange={(event) => setMiddleName(event.target.value)}
              autoComplete="off"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <Select
              label={t('student.classGroup')}
              value={classGroup}
              onChange={(event) => setClassGroup(event.target.value)}
              error={errors.class_group}
            >
              <option value="">{t('person.select')}</option>
              {classGroups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.display_name}
                </option>
              ))}
            </Select>
            <Input
              label={t('person.birthDate')}
              type="date"
              value={birthDate}
              onChange={(event) => setBirthDate(event.target.value)}
            />
            <Select
              label={t('person.gender')}
              value={gender}
              onChange={(event) => setGender(event.target.value)}
            >
              <option value="">—</option>
              <option value="MALE">{t('student.boy')}</option>
              <option value="FEMALE">{t('student.girl')}</option>
            </Select>
          </div>
        </section>

        {/* --- photo ---------------------------------------------------- */}
        <section>
          <p className="label">{t('student.photo')}</p>
          <div className="flex items-center gap-4">
            <img
              src={photoPreview ?? PHOTO_PLACEHOLDER}
              alt="O'quvchi rasmi"
              className="h-24 w-24 rounded-2xl border border-ink-200 object-cover"
            />
            <div className="space-y-1.5">
              <input
                ref={fileInput}
                type="file"
                accept="image/jpeg,image/png"
                className="hidden"
                onChange={(event) => pickPhoto(event.target.files?.[0])}
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => fileInput.current?.click()}
              >
                {photoPreview ? "Rasmni almashtirish" : 'Rasm yuklash'}
              </Button>
              <p className="text-xs text-ink-500">
                {t('student.photoHint')}
              </p>
            </div>
          </div>
        </section>

        {/* --- guardians ------------------------------------------------ */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="label mb-0">{t('student.guardians')}</p>
            <Button
              type="button"
              variant="subtle"
              size="sm"
              onClick={() => setGuardians((rows) => [...rows, emptyGuardian()])}
            >
              + Yaqini qo'shish
            </Button>
          </div>

          {guardians.length === 0 ? (
            <p className="rounded-xl border border-dashed border-ink-200 px-4 py-6 text-center text-sm text-ink-500">
              {t('student.noGuardiansYet')} <b>{t('student.addGuardian')}</b> tugmasini bosing.
            </p>
          ) : null}

          {guardians.map((guardian, index) => (
            <div
              key={index}
              className={cn(
                'space-y-3 rounded-xl border p-4',
                errors[`guardian-${index}`] ? 'border-red-300 bg-red-500/15/40' : 'border-ink-200',
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-ink-700">{index + 1}-yaqini</span>
                <button
                  type="button"
                  className="text-sm font-medium text-red-600 hover:text-red-700"
                  onClick={() =>
                    setGuardians((rows) => rows.filter((_, position) => position !== index))
                  }
                >
                  {t('actions.delete')}
                </button>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <Input
                  label={t('person.lastName')}
                  value={guardian.last_name}
                  onChange={(event) => updateGuardian(index, { last_name: event.target.value })}
                  autoComplete="off"
                />
                <Input
                  label={t('person.firstName')}
                  value={guardian.first_name}
                  onChange={(event) => updateGuardian(index, { first_name: event.target.value })}
                  autoComplete="off"
                />
                <Input
                  label={t('person.middleName')}
                  value={guardian.middle_name}
                  onChange={(event) => updateGuardian(index, { middle_name: event.target.value })}
                  autoComplete="off"
                />
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <Select
                  label={t('student.relation')}
                  value={guardian.relation}
                  onChange={(event) =>
                    updateGuardian(index, { relation: event.target.value as Relation })
                  }
                >
                  {RELATIONS.map((relation) => (
                    <option key={relation.value} value={relation.value}>
                      {relation.label}
                    </option>
                  ))}
                </Select>
                <PhoneInput
                  label={t('person.phone')}
                  value={guardian.phone}
                  onChange={(value) => updateGuardian(index, { phone: value })}
                />
                <JshshirInput
                  label={t('person.jshshir')}
                  value={guardian.jshshir}
                  placeholder={guardian.id ? "O'zgartirmaslik uchun bo'sh qoldiring" : '14 ta raqam'}
                  onChange={(value) => updateGuardian(index, { jshshir: value })}
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-ink-600">
                <input
                  type="checkbox"
                  checked={guardian.is_primary}
                  onChange={(event) =>
                    setGuardians((rows) =>
                      rows.map((row, position) => ({
                        ...row,
                        // Exactly one primary guardian per pupil.
                        is_primary: position === index ? event.target.checked : false,
                      })),
                    )
                  }
                />
                {t('profile.primaryGuardian')}
              </label>

              {errors[`guardian-${index}`] ? (
                <p className="text-sm text-red-600">{errors[`guardian-${index}`]}</p>
              ) : null}
            </div>
          ))}
        </section>
      </div>
    </Modal>
  )
}
