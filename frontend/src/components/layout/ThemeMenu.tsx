import { useTranslation } from 'react-i18next'

import { CheckIcon, ChevronDownIcon, Menu, MenuItem, PaletteIcon } from '@/components/ui'
import { availableThemes, useAppearanceStore } from '@/store/appearanceStore'
import { useThemeStore } from '@/store/themeStore'
import { cn } from '@/utils/cn'

/** Picks one of the five palettes. The choice is stored and applied at once. */
export function ThemeMenu() {
  const { t } = useTranslation()
  const theme = useThemeStore((state) => state.theme)
  const setTheme = useThemeStore((state) => state.setTheme)
  const multiTheme = useAppearanceStore((state) => state.multiTheme)
  const themes = availableThemes(multiTheme)

  return (
    <Menu
      label={t('common.theme')}
      width="w-48"
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={id}
          aria-label={t('common.theme')}
          title={t('common.theme')}
          onClick={toggle}
          className="flex h-9 items-center gap-1.5 rounded-xl border border-ink-200 px-2.5 text-ink-600 transition hover:bg-ink-100 hover:text-ink-900"
        >
          <PaletteIcon width={18} height={18} />
          <ChevronDownIcon
            width={14}
            height={14}
            className={cn('hidden text-ink-400 transition-transform sm:block', open && 'rotate-180')}
          />
        </button>
      )}
    >
      {({ close }) =>
        themes.map((item) => (
          <MenuItem
            key={item.value}
            active={item.value === theme}
            onSelect={() => {
              setTheme(item.value)
              close()
            }}
            icon={
              <span
                aria-hidden="true"
                className="h-4 w-4 shrink-0 rounded-full border border-ink-300"
                style={{ background: item.swatch }}
              />
            }
          >
            <span className="flex items-center justify-between gap-2">
              {t(item.labelKey)}
              {item.value === theme ? <CheckIcon width={14} height={14} /> : null}
            </span>
          </MenuItem>
        ))
      }
    </Menu>
  )
}
