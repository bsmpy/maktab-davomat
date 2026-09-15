import { useTranslation } from 'react-i18next'

import type { Integration } from '@/types/api'
import { cn } from '@/utils/cn'

import { SETTINGS_GROUPS, type SettingsGroup, type SettingsItem } from './settingsNav'

/**
 * The settings page's own menu.
 *
 * Deliberately separate from the cabinet's sidebar: this one scrolls on its
 * own, keeps a fixed width so the working area never shifts as you move
 * between sections, and collapses to a horizontal rail on narrow screens.
 */
export function SettingsSidebar({
  active,
  onSelect,
  statusFor,
  groups = SETTINGS_GROUPS,
}: {
  active: string
  onSelect: (id: string) => void
  /** Live status of the integration behind an item, when it has one. */
  statusFor?: (item: SettingsItem) => Integration | undefined
  /** The groups this viewer may open; the caller filters by permission. */
  groups?: SettingsGroup[]
}) {
  const { t } = useTranslation()
  return (
    <nav
      aria-label={t('settings.sectionsAria')}
      className={cn(
        'card p-2',
        // Narrow screens: one scrolling row above the content, snapping so a
        // half-cut item never ends up as the thing you are looking at.
        'rail-x gap-1 lg:block lg:overflow-y-auto',
        'lg:max-h-[calc(100dvh-9rem)] lg:w-[232px] lg:shrink-0 lg:space-y-4 lg:overflow-x-visible',
      )}
    >
      {groups.map((group) => (
        <div key={group.titleKey} className="shrink-0">
          <p className="hidden px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400 lg:block">
            {t(group.titleKey)}
          </p>

          <ul className="flex gap-1 lg:block lg:space-y-0.5">
            {group.items.map((item) => {
              const selected = item.id === active
              const integration = statusFor?.(item)
              const Icon = item.icon

              return (
                <li key={item.id}>
                  <button
                    type="button"
                    aria-current={selected ? 'page' : undefined}
                    onClick={() => onSelect(item.id)}
                    className={cn(
                      'group relative flex min-h-[40px] w-full items-center gap-2.5 whitespace-nowrap rounded-lg py-1.5 pl-3 pr-2.5',
                      'text-left text-[13px] font-medium transition-colors duration-150',
                      selected
                        ? 'bg-brand-50 text-brand-700'
                        : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900',
                    )}
                  >
                    {/* The blue rule that marks the active row. */}
                    <span
                      aria-hidden
                      className={cn(
                        'absolute left-0 top-1/2 w-[3px] -translate-y-1/2 rounded-r-full bg-brand-600 transition-all duration-200',
                        selected ? 'h-5 opacity-100' : 'h-0 opacity-0',
                      )}
                    />

                    <span
                      className={cn(
                        'grid h-6 w-6 shrink-0 place-items-center rounded-md transition-colors duration-150',
                        selected
                          ? 'bg-brand-600 text-onbrand'
                          : 'bg-ink-100 text-ink-500 group-hover:bg-ink-200 group-hover:text-ink-700',
                      )}
                    >
                      <Icon width={14} height={14} />
                    </span>

                    <span className="min-w-0 flex-1 truncate">{t(item.labelKey)}</span>

                    {integration?.is_enabled ? (
                      <span
                        aria-hidden
                        title={t('settings.onLabel')}
                        className={cn(
                          'h-1.5 w-1.5 shrink-0 rounded-full',
                          integration.effective_status === 'ERROR'
                            ? 'bg-red-500'
                            : 'bg-emerald-500',
                        )}
                      />
                    ) : null}

                    {item.ready === false ? (
                      <span className="hidden shrink-0 text-[10px] font-normal text-ink-400 lg:inline">
                        {t('settings.soon')}
                      </span>
                    ) : null}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </nav>
  )
}

/** Title strip above the working area: the section's own icon and name. */
export function SettingsSectionHeader({ item }: { item: SettingsItem }) {
  const { t } = useTranslation()
  const Icon = item.icon
  return (
    <header className="border-b border-ink-200/70 pb-4">
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600">
          <Icon width={18} height={18} />
        </span>
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold tracking-tight text-ink-900">
            {t(item.labelKey)}
          </h2>
          <p className="truncate text-sm text-ink-500">{t(item.descriptionKey)}</p>
        </div>
      </div>
    </header>
  )
}
