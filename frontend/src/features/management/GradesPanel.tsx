import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { managementApi } from '@/api/managementApi'
import { toApiError } from '@/api/errors'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  Input,
  Modal,
  Select,
} from '@/components/ui'
import { usePermissions } from '@/auth/permissions'
import { toast } from '@/store/toastStore'
import type { ManagedClassGroup, ManagedGrade } from '@/types/api'

const LEVELS = Array.from({ length: 11 }, (_, index) => index + 1)

/** Confirms a delete that also retires everything underneath it. */
function ConfirmDelete({
  open,
  title,
  description,
  busy,
  onClose,
  onConfirm,
}: {
  open: boolean
  title: string
  description: string
  busy: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  const { t } = useTranslation()
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            {t('actions.cancel')}
          </Button>
          <Button variant="danger" onClick={onConfirm} loading={busy}>
            {t('actions.delete')}
          </Button>
        </>
      }
    >
      <p className="text-sm text-ink-600">
        Ma'lumotlar arxivda saqlanadi — davomat tarixi yo'qolmaydi, lekin ro'yxatlarda
        ko'rinmay qoladi.
      </p>
    </Modal>
  )
}

export function GradesPanel({
  grades,
  classGroups,
  onChanged,
}: {
  grades: ManagedGrade[]
  classGroups: ManagedClassGroup[]
  onChanged: () => void
}) {
  const { t } = useTranslation()
  // A role that may only read the structure gets no button that would 403.
  const canWrite = usePermissions().can('classes.manage')
  const [newLevel, setNewLevel] = useState('')
  const [groupGrade, setGroupGrade] = useState('')
  const [groupName, setGroupName] = useState('')
  const [busy, setBusy] = useState(false)
  const [pendingGrade, setPendingGrade] = useState<ManagedGrade | null>(null)
  const [pendingGroup, setPendingGroup] = useState<ManagedClassGroup | null>(null)

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true)
    try {
      await action()
      toast.success(success)
      onChanged()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  const takenLevels = new Set(grades.map((grade) => grade.level))

  return (
    <div className="space-y-5">
      {/* --- grades --------------------------------------------------- */}
      <Card>
        <CardHeader
          title={t('register.gradesTitle')}
          description={t('register.gradesHint')}
        />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <Select
              label={t('register.newGrade')}
              value={newLevel}
              onChange={(event) => setNewLevel(event.target.value)}
              className="w-full sm:w-44"
            >
              <option value="">{t('person.select')}</option>
              {LEVELS.filter((level) => !takenLevels.has(level)).map((level) => (
                <option key={level} value={level}>
                  {level}-sinf
                </option>
              ))}
            </Select>
            {canWrite ? (
              <Button
                disabled={!newLevel || busy}
                onClick={() =>
                  run(async () => {
                    await managementApi.createGrade(Number(newLevel))
                    setNewLevel('')
                  }, 'Sinf qo’shildi')
                }
              >
                {t('actions.add')}
              </Button>
            ) : null}
          </div>

          {grades.length === 0 ? (
            <EmptyState
              title={t('register.noGrades')}
              description={t('register.noGradesHint')}
            />
          ) : (
            <ul className="divide-y divide-ink-100 rounded-xl border border-ink-100">
              {grades.map((grade) => (
                <li key={grade.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
                  <span className="w-20 text-[15px] font-semibold text-ink-800">
                    {grade.label}
                  </span>
                  <span className="text-sm text-ink-500">
                    {grade.class_groups_count} guruh · {grade.students_count} o'quvchi
                  </span>
                  {canWrite ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-auto text-red-600 hover:bg-red-500/15"
                      onClick={() => setPendingGrade(grade)}
                    >
                      {t('actions.delete')}
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      {/* --- class groups --------------------------------------------- */}
      <Card>
        <CardHeader
          title={t('register.groupsTitle')}
          description={t('register.groupsHint')}
        />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <Select
              label={t('register.grade')}
              value={groupGrade}
              onChange={(event) => setGroupGrade(event.target.value)}
              className="w-full sm:w-44"
            >
              <option value="">{t('person.select')}</option>
              {grades.map((grade) => (
                <option key={grade.id} value={grade.id}>
                  {grade.label}
                </option>
              ))}
            </Select>
            <Input
              label={t('register.groupName')}
              value={groupName}
              placeholder="A, B, G…"
              maxLength={8}
              className="w-36"
              onChange={(event) => setGroupName(event.target.value.toUpperCase())}
            />
            {canWrite ? (
              <Button
                disabled={!groupGrade || !groupName.trim() || busy}
                onClick={() =>
                  run(async () => {
                    await managementApi.createClassGroup({
                      grade: groupGrade,
                      name: groupName.trim(),
                    })
                    setGroupName('')
                  }, 'Guruh qo’shildi')
                }
              >
                {t('actions.add')}
              </Button>
            ) : null}
          </div>

          {classGroups.length === 0 ? (
            <EmptyState title={t('register.noGroups')} description={t('register.noGroupsHint')} />
          ) : (
            <ul className="divide-y divide-ink-100 rounded-xl border border-ink-100">
              {classGroups.map((group) => (
                <li key={group.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
                  <span className="w-20 text-[15px] font-semibold text-ink-800">
                    {group.display_name}
                  </span>
                  <span className="text-sm text-ink-500">
                    {group.students_count} o'quvchi
                    {group.room ? ` · ${group.room}-xona` : ''}
                  </span>
                  {canWrite ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-auto text-red-600 hover:bg-red-500/15"
                      onClick={() => setPendingGroup(group)}
                    >
                      {t('actions.delete')}
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <ConfirmDelete
        open={Boolean(pendingGrade)}
        busy={busy}
        title={`${pendingGrade?.label ?? ''} o'chirilsinmi?`}
        description={`${pendingGrade?.class_groups_count ?? 0} guruh va ${pendingGrade?.students_count ?? 0} o'quvchi ham arxivlanadi.`}
        onClose={() => setPendingGrade(null)}
        onConfirm={() =>
          run(async () => {
            await managementApi.deleteGrade(pendingGrade!.id)
            setPendingGrade(null)
          }, 'Sinf o’chirildi')
        }
      />

      <ConfirmDelete
        open={Boolean(pendingGroup)}
        busy={busy}
        title={`${pendingGroup?.display_name ?? ''} o'chirilsinmi?`}
        description={`${pendingGroup?.students_count ?? 0} o'quvchi ham arxivlanadi va turniketdan olib tashlanadi.`}
        onClose={() => setPendingGroup(null)}
        onConfirm={() =>
          run(async () => {
            await managementApi.deleteClassGroup(pendingGroup!.id)
            setPendingGroup(null)
          }, 'Guruh o’chirildi')
        }
      />
    </div>
  )
}
