import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { catalogApi } from '@/api/catalogApi'
import { terminalApi } from '@/api/settingsApi'
import { ApiError } from '@/api/errors'
import { Button, Input, Modal, Select, Toggle } from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { Terminal, TerminalDirection } from '@/types/api'

const DIRECTIONS: { value: TerminalDirection; label: string }[] = [
  { value: 'BOTH', label: 'Kirish va chiqish' },
  { value: 'IN', label: 'Faqat kirish' },
  { value: 'OUT', label: 'Faqat chiqish' },
]

export function TerminalFormModal({
  terminal,
  onClose,
  onSaved,
}: {
  terminal: Terminal | null
  onClose: () => void
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const isEdit = terminal !== null
  const schools = useAsyncData(() => catalogApi.schools(), [])

  const [form, setForm] = useState({
    school: terminal?.school ?? '',
    name: terminal?.name ?? '',
    host: terminal?.host ?? '',
    port: terminal?.port ?? 80,
    use_https: terminal?.use_https ?? false,
    username: terminal?.username ?? 'admin',
    password: '',
    direction: (terminal?.direction ?? 'BOTH') as TerminalDirection,
    location: terminal?.location ?? '',
    model: terminal?.model ?? 'DS-K1T341CMF',
    is_active: terminal?.is_active ?? true,
  })
  const [error, setError] = useState<ApiError | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  function update<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function testConnection() {
    if (!form.password && !isEdit) {
      toast.error(t('terminals.enterPassword'), 'Ulanishni tekshirish uchun parol kerak.')
      return
    }
    setTesting(true)
    try {
      const result = await terminalApi.testConnection({
        host: form.host,
        port: Number(form.port),
        use_https: form.use_https,
        username: form.username,
        password: form.password,
      })
      if (result.ok) {
        toast.success(
          t('terminals.deviceFound'),
          `${result.device?.model ?? ''} · ${result.device?.serial_number ?? ''}`,
        )
      } else {
        toast.error(t('settings.connectFailed'), result.message)
      }
    } catch (caught) {
      toast.error(t('common.checkFailed'), caught instanceof ApiError ? caught.message : undefined)
    } finally {
      setTesting(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = {
        ...form,
        port: Number(form.port),
        // An empty password means "keep the stored one".
        ...(form.password ? { password: form.password } : {}),
      }
      if (!form.password) delete (payload as Record<string, unknown>).password

      if (isEdit) await terminalApi.update(terminal.id, payload)
      else await terminalApi.create(payload)

      toast.success(isEdit ? 'Saqlandi' : "Terminal qo'shildi")
      onSaved()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? 'Terminalni tahrirlash' : "Terminal qo'shish"}
      description={t('terminals.formHint')}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('actions.cancel')}
          </Button>
          <Button variant="secondary" loading={testing} onClick={() => void testConnection()}>
            {t('terminals.testConnection')}
          </Button>
          <Button type="submit" form="terminal-form" loading={saving}>
            {t('actions.save')}
          </Button>
        </>
      }
    >
      <form id="terminal-form" onSubmit={submit} className="space-y-4" noValidate>
        {error && Object.keys(error.fields).length === 0 ? (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700"
          >
            {error.message}
          </div>
        ) : null}

        <Select
          name="school"
          label={t('nav.school')}
          value={form.school}
          onChange={(event) => update('school', event.target.value)}
          error={error?.fieldError('school')}
          required
        >
          <option value="" disabled>
            {t('person.select')}
          </option>
          {(schools.data ?? []).map((school) => (
            <option key={school.id} value={school.id}>
              {school.short_name || school.name}
            </option>
          ))}
        </Select>

        <Input
          name="name"
          label={t('terminals.name')}
          placeholder={t('terminals.namePlaceholder')}
          value={form.name}
          onChange={(event) => update('name', event.target.value)}
          error={error?.fieldError('name')}
          required
        />

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <Input
              name="host"
              label={t('terminals.ip')}
              placeholder="192.168.1.64"
              value={form.host}
              onChange={(event) => update('host', event.target.value)}
              error={error?.fieldError('host')}
              required
            />
          </div>
          <Input
            name="port"
            label={t('terminals.port')}
            type="number"
            min={1}
            max={65535}
            value={String(form.port)}
            onChange={(event) => update('port', Number(event.target.value))}
            error={error?.fieldError('port')}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            name="username"
            label={t('terminals.isapiLogin')}
            autoComplete="off"
            value={form.username}
            onChange={(event) => update('username', event.target.value)}
            error={error?.fieldError('username')}
          />
          <Input
            name="password"
            type="password"
            label={t('terminals.isapiPassword')}
            autoComplete="new-password"
            placeholder={isEdit ? "O'zgartirmaslik uchun bo'sh qoldiring" : ''}
            value={form.password}
            onChange={(event) => update('password', event.target.value)}
            error={error?.fieldError('password')}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            name="direction"
            label={t('terminals.direction')}
            value={form.direction}
            onChange={(event) => update('direction', event.target.value as TerminalDirection)}
            hint={t('terminals.directionHint')}
          >
            {DIRECTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
          <Input
            name="model"
            label={t('terminals.model')}
            value={form.model}
            onChange={(event) => update('model', event.target.value)}
          />
        </div>

        <Input
          name="location"
          label={t('terminals.location')}
          placeholder={t('terminals.locationPlaceholder')}
          value={form.location}
          onChange={(event) => update('location', event.target.value)}
        />

        <Toggle
          checked={form.use_https}
          onChange={(value) => update('use_https', value)}
          label={t('terminals.useHttps')}
          description={t('terminals.useHttpsHint')}
        />

        <Toggle
          checked={form.is_active}
          onChange={(value) => update('is_active', value)}
          label={t('users.active')}
          description={t('terminals.activeHint')}
        />
      </form>
    </Modal>
  )
}
