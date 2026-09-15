import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button, CheckIcon, CopyIcon } from '@/components/ui'
import { toast } from '@/store/toastStore'

/** Final screen: the generated username must be shown once, clearly. */
export function DoneStep({
  username,
  onContinue,
}: {
  username: string
  onContinue: () => void
}) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(username)
      setCopied(true)
      toast.success(t('registration.copied'), `Login: ${username}`)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error(t('common.copyFailed'), t('registration.copyFailedHint'))
    }
  }

  return (
    <div className="text-center">
      <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-emerald-500/15 text-emerald-600">
        <CheckIcon width={28} height={28} />
      </div>

      <h2 className="text-lg font-semibold text-ink-900">{t('registration.accountCreated')}</h2>
      <p className="mt-1.5 text-sm text-ink-500">
        {t('registration.saveLogin')}
      </p>

      <div className="mt-6 rounded-xl border border-dashed border-brand-300 bg-brand-50/60 px-4 py-5">
        <p className="text-xs font-medium uppercase tracking-wide text-brand-600">{t('auth.yourLogin')}</p>
        <p className="mt-1.5 select-all text-2xl font-semibold tracking-tight text-ink-900">
          {username}
        </p>
        <Button
          variant="ghost"
          size="sm"
          className="mt-2 text-brand-700"
          leftIcon={
            copied ? <CheckIcon width={16} height={16} /> : <CopyIcon width={16} height={16} />
          }
          onClick={() => void copy()}
        >
          {copied ? t('registration.copied') : 'Nusxalash'}
        </Button>
      </div>

      <p className="mt-4 text-sm text-ink-500">
        {t('registration.loginOrPhoneWorks')}
      </p>

      <Button fullWidth size="lg" className="mt-6" onClick={onContinue}>
        {t('registration.goToCabinet')}
      </Button>
    </div>
  )
}
