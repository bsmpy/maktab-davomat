import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ApiError } from '@/api/errors'
import { cn } from '@/utils/cn'

import { Button } from './Button'
import { AlertIcon, InboxIcon, RefreshIcon } from './Icon'

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: {
  title: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center px-6 py-14 text-center', className)}>
      <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-ink-100 text-ink-400">
        {icon ?? <InboxIcon width={26} height={26} />}
      </div>
      <p className="text-[15px] font-semibold text-ink-700">{title}</p>
      {description ? <p className="mt-1.5 max-w-sm text-sm text-ink-500">{description}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  )
}

export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: ApiError | string
  onRetry?: () => void
  className?: string
}) {
  const { t } = useTranslation()
  const message = typeof error === 'string' ? error : error.message
  const isNetwork = typeof error !== 'string' && error.isNetworkError

  return (
    <div className={cn('flex flex-col items-center px-6 py-14 text-center', className)}>
      <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-red-500/15 text-red-500">
        <AlertIcon width={26} height={26} />
      </div>
      <p className="text-[15px] font-semibold text-ink-800">
        {isNetwork ? "Aloqa yo'q" : 'Xatolik yuz berdi'}
      </p>
      <p className="mt-1.5 max-w-sm text-sm text-ink-500">{message}</p>
      {onRetry ? (
        <Button
          variant="secondary"
          size="sm"
          className="mt-5"
          onClick={onRetry}
          leftIcon={<RefreshIcon width={16} height={16} />}
        >
          {t('common.retry')}
        </Button>
      ) : null}
    </div>
  )
}
