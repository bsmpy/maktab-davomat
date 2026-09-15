import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { authApi } from '@/api/authApi'
import { toApiError } from '@/api/errors'
import { Button, EmptyState, Input, LockIcon, Spinner } from '@/components/ui'
import { AuthLayout } from '@/layouts/AuthLayout'
import { useAuthStore } from '@/store/authStore'
import { toast } from '@/store/toastStore'
import { useTranslation } from 'react-i18next'

type Stage = 'redeeming' | 'set-password' | 'failed'

/**
 * Landing for the bot's "open the cabinet" button.
 *
 * The bot already proved who this is — the number the school recorded,
 * confirmed by a code only that chat received. The ticket in the URL is
 * single-use and short-lived; redeeming it signs the browser in, and if the
 * account has no password yet this is where it gets set. That is why the
 * password is asked for here and never in a chat window.
 */
export function TelegramLoginPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const adoptSession = useAuthStore((state) => state.adoptSession)

  // Derived at first render rather than set from the effect: a missing ticket
  // is knowable before anything is fetched.
  const ticket = params.get('ticket') ?? ''
  const [stage, setStage] = useState<Stage>(ticket ? 'redeeming' : 'failed')
  const [error, setError] = useState(
    ticket ? '' : 'Havola noto‘g‘ri. Botdan yangi havola oling.',
  )
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [saving, setSaving] = useState(false)
  const [fieldError, setFieldError] = useState('')

  // Strict mode mounts effects twice; a one-time ticket must only be spent once.
  const redeemed = useRef(false)

  useEffect(() => {
    if (!ticket || redeemed.current) return
    redeemed.current = true

    authApi
      .loginWithTicket(ticket)
      .then((response) => {
        adoptSession(response)
        setLogin(response.user.username)
        if (response.must_set_password) {
          setStage('set-password')
        } else {
          navigate('/', { replace: true })
        }
      })
      .catch((cause) => {
        setError(toApiError(cause).message)
        setStage('failed')
      })
  }, [ticket, adoptSession, navigate])

  async function submit() {
    if (password.length < 8) {
      setFieldError('Parol kamida 8 ta belgidan iborat bo‘lsin.')
      return
    }
    if (password !== confirm) {
      setFieldError('Parollar mos kelmadi.')
      return
    }
    setFieldError('')
    setSaving(true)
    try {
      const response = await authApi.changePassword({
        password,
        password_confirm: confirm,
      })
      adoptSession(response)
      toast.success(t('auth.passwordSet'), 'Endi login va parol bilan kira olasiz.')
      navigate('/', { replace: true })
    } catch (cause) {
      const apiError = toApiError(cause)
      setFieldError(apiError.fields?.password?.[0] ?? apiError.message)
    } finally {
      setSaving(false)
    }
  }

  if (stage === 'redeeming') {
    return (
      <AuthLayout title={t('auth.telegramSigningIn')} subtitle={t('auth.telegramWait')}>
        <div className="grid place-items-center gap-3 py-8 text-ink-400">
          <Spinner className="h-7 w-7" />
          <p className="text-sm">{t('auth.waitAMoment')}</p>
        </div>
      </AuthLayout>
    )
  }

  if (stage === 'failed') {
    return (
      <AuthLayout title={t('auth.linkFailed')} subtitle={t('auth.linkFailedHint')}>
        <EmptyState
          icon={<LockIcon width={26} height={26} />}
          title={t('auth.linkExpired')}
          description={error}
          action={<Button onClick={() => navigate('/kirish')}>{t('auth.signInWithLogin')}</Button>}
        />
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title={t('auth.setPassword')} subtitle={t('auth.setPasswordHint')}>
      <div className="space-y-4">
        <Input label={t('person.login')} value={login} readOnly disabled />

        <Input
          label={t('auth.newPassword')}
          type="password"
          value={password}
          autoComplete="new-password"
          onChange={(event) => setPassword(event.target.value)}
        />
        <Input
          label={t('auth.repeatPassword')}
          type="password"
          value={confirm}
          autoComplete="new-password"
          error={fieldError || undefined}
          onChange={(event) => setConfirm(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') void submit()
          }}
        />

        <Button fullWidth loading={saving} onClick={submit}>
          {t('auth.saveAndContinue')}
        </Button>

        <p className="text-center text-xs text-ink-500">
          {t('auth.rememberLogin')}
        </p>
      </div>
    </AuthLayout>
  )
}
