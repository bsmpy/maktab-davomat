import type { AttendanceStatus, DayState, LessonStatus } from '@/types/api'
import i18n from '@/i18n'

/**
 * Presentation-only mapping. The percentage itself is *never* computed here —
 * the backend owns the formula and the UI renders `summary.rate` verbatim.
 */
export const STATUS_META: Record<
  AttendanceStatus,
  { labelKey: string; shortKey: string; emoji: string; dot: string; chip: string; text: string }
> = {
  PRESENT: {
    labelKey: 'status.present',
    shortKey: 'status.k',
    emoji: '✅',
    dot: 'bg-status-present',
    chip: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    text: 'text-emerald-700',
  },
  ABSENT: {
    labelKey: 'status.absent',
    shortKey: 'status.x',
    emoji: '❌',
    dot: 'bg-status-absent',
    chip: 'bg-red-50 text-red-700 ring-red-600/20',
    text: 'text-red-700',
  },
  LATE: {
    labelKey: 'status.late',
    shortKey: 'status.kch',
    emoji: '🟡',
    dot: 'bg-status-late',
    chip: 'bg-amber-50 text-amber-700 ring-amber-600/20',
    text: 'text-amber-700',
  },
  EXCUSED: {
    labelKey: 'status.excused',
    shortKey: 'status.s',
    emoji: '🔵',
    dot: 'bg-status-excused',
    chip: 'bg-blue-50 text-blue-700 ring-blue-600/20',
    text: 'text-blue-700',
  },
}

export const DAY_STATE_META: Record<
  DayState,
  { labelKey: string; cell: string; dot: string }
> = {
  PRESENT: {
    labelKey: 'status.present',
    cell: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    dot: 'bg-status-present',
  },
  ABSENT: {
    labelKey: 'status.absent',
    cell: 'bg-red-50 text-red-800 border-red-200',
    dot: 'bg-status-absent',
  },
  LATE: {
    labelKey: 'status.late',
    cell: 'bg-amber-50 text-amber-900 border-amber-200',
    dot: 'bg-status-late',
  },
  EXCUSED: {
    labelKey: 'status.excused',
    cell: 'bg-blue-50 text-blue-800 border-blue-200',
    dot: 'bg-status-excused',
  },
  NO_LESSONS: {
    labelKey: 'status.noData',
    cell: 'bg-ink-50 text-ink-400 border-ink-200',
    dot: 'bg-status-none',
  },
  NO_DATA: {
    labelKey: 'status.notYetHere',
    cell: 'bg-ink-50 text-ink-500 border-ink-200',
    dot: 'bg-status-none',
  },
  HOLIDAY: {
    labelKey: 'status.holiday',
    cell: 'bg-violet-50 text-violet-700 border-violet-200',
    dot: 'bg-violet-400',
  },
  WEEKEND: {
    labelKey: 'status.dayOff',
    cell: 'bg-ink-50 text-ink-400 border-ink-100',
    dot: 'bg-status-none',
  },
  FUTURE: {
    labelKey: 'status.notYet',
    cell: 'bg-surface text-ink-400 border-ink-200',
    dot: 'bg-ink-200',
  },
}

/** Colour band for a percentage — the only place thresholds are defined. */
export function rateTone(rate: number | undefined): 'good' | 'warn' | 'bad' {
  if (!Number.isFinite(rate)) return 'bad'
  if (rate! >= 90) return 'good'
  if (rate! >= 75) return 'warn'
  return 'bad'
}

export const RATE_TONE_CLASS = {
  good: 'text-emerald-600',
  warn: 'text-amber-600',
  bad: 'text-red-600',
} as const

export const RATE_BAR_CLASS = {
  good: 'bg-emerald-500',
  warn: 'bg-amber-500',
  bad: 'bg-red-500',
} as const

export function formatRate(rate: number | undefined): string {
  if (!Number.isFinite(rate)) return '—'
  return `${rate!.toFixed(1).replace(/\.0$/, '')}%`
}

/**
 * `45` → `45 daqiqa kechikdi`, `135` → `2 soat 15 daqiqa kechikdi`.
 * Past an hour, minutes alone stop being readable.
 */
export function formatLateMinutes(minutes: number): string {
  return `${formatDuration(minutes)} kechikdi`
}

/** `312` → `5 soat 12 daqiqa` — how long the pupil was inside or outside. */
export function formatDuration(minutes: number): string {
  if (!minutes || minutes < 0) return '—'
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  // The singleton translator rather than a hook: this is called from plain
  // helpers and from inside `map` callbacks as often as it is from a component.
  if (!hours) return i18n.t('duration.minutes', { count: rest })
  if (!rest) return i18n.t('duration.hours', { count: hours })
  return i18n.t('duration.hoursMinutes', { hours, minutes: rest })
}

/** Compact form for tight cells: `5h 12m`, in whichever language is on. */
export function formatDurationShort(minutes: number): string {
  if (!minutes || minutes < 0) return '—'
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (!hours) return i18n.t('duration.minutesShortUnit', { count: rest })
  if (!rest) return i18n.t('duration.hoursShort', { count: hours })
  return i18n.t('duration.hoursMinutesShort', { hours, minutes: rest })
}

export const DIRECTION_META = {
  IN: { labelKey: 'status.in', emoji: '🟢', chip: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20' },
  OUT: { labelKey: 'status.out', emoji: '🔴', chip: 'bg-red-50 text-red-700 ring-red-600/20' },
  UNKNOWN: { labelKey: 'status.unknown', emoji: '⚪', chip: 'bg-ink-50 text-ink-600 ring-ink-400/20' },
} as const

/**
 * The four marks a teacher can put on a pupil, and how each one looks.
 *
 * `EXCUSED` and `ABSENT` are both "kelmadi" — the difference is whether a
 * reason was given, which is why the labels say so rather than repeating the
 * status name.
 */
export const LESSON_STATUS_META: Record<
  Exclude<LessonStatus, null>,
  { labelKey: string; shortKey: string; chip: string; dot: string }
> = {
  PRESENT: {
    labelKey: 'status.present',
    shortKey: 'status.present',
    chip: 'border-emerald-500 bg-emerald-50 text-emerald-700',
    dot: 'bg-status-present',
  },
  LATE: {
    labelKey: 'status.late',
    shortKey: 'status.late',
    chip: 'border-amber-500 bg-amber-50 text-amber-800',
    dot: 'bg-status-late',
  },
  ABSENT: {
    labelKey: 'status.unexcusedLong',
    shortKey: 'status.unexcused',
    chip: 'border-red-500 bg-red-50 text-red-700',
    dot: 'bg-status-absent',
  },
  EXCUSED: {
    labelKey: 'status.excusedLong',
    shortKey: 'status.excused',
    chip: 'border-blue-500 bg-blue-50 text-blue-700',
    dot: 'bg-status-excused',
  },
}

/** `Kechikdi · 12 daqiqa`, `Sababli · Kasal`, or just the label. */
export function lessonMarkSummary(
  status: Exclude<LessonStatus, null>,
  lateMinutes: number,
  comment: string,
  /** The caller's translator: this composes words, so it needs one. */
  t: (key: string) => string,
): string {
  const meta = LESSON_STATUS_META[status]
  if (status === 'LATE') return `${t(meta.shortKey)} · ${formatDuration(lateMinutes)}`
  if (status === 'EXCUSED' && comment) return `${t(meta.shortKey)} · ${comment}`
  return t(meta.labelKey)
}
