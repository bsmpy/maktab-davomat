import '@testing-library/jest-dom/vitest'

import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Components read their labels through i18next; initialising the shared
// instance once here means tests assert on real strings, not on keys. The
// language is pinned so a runner whose navigator says "en" cannot change what
// the assertions see.
import i18n from '@/i18n'

void i18n.changeLanguage('uz')

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  localStorage.clear()
})

// jsdom does not implement matchMedia, which the responsive hooks rely on.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})
