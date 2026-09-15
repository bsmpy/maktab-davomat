import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/appearanceApi', () => ({
  appearanceApi: { get: vi.fn(), update: vi.fn() },
}))

const { appearanceApi } = await import('@/api/appearanceApi')
const { useAppearanceStore, availableThemes, BASE_THEMES } = await import(
  '@/store/appearanceStore'
)
const { useThemeStore } = await import('@/store/themeStore')

function serverSays(multiTheme: boolean, particles: boolean, canEdit = false) {
  return { multi_theme: multiTheme, particles, can_edit: canEdit }
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useAppearanceStore.setState({
    multiTheme: true,
    particles: true,
    canEdit: false,
    loading: false,
    error: null,
  })
  useThemeStore.setState({ theme: 'light' })
  document.documentElement.setAttribute('data-theme', 'light')
})

describe('the shared appearance settings', () => {
  /**
   * The point of moving these off the browser: a parent who never opens
   * Sozlamalar still has the particles turned off for them.
   */
  it('takes what the server says, whoever is looking', async () => {
    vi.mocked(appearanceApi.get).mockResolvedValue(serverSays(false, false))

    await useAppearanceStore.getState().load()

    expect(useAppearanceStore.getState().multiTheme).toBe(false)
    expect(useAppearanceStore.getState().particles).toBe(false)
    // A parent may read it and may not change it.
    expect(useAppearanceStore.getState().canEdit).toBe(false)
  })

  it('caches the answer so the next first paint already matches', async () => {
    vi.mocked(appearanceApi.get).mockResolvedValue(serverSays(false, false))

    await useAppearanceStore.getState().load()

    expect(localStorage.getItem('davomat.multiTheme')).toBe('off')
    expect(localStorage.getItem('davomat.particles')).toBe('off')
  })

  it('keeps the cached answer when the server cannot be reached', async () => {
    vi.mocked(appearanceApi.get).mockRejectedValue(new Error('offline'))
    useAppearanceStore.setState({ particles: false })

    await useAppearanceStore.getState().load()

    // A cabinet that cannot read one preference is still a working cabinet.
    expect(useAppearanceStore.getState().particles).toBe(false)
    expect(useAppearanceStore.getState().loading).toBe(false)
  })

  it('sends a change to the server rather than only to this browser', async () => {
    vi.mocked(appearanceApi.update).mockResolvedValue(serverSays(true, false, true))

    await useAppearanceStore.getState().setParticles(false)

    expect(appearanceApi.update).toHaveBeenCalledWith({ particles: false })
    expect(useAppearanceStore.getState().particles).toBe(false)
  })

  it('puts a refused change back', async () => {
    vi.mocked(appearanceApi.update).mockRejectedValue(new Error('403'))

    await useAppearanceStore.getState().setParticles(false)

    expect(useAppearanceStore.getState().particles).toBe(true)
    expect(useAppearanceStore.getState().error).toBeTruthy()
  })

  it('takes the browser off a palette the server has just withdrawn', async () => {
    useThemeStore.setState({ theme: 'emerald' })
    vi.mocked(appearanceApi.get).mockResolvedValue(serverSays(false, true))

    await useAppearanceStore.getState().load()

    // Nobody may be left standing on a theme the picker no longer lists — not
    // even someone who chose it before the switch was thrown.
    expect(useThemeStore.getState().theme).toBe('dark')
  })

  it('leaves a palette alone when it is still on offer', async () => {
    useThemeStore.setState({ theme: 'emerald' })
    vi.mocked(appearanceApi.get).mockResolvedValue(serverSays(true, true))

    await useAppearanceStore.getState().load()

    expect(useThemeStore.getState().theme).toBe('emerald')
  })

  it('restores the palette when a refused write is rolled back', async () => {
    useThemeStore.setState({ theme: 'emerald' })
    vi.mocked(appearanceApi.update).mockRejectedValue(new Error('403'))

    await useAppearanceStore.getState().setMultiTheme(false)

    expect(useAppearanceStore.getState().multiTheme).toBe(true)
    // The rollback has to undo the fallback too, or the extra palettes are on
    // offer while the browser sits on the one it was pushed to.
    expect(useThemeStore.getState().theme).toBe('emerald')
  })
})

describe('what the theme picker offers', () => {
  it('lists all five with the extra palettes on', () => {
    expect(availableThemes(true)).toHaveLength(5)
  })

  it('lists only light and dark with them off', () => {
    expect(availableThemes(false).map((theme) => theme.value)).toEqual(BASE_THEMES)
  })
})
