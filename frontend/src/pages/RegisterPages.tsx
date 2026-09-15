import { useTranslation } from 'react-i18next'

import { managementApi } from '@/api/managementApi'
import { ExportPanel } from '@/features/admin/ExportPanel'
import { SchedulePanel } from '@/features/admin/SchedulePanel'
import { PositionsPanel } from '@/features/admin/PositionsPanel'
import { SchoolPanel, SubjectsPanel, TeachersPanel } from '@/features/admin/SchoolPanel'
import { StaffPanel } from '@/features/admin/StaffPanel'
import { CuratorsPanel } from '@/features/management/CuratorsPanel'
import { GradesPanel } from '@/features/management/GradesPanel'
import { StudentsPanel } from '@/features/management/StudentsPanel'
import { UsersPanel } from '@/features/management/UsersPanel'
import { Card, ErrorState, LockIcon, Skeleton } from '@/components/ui'
import { usePermissions } from '@/auth/permissions'
import type { Permission } from '@/types/api'
import { useAsyncData } from '@/hooks'

/**
 * The frame every register page shares: a title, a read-only notice when the
 * role cannot write, and — for the pages that need it — the class-group list
 * they all read.
 *
 * There is no access check here any more. Each of these pages is declared in
 * the router with the permission it costs, so the gate is in one place instead
 * of being repeated per page and drifting; and the endpoints behind them
 * refuse the same thing again on their own authority.
 *
 * `write` is what *changing* anything on the page costs. A MODERATOR reads
 * every one of these sections and writes none of them, so saying so once at
 * the top is more honest than letting them press a button that answers 403.
 */
function RegisterPage({
  title,
  description,
  write,
  children,
}: {
  title: string
  description?: string
  write?: Permission
  children: React.ReactNode
}) {
  const { t } = useTranslation()
  const { can } = usePermissions()
  const readOnly = Boolean(write) && !can(write!)

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{title}</h1>
        {description ? <p className="mt-1 text-sm text-ink-500">{description}</p> : null}
      </div>

      {readOnly ? (
        <p className="flex items-center gap-2 rounded-xl bg-ink-50 px-4 py-3 text-sm text-ink-600">
          <LockIcon width={16} height={16} className="shrink-0 text-ink-400" />
          {t('access.readOnly')}
        </p>
      ) : null}

      {children}
    </div>
  )
}

/** The class groups the pupil and structure pages both need. */
function useClassGroups() {
  return useAsyncData(() => managementApi.classGroups(), [])
}

export function StudentsPage() {
  const { t } = useTranslation()
  const classGroups = useClassGroups()
  return (
    <RegisterPage
      title={t('nav.students')}
      write="students.manage"
      description={t('register.studentsHint')}
    >
      {classGroups.error ? (
        <Card>
          <ErrorState error={classGroups.error} onRetry={classGroups.reload} />
        </Card>
      ) : classGroups.initialLoading ? (
        <Skeleton className="h-96 w-full rounded-2xl" />
      ) : (
        <StudentsPanel classGroups={classGroups.data ?? []} />
      )}
    </RegisterPage>
  )
}

export function ClassesPage() {
  const { t } = useTranslation()
  const grades = useAsyncData(() => managementApi.grades(), [])
  const classGroups = useClassGroups()

  function reload() {
    grades.reload()
    classGroups.reload()
  }

  return (
    <RegisterPage
      title={t('nav.classes')}
      write="classes.manage"
      description={t('register.classesHint')}
    >
      {classGroups.error ? (
        <Card>
          <ErrorState error={classGroups.error} onRetry={reload} />
        </Card>
      ) : classGroups.initialLoading ? (
        <Skeleton className="h-96 w-full rounded-2xl" />
      ) : (
        <GradesPanel
          grades={grades.data ?? []}
          classGroups={classGroups.data ?? []}
          onChanged={reload}
        />
      )}
    </RegisterPage>
  )
}

export function SchoolSettingsPage() {
  const { t } = useTranslation()
  return (
    <RegisterPage
      title={t('nav.school')}
      write="school.manage"
      description={t('register.schoolHint')}
    >
      <SchoolPanel />
    </RegisterPage>
  )
}

export function SubjectsPage() {
  const { t } = useTranslation()
  return (
    <RegisterPage title={t('nav.subjects')} write="subjects.manage" description={t('register.subjectsHint')}>
      <SubjectsPanel />
    </RegisterPage>
  )
}

export function TeachersPage() {
  const { t } = useTranslation()
  return (
    <RegisterPage
      title={t('nav.teachers')}
      write="teachers.manage"
      description={t('register.teachersHint')}
    >
      <TeachersPanel />
    </RegisterPage>
  )
}

export function StaffPage() {
  const { t } = useTranslation()
  return (
    <RegisterPage
      title={t('staff.title')}
      write="staff.manage"
      description={t('staff.description')}
    >
      <StaffPanel />
    </RegisterPage>
  )
}

export function PositionsPage() {
  const { t } = useTranslation()
  return (
    <RegisterPage
      title={t('positions.title')}
      write="positions.manage"
      description={t('positions.description')}
    >
      <PositionsPanel />
    </RegisterPage>
  )
}

export function SchedulePage() {
  const { t } = useTranslation()
  return (
    <RegisterPage title={t('nav.schedule')} write="timetable.manage" description={t('register.scheduleHint')}>
      <SchedulePanel />
    </RegisterPage>
  )
}

export function ExportPage() {
  const { t } = useTranslation()
  return (
    <RegisterPage
      title={t('nav.export')}
      description={t('register.exportHint')}
    >
      <ExportPanel />
    </RegisterPage>
  )
}

export function UsersPage() {
  const { t } = useTranslation()
  return (
    <RegisterPage title={t('nav.users')} description={t('register.usersHint')}>
      <UsersPanel />
    </RegisterPage>
  )
}

export function CuratorsPage() {
  const { t } = useTranslation()
  return (
    <RegisterPage title={t('nav.curators')} write="curators.manage" description={t('curators.hint')}>
      <CuratorsPanel />
    </RegisterPage>
  )
}
