import { toApiError } from '@/api/errors'

/**
 * The server's answers for a roll call that is not open yet: the lesson has not
 * started, or the day has not come. Neither is a failure worth a retry button —
 * the message already says when it opens.
 */
const CLOSED_CODES = ['LESSON_NOT_STARTED', 'FUTURE_DATE']

/** The reason the roll call is shut, or `null` when the error is something else. */
export function rosterClosedMessage(error: unknown): string | null {
  if (!error) return null
  const apiError = toApiError(error)
  return CLOSED_CODES.includes(apiError.code) ? apiError.message : null
}
