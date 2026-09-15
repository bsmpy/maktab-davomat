import type { SyntheticEvent } from 'react'

/**
 * Wrap the actions inside a profile card with this, so pressing edit or delete
 * does not also open the profile the card stands for.
 */
export function stopCard(event: SyntheticEvent) {
  event.stopPropagation()
}
