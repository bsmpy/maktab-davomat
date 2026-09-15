import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { notificationApi } from '@/api/notificationApi'
import {
  BellIcon,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  SegmentedControl,
  SkeletonRows,
} from '@/components/ui'
import { useAsyncData } from '@/hooks'
import { toast } from '@/store/toastStore'
import type { Notification } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatRelative } from '@/utils/date'

const FILTERS = [
  { value: 'all', label: 'Barchasi' },
  { value: 'unread', label: "O'qilmagan" },
] as const

type Filter = (typeof FILTERS)[number]['value']

const TYPE_ICON: Record<string, string> = {
  ATTENDANCE_ABSENT: '❌',
  ATTENDANCE_LATE: '🟡',
  ABSENCE_REASON_APPROVED: '✅',
  ABSENCE_REASON_REJECTED: '⚠️',
  ANNOUNCEMENT: '📣',
  DAILY_SUMMARY: '📊',
  SYSTEM: '🔔',
}

export function NotificationsPage() {
  const { t } = useTranslation()
  const [filter, setFilter] = useState<Filter>('all')
  const [busy, setBusy] = useState(false)

  const list = useAsyncData(
    () => notificationApi.list(filter === 'unread' ? { is_read: false } : undefined),
    [filter],
  )

  async function markOne(notification: Notification) {
    if (notification.is_read) return
    try {
      await notificationApi.markAsRead([notification.id])
      list.reload()
    } catch {
      toast.error(t('common.error'), "Belgilab bo'lmadi.")
    }
  }

  async function markAll() {
    setBusy(true)
    try {
      const updated = await notificationApi.markAllAsRead()
      toast.success(t('notifications.done'), `${updated} ta bildirishnoma o'qilgan deb belgilandi.`)
      list.reload()
    } catch {
      toast.error(t('common.error'), "Belgilab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  const unreadCount = list.data?.unread_count ?? 0

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{t('notifications.title')}</h1>
        {unreadCount > 0 ? (
          <Button variant="secondary" size="sm" loading={busy} onClick={() => void markAll()}>
            {t('notifications.markAll')}
          </Button>
        ) : null}
      </div>

      <SegmentedControl segments={[...FILTERS]} value={filter} onChange={setFilter} />

      <Card>
        <CardHeader
          title={filter === 'unread' ? "O'qilmagan" : 'Barcha bildirishnomalar'}
          description={
            list.data ? `${list.data.count} ta · ${unreadCount} ta o'qilmagan` : undefined
          }
        />

        {list.initialLoading ? (
          <SkeletonRows count={5} />
        ) : list.error ? (
          <ErrorState error={list.error} onRetry={list.reload} />
        ) : (list.data?.results.length ?? 0) === 0 ? (
          <EmptyState
            icon={<BellIcon width={26} height={26} />}
            title={filter === 'unread' ? "O'qilmagan bildirishnoma yo'q" : 'Bildirishnomalar yo\'q'}
            description={t('notifications.hint')}
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {list.data!.results.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => void markOne(item)}
                  className={cn(
                    'flex w-full items-start gap-3.5 px-5 py-4 text-left transition hover:bg-ink-50',
                    !item.is_read && 'bg-brand-50/40',
                  )}
                >
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-surface text-base ring-1 ring-inset ring-ink-200">
                    {TYPE_ICON[item.type] ?? '🔔'}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start gap-2">
                      <p
                        className={cn(
                          'flex-1 text-[15px] text-ink-800',
                          item.is_read ? 'font-medium' : 'font-semibold',
                        )}
                      >
                        {item.title}
                      </p>
                      {!item.is_read ? (
                        <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand-500" />
                      ) : null}
                    </div>
                    <p className="mt-0.5 whitespace-pre-line text-sm text-ink-600">
                      {item.message}
                    </p>
                    <p className="mt-1.5 text-xs text-ink-400">
                      {formatRelative(item.created_at)}
                      {item.student_name ? ` · ${item.student_name}` : ''}
                      {item.student_class ? ` (${item.student_class})` : ''}
                    </p>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
