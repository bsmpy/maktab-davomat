import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { registrationApi } from '@/api/registrationApi'
import { ApiError } from '@/api/errors'
import { Button, ClockIcon, Input, TelegramIcon } from '@/components/ui'
import { config } from '@/config'
import { useCountdown } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { RegistrationSession } from '@/types/api'

/**
 * The confirmation step.
 *
 * The code is delivered to the parent's Telegram chat — the bot replaced SMS
 * as the channel — but it is typed here, on the site, where the rest of the
 * wizard lives. Reaching that chat requires the parent to have shared their
 * contact with the bot once; if they have not, `delivered` comes back false
 * and this says so instead of letting them guess.
 */
export function OtpStep({
  session,
  onVerified,
}: {
  session: RegistrationSession
  onVerified: (session: RegistrationSession) => void
}) {
  const { t } = useTranslation()
  const [code, setCode] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [sending, setSending] = useState(false)
  const [cooldown, startCooldown] = useCountdown()
  const [requested, setRequested] = useState(false)
  const [codeLength, setCodeLength] = useState(4)
  const [delivered, setDelivered] = useState(true)

  const botUrl = config.botUsername ? `https://t.me/${config.botUsername}` : ''

  async function sendCode() {
    setSending(true)
    setError(null)
    try {
      const result = await registrationApi.requestOtp(session.session_token)
      startCooldown(result.resend_after_seconds || 0)
      setRequested(true)
      setCode('')
      if (result.code_length) setCodeLength(result.code_length)
      setDelivered(result.delivered !== false)
      if (result.debug_code) toast.info('Test rejimi', `Kod: ${result.debug_code}`)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSending(false)
    }
  }

  useEffect(() => {
    if (!requested) void sendCode()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const verified = await registrationApi.verifyOtp(session.session_token, code.trim())
      onVerified(verified)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="rounded-xl bg-ink-50 px-4 py-3.5 text-sm">
        <p className="text-ink-600">
          {t('auth.code')} <b>Telegram</b> orqali yuborildi.
        </p>
        <p className="mt-1 text-ink-500">
          {session.guardian_name} · {session.student_name} ({session.class_group})
        </p>
      </div>

      {!delivered ? (
        <div
          role="alert"
          className="space-y-3 rounded-xl border border-amber-200 bg-amber-500/15 px-3.5 py-3 text-sm text-amber-800"
        >
          <p>
            {t('registration.botNotLinked')}
            <b> «📱 Raqamimni yuborish»</b> tugmasini bosing va shu yerga qayting.
          </p>
          {botUrl ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              leftIcon={<TelegramIcon width={16} height={16} />}
              onClick={() => window.open(botUrl, '_blank', 'noopener')}
            >
              {t('registration.openBot')}
            </Button>
          ) : null}
        </div>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700"
        >
          {error.message}
        </div>
      ) : null}

      <Input
        name="code"
        label={t('auth.code')}
        placeholder={'0'.repeat(codeLength)}
        inputMode="numeric"
        pattern="[0-9]*"
        autoComplete="one-time-code"
        maxLength={codeLength}
        className="text-center text-2xl tracking-[0.5em]"
        value={code}
        onChange={(event) =>
          setCode(event.target.value.replace(/\D/g, '').slice(0, codeLength))
        }
        autoFocus
        required
      />

      <Button
        type="submit"
        fullWidth
        size="lg"
        loading={submitting}
        disabled={code.length < codeLength}
      >
        {t('auth.confirm')}
      </Button>

      <Button
        type="button"
        variant="ghost"
        fullWidth
        loading={sending}
        disabled={cooldown > 0 || sending}
        leftIcon={cooldown > 0 ? <ClockIcon width={16} height={16} /> : undefined}
        onClick={() => void sendCode()}
      >
        {cooldown > 0 ? `Qayta yuborish (${cooldown}s)` : 'Kodni qayta yuborish'}
      </Button>
    </form>
  )
}
