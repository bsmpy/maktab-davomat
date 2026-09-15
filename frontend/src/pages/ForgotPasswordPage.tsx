import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { authApi } from '@/api/authApi'
import { ApiError } from '@/api/errors'
import { Button, ClockIcon, Input, LockIcon, UserIcon } from '@/components/ui'
import { useCountdown } from '@/hooks'
import { AuthLayout } from '@/layouts/AuthLayout'
import { useAuthStore } from '@/store/authStore'
import { toast } from '@/store/toastStore'
import type { PasswordResetStart } from '@/types/api'
import { useTranslation } from 'react-i18next'

type Step = 'login' | 'code' | 'password'

export function ForgotPasswordPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const adoptSession = useAuthStore((state) => state.adoptSession)

  const [step, setStep] = useState<Step>('login')
  const [session, setSession] = useState<PasswordResetStart | null>(null)
  const [login, setLogin] = useState('')
  const [code, setCode] = useState('')
  const [passwords, setPasswords] = useState({ password: '', password_confirm: '' })
  const [error, setError] = useState<ApiError | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [cooldown, startCooldown] = useCountdown()

  async function requestCode(event?: FormEvent) {
    event?.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const result = await authApi.requestPasswordReset(login.trim())
      setSession(result)
      startCooldown(result.resend_after_seconds || 60)
      if (result.sent) {
        setStep('code')
        if (result.debug_code) toast.info('Test rejimi', `Kod: ${result.debug_code}`)
      } else {
        // The API deliberately does not confirm whether the account exists.
        toast.info(
          'Kod yuborildi',
          'Agar bunday akkaunt mavjud bo\'lsa, telefon raqamiga kod yuborildi.',
        )
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSubmitting(false)
    }
  }

  async function verifyCode(event: FormEvent) {
    event.preventDefault()
    if (!session) return
    setSubmitting(true)
    setError(null)
    try {
      await authApi.verifyPasswordReset(session.session_token, code.trim())
      setStep('password')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSubmitting(false)
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault()
    if (!session) return
    setSubmitting(true)
    setError(null)
    try {
      const response = await authApi.confirmPasswordReset({
        session_token: session.session_token,
        ...passwords,
      })
      adoptSession(response)
      toast.success(t('auth.passwordUpdated'), 'Endi yangi parol bilan kirishingiz mumkin.')
      navigate('/', { replace: true })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSubmitting(false)
    }
  }

  const banner =
    error && Object.keys(error.fields).length === 0 ? (
      <div
        role="alert"
        className="rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700"
      >
        {error.message}
      </div>
    ) : null

  return (
    <AuthLayout
      title={t('auth.resetTitle')}
      subtitle={
        step === 'login'
          ? "Ro'yxatdan o'tgan telefon raqamingizga tasdiqlash kodi yuboriladi"
          : step === 'code'
            ? `Kod ${session?.masked_phone} raqamiga yuborildi`
            : 'Yangi parolni kiriting'
      }
      footer={
        <Link to="/kirish" className="font-medium text-brand-600 hover:text-brand-700">
          {t('auth.backToLogin')}
        </Link>
      }
    >
      {step === 'login' ? (
        <form onSubmit={requestCode} className="space-y-4" noValidate>
          {banner}
          <Input
            name="login"
            label={t('auth.loginOrPhone')}
            placeholder={t('auth.loginPlaceholder')}
            leftIcon={<UserIcon width={18} height={18} />}
            value={login}
            onChange={(event) => setLogin(event.target.value)}
            error={error?.fieldError('login')}
            required
          />
          <Button type="submit" fullWidth size="lg" loading={submitting}>
            {t('auth.sendCode')}
          </Button>
        </form>
      ) : null}

      {step === 'code' ? (
        <form onSubmit={verifyCode} className="space-y-4" noValidate>
          {banner}
          <Input
            name="code"
            label={t('auth.code')}
            placeholder="000000"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={8}
            className="text-center text-xl tracking-[0.4em]"
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
            required
          />
          <Button type="submit" fullWidth size="lg" loading={submitting}>
            {t('auth.confirm')}
          </Button>
          <Button
            type="button"
            variant="ghost"
            fullWidth
            disabled={cooldown > 0 || submitting}
            leftIcon={cooldown > 0 ? <ClockIcon width={16} height={16} /> : undefined}
            onClick={() => void requestCode()}
          >
            {cooldown > 0 ? `Qayta yuborish (${cooldown}s)` : 'Kodni qayta yuborish'}
          </Button>
        </form>
      ) : null}

      {step === 'password' ? (
        <form onSubmit={savePassword} className="space-y-4" noValidate>
          {banner}
          <Input
            name="password"
            type="password"
            label={t('auth.newPassword')}
            autoComplete="new-password"
            leftIcon={<LockIcon width={18} height={18} />}
            value={passwords.password}
            onChange={(event) =>
              setPasswords((state) => ({ ...state, password: event.target.value }))
            }
            error={error?.fieldError('password')}
            hint={t('auth.passwordHint')}
            required
          />
          <Input
            name="password_confirm"
            type="password"
            label={t('auth.passwordConfirm')}
            autoComplete="new-password"
            leftIcon={<LockIcon width={18} height={18} />}
            value={passwords.password_confirm}
            onChange={(event) =>
              setPasswords((state) => ({ ...state, password_confirm: event.target.value }))
            }
            error={error?.fieldError('password_confirm')}
            required
          />
          <Button type="submit" fullWidth size="lg" loading={submitting}>
            {t('auth.savePassword')}
          </Button>
        </form>
      ) : null}
    </AuthLayout>
  )
}
