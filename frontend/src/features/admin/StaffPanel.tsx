import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { adminApi } from '@/api/adminApi'
import { toApiError } from '@/api/errors'
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
  Modal,
  PassportIdInput,
  PhoneInput,
  Select,
  SkeletonCards,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { ManagedStaff, StaffPayload } from '@/types/api'
import {
  isJshshir,
  isPassportId,
  isPhoneComplete,
  phoneDigits,
  phoneToApi,
} from '@/utils/masks'
import { localizedTitle } from '@/utils/localized'

import {
  PersonProfileModal,
  type ProfileTarget,
} from '@/features/management/PersonProfileModal'
import { stopCard } from '@/features/management/cardActions'
import { ProfileCard } from '@/features/management/ProfileCard'
import { RoleBadges, RolePicker } from '@/features/management/RolePicker'

interface StaffForm {
  first_name: string
  last_name: string
  middle_name: string
  passport_id: string
  jshshir: string
  birth_date: string
  gender: string
  phone: string
  email: string
  position: string
  roles: string[]
  username: string
  password: string
  password_confirm: string
}

const EMPTY: StaffForm = {
  first_name: '',
  last_name: '',
  middle_name: '',
  passport_id: '',
  jshshir: '',
  birth_date: '',
  gender: '',
  phone: '',
  email: '',
  position: '',
  roles: [],
  username: '',
  password: '',
  password_confirm: '',
}

/**
 * Xodimlar — the people who run the school but do not teach in it.
 *
 * The same form a teacher is entered on, field for field, because it is the
 * same kind of record: a person and their documents.
 *
 * The person comes first and everything else is optional: a name is enough to
 * get somebody into the register, and the position and the cabinet role are
 * attached afterwards from the list — or never, which is the ordinary case for
 * a cook or a guard. The one role never on offer is DEVELOPER: that is the
 * platform owner's own account, not a job anybody holds at a school.
 */
export function StaffPanel() {
  const { t, i18n } = useTranslation()
  const staff = useAsyncData(() => adminApi.staff(), [])
  const positions = useAsyncData(() => adminApi.positions(), [])

  const [form, setForm] = useState<StaffForm>(EMPTY)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<ManagedStaff | null>(null)
  const [photo, setPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const photoInput = useRef<HTMLInputElement>(null)

  const rows = staff.data?.results ?? []
  const roles = staff.data?.assignable_roles ?? []
  const jobs = positions.data ?? []
  //: The row whose position or role is being attached from the list, and what
  //  it currently holds — the modal opens on the answer already stored.
  const [attaching, setAttaching] = useState<ManagedStaff | null>(null)
  const [attachPosition, setAttachPosition] = useState('')
  const [attachRoles, setAttachRoles] = useState<string[]>([])
  //: Whose profile is open, when a card has been pressed.
  const [profile, setProfile] = useState<ProfileTarget | null>(null)

  function startAttach(person: ManagedStaff) {
    setAttachPosition(person.position?.id ?? '')
    setAttachRoles(person.roles?.length ? [...person.roles] : [])
    setAttaching(person)
  }

  function set<K extends keyof StaffForm>(field: K, value: StaffForm[K]) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function startAdd() {
    // Nothing preselected: a blank position and a blank role are both a
    // perfectly good answer, and preselecting one would make it look decided.
    setForm(EMPTY)
    setPhoto(null)
    setPhotoPreview(null)
    setOpen(true)
  }

  function pickPhoto(file: File | null) {
    setPhoto(file)
    setPhotoPreview(file ? URL.createObjectURL(file) : null)
  }

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true)
    try {
      await action()
      toast.success(success)
      staff.reload()
      positions.reload()
      return true
    } catch (error) {
      toast.error(toApiError(error).message)
      return false
    } finally {
      setBusy(false)
    }
  }

  async function save() {
    const payload: StaffPayload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      middle_name: form.middle_name.trim(),
      passport_id: form.passport_id.trim(),
      jshshir: form.jshshir.replace(/\D/g, ''),
      birth_date: form.birth_date || null,
      gender: form.gender,
      // Only a whole number travels; the mask's own `+998(` prefix is not one.
      phone: isPhoneComplete(form.phone) ? phoneToApi(form.phone) : '',
      email: form.email.trim(),
      // Empty means "not decided yet", which the server stores as no position
      // and no role rather than refusing the person.
      position: form.position || null,
      // Nothing ticked is a real answer: most of this register never signs in,
      // and an account created without a role becomes STAFF server-side.
      roles: form.roles,
      username: form.username.trim(),
      password: form.password,
      password_confirm: form.password_confirm,
    }
    const done = await run(() => adminApi.createStaff(payload, photo), t('staff.added'))
    if (done) setOpen(false)
  }

  // Optional does not mean "anything goes": a half-typed passport or a phone
  // with three digits in it is not empty, it is wrong, and the server refuses
  // it. Saying so here beats a 400 with no field named.
  const passportError =
    form.passport_id && !isPassportId(form.passport_id)
      ? t('validation.passportFormat')
      : undefined
  const jshshirError =
    form.jshshir && !isJshshir(form.jshshir) ? t('validation.jshshirFormat') : undefined
  const phoneError =
    phoneDigits(form.phone).length > 0 && !isPhoneComplete(form.phone)
      ? t('validation.phoneIncomplete')
      : undefined
  const emailError =
    form.email.trim() && !form.email.includes('@') ? t('validation.emailInvalid') : undefined

  // Credentials are optional, but partial ones are not: a login with no
  // password would create an account nobody can sign in to.
  const wantsAccount = Boolean(form.username.trim() || form.password || form.password_confirm)
  const passwordError =
    wantsAccount && form.password.length < 8 ? t('validation.passwordShort') : undefined
  const confirmError =
    form.password_confirm && form.password !== form.password_confirm
      ? t('validation.passwordMismatch')
      : undefined

  // A name is the whole requirement. Everything else can follow later — but
  // what has been filled in has to be right.
  const complete =
    form.first_name.trim() &&
    form.last_name.trim() &&
    !passportError &&
    !jshshirError &&
    !phoneError &&
    !emailError &&
    !passwordError &&
    !confirmError

  return (
    <>
      <Card>
        <CardHeader
          title={t('staff.title')}
          description={t('staff.description')}
          action={
            <Button size="sm" onClick={startAdd}>
              {t('staff.add')}
            </Button>
          }
        />

        <CardBody>
          {staff.initialLoading ? (
            <SkeletonCards />
          ) : staff.error ? (
            <ErrorState error={staff.error} onRetry={staff.reload} />
          ) : rows.length === 0 ? (
            <EmptyState
              title={t('staff.empty')}
              description={t('staff.addHint')}
              action={<Button onClick={startAdd}>{t('staff.add')}</Button>}
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {rows.map((person) => (
                <ProfileCard
                  key={person.id}
                  label={t('personProfile.open', { name: person.full_name })}
                  onOpen={() =>
                    setProfile({ kind: 'staff', id: person.id, name: person.full_name })
                  }
                >
                  <div className="flex items-start gap-3">
                    <Avatar
                      name={person.full_name}
                      src={person.photo ?? undefined}
                      size="lg"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[15px] font-semibold text-ink-900">
                        {person.full_name}
                      </p>
                      <p className="truncate text-sm text-ink-500">
                        {person.position
                          ? localizedTitle(person.position.titles, i18n.language)
                          : t('staff.noPosition')}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        {person.roles?.length ? (
                          <RoleBadges roles={person.roles} />
                        ) : (
                          <span className="text-xs text-ink-400">{t('staff.noRole')}</span>
                        )}
                        {person.username ? (
                          <span className="text-xs text-ink-400">{person.username}</span>
                        ) : null}
                      </div>
                      {person.phone ? (
                        <p className="mt-1 truncate text-xs text-ink-400">{person.phone}</p>
                      ) : null}
                    </div>
                  </div>

                  <div className="mt-auto flex flex-wrap justify-end gap-1 pt-3" onClick={stopCard}>
                    <Button variant="ghost" size="sm" onClick={() => startAttach(person)}>
                      {t('actions.edit')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600 hover:bg-red-500/15"
                      onClick={() => setPendingDelete(person)}
                    >
                      {t('actions.delete')}
                    </Button>
                  </div>
                </ProfileCard>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      <PersonProfileModal target={profile} onClose={() => setProfile(null)} />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t('staff.add')}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              {t('actions.cancel')}
            </Button>
            <Button loading={busy} disabled={!complete} onClick={() => void save()}>
              {t('actions.save')}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {/* The face first, the way a teacher's record is entered. */}
          <div className="flex items-center gap-4">
            <Avatar name={form.last_name || '—'} src={photoPreview ?? undefined} size="lg" />
            <div>
              <input
                ref={photoInput}
                type="file"
                accept="image/*"
                hidden
                onChange={(event) => pickPhoto(event.target.files?.[0] ?? null)}
              />
              <Button
                variant="secondary"
                size="sm"
                onClick={() => photoInput.current?.click()}
              >
                {t('actions.upload')}
              </Button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label={t('person.firstName')}
              value={form.first_name}
              required
              onChange={(event) => set('first_name', event.target.value)}
            />
            <Input
              label={t('person.lastName')}
              value={form.last_name}
              required
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
              <option value="">{t('person.select')}</option>
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
              error={emailError}
              onChange={(event) => set('email', event.target.value)}
            />
            <Select
              label={t('staff.positionOptional')}
              value={form.position}
              onChange={(event) => set('position', event.target.value)}
            >
              <option value="">{t('staff.withoutPosition')}</option>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {localizedTitle(job.titles, i18n.language)}
                </option>
              ))}
            </Select>
          </div>

          <div className="border-t border-ink-100 pt-4">
            <p className="text-[15px] font-medium text-ink-800">
              {t('person.credentials')}
            </p>
            <p className="mt-0.5 text-sm text-ink-500">{t('person.credentialsHint')}</p>
            <p className="mt-0.5 text-xs text-ink-400">{t('staff.developerNotHere')}</p>
            <div className="mt-3">
              <RolePicker
                available={roles}
                value={form.roles}
                onChange={(next) => set('roles', next)}
                label={t('staff.roleOptional')}
                hint={t('staff.rolesHint')}
              />
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <Input
                label={t('person.login')}
                value={form.username}
                autoCapitalize="none"
                spellCheck={false}
                onChange={(event) => set('username', event.target.value)}
              />
              <Input
                label={t('person.password')}
                type="password"
                value={form.password}
                error={passwordError}
                onChange={(event) => set('password', event.target.value)}
              />
              <Input
                label={t('person.passwordConfirm')}
                type="password"
                value={form.password_confirm}
                error={confirmError}
                onChange={(event) => set('password_confirm', event.target.value)}
              />
            </div>
          </div>
        </div>
      </Modal>

      {/* Attaching, afterwards. The person is already in the register; this is
          only about what they are called and what their account may do. */}
      <Modal
        open={Boolean(attaching)}
        onClose={() => setAttaching(null)}
        title={attaching?.full_name ?? ''}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAttaching(null)}>
              {t('actions.cancel')}
            </Button>
            <Button
              loading={busy}
              onClick={async () => {
                const person = attaching
                if (!person) return
                const done = await run(
                  () =>
                    adminApi.updateStaff(person.id, {
                      position: attachPosition || null,
                      // Roles only travel when there is an account to put them
                      // on; the server says so too.
                      ...(person.username && attachRoles.length
                        ? { roles: attachRoles }
                        : {}),
                    }),
                  t('staff.updated'),
                )
                if (done) setAttaching(null)
              }}
            >
              {t('actions.save')}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Select
            label={t('staff.attachPosition')}
            value={attachPosition}
            onChange={(event) => setAttachPosition(event.target.value)}
          >
            <option value="">{t('staff.withoutPosition')}</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {localizedTitle(job.titles, i18n.language)}
              </option>
            ))}
          </Select>

          <RolePicker
            available={roles}
            value={attachRoles}
            onChange={setAttachRoles}
            label={t('staff.attachRole')}
            hint={
              attaching?.username ? t('staff.rolesHint') : t('staff.roleNeedsAccount')
            }
            disabled={!attaching?.username}
          />
        </div>
      </Modal>

      <Modal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title={t('staff.confirmDelete', { name: pendingDelete?.full_name ?? '' })}
        footer={
          <>
            <Button variant="secondary" onClick={() => setPendingDelete(null)}>
              {t('actions.cancel')}
            </Button>
            <Button
              variant="danger"
              loading={busy}
              onClick={async () => {
                const person = pendingDelete
                if (!person) return
                const done = await run(
                  () => adminApi.deleteStaff(person.id),
                  t('staff.deleted'),
                )
                if (done) setPendingDelete(null)
              }}
            >
              {t('actions.delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-600">{t('staff.description')}</p>
      </Modal>
    </>
  )
}
