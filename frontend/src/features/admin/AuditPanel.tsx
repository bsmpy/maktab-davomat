import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { adminApi } from '@/api/adminApi'
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  Select,
  SkeletonRows,
} from '@/components/ui'
import { useAsyncData, useDebouncedValue } from '@/hooks'
import { cn } from '@/utils/cn'

/** Actions worth colouring: a failed login is not the same as a page view. */
const ACTION_TONE: Record<string, string> = {
  LOGIN_FAILED: 'bg-red-500/15 text-red-700 ring-red-600/20',
  USER_PASSWORD_RESET: 'bg-amber-500/15 text-amber-700 ring-amber-600/20',
  USER_CREATE: 'bg-violet-500/15 text-violet-700 ring-violet-600/20',
  STUDENT_DELETE: 'bg-red-500/15 text-red-700 ring-red-600/20',
  SCHOOL_STRUCTURE_CHANGE: 'bg-brand-50 text-brand-700 ring-brand-600/20',
}

function timestamp(value: string): string {
  return new Date(value).toLocaleString('uz-UZ', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * The audit trail.
 *
 * Payloads are scrubbed before they are stored — passwords, OTP codes, JWTs and
 * JSHSHIR never reach this table — so what is shown here is safe to read, but
 * it still names people and what they did, which is why only the top two roles
 * can open it.
 */
export function AuditPanel() {
  const { t } = useTranslation()
  const [action, setAction] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<string | null>(null)

  const debouncedQuery = useDebouncedValue(query, 300)
  const entries = useAsyncData(
    () =>
      adminApi.audit({
        action: action || undefined,
        q: debouncedQuery || undefined,
        page,
      }),
    [action, debouncedQuery, page],
  )

  const data = entries.data

  return (
    <Card>
      <CardHeader
        title={t('nav.audit')}
        description={t('register.auditHint')}
      />
      <CardBody className="flex flex-wrap items-end gap-3">
        <Select
          label={t('register.action')}
          value={action}
          className="w-full sm:w-64"
          onChange={(event) => {
            setAction(event.target.value)
            setPage(1)
          }}
        >
          <option value="">{t('register.all')}</option>
          {(data?.actions ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        <Input
          label={t('profile.login')}
          value={query}
          placeholder={t('register.user')}
          className="w-full sm:w-52"
          onChange={(event) => {
            setQuery(event.target.value)
            setPage(1)
          }}
        />
      </CardBody>

      {entries.initialLoading ? (
        <SkeletonRows count={8} />
      ) : entries.error ? (
        <ErrorState error={entries.error} onRetry={entries.reload} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState title={t('register.noEntries')} description={t('register.noEntriesHint')} />
      ) : (
        <ul className="divide-y divide-ink-100 border-t border-ink-100">
          {data.results.map((entry) => (
            <li key={entry.id} className="px-5 py-3">
              <button
                type="button"
                className="flex w-full flex-wrap items-center gap-3 text-left"
                onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
              >
                <span className="w-36 shrink-0 text-xs tabular-nums text-ink-500">
                  {timestamp(entry.created_at)}
                </span>
                <Badge
                  className={cn(
                    'shrink-0 ring-1 ring-inset',
                    ACTION_TONE[entry.action] ?? 'bg-ink-100 text-ink-600 ring-ink-400/20',
                  )}
                >
                  {entry.action_label}
                </Badge>
                <span className="min-w-0 flex-1 truncate text-sm text-ink-700">
                  {entry.username || 'anonim'}
                  {entry.entity_type ? (
                    <span className="text-ink-400"> · {entry.entity_type.split('.').pop()}</span>
                  ) : null}
                </span>
                {entry.ip_address ? (
                  <span className="shrink-0 font-mono text-xs text-ink-400">
                    {entry.ip_address}
                  </span>
                ) : null}
                {!entry.success ? (
                  <Badge className="bg-red-500/15 text-red-700 ring-1 ring-inset ring-red-600/20">
                    {t('register.failed')}
                  </Badge>
                ) : null}
              </button>

              {expanded === entry.id ? (
                <pre className="mt-2 overflow-x-auto rounded-xl bg-ink-50 p-3 text-xs text-ink-700">
                  {JSON.stringify(
                    {
                      metadata: entry.metadata,
                      old_data: entry.old_data,
                      new_data: entry.new_data,
                    },
                    null,
                    2,
                  )}
                </pre>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {data && data.total_pages > 1 ? (
        <CardBody className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-100">
          <span className="text-sm text-ink-500">
            {data.count} ta yozuv · {data.page}/{data.total_pages}-sahifa
          </span>
          <div className="flex gap-1">
            <Button
              variant="secondary"
              size="sm"
              disabled={!data.previous}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
            >
              {t('register.previous')}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!data.next}
              onClick={() => setPage((value) => value + 1)}
            >
              {t('register.next')}
            </Button>
          </div>
        </CardBody>
      ) : null}
    </Card>
  )
}
