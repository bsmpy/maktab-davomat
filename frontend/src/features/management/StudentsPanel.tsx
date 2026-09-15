import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { managementApi } from '@/api/managementApi'
import { toApiError } from '@/api/errors'
import {
  Avatar,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Modal,
  SkeletonCards,
} from '@/components/ui'
import { usePermissions } from '@/auth/permissions'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { ManagedClassGroup, ManagedStudent } from '@/types/api'

import { StudentFormModal } from './StudentFormModal'

/** Whether the pupil's face actually reached the turnstiles. */
function TerminalBadge({ student }: { student: ManagedStudent }) {
  const { t } = useTranslation()
  const terminal = student.terminal
  if (!terminal) {
    return <Badge className="bg-ink-100 text-ink-600 ring-ink-400/20">{t('register.notOnTerminal')}</Badge>
  }
  if (terminal.sync_state === 'SYNCED' && terminal.has_face) {
    return (
      <Badge className="bg-emerald-500/15 text-emerald-700 ring-emerald-600/20">
        Turniketda · {terminal.terminals} qurilma
      </Badge>
    )
  }
  if (terminal.sync_state === 'FAILED') {
    return <Badge className="bg-red-500/15 text-red-700 ring-red-600/20">{t('register.uploadFailed')}</Badge>
  }
  return <Badge className="bg-amber-500/15 text-amber-700 ring-amber-600/20">{t('register.queued')}</Badge>
}

export function StudentsPanel({ classGroups }: { classGroups: ManagedClassGroup[] }) {
  const { t } = useTranslation()
  // A role that may only read this register gets no button that would 403.
  const canWrite = usePermissions().can('students.manage')
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<ManagedStudent | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<ManagedStudent | null>(null)
  const [busy, setBusy] = useState(false)

  const students = useAsyncData(() => managementApi.students({ page }), [page])

  function openAdd() {
    setEditing(null)
    setFormOpen(true)
  }

  function openEdit(student: ManagedStudent) {
    setEditing(student)
    setFormOpen(true)
  }

  async function confirmDelete() {
    if (!pendingDelete) return
    setBusy(true)
    try {
      await managementApi.deleteStudent(pendingDelete.id)
      toast.success("O'quvchi o'chirildi", 'Turniketdan ham olib tashlandi.')
      setPendingDelete(null)
      students.reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  const data = students.data

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={t('nav.students')}
          description={t('register.studentsSubtitle')}
          action={
            canWrite ? <Button onClick={openAdd}>{t('student.addStudent')}</Button> : undefined
          }
        />
        {students.initialLoading ? (
          <CardBody>
            <SkeletonCards />
          </CardBody>
        ) : students.error ? (
          <ErrorState error={students.error} onRetry={students.reload} />
        ) : !data || data.results.length === 0 ? (
          <EmptyState
            title={t('register.noStudents')}
            description={t('register.noStudentsHint')}
          />
        ) : (
          <CardBody className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {data.results.map((student) => (
              <article
                key={student.id}
                className="flex flex-col rounded-2xl border border-ink-200 bg-surface p-4"
              >
                <div className="flex items-center gap-3">
                  <Avatar
                    name={student.full_name}
                    initials={student.initials}
                    src={student.photo ?? undefined}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[15px] font-medium text-ink-900">
                      {student.full_name}
                    </p>
                    <p className="truncate text-xs text-ink-500">{student.class_group}</p>
                  </div>
                </div>

                <p className="mt-3 line-clamp-2 min-h-[2.5rem] text-xs text-ink-500">
                  {student.guardians.length > 0
                    ? student.guardians
                        .map((guardian) => `${guardian.relation_label}: ${guardian.full_name}`)
                        .join(', ')
                    : "Yaqini qo'shilmagan"}
                </p>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {student.registered_guardians > 0 ? (
                    <Badge className="bg-brand-500/15 text-brand-700 ring-brand-600/20">
                      {student.registered_guardians} ta yaqini ro'yxatda
                    </Badge>
                  ) : (
                    <Badge className="bg-ink-100 text-ink-600 ring-ink-400/20">
                      {t('register.guardianNotRegistered')}
                    </Badge>
                  )}
                  <TerminalBadge student={student} />
                </div>

                {canWrite ? (
                  <div className="mt-4 flex items-center gap-1">
                    <Button variant="secondary" size="sm" onClick={() => openEdit(student)}>
                      {t('actions.edit')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600 hover:bg-red-500/15"
                      onClick={() => setPendingDelete(student)}
                    >
                      {t('actions.delete')}
                    </Button>
                  </div>
                ) : null}
              </article>
            ))}
          </CardBody>
        )}

        {data && data.total_pages > 1 ? (
          <CardBody className="flex items-center justify-between border-t border-ink-100">
            <span className="text-sm text-ink-500">
              {data.count} ta o'quvchi · {data.page}/{data.total_pages}-sahifa
            </span>
            <div className="flex gap-1">
              <Button
                variant="secondary"
                size="sm"
                disabled={!data.previous}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                {t('register.previous')}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={!data.next}
                onClick={() => setPage((value) => value + 1)}
              >
                {t('register.next')}
              </Button>
            </div>
          </CardBody>
        ) : null}
      </Card>

      {formOpen ? (
        <StudentFormModal
          key={editing?.id ?? 'new'}
          student={editing}
          classGroups={classGroups}
          onClose={() => setFormOpen(false)}
          onSaved={students.reload}
        />
      ) : null}

      <Modal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        size="sm"
        title={`${pendingDelete?.full_name ?? ''} o'chirilsinmi?`}
        description={t('register.archiveWarning')}
        footer={
          <>
            <Button variant="secondary" onClick={() => setPendingDelete(null)} disabled={busy}>
              {t('actions.cancel')}
            </Button>
            <Button variant="danger" onClick={confirmDelete} loading={busy}>
              {t('actions.delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-600">
          {t('register.historyKept')}
        </p>
      </Modal>
    </div>
  )
}
