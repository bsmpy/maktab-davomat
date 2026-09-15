import { describe, expect, it } from 'vitest'

import en from '@/i18n/locales/en.json'
import ru from '@/i18n/locales/ru.json'
import uz from '@/i18n/locales/uz.json'

type Dictionary = Record<string, unknown>

/** Every leaf, as a dotted path — `nav.home`, `home.avgActive` and so on. */
function paths(dictionary: Dictionary, prefix = ''): string[] {
  return Object.entries(dictionary).flatMap(([key, value]) =>
    value && typeof value === 'object'
      ? paths(value as Dictionary, `${prefix}${key}.`)
      : [`${prefix}${key}`],
  )
}

function read(dictionary: Dictionary, path: string): unknown {
  return path.split('.').reduce<unknown>(
    (node, key) => (node as Dictionary | undefined)?.[key],
    dictionary,
  )
}

const LANGUAGES: Record<string, Dictionary> = { uz, ru, en }

describe('the three dictionaries', () => {
  /**
   * The interface ships in Uzbek, Russian and English, and a key missing from
   * one of them does not fail — i18next quietly falls back to Uzbek, so a
   * Russian screen grows an Uzbek word and nobody notices. This is the check
   * that does notice.
   */
  it('carry exactly the same keys', () => {
    const uzbek = paths(uz).sort()
    expect(paths(ru).sort()).toEqual(uzbek)
    expect(paths(en).sort()).toEqual(uzbek)
  })

  it('leave nothing blank', () => {
    for (const [language, dictionary] of Object.entries(LANGUAGES)) {
      for (const path of paths(dictionary)) {
        const value = read(dictionary, path)
        expect(typeof value, `${language}:${path}`).toBe('string')
        expect(String(value).trim(), `${language}:${path}`).not.toBe('')
      }
    }
  })

  /**
   * A translation that still reads as the Uzbek original is usually a key that
   * was copied across and never translated. Proper nouns and abbreviations are
   * genuinely the same word in all three, so they are listed rather than
   * guessed at.
   */
  it('actually translate, rather than repeating the Uzbek', () => {
    const SAME_IN_EVERY_LANGUAGE = new Set([
      'common.appName',
      'person.jshshir',
      'person.email',
      'person.login',
      'person.passportId',
      'profile.jshshir',
      'profile.login',
      'settings.telegramTitle',
      'settings.faceIdTitle',
      'settings.smsTitle',
      'settings.fdid',
      'settings.eskizEmail',
      'settings.botToken',
      'settings.botUsername',
      'settings.botLabel',
      'notifications.telegram',
      'school.emailExample',
      'school.loginExample',
      'school.subjectExample',
      'terminals.port',
      'terminals.model',
      'terminals.ip',
      'terminals.isapiLogin',
      'terminals.isapiPassword',
      'terminals.formHint',
      'terminals.devicesHint',
      'terminals.namePlaceholder',
      'terminals.locationPlaceholder',
      'importing.title',
      'nav.export',
      'themes.violet',
      'themes.orange',
      'themes.emerald',
      'themes.light',
      'themes.dark',
      'registration.childNameHint',
    ])

    const untranslated = paths(uz).filter(
      (path) =>
        !SAME_IN_EVERY_LANGUAGE.has(path) &&
        (read(ru, path) === read(uz, path) || read(en, path) === read(uz, path)),
    )
    expect(untranslated).toEqual([])
  })

  it('keep the same interpolation placeholders in every language', () => {
    const placeholders = (value: unknown) =>
      [...String(value).matchAll(/{{(\w+)}}/g)].map((match) => match[1]).sort()

    for (const path of paths(uz)) {
      const expected = placeholders(read(uz, path))
      expect(placeholders(read(ru, path)), `ru:${path}`).toEqual(expected)
      expect(placeholders(read(en, path)), `en:${path}`).toEqual(expected)
    }
  })
})
