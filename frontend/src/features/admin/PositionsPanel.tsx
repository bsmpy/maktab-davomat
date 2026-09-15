import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { adminApi } from '@/api/adminApi'
import { toApiError } from '@/api/errors'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  Modal,
  SkeletonRows,
} from '@/components/ui'
import { usePermissions } from '@/auth/permissions'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { ManagedPosition } from '@/types/api'
import { localizedTitle } from '@/utils/localized'

interface TitleForm {
  title_uz: string
  title_ru: string
  title_en: string
}

const EMPTY: TitleForm = { title_uz: '', title_ru: '', title_en: '' }

/**
 * Lavozimlar — the job titles a staff member is given.
 *
 * A position is nothing but its name, written once per interface language, so
 * "Hisobchi", "Бухгалтер" and "Accountant" stay one position and the register
 * can be read in whichever language the screen is running in. Nothing hangs off
 * a position: it is a label for people, not an access level.
 */
export function PositionsPanel() {
  const { t, i18n } = useTranslation()
  // A role that may only read this register gets no button that would 403.
  const canWrite = usePermissions().can('positions.manage')
  const positions = useAsyncData(() => adminApi.positions(), [])
  const [form, setForm] = useState<TitleForm>(EMPTY)
  const [editing, setEditing] = useState<ManagedPosition | null>(null)
  const [open, setOpen] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<ManagedPosition | null>(null)
  const [busy, setBusy] = useState(false)

  const rows = positions.data ?? []

  function set<K extends keyof TitleForm>(field: K, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function startAdd() {
    setEditing(null)
    setForm(EMPTY)
    setOpen(true)
  }

  function startEdit(position: ManagedPosition) {
    setEditing(position)
    setForm({
      title_uz: position.title_uz,
      title_ru: position.title_ru,
      title_en: position.title_en,
    })
    setOpen(true)
  }

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true)
    try {
      await action()
      toast.success(success)
      positions.reload()
      return true
    } catch (error) {
      toast.error(toApiError(error).message)
      return false
    } finally {
      setBusy(false)
    }
  }

  async function save() {
    const payload = {
      title_uz: form.title_uz.trim(),
      title_ru: form.title_ru.trim(),
      title_en: form.title_en.trim(),
    }
    const done = await run(
      () =>
        editing
          ? adminApi.updatePosition(editing.id, payload)
          : adminApi.createPosition(payload),
      editing ? t('positions.updated') : t('positions.added'),
    )
    if (done) setOpen(false)
  }

  return (
    <>
      <Card>
        <CardHeader
          title={t('positions.title')}
          description={t('positions.description')}
          action={
            <Button size="sm" onClick={startAdd}>
              {t('positions.add')}
            </Button>
          }
        />

        {positions.initialLoading ? (
          <SkeletonRows count={4} />
        ) : positions.error ? (
          <CardBody>
            <ErrorState error={positions.error} onRetry={positions.reload} />
          </CardBody>
        ) : rows.length === 0 ? (
          <CardBody>
            <EmptyState
              title={t('positions.empty')}
              description={t('positions.emptyHint')}
              action={canWrite ? <Button onClick={startAdd}>{t('positions.add')}</Button> : undefined}
            />
          </CardBody>
        ) : (
          <ul className="divide-y divide-ink-100 border-t border-ink-100">
            {rows.map((position) => (
              <li
                key={position.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-5"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-medium text-ink-800">
                    {localizedTitle(position.titles, i18n.language)}
                  </p>
                  {/* The other two languages, so it is plain at a glance which
                      translations are still missing. */}
                  <p className="truncate text-xs text-ink-500">
                    {[position.title_uz, position.title_ru, position.title_en]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                </div>

                <span className="shrink-0 text-sm text-ink-500">
                  {t('positions.staffCount', { count: position.staff_count })}
                </span>

                <div className="flex shrink-0 gap-1" hidden={!canWrite}>
                  <Button variant="ghost" size="sm" onClick={() => startEdit(position)}>
                    {t('actions.edit')}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-600 hover:bg-red-500/15"
                    // A position somebody holds is the label on their record;
                    // the server refuses, and there is no point offering it.
                    disabled={position.staff_count > 0}
                    title={position.staff_count > 0 ? t('positions.inUse') : undefined}
                    onClick={() => setPendingDelete(position)}
                  >
                    {t('actions.delete')}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t('actions.edit') : t('positions.add')}
        description={t('positions.uzRequired')}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              {t('actions.cancel')}
            </Button>
            <Button loading={busy} disabled={!form.title_uz.trim()} onClick={() => void save()}>
              {t('actions.save')}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label={t('positions.titleUz')}
            value={form.title_uz}
            required
            onChange={(event) => set('title_uz', event.target.value)}
          />
          <Input
            label={t('positions.titleRu')}
            value={form.title_ru}
            onChange={(event) => set('title_ru', event.target.value)}
          />
          <Input
            label={t('positions.titleEn')}
            value={form.title_en}
            onChange={(event) => set('title_en', event.target.value)}
          />
        </div>
      </Modal>

      <Modal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title={t('positions.confirmDelete', {
          title: localizedTitle(pendingDelete?.titles, i18n.language),
        })}
        footer={
          <>
            <Button variant="secondary" onClick={() => setPendingDelete(null)}>
              {t('actions.cancel')}
            </Button>
            <Button
              variant="danger"
              loading={busy}
              onClick={async () => {
                const position = pendingDelete
                if (!position) return
                const done = await run(
                  () => adminApi.deletePosition(position.id),
                  t('positions.deleted'),
                )
                if (done) setPendingDelete(null)
              }}
            >
              {t('actions.delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-600">{t('positions.description')}</p>
      </Modal>
    </>
  )
}
