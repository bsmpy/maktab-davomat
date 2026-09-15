import { create } from 'zustand'

/** The five palettes. The key is what lands in `data-theme` and localStorage. */
export const THEMES = [
  { value: 'light', labelKey: 'themes.light', swatch: '#4b4a89', paper: '#ffffff' },
  { value: 'dark', labelKey: 'themes.dark', swatch: '#8b8de0', paper: '#121828' },
  { value: 'violet', labelKey: 'themes.violet', swatch: '#8b83ea', paper: '#1a1640' },
  { value: 'orange', labelKey: 'themes.orange', swatch: '#f97316', paper: '#23170a' },
  { value: 'emerald', labelKey: 'themes.emerald', swatch: '#10b981', paper: '#07201a' },
] as const

export type ThemeName = (typeof THEMES)[number]['value']

export const THEME_STORAGE_KEY = 'davomat.theme'
const DEFAULT_THEME: ThemeName = 'light'

function isTheme(value: unknown): value is ThemeName {
  return THEMES.some((theme) => theme.value === value)
}

/** Storage can throw in a private window; a missing preference is not an error. */
export function readStoredTheme(): ThemeName {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return isTheme(stored) ? stored : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

function apply(theme: ThemeName): void {
  document.documentElement.setAttribute('data-theme', theme)
  // The browser chrome around the page should match the palette too.
  const meta = document.querySelector('meta[name="theme-color"]')
  const paper = THEMES.find((item) => item.value === theme)?.paper
  if (meta && paper) meta.setAttribute('content', paper)
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    /* nothing to do — the theme still applies for this session */
  }
}

interface ThemeState {
  theme: ThemeName
  setTheme: (theme: ThemeName) => void
}

/**
 * The chosen palette.
 *
 * `index.html` stamps `data-theme` before the first paint, so this store starts
 * from what is already on the document rather than fighting it.
 */
const initial = readStoredTheme()
// index.html already stamped data-theme; this brings the browser-chrome colour
// into line with it, which only ever happened on a change before.
if (typeof document !== 'undefined') apply(initial)

export const useThemeStore = create<ThemeState>((set) => ({
  theme: initial,
  setTheme(theme) {
    apply(theme)
    set({ theme })
  },
}))
