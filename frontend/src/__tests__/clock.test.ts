import { afterEach, describe, expect, it, vi } from 'vitest'

import { clockOffsetSeconds, isClockShifted, now, setClockOffset } from '@/utils/clock'
import { todayISO } from '@/utils/date'

afterEach(() => {
  setClockOffset(0)
  vi.useRealTimers()
})

describe('the app clock', () => {
  it('is real time until the server says otherwise', () => {
    expect(isClockShifted()).toBe(false)
    expect(clockOffsetSeconds()).toBe(0)
    expect(Math.abs(now().getTime() - Date.now())).toBeLessThan(50)
  })

  it('moves the day with the offset', () => {
    vi.useFakeTimers()
    // A Thursday.
    vi.setSystemTime(new Date(2026, 8, 10, 16, 0, 0))
    expect(todayISO()).toBe('2026-09-10')

    // Four days on, at 10:10 — the Monday the timetable was written for.
    const seconds = (new Date(2026, 8, 14, 10, 10, 0).getTime() - Date.now()) / 1000
    setClockOffset(seconds)

    expect(isClockShifted()).toBe(true)
    expect(todayISO()).toBe('2026-09-14')
    expect(now().getHours()).toBe(10)
    expect(now().getMinutes()).toBe(10)
  })

  it('keeps running at normal speed once shifted', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 8, 10, 16, 0, 0))
    setClockOffset((new Date(2026, 8, 14, 10, 10, 0).getTime() - Date.now()) / 1000)

    vi.advanceTimersByTime(90_000)
    expect(now().getHours()).toBe(10)
    expect(now().getMinutes()).toBe(11)
    expect(now().getSeconds()).toBe(30)
  })

  it('ignores a value that is not a number', () => {
    setClockOffset(Number.NaN)
    expect(clockOffsetSeconds()).toBe(0)
  })
})
