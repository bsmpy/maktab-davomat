import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { settingsApi } from '@/api/settingsApi'
import { ApiError } from '@/api/errors'
import { Button, RefreshIcon } from '@/components/ui'
import { toast } from '@/store/toastStore'
import type { Integration, IntegrationKind, IntegrationTestResult } from '@/types/api'
import { formatDateTime } from '@/utils/date'

import { StatusPill } from './StatusPill'

/** Shared save / test / status strip under every integration form. */
export function IntegrationFooter({
  integration,
  kind,
  readOnly,
  saving,
  onSave,
  onChecked,
  renderDetails,
}: {
  integration: Integration
  kind: IntegrationKind
  readOnly: boolean
  saving: boolean
  onSave: () => void | Promise<void>
  onChecked: (next: Integration) => void
  renderDetails?: (details: Record<string, unknown>) => ReactNode
}) {
  const { t } = useTranslation()
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<IntegrationTestResult | null>(null)

  async function test() {
    setTesting(true)
    setResult(null)
    try {
      const outcome = await settingsApi.testIntegration(kind)
      setResult(outcome)
      if (outcome.ok) toast.success(t('settings.connectOk'))
      else toast.error(t('settings.connectFailed'), outcome.message)
      onChecked(await settingsApi.integration(kind))
    } catch (error) {
      toast.error(t('common.checkFailed'), error instanceof ApiError ? error.message : undefined)
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="space-y-3 border-t border-ink-100 px-5 py-4">
      {result ? (
        <div
          role="status"
          className={
            result.ok
              ? 'rounded-xl border border-emerald-200 bg-emerald-500/15 px-3.5 py-3 text-sm text-emerald-800'
              : 'rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700'
          }
        >
          {result.ok
            ? renderDetails && result.details
              ? renderDetails(result.details)
              : 'Ulanish muvaffaqiyatli.'
            : result.message}
        </div>
      ) : integration.last_error ? (
        <div className="rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700">
          {integration.last_error}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <StatusPill status={integration.effective_status} />
        {integration.last_checked_at ? (
          <span className="text-xs text-ink-400">
            Oxirgi tekshiruv: {formatDateTime(integration.last_checked_at)}
          </span>
        ) : null}

        <div className="ml-auto flex gap-2">
          <Button
            variant="secondary"
            loading={testing}
            disabled={readOnly}
            leftIcon={<RefreshIcon width={16} height={16} />}
            onClick={() => void test()}
          >
            {t('settings.check')}
          </Button>
          <Button loading={saving} disabled={readOnly} onClick={() => void onSave()}>
            {t('actions.save')}
          </Button>
        </div>
      </div>

      {readOnly ? (
        <p className="text-xs text-ink-400">
          {t('settings.developerOnly')}
        </p>
      ) : null}
    </div>
  )
}
