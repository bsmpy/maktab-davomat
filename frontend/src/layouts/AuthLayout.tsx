import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Logo } from '@/components/ui'
import { config } from '@/config'

/** Centered card shell used by login / registration / password reset. */
export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
  wide = false,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-dvh flex-col bg-ink-50">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-brand-50 to-transparent" />

      <div
        className="relative flex flex-1 items-center justify-center px-4 py-8 sm:px-6 sm:py-10"
        // A notched phone in landscape puts the card under the cutout otherwise.
        style={{
          paddingTop: 'max(2rem, env(safe-area-inset-top))',
          paddingBottom: 'max(2rem, env(safe-area-inset-bottom))',
        }}
      >
        <div className={wide ? 'w-full max-w-2xl' : 'w-full max-w-md'}>
          <div className="mb-7 flex flex-col items-center text-center">
            <Logo size="xl" className="mb-4" />
            <h1 className="text-[22px] font-semibold tracking-tight text-ink-900">{title}</h1>
            {subtitle ? <p className="mt-1.5 text-sm text-ink-500">{subtitle}</p> : null}
          </div>

          <div className="card p-6 sm:p-7">{children}</div>

          {footer ? <div className="mt-5 text-center text-sm text-ink-500">{footer}</div> : null}

          <p className="mt-8 text-center text-xs text-ink-400">
            {config.appName} · {t('auth.tagline')}
          </p>
        </div>
      </div>
    </div>
  )
}
