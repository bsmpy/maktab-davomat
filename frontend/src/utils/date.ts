import { now } from './clock'

const MONTHS_UZ = [
  'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
  'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
]

const WEEKDAYS_UZ = [
  'Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba',
]

/** `2026-09-08` → local Date at midnight (no timezone drift). */
export function parseISODate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, (month ?? 1) - 1, day ?? 1)
}

export function toISODate(date: Date): string {
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function todayISO(): string {
  return toISODate(now())
}

/** `8 Sentabr 2026` */
export function formatLongDate(value: string | Date): string {
  const date = typeof value === 'string' ? parseISODate(value) : value
  return `${date.getDate()} ${MONTHS_UZ[date.getMonth()]} ${date.getFullYear()}`
}

/** `08.09.2026` */
export function formatShortDate(value: string | Date): string {
  const date = typeof value === 'string' ? parseISODate(value) : value
  const day = `${date.getDate()}`.padStart(2, '0')
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  return `${day}.${month}.${date.getFullYear()}`
}

export function formatWeekday(value: string | Date): string {
  const date = typeof value === 'string' ? parseISODate(value) : value
  return WEEKDAYS_UZ[date.getDay()]
}

export function formatDateTime(value: string): string {
  const date = new Date(value)
  const time = date.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
  return `${formatShortDate(date)} ${time}`
}

/** "2 daqiqa oldin", "3 soat oldin", "5 kun oldin" */
export function formatRelative(value: string): string {
  const diffMs = Date.now() - new Date(value).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'Hozirgina'
  if (minutes < 60) return `${minutes} daqiqa oldin`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} soat oldin`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} kun oldin`
  return formatShortDate(new Date(value))
}

export function addDays(value: string, days: number): string {
  const date = parseISODate(value)
  date.setDate(date.getDate() + days)
  return toISODate(date)
}

export function shiftMonth(year: number, month: number, delta: number) {
  const date = new Date(year, month - 1 + delta, 1)
  return { year: date.getFullYear(), month: date.getMonth() + 1 }
}

export function monthName(month: number): string {
  return MONTHS_UZ[month - 1] ?? ''
}

export { MONTHS_UZ, WEEKDAYS_UZ }

/** Monday…Sunday around the given day, as ISO dates. */
export function weekRange(value: string): { start: string; end: string } {
  const date = parseISODate(value)
  // getDay() is Sunday-first; the school week starts on Monday.
  const offset = (date.getDay() + 6) % 7
  const start = addDays(value, -offset)
  return { start, end: addDays(start, 6) }
}

/** The first and last day of a calendar month, as ISO dates. */
export function monthRange(year: number, month: number): { start: string; end: string } {
  return {
    start: toISODate(new Date(year, month - 1, 1)),
    end: toISODate(new Date(year, month, 0)),
  }
}

/**
 * The academic year containing the day: September through August, which is how
 * the school counts a year.
 */
export function academicYearRange(value: string): { start: string; end: string } {
  const date = parseISODate(value)
  const startYear = date.getMonth() + 1 >= 9 ? date.getFullYear() : date.getFullYear() - 1
  return {
    start: toISODate(new Date(startYear, 8, 1)),
    end: toISODate(new Date(startYear + 1, 7, 31)),
  }
}
