import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { settingsApi, terminalApi } from '@/api/settingsApi'
import { ApiError } from '@/api/errors'
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CheckIcon,
  CopyIcon,
  EmptyState,
  ErrorState,
  Input,
  PlusIcon,
  RefreshIcon,
  SkeletonRows,
  Toggle,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { Integration, Terminal } from '@/types/api'
import { formatDateTime, todayISO } from '@/utils/date'

import { IntegrationFooter } from './IntegrationFooter'
import { StatusPill } from './StatusPill'
import { TerminalFormModal } from './TerminalFormModal'

export function TerminalsIntegration({
  integration,
  onSaved,
  readOnly,
}: {
  integration: Integration
  onSaved: (next: Integration) => void
  readOnly: boolean
}) {
  const { t } = useTranslation()
  const [config, setConfig] = useState<Record<string, unknown>>(integration.config ?? {})
  const [enabled, setEnabled] = useState(integration.is_enabled)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState<Terminal | 'new' | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  const terminals = useAsyncData(() => terminalApi.list(), [])

  async function saveSettings() {
    setSaving(true)
    try {
      const next = await settingsApi.saveIntegration('TERMINALS', {
        is_enabled: enabled,
        config,
      })
      onSaved(next)
      toast.success(t('settings.saved'), 'Turniket sozlamalari yangilandi.')
    } catch (error) {
      toast.error(t('common.saveFailed'), error instanceof ApiError ? error.message : undefined)
    } finally {
      setSaving(false)
    }
  }

  async function testTerminal(terminal: Terminal) {
    setBusyId(terminal.id)
    try {
      const result = await terminalApi.test(terminal.id)
      if (result.ok) {
        toast.success(
          t('terminals.deviceAnswered'),
          `${result.device?.model ?? ''} ${result.device?.firmware ?? ''}`.trim(),
        )
      } else {
        toast.error(t('settings.connectFailed'), result.message)
      }
      terminals.reload()
    } catch (error) {
      toast.error(t('common.checkFailed'), error instanceof ApiError ? error.message : undefined)
    } finally {
      setBusyId(null)
    }
  }

  async function syncTerminal(terminal: Terminal) {
    setBusyId(terminal.id)
    try {
      const start = `${todayISO()}T00:00:00`
      const result = await terminalApi.sync(terminal.id, start)
      if (result.ok) {
        toast.success(
          t('terminals.synced'),
          `${result.stored} ta yangi hodisa, ${result.created ?? 0} ta davomat yozuvi.`,
        )
      } else {
        toast.error(t('terminals.syncFailed'), result.error)
      }
      terminals.reload()
    } catch (error) {
      toast.error(t('common.error'), error instanceof ApiError ? error.message : undefined)
    } finally {
      setBusyId(null)
    }
  }

  async function removeTerminal(terminal: Terminal) {
    if (!window.confirm(`"${terminal.name}" terminali o'chirilsinmi?`)) return
    try {
      await terminalApi.remove(terminal.id)
      toast.success('O\'chirildi')
      terminals.reload()
    } catch (error) {
      toast.error('O\'chirib bo\'lmadi', error instanceof ApiError ? error.message : undefined)
    }
  }

  async function copyIngest(terminal: Terminal) {
    try {
      await navigator.clipboard.writeText(terminal.ingest_url)
      setCopied(terminal.id)
      window.setTimeout(() => setCopied(null), 2000)
    } catch {
      toast.info('Nusxalab bo\'lmadi', terminal.ingest_url)
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={t('terminals.rulesTitle')}
          description={t('terminals.rulesHint')}
        />
        <CardBody className="space-y-5">
          <Toggle
            checked={enabled}
            onChange={setEnabled}
            disabled={readOnly}
            label={t('settings.enabled')}
          />
          <Toggle
            checked={Boolean(config.auto_mark_attendance ?? true)}
            onChange={(value) => setConfig((c) => ({ ...c, auto_mark_attendance: value }))}
            disabled={readOnly}
            label={t('terminals.autoMark')}
            description={t('terminals.autoMarkHint')}
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label={t('terminals.grace')}
              type="number"
              min={0}
              max={60}
              value={String(config.late_grace_minutes ?? 5)}
              disabled={readOnly}
              onChange={(event) =>
                setConfig((c) => ({ ...c, late_grace_minutes: Number(event.target.value) }))
              }
              hint={t('terminals.graceHint')}
            />
            <Input
              label={t('terminals.debounce')}
              type="number"
              min={0}
              max={600}
              value={String(config.debounce_seconds ?? 60)}
              disabled={readOnly}
              onChange={(event) =>
                setConfig((c) => ({ ...c, debounce_seconds: Number(event.target.value) }))
              }
              hint={t('terminals.debounceHint')}
            />
            <Input
              label={t('terminals.pollInterval')}
              type="number"
              min={1}
              max={120}
              value={String(config.poll_interval_minutes ?? 5)}
              disabled={readOnly}
              onChange={(event) =>
                setConfig((c) => ({ ...c, poll_interval_minutes: Number(event.target.value) }))
              }
            />
            <Input
              label={t('terminals.pollWindow')}
              type="number"
              min={5}
              max={1440}
              value={String(config.poll_window_minutes ?? 120)}
              disabled={readOnly}
              onChange={(event) =>
                setConfig((c) => ({ ...c, poll_window_minutes: Number(event.target.value) }))
              }
              hint={t('terminals.pollWindowHint')}
            />
          </div>

          <Toggle
            checked={Boolean(config.sync_device_time ?? true)}
            onChange={(value) => setConfig((c) => ({ ...c, sync_device_time: value }))}
            disabled={readOnly}
            label={t('terminals.syncClock')}
            description={t('terminals.syncClockHint')}
          />
        </CardBody>

        <IntegrationFooter
          integration={integration}
          kind="TERMINALS"
          readOnly={readOnly}
          saving={saving}
          onSave={saveSettings}
          onChecked={onSaved}
          renderDetails={(details) => (
            <>
              {t('settings.onlineDevices')} <b>{String(details.online)}</b>
            </>
          )}
        />
      </Card>

      <Card>
        <CardHeader
          title={t('settings.terminalsTitle')}
          description={t('terminals.devicesHint')}
          action={
            <Button
              size="sm"
              disabled={readOnly}
              leftIcon={<PlusIcon width={16} height={16} />}
              onClick={() => setEditing('new')}
            >
              {t('terminals.addDevice')}
            </Button>
          }
        />

        {terminals.initialLoading ? (
          <SkeletonRows count={2} />
        ) : terminals.error ? (
          <ErrorState error={terminals.error} onRetry={terminals.reload} />
        ) : (terminals.data?.results.length ?? 0) === 0 ? (
          <EmptyState
            title={t('terminals.noDevices')}
            description={t('terminals.noDevicesHint')}
            action={
              <Button disabled={readOnly} onClick={() => setEditing('new')}>
                {t('terminals.addDevice')}
              </Button>
            }
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {terminals.data!.results.map((terminal) => (
              <li key={terminal.id} className="px-5 py-4">
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[15px] font-semibold text-ink-800">{terminal.name}</p>
                      <StatusPill status={terminal.is_active ? terminal.status : 'DISABLED'} />
                      <Badge>{terminal.direction_display}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-ink-500">
                      {terminal.base_url} · {terminal.model}
                      {terminal.firmware ? ` · ${terminal.firmware}` : ''}
                      {terminal.location ? ` · ${terminal.location}` : ''}
                    </p>
                    <p className="mt-1 text-xs text-ink-400">
                      Bugungi hodisalar: {terminal.events_today} · Yuklangan:{' '}
                      {terminal.enrolled_count}
                      {terminal.last_event_at
                        ? ` · Oxirgi hodisa: ${formatDateTime(terminal.last_event_at)}`
                        : ''}
                    </p>
                    {terminal.last_error ? (
                      <p className="mt-1 text-xs text-red-600">{terminal.last_error}</p>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={busyId === terminal.id}
                      disabled={readOnly}
                      onClick={() => void testTerminal(terminal)}
                    >
                      {t('settings.check')}
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={readOnly || busyId === terminal.id}
                      leftIcon={<RefreshIcon width={15} height={15} />}
                      onClick={() => void syncTerminal(terminal)}
                    >
                      {t('terminals.sync')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={readOnly}
                      onClick={() => setEditing(terminal)}
                    >
                      {t('actions.edit')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600 hover:bg-red-500/15"
                      disabled={readOnly}
                      onClick={() => void removeTerminal(terminal)}
                    >
                      {t('actions.delete')}
                    </Button>
                  </div>
                </div>

                <div className="mt-3 rounded-xl bg-ink-50 p-3">
                  <p className="text-xs font-medium text-ink-600">
                    {t('terminals.listenerUrl')}
                  </p>
                  <div className="mt-1.5 flex items-center gap-2">
                    <code className="min-w-0 flex-1 truncate text-xs text-ink-700">
                      {terminal.ingest_url}
                    </code>
                    <Button
                      variant="ghost"
                      size="sm"
                      leftIcon={
                        copied === terminal.id ? (
                          <CheckIcon width={15} height={15} />
                        ) : (
                          <CopyIcon width={15} height={15} />
                        )
                      }
                      onClick={() => void copyIngest(terminal)}
                    >
                      {copied === terminal.id ? 'Nusxalandi' : 'Nusxalash'}
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {editing ? (
        <TerminalFormModal
          terminal={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            terminals.reload()
          }}
        />
      ) : null}
    </div>
  )
}
