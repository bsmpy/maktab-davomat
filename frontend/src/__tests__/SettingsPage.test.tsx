import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/errors'
import { SettingsPage } from '@/pages/SettingsPage'
import { useAppearanceStore } from '@/store/appearanceStore'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'
import type { Integration, Role, SettingsOverview } from '@/types/api'

import { PERMISSIONS_BY_ROLE, makeUser } from './session'

vi.mock('@/api/appearanceApi', () => ({
  appearanceApi: { get: vi.fn(), update: vi.fn() },
}))

vi.mock('@/api/settingsApi', () => ({
  settingsApi: {
    overview: vi.fn(),
    integrations: vi.fn(),
    integration: vi.fn(),
    saveIntegration: vi.fn(),
    testIntegration: vi.fn(),
  },
  terminalApi: { list: vi.fn(), test: vi.fn(), sync: vi.fn() },
  faceIdApi: { people: vi.fn() },
  presenceApi: { list: vi.fn() },
}))

const { settingsApi, terminalApi, faceIdApi } = await import('@/api/settingsApi')
const { appearanceApi } = await import('@/api/appearanceApi')

/** The server's answer after a switch has been moved. */
function appearance(multiTheme: boolean, particles: boolean, canEdit = true) {
  return { multi_theme: multiTheme, particles, can_edit: canEdit }
}

function integration(kind: Integration['kind'], overrides: Partial<Integration> = {}): Integration {
  return {
    id: `int-${kind}`,
    kind,
    kind_display: kind,
    school: null,
    school_name: null,
    is_enabled: true,
    config: {},
    secrets: {},
    status: 'OK',
    status_display: 'Ishlayapti',
    effective_status: 'OK',
    last_checked_at: null,
    last_error: '',
    updated_at: '2026-09-08T10:00:00Z',
    ...overrides,
  }
}

function overview(role: Role, canManage: boolean, available = true): SettingsOverview {
  return {
    role,
    roles: [role],
    permissions: PERMISSIONS_BY_ROLE[role],
    can_manage_integrations: canManage,
    sections: [
      { key: 'profile', label: 'Profil', description: '', available: true },
      {
        key: 'integrations',
        label: 'Integratsiyalar',
        description: '',
        available,
        children: [
          { key: 'TELEGRAM_BOT', label: 'Telegram bot' },
          { key: 'SMS_ESKIZ', label: 'SMS (Eskiz)' },
          { key: 'FACE_ID', label: 'Face ID' },
          { key: 'TERMINALS', label: 'Terminallar' },
        ],
      },
    ],
  }
}

/** The page opens on "Umumiy"; most tests want a specific section instead. */
function renderPage(section?: string) {
  return render(
    <MemoryRouter
      initialEntries={[section ? `/sozlamalar?bolim=${section}` : '/sozlamalar']}
    >
      <SettingsPage />
    </MemoryRouter>,
  )
}

describe('settings · integrations', () => {
  beforeEach(() => {
    useAuthStore.setState({
      status: 'authenticated',
      user: makeUser('DEVELOPER', { username: 'dev.user' }) as never,
    })
    vi.mocked(settingsApi.integrations).mockResolvedValue({
      kinds: [],
      results: [
        integration('TELEGRAM_BOT', { secrets: { bot_token: '••••••4ht4' } }),
        integration('SMS_ESKIZ', { is_enabled: false, effective_status: 'DISABLED' }),
        integration('FACE_ID'),
        integration('TERMINALS'),
      ],
    })
    vi.mocked(terminalApi.list).mockResolvedValue({ directions: [], vendors: [], results: [] })
    vi.mocked(faceIdApi.people).mockResolvedValue({
      count: 0, page: 1, page_size: 20, total_pages: 1, next: null, previous: null, results: [],
    })

    // The appearance store is a module singleton; a test that flips a switch
    // must not decide what the next one starts from. `canEdit` stands in for
    // the load the cabinet shell does on mount — this page renders below it.
    useAppearanceStore.setState({
      multiTheme: true,
      particles: true,
      canEdit: true,
      error: null,
    })
    vi.mocked(appearanceApi.update).mockImplementation(async (patch) =>
      appearance(patch.multi_theme ?? true, patch.particles ?? true),
    )
    useThemeStore.setState({ theme: 'light' })
    document.documentElement.setAttribute('data-theme', 'light')
  })

  it('shows the three live integrations to a developer', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Sozlamalar' })).toBeInTheDocument()
    for (const label of ['Telegram bot', 'Face ID', 'Terminallar']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    }
  })

  it('opens on Telegram and lists the two menu groups', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    renderPage()

    expect(
      (await screen.findAllByRole('heading', { name: 'Telegram bot' })).length,
    ).toBeGreaterThan(0)

    const menu = within(screen.getByRole('navigation', { name: /Sozlamalar/ }))
    for (const group of ['Integratsiyalar', "Ko'rinish"]) {
      expect(menu.getAllByText(group).length).toBeGreaterThan(0)
    }
  })

  it('offers only the sections that exist', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    renderPage()

    const menu = within(await screen.findByRole('navigation', { name: /Sozlamalar/ }))
    for (const gone of [
      'Umumiy',
      'Sayt sozlamalari',
      'Eskiz',
      'Kontent',
      'Email',
      'Imtihon',
      'Shartnoma',
      'Payme',
    ]) {
      expect(menu.queryByText(new RegExp(gone))).not.toBeInTheDocument()
    }
  })

  it('switches section without leaving the page', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    renderPage()

    const nav = await screen.findByRole('navigation', { name: /Sozlamalar/ })
    await userEvent.click(within(nav).getByRole('button', { name: /Face ID/ }))

    // The working area's own title strip now names the section.
    expect(
      (await screen.findAllByRole('heading', { name: 'Face ID' })).length,
    ).toBeGreaterThan(0)
    // The menu is still mounted: this was a section change, not a navigation.
    expect(screen.getByRole('navigation', { name: /Sozlamalar/ })).toBeInTheDocument()
  })

  it('lets the extra palettes be turned off, leaving light and dark', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    renderPage('mavzular')

    const toggle = await screen.findByRole('switch', { name: /Barcha mavzular/ })
    expect(screen.getByRole('button', { name: /Galaktika/ })).toBeInTheDocument()

    await userEvent.click(toggle)

    // The switch is the installation's, so it goes to the server, not to this
    // browser's storage.
    expect(appearanceApi.update).toHaveBeenCalledWith({ multi_theme: false })
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /Galaktika/ })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: /Yorug/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Tungi/ })).toBeInTheDocument()
  })

  it('puts the switch back when the server refuses the change', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    vi.mocked(appearanceApi.update).mockRejectedValue(new Error('nope'))
    renderPage('zarrachalar')

    const toggle = await screen.findByRole('switch', { name: /Zarrachalarni/ })
    expect(toggle).toHaveAttribute('aria-checked', 'true')

    await userEvent.click(toggle)

    // Everyone shares this setting: a refused write must not leave one screen
    // showing a state nobody else is in.
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'true'))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('locks the switches for someone who may only read them', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('SUPER_ADMIN', false))
    useAppearanceStore.setState({ canEdit: false })
    renderPage('zarrachalar')

    expect(await screen.findByRole('switch', { name: /Zarrachalarni/ })).toBeDisabled()
  })

  it('falls back off a palette that has just been withdrawn', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    renderPage('mavzular')

    await userEvent.click(await screen.findByRole('button', { name: /Zumrad/ }))
    expect(document.documentElement.getAttribute('data-theme')).toBe('emerald')

    await userEvent.click(screen.getByRole('switch', { name: /Barcha mavzular/ }))
    // The app cannot be left standing on a theme its own picker no longer lists.
    await waitFor(() =>
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark'),
    )
  })

  it('turns the particles off', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    renderPage('zarrachalar')

    const toggle = await screen.findByRole('switch', { name: /Zarrachalarni/ })
    await userEvent.click(toggle)

    expect(appearanceApi.update).toHaveBeenCalledWith({ particles: false })
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'false'))
  })

  it('never renders a real credential, only the mask', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    renderPage('telegram')

    expect(await screen.findByText('••••••4ht4')).toBeInTheDocument()
    expect(screen.queryByText(/AAGQ/)).not.toBeInTheDocument()
  })

  it('locks the forms for a super admin', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('SUPER_ADMIN', false))
    useAuthStore.setState({ user: makeUser('SUPER_ADMIN', { username: 'boss' }) as never })
    renderPage('telegram')

    expect(
      await screen.findByText(/faqat dasturchi \(DEVELOPER\) roli/i),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Saqlash' })).toBeDisabled()
  })

  it('says so plainly when the server refuses the whole section', async () => {
    // A role Sozlamalar is not for at all: the overview 403s, and that is an
    // answer rather than a failure to retry.
    vi.mocked(settingsApi.overview).mockRejectedValue(
      new ApiError({ code: 'FORBIDDEN', message: 'yo\'q', fields: {} }, 403),
    )
    useAuthStore.setState({ user: makeUser('TEACHER', { username: 'o.qituvchi' }) as never })
    renderPage()

    expect(await screen.findByText('Sozlamalar sizga ochiq emas')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Qayta urinish/ })).not.toBeInTheDocument()
  })

  /**
   * A school administrator opens Sozlamalar for the two appearance switches.
   * The integrations group is not merely disabled for them — it is not in the
   * menu, because the credentials in it are the platform's, not the school's.
   */
  it('shows an administrator the appearance group and nothing else', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('ADMIN', false, false))
    useAuthStore.setState({ user: makeUser('ADMIN', { username: 'school.admin' }) as never })
    renderPage()

    expect(await screen.findByRole('button', { name: /Mavzular/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Telegram/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Terminallar/ })).not.toBeInTheDocument()
  })

  it('saves only the secrets the user actually changed', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    vi.mocked(settingsApi.saveIntegration).mockResolvedValue(integration('TELEGRAM_BOT'))
    renderPage('telegram')

    const username = await screen.findByLabelText('Bot username')
    await userEvent.clear(username)
    await userEvent.type(username, 'yangi_bot')
    await userEvent.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() => expect(settingsApi.saveIntegration).toHaveBeenCalled())
    const [kind, payload] = vi.mocked(settingsApi.saveIntegration).mock.calls[0]
    expect(kind).toBe('TELEGRAM_BOT')
    expect(payload.config).toMatchObject({ bot_username: 'yangi_bot' })
    // The untouched token must not be part of the request at all.
    expect(payload.secrets).toBeUndefined()
  })

  it('sends a secret once the user opts into editing it', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    vi.mocked(settingsApi.saveIntegration).mockResolvedValue(integration('TELEGRAM_BOT'))
    renderPage('telegram')

    await userEvent.click(await screen.findByRole('button', { name: "O'zgartirish" }))
    await userEvent.type(screen.getByLabelText('Bot token (@BotFather)'), 'new-token')
    await userEvent.click(screen.getByRole('button', { name: 'Saqlash' }))

    await waitFor(() => expect(settingsApi.saveIntegration).toHaveBeenCalled())
    const [, payload] = vi.mocked(settingsApi.saveIntegration).mock.calls[0]
    expect(payload.secrets).toEqual({ bot_token: 'new-token' })
  })

  it('reports a failed connection test without breaking the page', async () => {
    vi.mocked(settingsApi.overview).mockResolvedValue(overview('DEVELOPER', true))
    vi.mocked(settingsApi.testIntegration).mockResolvedValue({
      ok: false,
      message: 'Bot tokeni kiritilmagan.',
    })
    vi.mocked(settingsApi.integration).mockResolvedValue(integration('TELEGRAM_BOT'))
    renderPage('telegram')

    await userEvent.click(await screen.findByRole('button', { name: 'Tekshirish' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Bot tokeni kiritilmagan.')
  })
})
