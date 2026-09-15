/**
 * The clock the app runs on.
 *
 * The server can be put on a demo clock — a fixed offset, so a timetable can be
 * shown on a weekday that has not arrived yet. When it is, the browser has to
 * follow: a page that thinks it is Thursday while the API answers for Monday
 * disagrees with itself about which lessons exist.
 *
 * The offset is fetched once at startup and defaults to zero, which is real
 * time and what a normal deployment runs on.
 */
let offsetMs = 0

export function setClockOffset(seconds: number): void {
  offsetMs = Number.isFinite(seconds) ? seconds * 1000 : 0
}

export function clockOffsetSeconds(): number {
  return offsetMs / 1000
}

export function isClockShifted(): boolean {
  return offsetMs !== 0
}

/** Use this instead of `new Date()` anywhere "now" matters. */
export function now(): Date {
  return new Date(Date.now() + offsetMs)
}
