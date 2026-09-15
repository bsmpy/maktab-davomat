import { describe, expect, it } from 'vitest'

import {
  formatJshshir,
  formatPassportId,
  formatPhone,
  isJshshir,
  isPassportId,
  isPhoneComplete,
  phoneDigits,
  phoneFromApi,
  phoneToApi,
} from '@/utils/masks'

describe('formatPhone', () => {
  it('always keeps the country code in front', () => {
    expect(formatPhone('')).toBe('+998(')
    expect(formatPhone('+998(')).toBe('+998(')
  })

  it('fills the mask digit by digit', () => {
    expect(formatPhone('+998(9')).toBe('+998(9')
    expect(formatPhone('+998(90')).toBe('+998(90')
    expect(formatPhone('+998(901')).toBe('+998(90)1')
    expect(formatPhone('+998(90)123')).toBe('+998(90)123')
    expect(formatPhone('+998(90)1234')).toBe('+998(90)123-4')
    expect(formatPhone('+998(90)123456')).toBe('+998(90)123-45-6')
    expect(formatPhone('+998(90)1234567')).toBe('+998(90)123-45-67')
  })

  it('drops the closing bracket once the digits behind it are gone', () => {
    // Backspacing from `+998(90)1` must not leave a dangling `)`.
    expect(formatPhone('+998(90)')).toBe('+998(90')
  })

  it('rebuilds the prefix when it is missing', () => {
    expect(formatPhone('998(90)123-45-67')).toBe('+998(90)123-45-67')
  })

  it('ignores everything that is not a digit', () => {
    expect(formatPhone('+998(9a0)1-2-3')).toBe('+998(90)123')
  })

  it('stops at nine subscriber digits', () => {
    expect(formatPhone('+998(90)123-45-6789')).toBe('+998(90)123-45-67')
  })

  it('accepts a pasted full number', () => {
    expect(formatPhone('+998901234567')).toBe('+998(90)123-45-67')
    // Pasted after the prefix that is already there.
    expect(formatPhone('+998(998901234567')).toBe('+998(90)123-45-67')
  })

  it('keeps 99 as a real operator code', () => {
    expect(formatPhone('+998(998123456')).toBe('+998(99)812-34-56')
    expect(phoneDigits('+998(99)812-34-56')).toBe('998123456')
  })
})

describe('phone helpers', () => {
  it('reports completeness', () => {
    expect(isPhoneComplete('+998(')).toBe(false)
    expect(isPhoneComplete('+998(90)123-45-6')).toBe(false)
    expect(isPhoneComplete('+998(90)123-45-67')).toBe(true)
  })

  it('converts to and from the API shape', () => {
    expect(phoneToApi('+998(90)123-45-67')).toBe('+998901234567')
    expect(phoneToApi('+998(')).toBe('')
    expect(phoneFromApi('+998901234567')).toBe('+998(90)123-45-67')
    expect(phoneFromApi('')).toBe('')
    expect(phoneFromApi(null)).toBe('')
  })
})

describe('formatPassportId', () => {
  it('takes two letters, then seven digits', () => {
    expect(formatPassportId('aa1234567')).toBe('AA1234567')
    expect(formatPassportId('AA 123 45 67')).toBe('AA1234567')
  })

  it('refuses a digit in a letter slot and a letter in a digit slot', () => {
    // Only the leading letter survives: slot 2 rejects the digit that follows.
    expect(formatPassportId('1A234567')).toBe('A')
    expect(formatPassportId('AAb123')).toBe('AA123')
  })

  it('stops after seven digits', () => {
    expect(formatPassportId('AA123456789')).toBe('AA1234567')
  })

  it('validates the finished value', () => {
    expect(isPassportId('AA1234567')).toBe(true)
    expect(isPassportId('AA123456')).toBe(false)
    expect(isPassportId('A11234567')).toBe(false)
    expect(isPassportId('')).toBe(false)
  })
})

describe('formatJshshir', () => {
  it('keeps digits only, capped at fourteen', () => {
    expect(formatJshshir('312-345 678a90123')).toBe('31234567890123')
    expect(formatJshshir('312345678901234567')).toBe('31234567890123')
  })

  it('validates the finished value', () => {
    expect(isJshshir('31234567890123')).toBe(true)
    expect(isJshshir('3123456789012')).toBe(false)
  })
})
