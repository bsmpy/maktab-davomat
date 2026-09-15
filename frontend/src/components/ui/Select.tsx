import { forwardRef, useId, type SelectHTMLAttributes } from 'react'

import { cn } from '@/utils/cn'

import { ChevronDownIcon } from './Icon'

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  hint?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, hint, className, id, children, ...props },
  ref,
) {
  const generatedId = useId()
  const selectId = id ?? props.name ?? generatedId
  return (
    <div className="w-full">
      {label ? (
        <label className="label" htmlFor={selectId}>
          {label}
        </label>
      ) : null}
      <div className="relative">
        <select
          ref={ref}
          id={selectId}
          className={cn('input appearance-none pr-10', error && 'input-error', className)}
          {...props}
        >
          {children}
        </select>
        <ChevronDownIcon
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-400"
          width={18}
          height={18}
        />
      </div>
      {error ? (
        <p className="mt-1.5 text-sm text-red-600">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-sm text-ink-500">{hint}</p>
      ) : null}
    </div>
  )
})
