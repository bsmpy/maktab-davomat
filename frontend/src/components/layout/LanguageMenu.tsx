import { useTranslation } from 'react-i18next'

import { CheckIcon, ChevronDownIcon, GlobeIcon, Menu, MenuItem } from '@/components/ui'
import { SUPPORTED_LANGUAGES } from '@/i18n'
import { cn } from '@/utils/cn'

/**
 * The interface language.
 *
 * i18next was already configured with uz / ru / en and a localStorage detector,
 * so switching is `changeLanguage` — no reload, and the choice survives one.
 */
export function LanguageMenu() {
  const { t, i18n } = useTranslation()
  const current = i18n.resolvedLanguage ?? i18n.language

  return (
    <Menu
      label={t('common.language')}
      width="w-44"
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={id}
          aria-label={t('common.language')}
          title={t('common.language')}
          onClick={toggle}
          className="flex h-9 items-center gap-1.5 rounded-xl border border-ink-200 px-2.5 text-ink-600 transition hover:bg-ink-100 hover:text-ink-900"
        >
          <GlobeIcon width={18} height={18} />
          <span className="hidden text-xs font-semibold uppercase sm:block">{current}</span>
          <ChevronDownIcon
            width={14}
            height={14}
            className={cn('hidden text-ink-400 transition-transform sm:block', open && 'rotate-180')}
          />
        </button>
      )}
    >
      {({ close }) =>
        SUPPORTED_LANGUAGES.map((language) => (
          <MenuItem
            key={language.code}
            active={language.code === current}
            onSelect={() => {
              void i18n.changeLanguage(language.code)
              document.documentElement.setAttribute('lang', language.code)
              close()
            }}
            icon={
              language.code === current ? (
                <CheckIcon width={16} height={16} />
              ) : (
                <span className="w-4" />
              )
            }
          >
            {language.label}
          </MenuItem>
        ))
      }
    </Menu>
  )
}
