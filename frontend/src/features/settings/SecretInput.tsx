import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button, Input } from '@/components/ui'

/**
 * A credential field that never shows the stored value.
 *
 * The server only ever returns a mask (`••••••1234`). Until the user clicks
 * "O'zgartirish" the field stays read-only and nothing is sent, so saving a
 * config change cannot accidentally overwrite a secret with a placeholder.
 */
export function SecretInput({
  label,
  masked,
  value,
  onChange,
  hint,
  placeholder = '••••••••',
}: {
  label: string
  masked?: string
  value: string | null
  onChange: (value: string | null) => void
  hint?: string
  placeholder?: string
}) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const fieldId = useId()
  const isSet = Boolean(masked)

  if (!editing) {
    return (
      <div role="group" aria-labelledby={`${fieldId}-label`}>
        <span className="label" id={`${fieldId}-label`}>
          {label}
        </span>
        <div className="flex items-center gap-2">
          <div className="flex h-11 flex-1 items-center rounded-xl border border-ink-200 bg-ink-50 px-3.5 text-[15px] text-ink-500">
            {isSet ? masked : <span className="text-ink-400">{t('settings.notEntered')}</span>}
          </div>
          <Button
            variant="secondary"
            size="md"
            onClick={() => {
              setEditing(true)
              onChange('')
            }}
          >
            {isSet ? "O'zgartirish" : 'Kiritish'}
          </Button>
        </div>
        {hint ? <p className="mt-1.5 text-sm text-ink-500">{hint}</p> : null}
      </div>
    )
  }

  return (
    <div>
      <Input
        id={fieldId}
        label={label}
        type="password"
        autoComplete="new-password"
        placeholder={placeholder}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
        hint={hint}
      />
      <button
        type="button"
        className="mt-1.5 text-sm font-medium text-ink-500 hover:text-ink-700"
        onClick={() => {
          setEditing(false)
          onChange(null)
        }}
      >
        {t('actions.cancel')}
      </button>
    </div>
  )
}
