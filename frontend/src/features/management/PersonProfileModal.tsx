import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { adminApi } from '@/api/adminApi'
import { Avatar, ErrorState, Modal, Skeleton } from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { PersonProfile } from '@/types/api'
import { formatDuration } from '@/utils/attendance'
import { formatShortDate } from '@/utils/date'
import { localizedTitle } from '@/utils/localized'
import { phoneFromApi } from '@/utils/masks'

import { RoleBadges } from './RolePicker'

/** Which register row a card stands for. */
export interface ProfileTarget {
  kind: 'teacher' | 'staff'
  id: string
  /** Shown in the dialog title while the profile is still loading. */
  name?: string
}

/** One label with its value. A missing value says so instead of leaving a gap. */
function Field({ label, value, mono }: { label: string; value?: ReactNode; mono?: boolean }) {
  const empty = value === undefined || value === null || value === ''
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-ink-400">{label}</dt>
      <dd
        className={
          empty
            ? 'mt-0.5 text-sm text-ink-300'
            : `mt-0.5 break-words text-sm text-ink-800 ${mono ? 'font-mono tabular-nums' : ''}`
        }
      >
        {empty ? '—' : value}
      </dd>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3 border-t border-ink-100 pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-500">{title}</h3>
      {children}
    </section>
  )
}

/**
 * A person's whole record, opened from any card that stands for them.
 *
 * One dialog for a teacher, a curator and any other employee: they are the same
 * kind of record, and a curator *is* a teacher. The dialog asks the server for
 * the profile itself rather than reusing the card's data — the card carries a
 * summary, the profile carries the timetable, the curated groups and the week at
 * the turnstile, which no list needs.
 */
export function PersonProfileModal({
  target,
  onClose,
}: {
  target: ProfileTarget | null
  onClose: () => void
}) {
  const { t } = useTranslation()
  const profile = useAsyncData(
    () =>
      target!.kind === 'teacher'
        ? adminApi.teacherProfile(target!.id)
        : adminApi.staffProfile(target!.id),
    [target?.kind, target?.id],
    { enabled: Boolean(target) },
  )

  if (!target) return null
  const data = profile.data

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={data?.full_name ?? target.name ?? t('personProfile.title')}
      description={
        target.kind === 'teacher' ? t('personProfile.teacher') : t('personProfile.staff')
      }
    >
      {/* An error is the only thing that is an error. No data yet — including
          the render straight after a click, before the request has even
          started — is still loading, and says so. */}
      {profile.error ? (
        <ErrorState error={profile.error} onRetry={profile.reload} />
      ) : !data ? (
        <div className="space-y-4">
          <Skeleton className="h-24 w-full rounded-2xl" />
          <Skeleton className="h-40 w-full rounded-2xl" />
        </div>
      ) : (
        <ProfileBody data={data} />
      )}
    </Modal>
  )
}

function ProfileBody({ data }: { data: PersonProfile }) {
  const { t, i18n } = useTranslation()
  const account = data.account

  return (
    <div className="space-y-5">
      {/* Who: the face, the name, and every role the account holds. */}
      <div className="flex items-start gap-4">
        {data.photo ? (
          <img
            src={data.photo}
            alt=""
            className="h-24 w-24 shrink-0 rounded-2xl border border-ink-200 object-cover"
          />
        ) : (
          <Avatar name={data.full_name} size="lg" />
        )}
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-lg font-semibold leading-tight text-ink-900">{data.full_name}</p>
          <p className="text-sm text-ink-500">
            {data.position
              ? localizedTitle(data.position.titles, i18n.language)
              : data.kind === 'teacher'
                ? t('personProfile.teacher')
                : t('staff.noPosition')}
          </p>
          {account?.roles.length ? <RoleBadges roles={account.roles} /> : null}
          {!data.is_active ? (
            <p className="text-xs font-medium text-red-600">{t('users.disabled')}</p>
          ) : null}
        </div>
      </div>

      <Section title={t('personProfile.personal')}>
        <dl className="grid gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label={t('person.lastName')} value={data.last_name} />
          <Field label={t('person.firstName')} value={data.first_name} />
          <Field label={t('person.middleName')} value={data.middle_name} />
          <Field label={t('person.gender')} value={data.gender_label} />
          <Field
            label={t('person.birthDate')}
            value={data.birth_date ? formatShortDate(data.birth_date) : ''}
          />
          <Field label={t('person.passportId')} value={data.passport_id} mono />
          <Field label={t('person.jshshir')} value={data.jshshir || data.masked_jshshir} mono />
          <Field label={t('person.phone')} value={phoneFromApi(data.phone)} mono />
          <Field label={t('person.email')} value={data.email} />
        </dl>
      </Section>

      <Section title={t('personProfile.account')}>
        {account ? (
          <dl className="grid gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
            <Field label={t('person.login')} value={account.username} mono />
            <Field label={t('personProfile.activeRole')} value={account.active_role} mono />
            <Field
              label={t('personProfile.lastLogin')}
              value={
                account.last_login
                  ? formatShortDate(account.last_login)
                  : t('personProfile.neverLoggedIn')
              }
            />
            <Field
              label={t('personProfile.password')}
              value={
                account.must_change_password
                  ? t('users.passwordUnchanged')
                  : t('personProfile.passwordSet')
              }
            />
            <Field
              label={t('personProfile.accountCreated')}
              value={account.created_at ? formatShortDate(account.created_at) : ''}
            />
          </dl>
        ) : (
          <p className="text-sm text-ink-500">{t('staff.noAccount')}</p>
        )}
      </Section>

      {data.curator_groups.length ? (
        <Section title={t('personProfile.curatorOf')}>
          <ul className="flex flex-wrap gap-2">
            {data.curator_groups.map((group) => (
              <li
                key={group.id}
                className="rounded-xl bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700"
              >
                {group.display_name}
                <span className="ml-1.5 text-xs font-normal text-brand-600">
                  {group.students_count} {t('curators.pupils')}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {data.kind === 'teacher' ? (
        <Section
          title={`${t('personProfile.subjects')} · ${data.subjects_count}`}
        >
          {data.subjects.length ? (
            <ul className="grid gap-2 sm:grid-cols-2">
              {data.subjects.map((row) => (
                <li key={row.class_group} className="rounded-xl border border-ink-100 px-3 py-2">
                  <p className="text-sm font-semibold text-ink-800">{row.class_group}</p>
                  <p className="text-xs text-ink-500">{row.subjects.join(', ')}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-500">{t('personProfile.noSubjects')}</p>
          )}
        </Section>
      ) : null}

      {data.kind === 'teacher' ? (
        <Section
          title={`${t('nav.schedule')} · ${t('personProfile.lessonsPerWeek', {
            count: data.timetable.lessons_per_week,
          })}`}
        >
          {data.timetable.days.length ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.timetable.days.map((day) => (
                <div key={day.weekday} className="rounded-xl border border-ink-100">
                  <p className="border-b border-ink-100 px-3 py-1.5 text-xs font-semibold text-ink-600">
                    {day.label}
                    <span className="ml-1 font-normal text-ink-400">· {day.lessons.length}</span>
                  </p>
                  <ol className="divide-y divide-ink-50">
                    {day.lessons.map((lesson) => (
                      <li
                        key={`${lesson.start_time}-${lesson.class_group}`}
                        className="flex items-baseline gap-2 px-3 py-1.5 text-xs"
                      >
                        <span className="w-10 shrink-0 font-mono tabular-nums text-ink-400">
                          {lesson.start_time}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-ink-800">
                          {lesson.subject}
                        </span>
                        <span className="shrink-0 font-medium text-ink-600">
                          {lesson.class_group}
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-500">{t('personProfile.noTimetable')}</p>
          )}
        </Section>
      ) : null}

      {data.week ? (
        <Section title={t('personProfile.thisWeek')}>
          <dl className="grid gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label={t('attendance.schoolDays')} value={String(data.week.school_days)} />
            <Field label={t('attendance.wasInside')} value={String(data.week.days_present)} />
            <Field label={t('attendance.daysLate')} value={String(data.week.late_days)} />
            <Field
              label={t('teacher.activeAtSchool')}
              value={formatDuration(data.week.active_minutes)}
            />
          </dl>
        </Section>
      ) : null}
    </div>
  )
}
