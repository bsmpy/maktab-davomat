import { cn } from '@/utils/cn'
import { useTranslation } from 'react-i18next'

const SIZES = {
  sm: 'h-7 w-7',
  md: 'h-9 w-9',
  lg: 'h-12 w-12',
  xl: 'h-16 w-16',
} as const

/**
 * The single place the mark is rendered. `public/logo.png` is served from the
 * site root, so it works identically in dev, in the production build and
 * behind the reverse proxy.
 */
export function Logo({
  size = 'md',
  className,
}: {
  size?: keyof typeof SIZES
  className?: string
}) {
  return (
    <img
      src="/logo.png"
      alt=""
      aria-hidden="true"
      width={64}
      height={64}
      className={cn('shrink-0 select-none object-contain', SIZES[size], className)}
      draggable={false}
    />
  )
}

/** Mark + wordmark, used in the sidebar and on the auth screens. */
export function LogoLockup({
  size = 'md',
  subtitle,
  className,
}: {
  size?: keyof typeof SIZES
  subtitle?: string
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <span className={cn('flex items-center gap-2.5', className)}>
      <Logo size={size} />
      <span className="min-w-0">
        <span className="block truncate text-[15px] font-semibold tracking-tight text-brand-700">
          {t('common.appName')}
        </span>
        {subtitle ? (
          <span className="block truncate text-xs text-ink-500">{subtitle}</span>
        ) : null}
      </span>
    </span>
  )
}
