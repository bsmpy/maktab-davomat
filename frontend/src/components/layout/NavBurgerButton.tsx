import { useTranslation } from 'react-i18next'

import { CloseIcon, MenuIcon } from '@/components/ui'
import { cn } from '@/utils/cn'

/** Opens and closes the sidebar. On desktop the rail is always there, so this
 *  collapses it instead of overlaying a drawer. */
export function NavBurgerButton({
  open,
  onToggle,
}: {
  open: boolean
  onToggle: () => void
}) {
  const { t } = useTranslation()
  const label = open ? t('common.closeMenu') : t('common.openMenu')

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-expanded={open}
      aria-controls="cabinet-sidebar"
      onClick={onToggle}
      className={cn(
        'grid h-9 w-9 shrink-0 place-items-center rounded-xl border transition',
        open
          ? 'border-brand-200 bg-brand-50 text-brand-700'
          : 'border-ink-200 text-ink-600 hover:bg-ink-100 hover:text-ink-900 active:bg-ink-200',
      )}
    >
      {open ? <CloseIcon width={18} height={18} /> : <MenuIcon width={18} height={18} />}
    </button>
  )
}
