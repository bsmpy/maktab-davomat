import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { settingsApi } from '@/api/settingsApi'
import { ApiError } from '@/api/errors'
import { Card, CardBody, CardHeader, Input, Toggle } from '@/components/ui'
import { toast } from '@/store/toastStore'
import type { Integration } from '@/types/api'

import { IntegrationFooter } from './IntegrationFooter'
import { SecretInput } from './SecretInput'

export function SmsIntegration({
  integration,
  onSaved,
  readOnly,
}: {
  integration: Integration
  onSaved: (next: Integration) => void
  readOnly: boolean
}) {
  const { t } = useTranslation()
  const [enabled, setEnabled] = useState(integration.is_enabled)
  const [config, setConfig] = useState<Record<string, unknown>>(integration.config ?? {})
  const [password, setPassword] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      const secrets: Record<string, string> = {}
      if (password !== null) secrets.password = password
      if (token !== null) secrets.token = token

      const next = await settingsApi.saveIntegration('SMS_ESKIZ', {
        is_enabled: enabled,
        config,
        ...(Object.keys(secrets).length ? { secrets } : {}),
      })
      onSaved(next)
      setPassword(null)
      setToken(null)
      toast.success(t('settings.saved'), 'SMS sozlamalari yangilandi.')
    } catch (error) {
      toast.error(t('common.saveFailed'), error instanceof ApiError ? error.message : undefined)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title={t('settings.smsTitle')}
        description={t('settings.smsHint')}
      />
      <CardBody className="space-y-5">
        <Toggle
          checked={enabled}
          onChange={setEnabled}
          disabled={readOnly}
          label={t('settings.enabled')}
          description={t('settings.smsOffHint')}
        />

        <Input
          label={t('settings.apiUrl')}
          value={String(config.base_url ?? 'https://notify.eskiz.uz/api')}
          disabled={readOnly}
          onChange={(event) => setConfig((c) => ({ ...c, base_url: event.target.value }))}
        />

        <Input
          label={t('settings.eskizEmail')}
          type="email"
          autoComplete="off"
          placeholder="maktab@example.uz"
          value={String(config.email ?? '')}
          disabled={readOnly}
          onChange={(event) => setConfig((c) => ({ ...c, email: event.target.value }))}
          hint={t('settings.eskizEmailHint')}
        />

        <SecretInput
          label={t('settings.eskizPassword')}
          masked={integration.secrets.password}
          value={password}
          onChange={setPassword}
        />

        <SecretInput
          label={t('settings.readyToken')}
          masked={integration.secrets.token}
          value={token}
          onChange={setToken}
          hint={t('settings.readyTokenHint')}
        />

        <Input
          label={t('settings.sender')}
          value={String(config.sender ?? '4546')}
          disabled={readOnly}
          onChange={(event) => setConfig((c) => ({ ...c, sender: event.target.value }))}
          hint={t('settings.senderHint')}
        />

        <Toggle
          checked={Boolean(config.send_otp ?? true)}
          onChange={(value) => setConfig((c) => ({ ...c, send_otp: value }))}
          disabled={readOnly}
          label={t('settings.otpBySms')}
        />
      </CardBody>

      <IntegrationFooter
        integration={integration}
        kind="SMS_ESKIZ"
        readOnly={readOnly}
        saving={saving}
        onSave={save}
        onChecked={onSaved}
        renderDetails={(details) => (
          <>
            {t('settings.accountLabel')} <b>{String(details.email ?? '—')}</b>
            {details.balance != null ? <> · Balans: <b>{String(details.balance)}</b></> : null}
          </>
        )}
      />
    </Card>
  )
}
