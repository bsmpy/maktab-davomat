import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ArrowLeftIcon } from '@/components/ui'

/**
 * Steps back through the router's own history.
 *
 * Not a link to a fixed URL: the cabinet's drill-downs live in query parameters,
 * so "back" has to mean whatever the user actually did last.
 */
export function NavBackButton() {
  const navigate = useNavigate()
  const { t } = useTranslation()

  return (
    <button
      type="button"
      aria-label={t('common.back')}
      title={t('common.back')}
      onClick={() => navigate(-1)}
      className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-ink-200 text-ink-600 transition hover:bg-ink-100 hover:text-ink-900 active:bg-ink-200"
    >
      <ArrowLeftIcon width={18} height={18} />
    </button>
  )
}
