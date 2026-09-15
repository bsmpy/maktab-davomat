import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { guardianApi } from '@/api/managementApi'
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
import type { ManagedClassGroup } from '@/types/api'
import { formatShortDate } from '@/utils/date'

type Filter = '' | 'yes' | 'no'

/**
 * The parent register and who out of it has claimed an account.
 *
 * Registration is what turns a row the school typed in into a person who can
 * sign in, so the useful question here is "which children have a parent on the
 * system yet" — hence the filter.
 */
export function GuardiansPanel({ classGroups }: { classGroups: ManagedClassGroup[] }) {
  const { t } = useTranslation()
  const [registered, setRegistered] = useState<Filter>('')
  const [classGroup, setClassGroup] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)

  const debouncedQuery = useDebouncedValue(query, 300)
  const guardians = useAsyncData(
    () =>
      guardianApi.list({
        registered: registered || undefined,
        class_group: classGroup || undefined,
        q: debouncedQuery || undefined,
        page,
      }),
    [registered, classGroup, debouncedQuery, page],
  )

  const data = guardians.data

  return (
    <Card>
      <CardHeader
        title={t('register.guardiansTitle')}
        description={t('register.guardiansHint')}
      />
      <CardBody className="flex flex-wrap items-end gap-3">
        <Select
          label={t('register.registered')}
          value={registered}
          className="w-full sm:w-52"
          onChange={(event) => {
            setRegistered(event.target.value as Filter)
            setPage(1)
          }}
        >
          <option value="">{t('register.all')}</option>
          <option value="yes">{t('register.hasAccount')}</option>
          <option value="no">{t('register.noAccount')}</option>
        </Select>
        <Select
          label={t('register.group')}
          value={classGroup}
          className="w-full sm:w-44"
          onChange={(event) => {
            setClassGroup(event.target.value)
            setPage(1)
          }}
        >
          <option value="">{t('register.all')}</option>
          {classGroups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.display_name}
            </option>
          ))}
        </Select>
        <Input
          label={t('common.search')}
          value={query}
          placeholder={t('register.nameOrSurname')}
          className="w-full sm:w-64"
          onChange={(event) => {
            setQuery(event.target.value)
            setPage(1)
          }}
        />
      </CardBody>

      {guardians.initialLoading ? (
        <SkeletonRows count={6} />
      ) : guardians.error ? (
        <ErrorState error={guardians.error} onRetry={guardians.reload} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          title={t('register.noGuardians')}
          description={t('register.noGuardiansHint')}
        />
      ) : (
        <ul className="divide-y divide-ink-100 border-t border-ink-100">
          {data.results.map((guardian) => (
            <li key={guardian.id} className="px-5 py-3.5">
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-medium text-ink-800">
                    {guardian.full_name}
                  </p>
                  <p className="truncate text-xs text-ink-500">
                    {guardian.phone} · JSHSHIR {guardian.jshshir || guardian.masked_jshshir}
                  </p>
                </div>

                {guardian.has_account ? (
                  <Badge className="bg-emerald-500/15 text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                    {guardian.username}
                  </Badge>
                ) : (
                  <Badge className="bg-ink-100 text-ink-600 ring-1 ring-inset ring-ink-400/20">
                    {t('register.notRegistered')}
                  </Badge>
                )}

                {guardian.registered_at ? (
                  <span className="text-xs text-ink-400">
                    {formatShortDate(guardian.registered_at)} dan beri
                  </span>
                ) : null}
              </div>

              {guardian.children.length > 0 ? (
                <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                  {guardian.children.map((child) => (
                    <li key={child.id} className="text-xs text-ink-600">
                      <span className="font-medium text-ink-700">{child.full_name}</span>
                      <span className="text-ink-400">
                        {' '}
                        · {child.class_group} · {child.relation_label}
                        {child.is_primary ? ' · asosiy vakil' : ''}
                        {child.verified ? '' : ' · tasdiqlanmagan'}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-xs text-ink-400">{t('register.noChildLinked')}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {data && data.total_pages > 1 ? (
        <CardBody className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-100">
          <span className="text-sm text-ink-500">
            {data.count} ta yaqini · {data.page}/{data.total_pages}-sahifa
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
