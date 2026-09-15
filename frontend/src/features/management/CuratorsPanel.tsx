import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { curatorApi } from '@/api/managementApi'
import { toApiError } from '@/api/errors'
import { usePermissions } from '@/auth/permissions'
import {
  Avatar,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Modal,
  Select,
  SkeletonRows,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { CuratorAssignment } from '@/types/api'

import { PersonProfileModal, type ProfileTarget } from './PersonProfileModal'
import { stopCard } from './cardActions'
import { ProfileCard } from './ProfileCard'
import { RoleBadges } from './RolePicker'

/**
 * Kuratorlar — pick a person, pick a class group, done.
 *
 * The role is not a separate step: assigning a group grants CURATOR, and
 * removing somebody's last group takes it back. That is the server's rule, not
 * this panel's, which is why nothing here touches roles directly.
 */
export function CuratorsPanel() {
  const { t } = useTranslation()
  const { can } = usePermissions()
  const section = useAsyncData(() => curatorApi.list(), [])

  const [formOpen, setFormOpen] = useState(false)
  const [person, setPerson] = useState('')
  const [group, setGroup] = useState('')
  const [busy, setBusy] = useState(false)
  //: The link being moved to another group, and the link being removed.
  const [moving, setMoving] = useState<CuratorAssignment | null>(null)
  const [moveTarget, setMoveTarget] = useState('')
  const [removing, setRemoving] = useState<CuratorAssignment | null>(null)
  //: Whose profile is open, when a curator card has been pressed.
  const [profile, setProfile] = useState<ProfileTarget | null>(null)

  const data = section.data
  const rows = data?.results ?? []
  const groups = data?.class_groups ?? []
  const candidates = data?.candidates ?? []
  const canManage = can('curators.manage')

  function startAdd() {
    setPerson(candidates[0] ? String(candidates[0].id) : '')
    setGroup(groups[0]?.id ?? '')
    setFormOpen(true)
  }

  async function assign() {
    if (!person || !group) return
    setBusy(true)
    try {
      await curatorApi.assign(Number(person), group)
      toast.success(t('curators.assigned'))
      setFormOpen(false)
      section.reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  async function move() {
    if (!moving || !moveTarget) return
    setBusy(true)
    try {
      await curatorApi.changeGroup(moving.id, moveTarget)
      toast.success(t('curators.groupChanged'))
      setMoving(null)
      section.reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!removing) return
    setBusy(true)
    try {
      const result = await curatorApi.remove(removing.id)
      toast.success(
        t('curators.removed'),
        result.role_revoked ? t('curators.roleRevoked') : undefined,
      )
      setRemoving(null)
      section.reload()
    } catch (error) {
      toast.error(t('register.actionFailed'), toApiError(error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={t('nav.curators')}
          description={t('curators.hint')}
          action={
            canManage ? (
              <Button onClick={startAdd} disabled={!candidates.length || !groups.length}>
                + {t('curators.assign')}
              </Button>
            ) : undefined
          }
        />

        {section.initialLoading ? (
          <SkeletonRows count={4} />
        ) : section.error ? (
          <ErrorState error={section.error} onRetry={section.reload} />
        ) : rows.length === 0 ? (
          <CardBody>
            <EmptyState title={t('curators.empty')} description={t('curators.emptyHint')} />
          </CardBody>
        ) : (
          <CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {rows.map((row) => {
              const target: ProfileTarget | null = row.teacher_id
                ? { kind: 'teacher', id: row.teacher_id, name: row.full_name }
                : row.staff_id
                  ? { kind: 'staff', id: row.staff_id, name: row.full_name }
                  : null
              return (
                <ProfileCard
                  key={row.id}
                  label={t('personProfile.open', { name: row.full_name })}
                  onOpen={() => target && setProfile(target)}
                >
                  <div className="flex items-start gap-3">
                    <Avatar name={row.full_name} src={row.photo ?? undefined} size="lg" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[15px] font-semibold text-ink-900">
                        {row.full_name}
                      </p>
                      <p className="truncate text-xs text-ink-500">{row.username}</p>
                      {row.roles?.length ? (
                        <div className="mt-1.5">
                          <RoleBadges roles={row.roles} />
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div className="mt-3 flex items-baseline justify-between gap-2 rounded-xl bg-brand-50 px-3 py-2">
                    <span className="text-lg font-semibold text-brand-700">
                      {row.class_group_name}
                    </span>
                    <span className="text-xs text-brand-600">
                      {row.students_count} {t('curators.pupils')}
                    </span>
                  </div>

                  {canManage ? (
                    <div className="mt-auto flex flex-wrap justify-end gap-1 pt-3" onClick={stopCard}>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setMoveTarget(row.class_group)
                          setMoving(row)
                        }}
                      >
                        {t('curators.changeGroup')}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:bg-red-500/15"
                        onClick={() => setRemoving(row)}
                      >
                        {t('actions.delete')}
                      </Button>
                    </div>
                  ) : null}
                </ProfileCard>
              )
            })}
          </CardBody>
        )}
      </Card>

      <PersonProfileModal target={profile} onClose={() => setProfile(null)} />

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        size="sm"
        title={t('curators.assign')}
        description={t('curators.assignHint')}
        footer={
          <>
            <Button variant="secondary" onClick={() => setFormOpen(false)} disabled={busy}>
              {t('actions.cancel')}
            </Button>
            <Button onClick={assign} loading={busy} disabled={!person || !group}>
              {t('actions.save')}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Select
            label={t('curators.person')}
            value={person}
            onChange={(event) => setPerson(event.target.value)}
          >
            {candidates.map((row) => (
              <option key={row.id} value={row.id}>
                {row.full_name} · {row.roles.join(', ')}
              </option>
            ))}
          </Select>
          <Select
            label={t('curators.group')}
            value={group}
            onChange={(event) => setGroup(event.target.value)}
          >
            {groups.map((row) => (
              <option key={row.id} value={row.id}>
                {row.display_name}
              </option>
            ))}
          </Select>
        </div>
      </Modal>

      <Modal
        open={Boolean(moving)}
        onClose={() => setMoving(null)}
        size="sm"
        title={t('curators.changeGroup')}
        description={moving?.full_name}
        footer={
          <>
            <Button variant="secondary" onClick={() => setMoving(null)} disabled={busy}>
              {t('actions.cancel')}
            </Button>
            <Button onClick={move} loading={busy}>
              {t('actions.save')}
            </Button>
          </>
        }
      >
        <Select
          label={t('curators.group')}
          value={moveTarget}
          onChange={(event) => setMoveTarget(event.target.value)}
        >
          {groups.map((row) => (
            <option key={row.id} value={row.id}>
              {row.display_name}
            </option>
          ))}
        </Select>
      </Modal>

      <Modal
        open={Boolean(removing)}
        onClose={() => setRemoving(null)}
        size="sm"
        title={t('curators.confirmRemove')}
        description={`${removing?.full_name ?? ''} · ${removing?.class_group_name ?? ''}`}
        footer={
          <>
            <Button variant="secondary" onClick={() => setRemoving(null)} disabled={busy}>
              {t('actions.cancel')}
            </Button>
            <Button onClick={remove} loading={busy}>
              {t('actions.delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-600">{t('curators.removeHint')}</p>
      </Modal>
    </div>
  )
}
