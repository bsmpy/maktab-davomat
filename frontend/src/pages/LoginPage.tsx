import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { Button, Input, LockIcon, UserIcon } from '@/components/ui'
import { AuthLayout } from '@/layouts/AuthLayout'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import { useTranslation } from 'react-i18next'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)
  const resetChildren = useChildStore((state) => state.reset)

  const [form, setForm] = useState({ login: '', password: '' })
  const [error, setError] = useState<ApiError | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      resetChildren()
      await login(form.login.trim(), form.password)
      navigate('/', { replace: true })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout
      title={t('auth.welcome')}
      subtitle={t('auth.loginSubtitle')}
      footer={
        <>
          {t('auth.noAccount')}{' '}
          <Link to="/royxatdan-otish" className="font-medium text-brand-600 hover:text-brand-700">
            {t('auth.register')}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error && !error.fieldError('login') && !error.fieldError('password') ? (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700"
          >
            {error.message}
          </div>
        ) : null}

        <Input
          name="login"
          label={t('auth.loginOrPhone')}
          placeholder={t('auth.loginPlaceholder')}
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          leftIcon={<UserIcon width={18} height={18} />}
          value={form.login}
          onChange={(event) => setForm((state) => ({ ...state, login: event.target.value }))}
          error={error?.fieldError('login')}
          required
        />

        <Input
          name="password"
          type="password"
          label={t('auth.password')}
          placeholder="••••••••"
          autoComplete="current-password"
          leftIcon={<LockIcon width={18} height={18} />}
          value={form.password}
          onChange={(event) => setForm((state) => ({ ...state, password: event.target.value }))}
          error={error?.fieldError('password')}
          required
        />

        <div className="flex justify-end">
          <Link
            to="/parolni-tiklash"
            className="text-sm font-medium text-brand-600 hover:text-brand-700"
          >
            {t('auth.forgotPassword')}
          </Link>
        </div>

        <Button type="submit" fullWidth size="lg" loading={submitting}>
          {t('auth.login')}
        </Button>
      </form>
    </AuthLayout>
  )
}
