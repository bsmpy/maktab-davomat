import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { registrationApi } from '@/api/registrationApi'
import { ApiError } from '@/api/errors'
import { Button, Input, JshshirInput, LockIcon, Select } from '@/components/ui'
import { useAsyncData } from '@/hooks'
import type { Relation, RegistrationSession, StudentSearchResult } from '@/types/api'
import { isJshshir } from '@/utils/masks'

/**
 * Identity proof. The applicant supplies their own JSHSHIR and the last four
 * digits of the phone the school already has on file; the backend checks both
 * against the guardian↔pupil link before anything else happens.
 */
export function IdentityStep({
  student,
  onVerified,
  onBack,
}: {
  student: StudentSearchResult
  onVerified: (session: RegistrationSession) => void
  onBack: () => void
}) {
  const { t } = useTranslation()
  const relations = useAsyncData(() => registrationApi.relations(), [])
  const [relation, setRelation] = useState<Relation | ''>('')
  const [jshshir, setJshshir] = useState('')
  const [phoneLast4, setPhoneLast4] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!relation) return
    setSubmitting(true)
    setError(null)
    try {
      const session = await registrationApi.identify({
        student: student.id,
        relation,
        jshshir,
        phone_last4: phoneLast4,
      })
      onVerified(session)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="rounded-xl bg-brand-50 px-3.5 py-2.5 text-sm text-brand-800">
        <span className="font-semibold">{student.display_name}</span>
        <span className="text-brand-600"> · {student.class_group}</span>
      </div>

      {error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-500/15 px-3.5 py-3 text-sm text-red-700"
        >
          {error.message}
        </div>
      ) : null}

      <Select
        name="relation"
        label={t('registration.relation')}
        value={relation}
        onChange={(event) => setRelation(event.target.value as Relation)}
        error={error?.fieldError('relation')}
        required
      >
        <option value="" disabled>
          {t('person.select')}
        </option>
        {(relations.data ?? []).map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </Select>

      <JshshirInput
        name="jshshir"
        label={t('registration.jshshir14')}
        autoComplete="off"
        leftIcon={<LockIcon width={18} height={18} />}
        value={jshshir}
        onChange={setJshshir}
        error={error?.fieldError('jshshir')}
        hint={t('registration.dataEncrypted')}
        required
      />

      <Input
        name="phone_last4"
        label={t('registration.lastFour')}
        placeholder="4567"
        inputMode="numeric"
        maxLength={4}
        autoComplete="off"
        className="tracking-[0.3em]"
        value={phoneLast4}
        onChange={(event) => setPhoneLast4(event.target.value.replace(/\D/g, ''))}
        error={error?.fieldError('phone_last4')}
        hint={t('registration.registeredNumber')}
        required
      />

      <Button
        type="submit"
        fullWidth
        size="lg"
        loading={submitting}
        disabled={!relation || !isJshshir(jshshir) || phoneLast4.length !== 4}
      >
        {t('registration.verify')}
      </Button>
      <Button type="button" variant="ghost" fullWidth onClick={onBack}>
        {t('actions.back')}
      </Button>
    </form>
  )
}
