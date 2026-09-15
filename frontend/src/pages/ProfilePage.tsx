import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { authApi } from '@/api/authApi'
import { profileApi } from '@/api/profileApi'
import { ApiError } from '@/api/errors'
import { TelegramCard } from '@/features/notifications/TelegramCard'
import { TeacherProfile } from '@/features/teacher/TeacherProfile'
import {
  Avatar,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorState,
  Input,
  LockIcon,
  LogoutIcon,
  Modal,
  Skeleton,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { useAuth } from '@/auth/permissions'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import { toast } from '@/store/toastStore'
import { cn } from '@/utils/cn'
import { phoneFromApi } from '@/utils/masks'

/** Same palette as Boshqaruv → Foydalanuvchilar, so a role reads the same everywhere. */
const ROLE_CHIP: Record<string, string> = {
  DEVELOPER: 'bg-violet-500/15 text-violet-700 ring-violet-600/20',
  SUPER_ADMIN: 'bg-indigo-500/15 text-indigo-700 ring-indigo-600/20',
  ADMIN: 'bg-blue-500/15 text-blue-700 ring-blue-600/20',
  TEACHER: 'bg-emerald-500/15 text-emerald-700 ring-emerald-600/20',
  PARENT: 'bg-brand-50 text-brand-700 ring-brand-600/20',
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5">
      <span className="text-sm text-ink-500">{label}</span>
      <span className="text-right text-sm font-medium text-ink-800">{value}</span>
    </div>
  )
}

function PasswordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const adoptSession = useAuthStore((state) => state.adoptSession)
  const [form, setForm] = useState({
    current_password: '',
    password: '',
    password_confirm: '',
  })
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const response = await authApi.changePassword(form)
      // Changing the password rotates the tokens; adopt the new session.
      adoptSession(response)
      toast.success(t('auth.passwordUpdated'))
      setForm({ current_password: '', password: '', password_confirm: '' })
      onClose()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('profile.changePassword')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('actions.cancel')}
          </Button>
          <Button type="submit" form="password-form" loading={busy}>
            {t('actions.save')}
          </Button>
        </>
      }
    >
      <form id="password-form" onSubmit={onSubmit} className="space-y-4" noValidate>
        {error && Object.keys(error.fields).length === 0 ? (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700"
          >
            {error.message}
          </div>
        ) : null}

        <Input
          name="current_password"
          type="password"
          label={t('profile.currentPassword')}
          autoComplete="current-password"
          value={form.current_password}
          onChange={(event) =>
            setForm((state) => ({
              ...state,
              current_password: event.target.value,
            }))
          }
          error={error?.fieldError('current_password')}
          required
        />
        <Input
          name="password"
          type="password"
          label={t('auth.newPassword')}
          autoComplete="new-password"
          value={form.password}
          onChange={(event) => setForm((state) => ({ ...state, password: event.target.value }))}
          error={error?.fieldError('password')}
          hint={t('auth.passwordHint')}
          required
        />
        <Input
          name="password_confirm"
          type="password"
          label={t('profile.confirmNew')}
          autoComplete="new-password"
          value={form.password_confirm}
          onChange={(event) =>
            setForm((state) => ({
              ...state,
              password_confirm: event.target.value,
            }))
          }
          error={error?.fieldError('password_confirm')}
          required
        />
      </form>
    </Modal>
  )
}

export function ProfilePage() {
  const { t } = useTranslation()
  const { user, isActing } = useAuth()
  const role = user?.active_role
  const logout = useAuthStore((state) => state.logout)
  const children = useChildStore((state) => state.children)
  const [passwordOpen, setPasswordOpen] = useState(false)
  // An employee reads their own register row instead, so the guardian call is
  // skipped whenever there is one to read. A platform owner with no row in
  // either register still gets the account card.
  const ownRecord = Boolean(user?.has_staff_record) && !isActing('OTA-ONA')
  const profile = useAsyncData(() => profileApi.me(), [role], {
    enabled: !ownRecord,
  })
  // JSHSHIR and the children count live on the guardian record; a teacher has
  // none, so those rows would only ever read empty.
  const isParent = profile.data?.active_role === 'OTA-ONA'

  // An employee's profile is their own register row — editable, with their
  // subjects or position under it — rather than the read-only guardian card.
  if (ownRecord) return <TeacherProfile />

  if (profile.initialLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-32 w-full rounded-2xl" />
        <Skeleton className="h-60 w-full rounded-2xl" />
      </div>
    )
  }

  if (profile.error) {
    return (
      <Card>
        <ErrorState error={profile.error} onRetry={profile.reload} />
      </Card>
    )
  }

  const data = profile.data!

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('nav.profile')}</h1>

      <Card>
        <CardBody className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <Avatar name={data.full_name} size="lg" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-semibold text-ink-900">{data.full_name}</p>
            <p className="text-sm text-ink-500">@{data.username}</p>
          </div>
          <Badge className={cn('ring-1 ring-inset', ROLE_CHIP[data.role])}>{data.role_label}</Badge>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={t('profile.personal')} />
        <CardBody className="divide-y divide-ink-100 py-1">
          <InfoRow label={t('profile.fullName')} value={data.full_name} />
          <InfoRow label={t('profile.login')} value={data.username} />
          <InfoRow label={t('profile.phone')} value={phoneFromApi(data.phone) || '—'} />
          {isParent ? (
            <>
              <InfoRow label={t('profile.jshshir')} value={data.jshshir || data.masked_jshshir} />
              <InfoRow label={t('profile.children')} value={`${data.children_count} ta`} />
            </>
          ) : null}
        </CardBody>
      </Card>

      {children.length > 0 ? (
        <Card>
          <CardHeader title={t('profile.children')} description={t('profile.myChildrenHint')} />
          <ul className="divide-y divide-ink-100">
            {children.map((child) => (
              <li key={child.id} className="flex items-center gap-3.5 px-5 py-3.5">
                <Avatar name={child.full_name} initials={child.initials} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-medium text-ink-800">{child.full_name}</p>
                  <p className="text-xs text-ink-500">
                    {child.class_group} sinf
                    {child.relation_label ? ` · ${child.relation_label}` : ''}
                  </p>
                </div>
                {child.is_primary ? (
                  <Badge className="bg-ink-100 text-ink-600 ring-ink-200">{t('profile.primaryGuardian')}</Badge>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <TelegramCard />

      <Card>
        <CardHeader title={t('settings.title')} />
        <CardBody className="flex flex-col gap-2 sm:flex-row">
          <Button
            variant="secondary"
            leftIcon={<LockIcon width={18} height={18} />}
            onClick={() => setPasswordOpen(true)}
          >
            {t('profile.changePassword')}
          </Button>
          <Button
            variant="ghost"
            className="text-red-600 hover:bg-red-500/15"
            leftIcon={<LogoutIcon width={18} height={18} />}
            onClick={() => void logout()}
          >
            {t('common.logout')}
          </Button>
        </CardBody>
      </Card>

      <PasswordModal open={passwordOpen} onClose={() => setPasswordOpen(false)} />
    </div>
  )
}
