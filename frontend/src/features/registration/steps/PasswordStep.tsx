import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { registrationApi } from '@/api/registrationApi'
import { ApiError } from '@/api/errors'
import { Button, Input } from '@/components/ui'
import type { LoginResponse, RegistrationSession } from '@/types/api'

/** The last step: pick a password, and the account is created and signed in. */
export function PasswordStep({
  session,
  onCreated,
}: {
  session: RegistrationSession
  onCreated: (response: LoginResponse) => void
}) {
  const { t } = useTranslation()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [fieldError, setFieldError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (password.length < 8) {
      setFieldError('Parol kamida 8 ta belgidan iborat bo‘lsin.')
      return
    }
    if (password !== confirm) {
      setFieldError('Parollar mos kelmadi.')
      return
    }

    setFieldError('')
    setError(null)
    setSubmitting(true)
    try {
      const response = await registrationApi.complete({
        session_token: session.session_token,
        password,
        password_confirm: confirm,
      })
      onCreated(response)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="rounded-xl bg-ink-50 px-4 py-3.5 text-sm text-ink-600">
        {t('registration.passwordOnly')}
      </div>

      {error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700"
        >
          {error.message}
        </div>
      ) : null}

      <Input
        label={t('auth.password')}
        type="password"
        value={password}
        autoComplete="new-password"
        onChange={(event) => setPassword(event.target.value)}
        required
      />
      <Input
        label={t('auth.repeatPassword')}
        type="password"
        value={confirm}
        autoComplete="new-password"
        error={fieldError || undefined}
        onChange={(event) => setConfirm(event.target.value)}
        required
      />

      <Button type="submit" fullWidth size="lg" loading={submitting}>
        {t('auth.register')}
      </Button>
    </form>
  )
}
