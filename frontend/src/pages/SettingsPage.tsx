import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { settingsApi } from '@/api/settingsApi'
import { PositionsPanel } from '@/features/admin/PositionsPanel'
import {
  ParticlesSection,
  ThemesSection,
} from '@/features/settings/AppearanceSection'
import { FaceIdIntegration } from '@/features/settings/FaceIdIntegration'
import { PlaceholderSection } from '@/features/settings/GeneralSection'
import { SettingsSectionHeader, SettingsSidebar } from '@/features/settings/SettingsSidebar'
import { SmsIntegration } from '@/features/settings/SmsIntegration'
import { TelegramIntegration } from '@/features/settings/TelegramIntegration'
import { TerminalsIntegration } from '@/features/settings/TerminalsIntegration'
import {
  findSettingsItem,
  settingsGroupsFor,
  type SettingsItem,
} from '@/features/settings/settingsNav'
import { Card, EmptyState, ErrorState, LockIcon, Skeleton } from '@/components/ui'
import { useAuth } from '@/auth/permissions'
import { useAsyncData } from '@/hooks'
import type { Integration } from '@/types/api'

/**
 * Sozlamalar.
 *
 * A settings shell: its own scrolling menu on the left, a fixed-width working
 * area on the right so nothing shifts as you switch sections. The section is
 * held in `?bolim=`, so a section is linkable and survives a reload — and
 * switching never leaves the SPA.
 *
 * Who sees what: an ADMIN opens it for Mavzular and Zarrachalar, which are
 * about how the cabinet looks to everybody in the school. The integration
 * credentials — bot tokens, SMS logins, turnstile passwords — belong to the
 * platform rather than to the school, so only DEVELOPER and SUPER_ADMIN see
 * that group at all, and only DEVELOPER may save in it. The server enforces
 * every one of those; this is presentation, not protection.
 */
export function SettingsPage() {
  const { t } = useTranslation()
  const { activeRole, can } = useAuth()
  const [params, setParams] = useSearchParams()
  const [overrides, setOverrides] = useState<Record<string, Integration>>({})

  const canReadIntegrations = can('integrations.view')
  const overview = useAsyncData(() => settingsApi.overview(), [])
  // Nothing to fetch when the whole group is out of reach.
  const integrations = useAsyncData(() => settingsApi.integrations(), [], {
    enabled: canReadIntegrations,
  })

  // The menu this viewer gets, and the section inside it they asked for.
  const groups = settingsGroupsFor(can)
  const item = findSettingsItem(params.get('bolim'), groups)
  const readOnly = !can('integrations.manage')

  function open(id: string) {
    const merged = new URLSearchParams(params)
    merged.set('bolim', id)
    // Push rather than replace: every step the user takes is its own history
    // entry, so the browser's Back button undoes exactly one of them.
    setParams(merged)
  }

  function onSaved(next: Integration) {
    setOverrides((current) => ({ ...current, [next.kind]: next }))
  }

  if (overview.initialLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-96 w-full rounded-2xl" />
      </div>
    )
  }

  // A role that may not open Sozlamalar at all gets a 403 here. That is an
  // answer, not a failure: say so plainly instead of offering a retry button
  // that can only fail again.
  if (overview.error?.status === 403) {
    return <NoAccess role={activeRole} />
  }

  if (overview.error) {
    return (
      <Card>
        <ErrorState error={overview.error} onRetry={overview.reload} />
      </Card>
    )
  }

  if (!item) {
    return <NoAccess role={activeRole} />
  }

  const stored = integrations.data?.results ?? []
  const byKind = new Map<string, Integration>(stored.map((row) => [row.kind, row]))
  Object.values(overrides).forEach((row) => byKind.set(row.kind, row))

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('settings.title')}</h1>
        <p className="mt-1 text-sm text-ink-500">
          {t('settings.subtitle')}
        </p>
      </div>

      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        <SettingsSidebar
          active={item.id}
          groups={groups}
          onSelect={open}
          statusFor={(entry) => (entry.kind ? byKind.get(entry.kind) : undefined)}
        />

        {/* min-w-0 keeps a wide table inside this column instead of stretching it. */}
        <section className="card min-w-0 flex-1 p-5 sm:p-6">
          <SettingsSectionHeader item={item} />
          <div className="pt-5">
            <SectionBody
              item={item}
              integrations={byKind}
              loading={integrations.initialLoading}
              error={integrations.error}
              onRetry={integrations.reload}
              onSaved={onSaved}
              readOnly={readOnly}
            />
          </div>
        </section>
      </div>
    </div>
  )
}

function SectionBody({
  item,
  integrations,
  loading,
  error,
  onRetry,
  onSaved,
  readOnly,
}: {
  item: SettingsItem
  integrations: Map<string, Integration>
  loading: boolean
  error: unknown
  onRetry: () => void
  onSaved: (next: Integration) => void
  readOnly: boolean
}) {
  const { t } = useTranslation()
  // The register page that left the rail keeps working exactly as it did —
  // same panel, same permission checks inside it.
  if (item.id === 'lavozimlar') return <PositionsPanel />

  // Appearance is a preference of the person looking at the screen, so it has
  // no integration row behind it and no backend to wait for.
  if (item.id === 'mavzular') return <ThemesSection />
  if (item.id === 'zarrachalar') return <ParticlesSection />

  if (!item.kind) {
    return <PlaceholderSection item={item} />
  }

  if (loading) return <Skeleton className="h-80 w-full rounded-2xl" />
  if (error) return <ErrorState error={error as never} onRetry={onRetry} />

  const integration = integrations.get(item.kind)
  if (!integration) {
    return (
      <EmptyState
        title={t('settings.integrationMissing')}
        description={t('settings.integrationMissingHint')}
      />
    )
  }

  // Keyed by id: a different integration row remounts the form with fresh
  // state instead of being synced by an effect. The key is passed explicitly,
  // never spread — React reads it before props are applied.
  const props = { integration, onSaved, readOnly }

  switch (item.kind) {
    case 'TELEGRAM_BOT':
      return <TelegramIntegration key={integration.id} {...props} />
    case 'SMS_ESKIZ':
      return <SmsIntegration key={integration.id} {...props} />
    case 'FACE_ID':
      return <FaceIdIntegration key={integration.id} {...props} />
    default:
      return <TerminalsIntegration key={integration.id} {...props} />
  }
}

/** Shown to a role that Sozlamalar is not for. */
function NoAccess({ role }: { role?: string | null }) {
  const { t } = useTranslation()
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('settings.title')}</h1>
      <Card>
        <EmptyState
          icon={<LockIcon width={26} height={26} />}
          title={t('settings.noAccess')}
          description={`Bu bo'lim faqat DEVELOPER va SUPER_ADMIN rollari uchun. Sizning rolingiz: ${role ?? '—'}.`}
        />
      </Card>
    </div>
  )
}
