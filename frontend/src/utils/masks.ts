/** Input masks for the three identifiers used across the whole app.
 *
 * Phone, passport ID and JSHSHIR are typed on registration, on the pupil form,
 * on the teacher form and in the admin console. The rules live here so every
 * field behaves identically and the backend receives one predictable shape.
 */

/** Never editable: the country code is part of the field, not of the value. */
export const PHONE_PREFIX = '+998('

const PHONE_BODY_LENGTH = 9
const PASSPORT_LETTERS = 2
const PASSPORT_DIGITS = 7
export const JSHSHIR_LENGTH = 14

/** The nine subscriber digits, with the country code stripped off. */
export function phoneDigits(value: string): string {
  let text = value ?? ''
  // Strip the prefix as text, not as digits: `99` is a real operator code, so
  // a bare `998123456` must survive as the subscriber number it is.
  if (text.startsWith(PHONE_PREFIX)) text = text.slice(PHONE_PREFIX.length)
  let digits = text.replace(/\D/g, '')
  // Whatever is left over is a pasted number still carrying its country code.
  if (digits.length > PHONE_BODY_LENGTH && digits.startsWith('998')) {
    digits = digits.slice(3)
  }
  return digits.slice(0, PHONE_BODY_LENGTH)
}

/**
 * `+998(`, `+998(9`, `+998(90`, `+998(90)1`, … `+998(90)123-45-67`.
 *
 * The closing bracket only appears once there is something after it, so
 * deleting the subscriber digits takes it away again.
 */
export function formatPhone(value: string): string {
  const d = phoneDigits(value)
  let out = PHONE_PREFIX + d.slice(0, 2)
  if (d.length > 2) out += `)${d.slice(2, 5)}`
  if (d.length > 5) out += `-${d.slice(5, 7)}`
  if (d.length > 7) out += `-${d.slice(7, 9)}`
  return out
}

/** True once all nine subscriber digits are there. */
export function isPhoneComplete(value: string): boolean {
  return phoneDigits(value).length === PHONE_BODY_LENGTH
}

/** `+998901234567` for the API, or `''` when nothing was typed. */
export function phoneToApi(value: string): string {
  const d = phoneDigits(value)
  return d ? `+998${d}` : ''
}

/** Turns whatever the API returns back into the masked display value. */
export function phoneFromApi(value: string | null | undefined): string {
  return value ? formatPhone(value) : ''
}

/**
 * Two uppercase Latin letters, then up to seven digits — `AA1234567`.
 *
 * Filtering is positional: while the first two slots are empty only letters
 * are taken, afterwards only digits, so a stray character is dropped instead
 * of shifting everything along.
 */
export function formatPassportId(value: string): string {
  let out = ''
  for (const char of (value ?? '').toUpperCase()) {
    if (out.length < PASSPORT_LETTERS) {
      if (/[A-Z]/.test(char)) out += char
    } else if (out.length < PASSPORT_LETTERS + PASSPORT_DIGITS) {
      if (/\d/.test(char)) out += char
    } else {
      break
    }
  }
  return out
}

export function isPassportId(value: string): boolean {
  return /^[A-Z]{2}\d{7}$/.test(value)
}

/** Digits only, at most fourteen of them. */
export function formatJshshir(value: string): string {
  return (value ?? '').replace(/\D/g, '').slice(0, JSHSHIR_LENGTH)
}

export function isJshshir(value: string): boolean {
  return formatJshshir(value).length === JSHSHIR_LENGTH
}
