import { create } from 'zustand'

import { appearanceApi } from '@/api/appearanceApi'
import { toApiError } from '@/api/errors'

import { THEMES, useThemeStore, type ThemeName } from './themeStore'

/**
 * Appearance is decided for the whole installation, not per browser.
 *
 * It used to live in `localStorage`, on the reasoning that how the screen looks
 * is the choice of the person in front of it. The requirement is now the
 * opposite: when a DEVELOPER or SUPER_ADMIN turns the extra palettes or the
 * particles off, they go off for everybody. So the server owns both switches
 * and this store is a cache of what it said.
 *
 * What stays personal is the palette someone picks out of what is on offer —
 * that is still `themeStore`, still their own browser.
 *
 * The two keys below are only a boot cache: they let the first paint match what
 * the server said last time instead of flashing particles at someone who has
 * had them turned off. The server is always the authority, and `load()`
 * overwrites them.
 */
const MULTI_THEME_KEY = 'davomat.multiTheme'
const PARTICLES_KEY = 'davomat.particles'

/** With multi-theme off, only these two remain on offer. */
export const BASE_THEMES: ThemeName[] = ['light', 'dark']

/** Storage can throw in a private window; both switches default to on. */
function readCached(key: string): boolean {
  try {
    return localStorage.getItem(key) !== 'off'
  } catch {
    return true
  }
}

function cache(key: string, value: boolean): void {
  try {
    localStorage.setItem(key, value ? 'on' : 'off')
  } catch {
    /* the switch still applies for this session */
  }
}

/**
 * Turning the extra palettes off cannot leave the app standing on one of them:
 * fall back to the nearest of the two that remain.
 */
function clampTheme(multiTheme: boolean): void {
  if (multiTheme) return
  const current = useThemeStore.getState().theme
  if (!BASE_THEMES.includes(current)) useThemeStore.getState().setTheme('dark')
}

interface AppearanceState {
  /** All five palettes, or just light and dark. */
  multiTheme: boolean
  /** The drifting motes over the interface. */
  particles: boolean
  /** Whether this viewer may move the switches. The server decides. */
  canEdit: boolean
  /** True until the server has been heard from once. */
  loading: boolean
  /** Set when a write was refused or failed, for the settings screen to show. */
  error: string | null
  load: () => Promise<void>
  setMultiTheme: (value: boolean) => Promise<void>
  setParticles: (value: boolean) => Promise<void>
}

export const useAppearanceStore = create<AppearanceState>((set, get) => ({
  multiTheme: readCached(MULTI_THEME_KEY),
  particles: readCached(PARTICLES_KEY),
  canEdit: false,
  loading: false,
  error: null,

  async load() {
    set({ loading: true })
    try {
      const data = await appearanceApi.get()
      cache(MULTI_THEME_KEY, data.multi_theme)
      cache(PARTICLES_KEY, data.particles)
      set({
        multiTheme: data.multi_theme,
        particles: data.particles,
        canEdit: data.can_edit,
        loading: false,
        error: null,
      })
      clampTheme(data.multi_theme)
    } catch {
      // A cabinet that cannot read one preference is still a working cabinet:
      // keep the cached answer rather than blanking the interface.
      set({ loading: false })
    }
  },

  async setMultiTheme(value) {
    await write(set, get, { multi_theme: value })
  },

  async setParticles(value) {
    await write(set, get, { particles: value })
  },
}))

/**
 * One write path for both switches: show the new state at once, then let the
 * server confirm it — and put it back if the server says no.
 */
async function write(
  set: (partial: Partial<AppearanceState>) => void,
  get: () => AppearanceState,
  patch: { multi_theme?: boolean; particles?: boolean },
): Promise<void> {
  const previous = { multiTheme: get().multiTheme, particles: get().particles }
  // Withdrawing the palettes pushes this browser off one of them; if the write
  // is then refused, putting the switch back is not enough — the palette the
  // person had chosen has to come back with it.
  const previousTheme = useThemeStore.getState().theme
  const optimistic = {
    ...(patch.multi_theme === undefined ? {} : { multiTheme: patch.multi_theme }),
    ...(patch.particles === undefined ? {} : { particles: patch.particles }),
  }
  set({ ...optimistic, error: null })
  if (optimistic.multiTheme !== undefined) clampTheme(optimistic.multiTheme)

  try {
    const data = await appearanceApi.update(patch)
    cache(MULTI_THEME_KEY, data.multi_theme)
    cache(PARTICLES_KEY, data.particles)
    set({ multiTheme: data.multi_theme, particles: data.particles, canEdit: data.can_edit })
    clampTheme(data.multi_theme)
  } catch (error) {
    // The switch is shared, so a refused write must not leave this screen
    // showing a state nobody else is in.
    set({ ...previous, error: toApiError(error).message })
    if (useThemeStore.getState().theme !== previousTheme) {
      useThemeStore.getState().setTheme(previousTheme)
    }
  }
}

/** The palettes on offer right now. */
export function availableThemes(multiTheme: boolean) {
  return multiTheme ? THEMES : THEMES.filter((theme) => BASE_THEMES.includes(theme.value))
}
