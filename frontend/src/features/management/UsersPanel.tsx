import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { userApi } from '@/api/managementApi'
import { toApiError } from '@/api/errors'
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CopyIcon,
  EmptyState,
  ErrorState,
  Input,
  Modal,
  PhoneInput,
  Select,
  SkeletonRows,
  Toggle,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { useAuthStore } from '@/store/authStore'
import { toast } from '@/store/toastStore'
import type { Choice, ProvisionedUser, StaffUser } from '@/types/api'
import { isPhoneComplete, phoneDigits, phoneFromApi, phoneToApi } from '@/utils/masks'

import { RoleBadges, RolePicker } from './RolePicker'

/**
 * Shows a generated password exactly once.
 *
 * Passwords are stored as Argon2 hashes, so nothing — no role, no endpoint —
 * can read an existing one back. This is the only moment the value exists in
 * readable form, which is why the dialog says so out loud.
 */
function PasswordDialog({
  result,
  onClose,
}: {
  result: ProvisionedUser | null
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  if (!result) return null

  async function copy() {
    try {
      await navigator.clipboard.writeText(result!.temporary_password)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error(t('users.copyFailed'), 'Parolni qo‘lda ko‘chiring.')
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="sm"
      title={t('users.oneTimePassword')}
      description={`${result.user.full_name} · ${result.user.username}`}
      footer={
        <Button onClick={onClose}>{t('users.closeSaved')}</Button>
      }
    >
      <div className="space-y-4">
        <div className="flex items-center gap-2 rounded-xl border border-ink-200 bg-ink-50 px-4 py-3">
          <code className="flex-1 select-all font-mono text-lg tracking-wide text-ink-900">
            {result.temporary_password}
          </code>
          <Button variant="secondary" size="sm" onClick={copy}>
            <CopyIcon width={16} height={16} />
            {copied ? 'Nusxalandi' : 'Nusxalash'}
          </Button>
        </div>

        <p className="rounded-xl bg-amber-500/15 px-4 py-3 text-sm text-amber-800">
          Bu parol boshqa hech qachon ko‘rsatilmaydi — bazada faqat uning
          qaytarib bo‘lmaydigan xesh-qiymati saqlanadi. Foydalanuvchi birinchi
          kirishda uni o‘zgartirishi shart. Yo‘qolsa — yangi parol bering.
        </p>
      </div>
    </Modal>
  )
}

function UserFormModal({
  assignableRoles,
  onClose,
  onCreated,
}: {
  assignableRoles: Choice[]
  onClose: () => void
  onCreated: (result: ProvisionedUser) => void
}) {
  const { t } = useTranslation()
  const [lastName, setLastName] = useState('')
  const [firstName, setFirstName] = useState('')
  const [middleName, setMiddleName] = useState('')
  const [phone, setPhone] = useState('')
  // Several at once is the ordinary case, not the exception: a teacher who
  // also curates a class and is on the payroll ticks three boxes.
  const [roles, setRoles] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  async function submit() {
    const next: Record<string, string> = {}
    if (!lastName.trim()) next.last_name = 'Familiyani kiriting.'
    if (!firstName.trim()) next.first_name = 'Ismni kiriting.'
    // Optional, but a half-typed number would be rejected by the API anyway.
    if (phoneDigits(phone).length > 0 && !isPhoneComplete(phone)) {
      next.phone = "Telefon raqamini to'liq kiriting."
    }
    setErrors(next)
    if (Object.keys(next).length > 0) return

    setSaving(true)
    try {
      const result = await userApi.create({
        last_name: lastName.trim(),
        first_name: firstName.trim(),
        middle_name: middleName.trim(),
        phone: phoneToApi(phone),
        // Nothing ticked is allowed: the server falls back to STAFF rather
        // than creating a login that can see nothing.
        roles,
      })
      onCreated(result)
      onClose()
    } catch (error) {
      toast.error(t('users.createFailed'), toApiError(error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t('users.newUser')}
      description={t('users.newUserHint')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            {t('actions.cancel')}
          </Button>
          <Button onClick={submit} loading={saving}>
            {t('users.create')}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
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
        <PhoneInput
          label={t('person.phone')}
          value={phone}
          onChange={setPhone}
          error={errors.phone}
        />
        <RolePicker available={assignableRoles} value={roles} onChange={setRoles} />
      </div>
    </Modal>
  )
}

/**
 * Name, phone and roles of one account — somebody else's, or your own.
 *
 * On your own row the highest role you hold stays ticked and locked: the
 * server refuses to let you take it away from yourself, and the box says so
 * before you try. Saving your own account re-reads the session, because the
 * roles in the switcher and the rail come from it.
 */
function EditUserModal({
  user,
  assignableRoles,
  onClose,
  onSaved,
}: {
  user: StaffUser
  assignableRoles: Choice[]
  onClose: () => void
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const refreshProfile = useAuthStore((state) => state.refreshProfile)
  const [lastName, setLastName] = useState(user.last_name)
  const [firstName, setFirstName] = useState(user.first_name)
  const [middleName, setMiddleName] = useState(user.middle_name ?? '')
  const [phone, setPhone] = useState(phoneFromApi(user.phone ?? ''))
  const [roles, setRoles] = useState<string[]>(user.roles?.length ? [...user.roles] : [user.role])
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const locked = user.locked_role ? [user.locked_role] : []

  async function submit() {
    const next: Record<string, string> = {}
    if (!lastName.trim()) next.last_name = 'Familiyani kiriting.'
    if (!firstName.trim()) next.first_name = 'Ismni kiriting.'
    if (phoneDigits(phone).length > 0 && !isPhoneComplete(phone)) {
      next.phone = "Telefon raqamini to'liq kiriting."
    }
    setErrors(next)
    if (Object.keys(next).length > 0) return

    setSaving(true)
    try {
      await userApi.update(user.id, {
        last_name: lastName.trim(),
        first_name: firstName.trim(),
        middle_name: middleName.trim(),
        phone: phoneToApi(phone),
        roles: Array.from(new Set([...locked, ...roles])),
      })
      if (user.is_self) await refreshProfile()
      toast.success(t('users.saved'))
      onSaved()
      onClose()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t('users.editTitle')}
      description={`${user.full_name} · ${user.username}`}
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
      <div className="space-y-3">
        {user.is_self ? (
          <p className="rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
            {t('users.selfHint')}
          </p>
        ) : null}
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
        <PhoneInput label={t('person.phone')} value={phone} onChange={setPhone} error={errors.phone} />
        <RolePicker
          available={assignableRoles}
          value={roles}
          onChange={setRoles}
          locked={locked}
        />
      </div>
    </Modal>
  )
}

export function UsersPanel() {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [password, setPassword] = useState<ProvisionedUser | null>(null)
  const [resetting, setResetting] = useState<StaffUser | null>(null)
  //: The account being edited — possibly the signed-in user's own.
  const [editing, setEditing] = useState<StaffUser | null>(null)
  const [removing, setRemoving] = useState<StaffUser | null>(null)
  const [busy, setBusy] = useState(false)

  const users = useAsyncData(
    () => userApi.list({ q: query || undefined, role: roleFilter || undefined }),
    [query, roleFilter],
  )

  async function toggleActive(user: StaffUser) {
    try {
      await userApi.update(user.id, { is_active: !user.is_active })
      toast.success(user.is_active ? 'Akkaunt o‘chirildi' : 'Akkaunt yoqildi')
      users.reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    }
  }

  async function confirmRemove() {
    if (!removing) return
    setBusy(true)
    try {
      const result = await userApi.remove(removing.id)
      toast.success(
        result.deleted ? t('users.deleted') : t('users.disabledInstead'),
        result.detail,
      )
      setRemoving(null)
      users.reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  async function confirmReset() {
    if (!resetting) return
    setBusy(true)
    try {
      const result = await userApi.resetPassword(resetting.id)
      setResetting(null)
      setPassword(result)
      users.reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  const data = users.data

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={t('nav.users')}
          description={t('users.subtitle')}
          action={
            <Button onClick={() => setFormOpen(true)} disabled={!data?.assignable_roles.length}>
              + Foydalanuvchi qo'shish
            </Button>
          }
        />
        <CardBody className="flex flex-wrap items-end gap-3">
          <Select
            label={t('users.role')}
            value={roleFilter}
            className="w-full sm:w-52"
            onChange={(event) => setRoleFilter(event.target.value)}
          >
            <option value="">{t('register.all')}</option>
            {(data?.assignable_roles ?? []).map((option) => (
              <option key={option.value} value={option.value}>
                {option.value}
              </option>
            ))}
          </Select>
          <Input
            label={t('common.search')}
            value={query}
            placeholder={t('users.nameOrLogin')}
            className="w-full sm:w-64"
            onChange={(event) => setQuery(event.target.value)}
          />
        </CardBody>

        {users.initialLoading ? (
          <SkeletonRows count={5} />
        ) : users.error ? (
          <ErrorState error={users.error} onRetry={users.reload} />
        ) : !data || data.results.length === 0 ? (
          <EmptyState title={t('users.notFound')} />
        ) : (
          <ul className="divide-y divide-ink-100 border-t border-ink-100">
            {data.results.map((user) => (
              <li key={user.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 truncate text-[15px] font-medium text-ink-800">
                    <span className="truncate">{user.full_name}</span>
                    {user.is_self ? (
                      <Badge className="bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200">
                        {t('users.you')}
                      </Badge>
                    ) : null}
                  </p>
                  <p className="truncate text-xs text-ink-500">
                    {user.username}
                    {user.school ? ` · ${user.school}` : ''}
                    {user.phone ? ` · ${phoneFromApi(user.phone)}` : ''}
                  </p>
                </div>

                {/* Every role the person holds, not only the one they are
                    working in: this list is about what an account *is*. */}
                <RoleBadges roles={user.roles?.length ? user.roles : [user.role]} />

                {user.must_change_password ? (
                  <Badge className="bg-amber-500/15 text-amber-700 ring-1 ring-inset ring-amber-600/20">
                    {t('users.passwordUnchanged')}
                  </Badge>
                ) : null}

                {!user.is_active ? (
                  <Badge className="bg-red-500/15 text-red-700 ring-1 ring-inset ring-red-600/20">
                    {t('users.disabled')}
                  </Badge>
                ) : null}

                {user.can_manage || user.can_edit ? (
                  <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                    {user.can_manage ? (
                      <Toggle
                        checked={user.is_active}
                        onChange={() => toggleActive(user)}
                        label={t('users.active')}
                      />
                    ) : null}
                    {user.can_edit ? (
                      <Button variant="secondary" size="sm" onClick={() => setEditing(user)}>
                        {t('users.edit')}
                      </Button>
                    ) : null}
                    {/* Your own password is changed on Profil; deleting or
                        switching yourself off is refused by the server. */}
                    {user.can_manage ? (
                      <>
                        <Button variant="secondary" size="sm" onClick={() => setResetting(user)}>
                          {t('auth.newPassword')}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setRemoving(user)}>
                          {t('actions.delete')}
                        </Button>
                      </>
                    ) : null}
                  </div>
                ) : (
                  <span className="text-xs text-ink-400">{t('users.cannotChange')}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {formOpen ? (
        <UserFormModal
          assignableRoles={data?.assignable_roles ?? []}
          onClose={() => setFormOpen(false)}
          onCreated={(result) => {
            setPassword(result)
            users.reload()
          }}
        />
      ) : null}

      <Modal
        open={Boolean(resetting)}
        onClose={() => setResetting(null)}
        size="sm"
        title={`${resetting?.full_name ?? ''} uchun yangi parol?`}
        description={t('users.oldPasswordDies')}
        footer={
          <>
            <Button variant="secondary" onClick={() => setResetting(null)} disabled={busy}>
              {t('actions.cancel')}
            </Button>
            <Button onClick={confirmReset} loading={busy}>
              {t('users.issuePassword')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-600">
          Mavjud parolni ko‘rsatib bo‘lmaydi — u qaytarib bo‘lmaydigan xesh
          ko‘rinishida saqlanadi. Uning o‘rniga yangi bir martalik parol
          beriladi; foydalanuvchi birinchi kirishda uni o‘zgartiradi.
        </p>
      </Modal>

      {editing ? (
        <EditUserModal
          key={editing.id}
          user={editing}
          assignableRoles={data?.assignable_roles ?? []}
          onClose={() => setEditing(null)}
          onSaved={users.reload}
        />
      ) : null}

      <Modal
        open={Boolean(removing)}
        onClose={() => setRemoving(null)}
        size="sm"
        title={t('users.confirmDelete')}
        description={`${removing?.full_name ?? ''} · ${removing?.username ?? ''}`}
        footer={
          <>
            <Button variant="secondary" onClick={() => setRemoving(null)} disabled={busy}>
              {t('actions.cancel')}
            </Button>
            <Button onClick={confirmRemove} loading={busy}>
              {t('actions.delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-600">{t('users.deleteHint')}</p>
      </Modal>

      <PasswordDialog result={password} onClose={() => setPassword(null)} />
    </div>
  )
}
