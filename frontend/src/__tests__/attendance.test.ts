import { describe, expect, it } from 'vitest'

import {
  DAY_STATE_META,
  formatDuration,
  formatDurationShort,
  formatLateMinutes,
  formatRate,
  rateTone,
  STATUS_META,
} from '@/utils/attendance'
import { addDays, formatLongDate, formatShortDate, shiftMonth, toISODate } from '@/utils/date'
import i18n from '@/i18n'

describe('attendance presentation helpers', () => {
  it('labels every attendance status in all three languages', () => {
    // The table holds keys now, not words: the same status has to read as
    // "Keldi", "Пришёл" or "Present" depending on who is looking.
    expect(i18n.t(STATUS_META.PRESENT.labelKey)).toBe('Keldi')
    expect(i18n.t(STATUS_META.ABSENT.labelKey)).toBe('Kelmadi')
    expect(i18n.t(STATUS_META.LATE.labelKey)).toBe('Kechikdi')
    expect(i18n.t(STATUS_META.EXCUSED.labelKey)).toBe('Sababli')

    expect(i18n.t(STATUS_META.PRESENT.labelKey, { lng: 'ru' })).toBe('Пришёл')
    expect(i18n.t(STATUS_META.PRESENT.labelKey, { lng: 'en' })).toBe('Present')
  })

  it('covers every calendar day state', () => {
    for (const state of [
      'PRESENT', 'ABSENT', 'LATE', 'EXCUSED', 'NO_LESSONS', 'NO_DATA', 'HOLIDAY',
      'WEEKEND', 'FUTURE',
    ] as const) {
      expect(DAY_STATE_META[state]).toBeDefined()
      // Every state names itself in every language, with nothing missing.
      for (const lng of ['uz', 'ru', 'en']) {
        const word = i18n.t(DAY_STATE_META[state].labelKey, { lng })
        expect(word).toBeTruthy()
        expect(word).not.toBe(DAY_STATE_META[state].labelKey)
      }
    }
  })

  it('bands the rate into three tones', () => {
    expect(rateTone(96)).toBe('good')
    expect(rateTone(90)).toBe('good')
    expect(rateTone(80)).toBe('warn')
    expect(rateTone(74.9)).toBe('bad')
  })

  it('formats a rate without a trailing .0', () => {
    expect(formatRate(95.7)).toBe('95.7%')
    expect(formatRate(100)).toBe('100%')
  })
})

describe('date helpers', () => {
  it('formats dates the way the UI shows them', () => {
    expect(formatLongDate('2026-09-08')).toBe('8 Sentabr 2026')
    expect(formatShortDate('2026-09-08')).toBe('08.09.2026')
  })

  it('parses ISO dates without timezone drift', () => {
    expect(toISODate(new Date(2026, 8, 8))).toBe('2026-09-08')
  })

  it('shifts days and months across boundaries', () => {
    expect(addDays('2026-09-01', -1)).toBe('2026-08-31')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
    expect(shiftMonth(2026, 1, -1)).toEqual({ year: 2025, month: 12 })
    expect(shiftMonth(2026, 12, 1)).toEqual({ year: 2027, month: 1 })
  })
})

describe('late arrivals', () => {
  it('reads in minutes below an hour', () => {
    expect(formatLateMinutes(1)).toBe('1 daqiqa kechikdi')
    expect(formatLateMinutes(45)).toBe('45 daqiqa kechikdi')
  })

  it('switches to hours and minutes past an hour', () => {
    expect(formatLateMinutes(60)).toBe('1 soat kechikdi')
    expect(formatLateMinutes(90)).toBe('1 soat 30 daqiqa kechikdi')
    expect(formatLateMinutes(135)).toBe('2 soat 15 daqiqa kechikdi')
  })
})

describe('durations', () => {
  it('spells minutes out in Uzbek', () => {
    expect(formatDuration(45)).toBe('45 daqiqa')
    expect(formatDuration(120)).toBe('2 soat')
    expect(formatDuration(312)).toBe('5 soat 12 daqiqa')
  })

  it('has a compact form for tight cells', () => {
    expect(formatDurationShort(45)).toBe('45d')
    expect(formatDurationShort(120)).toBe('2s')
    expect(formatDurationShort(312)).toBe('5s 12d')
  })

  it('renders a dash rather than a broken value when there is no time', () => {
    expect(formatDuration(0)).toBe('—')
    expect(formatDuration(undefined as unknown as number)).toBe('—')
    expect(formatDurationShort(undefined as unknown as number)).toBe('—')
  })
})

describe('tolerating a payload from an older API', () => {
  /**
   * The SPA is served as static files and can go live before the API restarts.
   * A shape mismatch has to degrade to a dash or an empty state — never throw
   * and blank the whole page.
   */
  it('never throws on a missing rate', () => {
    expect(formatRate(undefined as unknown as number)).toBe('—')
    expect(rateTone(undefined as unknown as number)).toBe('bad')
  })

  it('falls back to a known day state for an unknown one', () => {
    const unknown = DAY_STATE_META['SOMETHING_ELSE' as keyof typeof DAY_STATE_META]
    expect(unknown).toBeUndefined()
    expect(i18n.t(DAY_STATE_META.NO_DATA.labelKey)).toBeTruthy()
  })
})
