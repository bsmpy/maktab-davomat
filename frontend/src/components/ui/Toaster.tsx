import { useToastStore, type ToastVariant } from '@/store/toastStore'
import { useTranslation } from 'react-i18next'
import { cn } from '@/utils/cn'

import { AlertIcon, CheckIcon, CloseIcon } from './Icon'

const VARIANT_STYLES: Record<ToastVariant, { ring: string; icon: string; badge: string }> = {
  success: {
    ring: 'ring-emerald-200',
    icon: 'text-emerald-600',
    badge: 'bg-emerald-500/15',
  },
  error: { ring: 'ring-red-200', icon: 'text-red-600', badge: 'bg-red-500/15' },
  info: { ring: 'ring-brand-200', icon: 'text-brand-600', badge: 'bg-brand-50' },
}

export function Toaster() {
  const { t } = useTranslation()
  const toasts = useToastStore((state) => state.toasts)
  const dismiss = useToastStore((state) => state.dismiss)

  if (toasts.length === 0) return null

  return (
    <div
      // On a phone the toasts stack above the tab bar rather than on top of
      // it; from `sm` they go back to the top-right corner.
      className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 pb-[calc(4.5rem+env(safe-area-inset-bottom))] sm:inset-x-auto sm:right-0 sm:top-0 sm:items-end sm:p-4 md:pb-4"
    >
      {toasts.map((item) => {
        const styles = VARIANT_STYLES[item.variant]
        return (
          <div
            key={item.id}
            role="status"
            className={cn(
              'pointer-events-auto flex w-full max-w-sm animate-slide-in-right items-start gap-3',
              'rounded-xl bg-surface p-3.5 shadow-pop ring-1',
              styles.ring,
            )}
          >
            <span className={cn('grid h-8 w-8 shrink-0 place-items-center rounded-lg', styles.badge, styles.icon)}>
              {item.variant === 'success' ? (
                <CheckIcon width={18} height={18} />
              ) : (
                <AlertIcon width={18} height={18} />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink-800">{item.title}</p>
              {item.description ? (
                <p className="mt-0.5 text-sm text-ink-500">{item.description}</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => dismiss(item.id)}
              className="-mr-1 rounded-lg p-1 text-ink-400 transition hover:bg-ink-100"
              aria-label={t('common.close')}
            >
              <CloseIcon width={16} height={16} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
