import { useLayoutEffect, useReducer, useRef, type ChangeEvent } from 'react'

import {
  JSHSHIR_LENGTH,
  PHONE_PREFIX,
  formatJshshir,
  formatPassportId,
  formatPhone,
} from '@/utils/masks'

import { Input, type InputProps } from './Input'

export type MaskedInputProps = Omit<InputProps, 'value' | 'onChange' | 'type'> & {
  value: string
  /** Receives the already-masked value, never the raw keystrokes. */
  onChange: (value: string) => void
}

type InternalProps = MaskedInputProps & {
  format: (raw: string) => string
  /** Characters the caret counts by: everything else is decoration. */
  significant: RegExp
  /** Literal text at the head of the field that the user may never remove. */
  prefix?: string
}

function countSignificant(text: string, significant: RegExp): number {
  let count = 0
  for (const char of text) if (significant.test(char)) count += 1
  return count
}

/** Index just after the `count`-th significant character of `text`. */
function indexAfter(text: string, count: number, significant: RegExp): number {
  if (count <= 0) return 0
  let seen = 0
  for (let index = 0; index < text.length; index += 1) {
    if (significant.test(text[index])) {
      seen += 1
      if (seen === count) return index + 1
    }
  }
  return text.length
}

/**
 * A controlled input that rewrites what is typed into a fixed shape.
 *
 * Two details make it behave like a native field rather than a jumping one:
 * the caret is restored by counting significant characters (so editing in the
 * middle does not throw it to the end), and the component re-renders on every
 * keystroke even when the masked value is unchanged — otherwise a rejected
 * character would stay visible in the DOM that React never revisits.
 */
function MaskedInput({
  value,
  onChange,
  format,
  significant,
  prefix = '',
  ...rest
}: InternalProps) {
  const ref = useRef<HTMLInputElement>(null)
  const caret = useRef<number | null>(null)
  const [, forceRender] = useReducer((tick: number) => tick + 1, 0)
  const display = format(value)

  useLayoutEffect(() => {
    const input = ref.current
    if (!input) return
    if (input.value !== display) input.value = display
    if (caret.current !== null) {
      if (document.activeElement === input) {
        input.setSelectionRange(caret.current, caret.current)
      }
      caret.current = null
    }
  })

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const raw = event.target.value

    // A Backspace that reached into the fixed prefix: refuse the edit whole,
    // otherwise the country code's own digits slide into the subscriber part.
    // Emptying the field is still allowed — nothing is left to protect then —
    // and so is a paste, which replaces the prefix rather than eating into it.
    const inputType =
      'inputType' in event.nativeEvent ? String(event.nativeEvent.inputType) : ''
    if (
      prefix &&
      !raw.startsWith(prefix) &&
      raw.length > 0 &&
      raw.length < display.length &&
      !inputType.startsWith('insert')
    ) {
      caret.current = prefix.length
      forceRender()
      return
    }

    const position = event.target.selectionStart ?? raw.length
    const typed = countSignificant(raw.slice(0, position), significant)
    const next = format(raw)
    caret.current = Math.max(prefix.length, indexAfter(next, typed, significant))
    forceRender()
    if (next !== value) onChange(next)
  }

  return <Input ref={ref} value={display} onChange={handleChange} {...rest} />
}

/** `+998(90)123-45-67`. The `+998(` prefix can never be deleted. */
export function PhoneInput(props: MaskedInputProps) {
  return (
    <MaskedInput
      inputMode="tel"
      autoComplete="tel"
      maxLength={17}
      {...props}
      format={formatPhone}
      significant={/\d/}
      prefix={PHONE_PREFIX}
    />
  )
}

/** `AA1234567` — two uppercase Latin letters, then exactly seven digits. */
export function PassportIdInput(props: MaskedInputProps) {
  return (
    <MaskedInput
      placeholder="AA1234567"
      autoCapitalize="characters"
      spellCheck={false}
      maxLength={9}
      {...props}
      format={formatPassportId}
      significant={/[A-Za-z0-9]/}
    />
  )
}

/** Fourteen digits, nothing else. */
export function JshshirInput(props: MaskedInputProps) {
  return (
    <MaskedInput
      inputMode="numeric"
      placeholder={'0'.repeat(JSHSHIR_LENGTH)}
      maxLength={JSHSHIR_LENGTH}
      {...props}
      format={formatJshshir}
      significant={/\d/}
    />
  )
}
