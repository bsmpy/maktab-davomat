import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAuth } from '@/auth/permissions'
import { Button, Card, EmptyState, Skeleton, UserIcon } from '@/components/ui'
import { useChildStore } from '@/store/childStore'

/**
 * What a child-scoped page shows when there is no child to show.
 *
 * For a parent this is a transient loading state — their children arrive with
 * the shell. For staff it is the normal state of an empty register, and the
 * useful thing to say is where to go and fill it.
 */
export function NoChildState() {
  const { t } = useTranslation()
  const { can, isActing } = useAuth()
  const loading = useChildStore((state) => state.loading)
  const navigate = useNavigate()

  // A parent waiting for their children is the transient case; anybody else on
  // a child-scoped page is looking at a register that is simply empty.
  const isStaff = !isActing('OTA-ONA')
  const canAdminister = can('students.manage')

  if (loading || !isStaff) {
    return <Skeleton className="h-96 w-full rounded-2xl" />
  }

  return (
    <Card>
      <EmptyState
        icon={<UserIcon width={26} height={26} />}
        title={t('common.noPupilsYet')}
        description={
          canAdminister
            ? "Bu bo'lim tanlangan o'quvchi bo'yicha ma'lumot ko'rsatadi. Avval boshqaruv panelida o'quvchilarni qo'shing."
            : "Sizga hali biror sinf biriktirilmagan. Maktab ma'muriyatiga murojaat qiling."
        }
        action={
          canAdminister ? (
            <Button onClick={() => navigate('/oquvchilar')}>
              {t('common.adminPanel')}
            </Button>
          ) : undefined
        }
      />
    </Card>
  )
}
