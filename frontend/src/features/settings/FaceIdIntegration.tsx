import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { managementApi } from '@/api/managementApi'
import { faceIdApi, settingsApi } from '@/api/settingsApi'
import { ApiError } from '@/api/errors'
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  Input,
  Select,
  SkeletonRows,
  Toggle,
  UserIcon,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { Integration } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatDateTime } from '@/utils/date'

import { IntegrationFooter } from './IntegrationFooter'

const SYNC_META = {
  SYNCED: { label: 'Yuklangan', chip: 'bg-emerald-500/15 text-emerald-700 ring-emerald-600/20' },
  PENDING: { label: 'Navbatda', chip: 'bg-amber-500/15 text-amber-700 ring-amber-600/20' },
  FAILED: { label: 'Xatolik', chip: 'bg-red-500/15 text-red-700 ring-red-600/20' },
} as const

export function FaceIdIntegration({
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
  const [saving, setSaving] = useState(false)
  const [enrolling, setEnrolling] = useState(false)
  const people = useAsyncData(() => faceIdApi.people(), [])
  const classGroups = useAsyncData(() => managementApi.classGroups(), [])
  const [target, setTarget] = useState('')

  async function save() {
    setSaving(true)
    try {
      const next = await settingsApi.saveIntegration('FACE_ID', { is_enabled: enabled, config })
      onSaved(next)
      toast.success(t('settings.saved'), 'Face ID sozlamalari yangilandi.')
    } catch (error) {
      toast.error(t('common.saveFailed'), error instanceof ApiError ? error.message : undefined)
    } finally {
      setSaving(false)
    }
  }

  /**
   * Push pupils onto the devices by hand.
   *
   * A pupil added before a terminal existed sits at PENDING: the automatic
   * push at upload time had nowhere to go. Adding a device does not retry
   * them, so this is the way to catch them up.
   */
  async function enroll() {
    setEnrolling(true)
    try {
      // "Everyone" has to be asked for by name: an empty body is refused.
      const result = await faceIdApi.enroll(target ? { class_group: target } : { all: true })
      const enrolled = Number(result?.faces ?? 0)
      const errors = (result?.errors as string[] | undefined) ?? []
      if (errors.length > 0) {
        toast.error(`${errors.length} ta xatolik`, errors[0])
      } else {
        toast.success(t('settings.uploaded'), `${enrolled} ta yuz yuklandi.`)
      }
      people.reload()
    } catch (error) {
      toast.error("Yuklab bo'lmadi", error instanceof ApiError ? error.message : undefined)
    } finally {
      setEnrolling(false)
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="Face ID"
          description={t('settings.faceIdHint')}
        />
        <CardBody className="space-y-5">
          <Toggle
            checked={enabled}
            onChange={setEnabled}
            disabled={readOnly}
            label={t('settings.enabled')}
            description={t('settings.faceIdOn')}
          />

          <Toggle
            checked={Boolean(config.auto_enroll ?? true)}
            onChange={(value) => setConfig((c) => ({ ...c, auto_enroll: value }))}
            disabled={readOnly}
            label={t('settings.autoEnroll')}
            description={t('settings.autoEnrollHint')}
          />

          <Input
            label={t('settings.fdid')}
            value={String(config.fdid ?? '1')}
            disabled={readOnly}
            onChange={(event) => setConfig((c) => ({ ...c, fdid: event.target.value }))}
            hint={t('settings.fdidHint')}
          />

          <Input
            label={t('settings.maxPhotoBytes')}
            type="number"
            value={String(config.max_photo_bytes ?? 2097152)}
            disabled={readOnly}
            onChange={(event) =>
              setConfig((c) => ({ ...c, max_photo_bytes: Number(event.target.value) }))
            }
          />
        </CardBody>

        <IntegrationFooter
          integration={integration}
          kind="FACE_ID"
          readOnly={readOnly}
          saving={saving}
          onSave={save}
          onChecked={onSaved}
          renderDetails={(details) => (
            <>
              {t('settings.loadedFaces')} <b>{String(details.enrolled_faces)}</b> /{' '}
              {String(details.people)}
            </>
          )}
        />
      </Card>

      <Card>
        <CardHeader
          title={t('settings.enrolledPupils')}
          description={
            people.data ? `${people.data.count} ta yozuv` : "Qurilmadagi shaxs kodlari"
          }
          action={
            <Button variant="secondary" size="sm" onClick={people.reload}>
              {t('settings.refresh')}
            </Button>
          }
        />

        <CardBody className="flex flex-wrap items-end gap-3 border-b border-ink-100">
          <Select
            label={t('settings.whoToUpload')}
            value={target}
            className="w-full sm:w-56"
            disabled={readOnly}
            onChange={(event) => setTarget(event.target.value)}
          >
            <option value="">{t('settings.allPupils')}</option>
            {(classGroups.data ?? []).map((group) => (
              <option key={group.id} value={group.id}>
                {group.display_name}
              </option>
            ))}
          </Select>
          <Button disabled={readOnly || enrolling} loading={enrolling} onClick={enroll}>
            {t('settings.uploadToDevice')}
          </Button>
          <p className="w-full text-xs text-ink-500">
            Terminal qo'shilgandan keyin avval kiritilgan o'quvchilar avtomatik
            yuklanmaydi — ularni shu yerdan yuklang.
          </p>
        </CardBody>
        {people.initialLoading ? (
          <SkeletonRows count={4} />
        ) : (people.data?.results.length ?? 0) === 0 ? (
          <EmptyState
            icon={<UserIcon width={26} height={26} />}
            title={t('settings.nobodyLoaded')}
            description={t('settings.nobodyLoadedHint')}
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {people.data!.results.map((person) => {
              const meta = SYNC_META[person.sync_state] ?? SYNC_META.PENDING
              return (
                <li key={person.id} className="flex items-center gap-3 px-5 py-3.5">
                  <code className="shrink-0 rounded-lg bg-ink-100 px-2 py-1 text-xs text-ink-600">
                    {person.person_code}
                  </code>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[15px] font-medium text-ink-800">
                      {person.student_name}
                    </p>
                    <p className="text-xs text-ink-500">
                      {person.student_class}
                      {person.face_synced_at
                        ? ` · yuz: ${formatDateTime(person.face_synced_at)}`
                        : ''}
                    </p>
                  </div>
                  {person.has_face ? (
                    <Badge className="bg-brand-50 text-brand-700 ring-brand-600/20">{t('settings.hasFace')}</Badge>
                  ) : person.has_photo ? (
                    <Badge className="bg-amber-500/15 text-amber-700 ring-amber-600/20">
                      {t('settings.hasPhoto')}
                    </Badge>
                  ) : (
                    <Badge>{t('settings.noPhoto')}</Badge>
                  )}
                  <Badge className={cn(meta.chip)}>{meta.label}</Badge>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}
