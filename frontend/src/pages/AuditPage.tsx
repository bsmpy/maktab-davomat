import { AuditPanel } from '@/features/admin/AuditPanel'
import { useTranslation } from 'react-i18next'
import { Card, EmptyState, LockIcon } from '@/components/ui'
import { useAuthStore } from '@/store/authStore'

/** The audit trail. Kept reachable by URL, out of the menu by design. */
export function AuditPage() {
  const { t } = useTranslation()
  const role = useAuthStore((state) => state.user?.role)

  if (role !== 'DEVELOPER' && role !== 'SUPER_ADMIN') {
    return (
      <Card>
        <EmptyState
          icon={<LockIcon width={28} height={28} />}
          title={t('register.noAccess')}
          description={t('common.auditForOwners')}
        />
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('nav.audit')}</h1>
        <p className="mt-1 text-sm text-ink-500">{t('common.whoDidWhat')}</p>
      </div>
      <AuditPanel />
    </div>
  )
}
