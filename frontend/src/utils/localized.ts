/** A title the server sent in every interface language at once. */
export interface LocalizedTitle {
  uz: string
  ru: string
  en: string
}

/**
 * The title in the language on screen, falling back to the Uzbek original.
 *
 * A position added before its Russian name was filled in should read as its
 * Uzbek name on a Russian screen, not as an empty cell. The server applies the
 * same fallback; this is for the places where the client picks the language
 * itself out of the three it was given.
 */
export function localizedTitle(
  titles: LocalizedTitle | undefined | null,
  language: string,
): string {
  if (!titles) return ''
  const key = language.slice(0, 2) as keyof LocalizedTitle
  return titles[key] || titles.uz || ''
}
