import { forwardRef, useId, useState, type InputHTMLAttributes, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/utils/cn'

import { EyeIcon, EyeOffIcon } from './Icon'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: ReactNode
  leftIcon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, leftIcon, className, id, type = 'text', ...props },
  ref,
) {
  const { t } = useTranslation()
  const [revealed, setRevealed] = useState(false)
  const generatedId = useId()
  const isPassword = type === 'password'
  // Always give the label something to point at, even for unnamed fields —
  // otherwise the label is decorative and screen readers announce nothing.
  const inputId = id ?? props.name ?? generatedId

  return (
    <div className="w-full">
      {label ? (
        <label className="label" htmlFor={inputId}>
          {label}
        </label>
      ) : null}

      <div className="relative">
        {leftIcon ? (
          <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-400">
            {leftIcon}
          </span>
        ) : null}

        <input
          ref={ref}
          id={inputId}
          type={isPassword && revealed ? 'text' : type}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${inputId}-error` : undefined}
          className={cn(
            'input',
            leftIcon && 'pl-10',
            isPassword && 'pr-11',
            error && 'input-error',
            className,
          )}
          {...props}
        />

        {isPassword ? (
          <button
            type="button"
            onClick={() => setRevealed((value) => !value)}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-ink-400 transition hover:bg-ink-50 hover:text-ink-600"
            aria-label={
              revealed ? t('validation.hidePassword') : t('validation.showPassword')
            }
            tabIndex={-1}
          >
            {revealed ? <EyeOffIcon width={18} height={18} /> : <EyeIcon width={18} height={18} />}
          </button>
        ) : null}
      </div>

      {error ? (
        <p id={`${inputId}-error`} className="mt-1.5 text-sm text-red-600">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1.5 text-sm text-ink-500">{hint}</p>
      ) : null}
    </div>
  )
})
