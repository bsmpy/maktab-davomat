import { Card, CardBody, CardHeader, Toggle } from '@/components/ui'
import {
  BASE_THEMES,
  availableThemes,
  useAppearanceStore,
} from '@/store/appearanceStore'
import { useThemeStore } from '@/store/themeStore'
import { cn } from '@/utils/cn'
import { useTranslation } from 'react-i18next'

/** Shown under a switch that was refused or could not be saved. */
function WriteError() {
  const error = useAppearanceStore((state) => state.error)
  if (!error) return null
  return (
    <p role="alert" className="mt-3 text-sm text-red-600">
      {error}
    </p>
  )
}

/**
 * The palettes on offer — for everyone.
 *
 * This is not a per-browser preference: turning the extra palettes off takes
 * them away from every signed-in person on the installation. If one of the
 * extra palettes was in use at the time, that browser falls back rather than
 * sitting on a theme its own picker no longer lists.
 *
 * The palette a person then picks out of what is left is still their own.
 */
export function ThemesSection() {
  const { t } = useTranslation()
  const multiTheme = useAppearanceStore((state) => state.multiTheme)
  const setMultiTheme = useAppearanceStore((state) => state.setMultiTheme)
  const canEdit = useAppearanceStore((state) => state.canEdit)
  const theme = useThemeStore((state) => state.theme)
  const setTheme = useThemeStore((state) => state.setTheme)
  const offered = availableThemes(multiTheme)

  return (
    <Card>
      <CardHeader
        title={t('settings.themes')}
        description={t('settings.sharedSetting')}
      />
      <CardBody className="space-y-5">
        <label className="flex items-start justify-between gap-4">
          <span className="min-w-0">
            <span className="block text-[15px] font-medium text-ink-800">
              {t('settings.allThemes')}
            </span>
            <span className="mt-0.5 block text-sm text-ink-500">
              {t('settings.allThemesHint')}
            </span>
          </span>
          <Toggle
            checked={multiTheme}
            disabled={!canEdit}
            onChange={(value) => void setMultiTheme(value)}
          />
        </label>

        <WriteError />

        <div>
          {/* The palette itself is a personal choice out of what is offered, so
              this half stays live for everybody. */}
          <p className="label">{t('settings.currentTheme')}</p>
          <div className="flex flex-wrap gap-2">
            {offered.map((item) => (
              <button
                key={item.value}
                type="button"
                aria-pressed={item.value === theme}
                onClick={() => setTheme(item.value)}
                className={cn(
                  'flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition',
                  item.value === theme
                    ? 'border-brand-500 bg-brand-50 text-brand-700'
                    : 'border-ink-200 text-ink-600 hover:bg-ink-100',
                )}
              >
                <span
                  aria-hidden="true"
                  className="h-4 w-4 rounded-full border border-ink-300"
                  style={{ background: item.swatch }}
                />
                {t(item.labelKey)}
              </button>
            ))}
          </div>
          {!multiTheme ? (
            <p className="mt-2 text-xs text-ink-500">
              {t('settings.extraThemesOff', { count: BASE_THEMES.length })}
            </p>
          ) : null}
        </div>
      </CardBody>
    </Card>
  )
}

/** The drifting motes over the interface — on or off for the whole installation. */
export function ParticlesSection() {
  const { t } = useTranslation()
  const particles = useAppearanceStore((state) => state.particles)
  const setParticles = useAppearanceStore((state) => state.setParticles)
  const canEdit = useAppearanceStore((state) => state.canEdit)

  return (
    <Card>
      <CardHeader
        title={t('settings.particles')}
        description={t('settings.sharedSetting')}
      />
      <CardBody>
        <label className="flex items-start justify-between gap-4">
          <span className="min-w-0">
            <span className="block text-[15px] font-medium text-ink-800">
              {t('settings.showParticles')}
            </span>
            <span className="mt-0.5 block text-sm text-ink-500">
              {t('settings.particlesHint')}
            </span>
          </span>
          <Toggle
            checked={particles}
            disabled={!canEdit}
            onChange={(value) => void setParticles(value)}
          />
        </label>

        <WriteError />
      </CardBody>
    </Card>
  )
}
