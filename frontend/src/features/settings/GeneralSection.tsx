import { Badge, EmptyState } from '@/components/ui'
import { useTranslation } from 'react-i18next'
import type { Integration, SettingsOverview } from '@/types/api'
import { cn } from '@/utils/cn'

import { StatusPill } from './StatusPill'
import { SETTINGS_ITEMS, type SettingsItem } from './settingsNav'

/**
 * "Umumiy" — what this account may open, and where every live integration
 * stands. It reads the overview endpoint the page already loads; nothing new
 * is fetched for it.
 */
export function GeneralSection({
  overview,
  integrations,
  onOpen,
}: {
  overview: SettingsOverview | null
  integrations: Map<string, Integration>
  onOpen: (id: string) => void
}) {
  const { t } = useTranslation()
  const connected = SETTINGS_ITEMS.filter((item) => item.kind)

  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-3 text-sm font-semibold text-ink-800">{t('settings.integrationsState')}</h3>
        <ul className="divide-y divide-ink-100 rounded-xl border border-ink-200/70">
          {connected.map((item) => {
            const integration = integrations.get(item.kind!)
            const Icon = item.icon
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onOpen(item.id)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-150 hover:bg-ink-50"
                >
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-ink-100 text-ink-600">
                    <Icon width={16} height={16} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-ink-800">
                      {t(item.labelKey)}
                    </span>
                    <span className="block truncate text-xs text-ink-500">
                      {integration?.is_enabled ? t('settings.onLabel') : t('settings.off')}
                    </span>
                  </span>
                  {integration ? <StatusPill status={integration.effective_status} /> : null}
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-semibold text-ink-800">{t('settings.sectionsOpenToYou')}</h3>
        {overview ? (
          <ul className="grid gap-2 sm:grid-cols-2">
            {overview.sections.map((section) => (
              <li
                key={section.key}
                className={cn(
                  'flex items-center justify-between gap-3 rounded-xl border px-4 py-3',
                  section.available
                    ? 'border-ink-200/70 bg-surface'
                    : 'border-ink-100 bg-ink-50/60',
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-ink-800">
                    {section.label}
                  </span>
                  {section.description ? (
                    <span className="block truncate text-xs text-ink-500">
                      {section.description}
                    </span>
                  ) : null}
                </span>
                <Badge
                  className={
                    section.available
                      ? 'bg-emerald-500/15 text-emerald-700 ring-1 ring-inset ring-emerald-600/20'
                      : 'bg-ink-100 text-ink-500 ring-1 ring-inset ring-ink-400/20'
                  }
                >
                  {section.available ? 'Ochiq' : 'Yopiq'}
                </Badge>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title={t('settings.noData')} />
        )}
      </section>
    </div>
  )
}

/**
 * A section whose backend does not exist yet.
 *
 * Shown as an honest placeholder rather than a form that pretends to save: a
 * settings screen that silently discards what you type is worse than one that
 * says it is not connected.
 */
export function PlaceholderSection({ item }: { item: SettingsItem }) {
  const { t } = useTranslation()
  const Icon = item.icon
  return (
    <EmptyState
      icon={<Icon width={26} height={26} />}
      title={t('settings.notWired')}
      description={t('settings.notWiredHint', { section: t(item.descriptionKey) })}
    />
  )
}
