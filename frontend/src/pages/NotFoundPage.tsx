import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui'

export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <div className="grid min-h-dvh place-items-center bg-ink-50 px-6">
      <div className="text-center">
        <p className="text-6xl font-semibold tracking-tight text-ink-200">404</p>
        <h1 className="mt-3 text-xl font-semibold text-ink-900">{t('common.pageNotFound')}</h1>
        <p className="mt-1.5 text-sm text-ink-500">
          {t('common.pageNotFoundHint')}
        </p>
        <Link to="/" className="mt-6 inline-block">
          <Button>{t('common.backHome')}</Button>
        </Link>
      </div>
    </div>
  )
}
