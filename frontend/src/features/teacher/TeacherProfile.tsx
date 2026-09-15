import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { toApiError } from '@/api/errors'
import { teachingApi } from '@/api/teachingApi'
import {
  Avatar,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  JshshirInput,
  PassportIdInput,
  PhoneInput,
  Select,
  Skeleton,
} from '@/components/ui'
import { useTeacherStore } from '@/store/teacherStore'
import { toast } from '@/store/toastStore'
import type { TeacherProfile as Profile, TeacherProfilePayload } from '@/types/api'
import { cn } from '@/utils/cn'
import { isJshshir, isPassportId, isPhoneComplete, phoneDigits, phoneFromApi, phoneToApi } from '@/utils/masks'

/** The editable copy of the record; the stored one is never mutated in place. */
type Form = {
  first_name: string
  last_name: string
  middle_name: string
  birth_date: string
  passport_id: string
  jshshir: string
  gender: string
  phone: string
  email: string
  password: string
  password_confirm: string
}

function formOf(profile: Profile): Form {
  return {
    first_name: profile.first_name,
    last_name: profile.last_name,
    middle_name: profile.middle_name,
    birth_date: profile.birth_date ?? '',
    passport_id: profile.passport_id,
    jshshir: profile.jshshir ?? '',
    gender: profile.gender,
    phone: phoneFromApi(profile.phone),
    email: profile.email,
    password: '',
    password_confirm: '',
  }
}

export function TeacherProfile() {
  const { t } = useTranslation()
  const profile = useTeacherStore((state) => state.profile)
  const loading = useTeacherStore((state) => state.loading)
  const error = useTeacherStore((state) => state.error)
  const load = useTeacherStore((state) => state.load)
  const store = useTeacherStore((state) => state.set)

  const [loaded, setLoaded] = useState<Profile | null>(null)
  const [form, setForm] = useState<Form>(() => ({
    first_name: '',
    last_name: '',
    middle_name: '',
    birth_date: '',
    passport_id: '',
    jshshir: '',
    gender: '',
    phone: '',
    email: '',
    password: '',
    password_confirm: '',
  }))
  const [changePassword, setChangePassword] = useState(false)

  // The layout usually has it already; this makes the page work on its own too.
  useEffect(() => {
    void load()
  }, [load])

  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  // Start again from the server's copy whenever a fresh one arrives.
  if (profile && profile !== loaded) {
    setLoaded(profile)
    setForm(formOf(profile))
  }

  function set<K extends keyof Form>(field: K, value: Form[K]) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  if (loading && !profile) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-96 w-full rounded-2xl" />
      </div>
    )
  }

  if (error && !profile) {
    return (
      <Card>
        <ErrorState error={error} onRetry={() => void load({ force: true })} />
      </Card>
    )
  }

  if (!profile) return null

  // One block per class: the heading is the group, the cards under it are what
  // this teacher carries there.
  const byClass = Object.values(
    profile.subjects.reduce<Record<string, { name: string; subjects: typeof profile.subjects }>>(
      (groups, subject) => {
        const name = subject.class_group_name || "Sinf biriktirilmagan"
        groups[name] = groups[name] ?? { name, subjects: [] }
        groups[name].subjects.push(subject)
        return groups
      },
      {},
    ),
  ).sort((a, b) => a.name.localeCompare(b.name, 'en', { numeric: true }))

  const passportError =
    form.passport_id && !isPassportId(form.passport_id)
      ? '2 ta katta lotin harfi va 7 ta raqam'
      : undefined
  const jshshirError =
    form.jshshir && !isJshshir(form.jshshir) ? '14 ta raqam kiriting' : undefined
  const phoneError =
    phoneDigits(form.phone).length > 0 && !isPhoneComplete(form.phone)
      ? "Raqamni to'liq kiriting"
      : undefined
  const passwordError =
    changePassword && form.password.length < 8 ? t('validation.passwordShort') : undefined
  const confirmError =
    changePassword && form.password_confirm !== form.password
      ? t('validation.passwordMismatch')
      : undefined

  const canSave =
    Boolean(form.first_name.trim()) &&
    Boolean(form.last_name.trim()) &&
    !passportError &&
    !jshshirError &&
    !phoneError &&
    !passwordError &&
    !confirmError &&
    !saving

  async function save() {
    setSaving(true)
    try {
      const payload: TeacherProfilePayload = {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        middle_name: form.middle_name.trim(),
        birth_date: form.birth_date || null,
        passport_id: form.passport_id,
        gender: form.gender,
        phone: phoneToApi(form.phone),
        email: form.email.trim(),
      }
      // A blank field means "leave the stored one alone".
      if (form.jshshir) payload.jshshir = form.jshshir
      // The password only travels when the box is ticked.
      if (changePassword) {
        payload.password = form.password
        payload.password_confirm = form.password_confirm
      }

      const saved = await teachingApi.saveProfile(payload)
      store(saved)
      setChangePassword(false)
      toast.success("Ma'lumotlar muvaffaqiyatli saqlandi")
    } catch (caught) {
      toast.error(t('teacher.saveFailed'), toApiError(caught).message)
    } finally {
      setSaving(false)
    }
  }

  async function uploadPhoto(file: File | undefined) {
    if (!file) return
    setUploading(true)
    try {
      const { photo } = await teachingApi.uploadPhoto(file)
      store({ ...profile!, photo })
      toast.success(t('teacher.photoUpdated'))
    } catch (caught) {
      toast.error(t('teacher.photoFailed'), toApiError(caught).message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('nav.profile')}</h1>

      <Card>
        <CardBody className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="relative">
            <Avatar name={profile.full_name} src={profile.photo ?? undefined} size="lg" />
            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(event) => void uploadPhoto(event.target.files?.[0])}
            />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-semibold uppercase text-ink-900">
              {profile.full_name}
            </p>
            <p className="text-sm text-ink-600">{profile.role_label}</p>
            <p className="truncate text-sm text-ink-500">{profile.email || '—'}</p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            loading={uploading}
            onClick={() => fileInput.current?.click()}
          >
            {t('teacher.changePhoto')}
          </Button>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={t('profile.personal')} />
        <CardBody className="space-y-4 [&_.label]:uppercase">
          <div className="grid gap-4 sm:grid-cols-2">
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
            <Input
              label={t('person.birthDate')}
              type="date"
              value={form.birth_date}
              onChange={(event) => set('birth_date', event.target.value)}
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
              placeholder={t('teacher.fourteenDigits')}
              onChange={(value) => set('jshshir', value)}
            />
            <Select
              label={t('person.gender')}
              value={form.gender}
              onChange={(event) => set('gender', event.target.value)}
            >
              <option value="">{t('teacher.notSet')}</option>
              {profile.genders.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
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
              onChange={(event) => set('email', event.target.value)}
            />
            <Input
              label={t('person.login')}
              value={profile.username}
              disabled
              hint={t('teacher.loginByAdminOnly')}
            />
            <Input
              label={t('person.password')}
              type="password"
              autoComplete="new-password"
              value={form.password}
              disabled={!changePassword}
              error={passwordError}
              onChange={(event) => set('password', event.target.value)}
            />
            <Input
              label={t('person.passwordConfirm')}
              type="password"
              autoComplete="new-password"
              value={form.password_confirm}
              disabled={!changePassword}
              error={confirmError}
              onChange={(event) => set('password_confirm', event.target.value)}
            />
          </div>

          <label className="flex w-fit items-center gap-2.5 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={changePassword}
              className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
              onChange={(event) => {
                setChangePassword(event.target.checked)
                // Leaving the box never carries a half-typed password with it.
                setForm((current) => ({ ...current, password: '', password_confirm: '' }))
              }}
            />
            {t('profile.changePassword')}
          </label>

          <div>
            <Button disabled={!canSave} loading={saving} onClick={save}>
              {saving ? t('validation.saving') : 'Saqlash'}
            </Button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={t('teacher.mySubjects')} />
        <CardBody className="space-y-6">
          {byClass.length === 0 ? (
            <EmptyState title={t('teacher.noSubjectsForYou')} />
          ) : (
            byClass.map((group) => (
              <section key={group.name}>
                <h3 className="text-2xl font-semibold tracking-tight text-ink-900">
                  {group.name}
                </h3>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {group.subjects.map((subject) => (
                    <div
                      key={subject.id}
                      className={cn(
                        'rounded-xl border border-ink-200 bg-surface p-4',
                        'transition hover:border-brand-300',
                      )}
                    >
                      <p className="truncate text-[15px] font-medium text-ink-900">
                        {subject.name}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            ))
          )}
        </CardBody>
      </Card>
    </div>
  )
}
