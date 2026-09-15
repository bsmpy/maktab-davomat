import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { registrationApi } from '@/api/registrationApi'
import { ApiError } from '@/api/errors'
import { Avatar, Button, Input, SearchIcon, Spinner } from '@/components/ui'
import { useDebouncedValue } from '@/hooks'
import type { ClassGroup, StudentSearchResult } from '@/types/api'

const MIN_QUERY = 3

/**
 * Searching is scoped to the chosen class group and capped server-side, so the
 * register can never be enumerated from here. Results show a masked name
 * ("Valiyev A.") — enough to recognise your own child, not to harvest a list.
 */
export function StudentStep({
  classGroup,
  onSelect,
  onBack,
}: {
  classGroup: ClassGroup
  onSelect: (student: StudentSearchResult) => void
  onBack: () => void
}) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  // Results are keyed by the term they belong to, so a stale response can never
  // be shown next to a newer query and no effect has to reset them.
  const [outcome, setOutcome] = useState<{
    term: string
    results: StudentSearchResult[]
    error: string | null
  } | null>(null)
  const debounced = useDebouncedValue(query.trim(), 450)
  const longEnough = debounced.length >= MIN_QUERY

  useEffect(() => {
    if (!longEnough) return

    let cancelled = false

    registrationApi
      .searchStudents({ class_group: classGroup.id, query: debounced })
      .then((found) => {
        if (!cancelled) setOutcome({ term: debounced, results: found, error: null })
      })
      .catch((caught) => {
        if (cancelled) return
        setOutcome({
          term: debounced,
          results: [],
          error: caught instanceof ApiError ? caught.message : 'Qidiruvda xatolik.',
        })
      })
    return () => {
      cancelled = true
    }
  }, [debounced, longEnough, classGroup.id])

  // "In flight" is derived, not stored: a request is outstanding exactly when
  // the term we would search for has no result attached to it yet.
  const current = longEnough && outcome?.term === debounced ? outcome : null
  const results = current?.results ?? []
  const error = current?.error ?? null
  const searching = longEnough && current === null

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 rounded-xl bg-brand-50 px-3.5 py-2.5 text-sm text-brand-800">
        <span className="font-semibold">{classGroup.display_name}</span>
        <span className="text-brand-600">sinfi tanlandi</span>
        <button
          type="button"
          onClick={onBack}
          className="ml-auto text-xs font-medium text-brand-700 underline underline-offset-2"
        >
          {t('actions.change')}
        </button>
      </div>

      <Input
        name="query"
        label={t('registration.childName')}
        placeholder={t('registration.childNameHint')}
        leftIcon={<SearchIcon width={18} height={18} />}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        hint={`Kamida ${MIN_QUERY} ta harf kiriting`}
        error={error ?? undefined}
        autoFocus
      />

      {searching ? (
        <div className="flex items-center justify-center gap-2 py-6 text-sm text-ink-400">
          <Spinner className="h-4 w-4" /> {t('registration.searching')}
        </div>
      ) : null}

      {!searching && current && results.length === 0 && !error ? (
        <p className="rounded-xl bg-ink-50 px-4 py-6 text-center text-sm text-ink-500">
          Hech narsa topilmadi. Familiyani boshqacha yozib ko'ring yoki maktab ma'muriyatiga
          murojaat qiling.
        </p>
      ) : null}

      {results.length > 0 ? (
        <ul className="divide-y divide-ink-100 overflow-hidden rounded-xl border border-ink-200">
          {results.map((student) => (
            <li key={student.id}>
              <button
                type="button"
                onClick={() => onSelect(student)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-ink-50"
              >
                <Avatar
                  name={student.display_name}
                  src={student.photo ?? undefined}
                  size="md"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink-800">
                    {student.display_name}
                  </span>
                  <span className="block text-xs text-ink-500">
                    {student.class_group}
                    {student.birth_year ? ` · ${student.birth_year}-yil` : ''}
                  </span>
                </span>
                <span className="text-xs font-medium text-brand-600">{t('registration.choose')}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <Button variant="ghost" fullWidth onClick={onBack}>
        {t('actions.back')}
      </Button>
    </div>
  )
}
