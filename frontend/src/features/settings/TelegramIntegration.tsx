import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { settingsApi } from '@/api/settingsApi'
import { ApiError } from '@/api/errors'
import { Card, CardBody, CardHeader, Input, Toggle } from '@/components/ui'
import { toast } from '@/store/toastStore'
import type { Integration } from '@/types/api'

import { IntegrationFooter } from './IntegrationFooter'
import { SecretInput } from './SecretInput'

export function TelegramIntegration({
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
  const [token, setToken] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      const next = await settingsApi.saveIntegration('TELEGRAM_BOT', {
        is_enabled: enabled,
        config,
        ...(token !== null ? { secrets: { bot_token: token } } : {}),
      })
      onSaved(next)
      setToken(null)
      toast.success(t('settings.saved'), 'Telegram bot sozlamalari yangilandi.')
    } catch (error) {
      toast.error(t('common.saveFailed'), error instanceof ApiError ? error.message : undefined)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title={t('settings.telegramTitle')}
        description={t('settings.telegramHint')}
      />
      <CardBody className="space-y-5">
        <Toggle
          checked={enabled}
          onChange={setEnabled}
          disabled={readOnly}
          label={t('settings.enabled')}
          description={t('settings.telegramOffHint')}
        />

        <SecretInput
          label={t('settings.botToken')}
          masked={integration.secrets.bot_token}
          value={token}
          onChange={setToken}
          hint={t('settings.botTokenHint')}
        />

        <Input
          label={t('settings.botUsername')}
          placeholder="davomat_bot"
          value={String(config.bot_username ?? '')}
          disabled={readOnly}
          onChange={(event) =>
            setConfig((current) => ({ ...current, bot_username: event.target.value.replace('@', '') }))
          }
          hint={t('settings.botUsernameHint')}
        />

        <div className="space-y-3 rounded-xl bg-ink-50 p-4">
          <p className="text-sm font-medium text-ink-700">{t('settings.whichEvents')}</p>
          <Toggle
            checked={Boolean(config.send_absence ?? true)}
            onChange={(value) => setConfig((current) => ({ ...current, send_absence: value }))}
            disabled={readOnly}
            label={t('settings.onAbsence')}
          />
          <Toggle
            checked={Boolean(config.send_late ?? true)}
            onChange={(value) => setConfig((current) => ({ ...current, send_late: value }))}
            disabled={readOnly}
            label={t('settings.onLate')}
          />
          <Toggle
            checked={Boolean(config.send_reason_updates ?? true)}
            onChange={(value) =>
              setConfig((current) => ({ ...current, send_reason_updates: value }))
            }
            disabled={readOnly}
            label={t('settings.onReasonDecided')}
          />
        </div>
      </CardBody>

      <IntegrationFooter
        integration={integration}
        kind="TELEGRAM_BOT"
        readOnly={readOnly}
        saving={saving}
        onSave={save}
        onChecked={onSaved}
        renderDetails={(details) => (
          <>
            {t('settings.botLabel')} <b>@{String(details.username)}</b> (
            {String(details.first_name)})
          </>
        )}
      />
    </Card>
  )
}
