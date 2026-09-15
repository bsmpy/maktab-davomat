import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { LanguageMenu } from '@/components/layout/LanguageMenu'
import { NavBackButton } from '@/components/layout/NavBackButton'
import { NavBurgerButton } from '@/components/layout/NavBurgerButton'
import { NavSearch } from '@/components/layout/NavSearch'
import { ThemeMenu } from '@/components/layout/ThemeMenu'
import { Topbar } from '@/components/layout/Topbar'
import i18n from '@/i18n'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import { THEMES, readStoredTheme, useThemeStore } from '@/store/themeStore'

import { makeUser } from './session'

beforeEach(async () => {
  await i18n.changeLanguage('uz')
  document.documentElement.removeAttribute('data-theme')
  useThemeStore.setState({ theme: 'light' })
  useChildStore.setState({ children: [], activeChildId: null } as never)
  useAuthStore.setState({
    user: makeUser('TEACHER', { username: 't', full_name: 'T' }) as never,
  })
})

describe('the burger button', () => {
  it('reports and flips the sidebar state', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    const { rerender } = render(<NavBurgerButton open={false} onToggle={onToggle} />)

    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveAccessibleName('Menyuni ochish')

    await user.click(button)
    expect(onToggle).toHaveBeenCalledTimes(1)

    rerender(<NavBurgerButton open onToggle={onToggle} />)
    expect(screen.getByRole('button')).toHaveAccessibleName('Menyuni yopish')
  })
})

describe('the back button', () => {
  function Where() {
    const location = useLocation()
    return <span data-testid="where">{location.pathname}</span>
  }

  it('steps back through history, not to a fixed URL', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/', '/davomat']} initialIndex={1}>
        <NavBackButton />
        <Where />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('where')).toHaveTextContent('/davomat')
    await user.click(screen.getByRole('button', { name: 'Orqaga' }))
    expect(screen.getByTestId('where')).toHaveTextContent('/')
  })
})

describe('the navbar search', () => {
  function renderSearch() {
    return render(
      <MemoryRouter initialEntries={['/']}>
        <NavSearch />
        <Routes>
          <Route path="/davomat" element={<span>davomat page</span>} />
          <Route path="/" element={<span>home page</span>} />
        </Routes>
      </MemoryRouter>,
    )
  }

  it('offers the pages this user can open', async () => {
    const user = userEvent.setup()
    renderSearch()

    await user.type(screen.getByRole('combobox'), 'dav')
    expect(await screen.findByRole('option', { name: /Davomat/ })).toBeInTheDocument()
  })

  it('navigates to the page that was picked', async () => {
    const user = userEvent.setup()
    renderSearch()

    await user.type(screen.getByRole('combobox'), 'dav')
    await user.click(await screen.findByRole('option', { name: /Davomat/ }))

    expect(await screen.findByText('davomat page')).toBeInTheDocument()
    // The field clears once you have arrived.
    expect(screen.getByRole('combobox')).toHaveValue('')
  })

  it('says so when nothing matches', async () => {
    const user = userEvent.setup()
    renderSearch()

    await user.type(screen.getByRole('combobox'), 'zzzz')
    expect(await screen.findByText('Hech narsa topilmadi')).toBeInTheDocument()
  })
})

describe('the language menu', () => {
  it('lists the languages the app ships with', async () => {
    const user = userEvent.setup()
    render(<LanguageMenu />)

    await user.click(screen.getByRole('button'))
    expect(
      screen.getAllByRole('menuitem').map((item) => item.textContent),
    ).toEqual(["O'zbekcha", 'Русский', 'English'])
  })

  it('switches the language in place and stamps the document', async () => {
    const user = userEvent.setup()
    render(<LanguageMenu />)

    await user.click(screen.getByRole('button'))
    await user.click(screen.getByRole('menuitem', { name: 'Русский' }))

    await waitFor(() => expect(i18n.resolvedLanguage).toBe('ru'))
    expect(document.documentElement.getAttribute('lang')).toBe('ru')
    await i18n.changeLanguage('uz')
  })
})

describe('the theme menu', () => {
  it('offers exactly five palettes', async () => {
    const user = userEvent.setup()
    render(<ThemeMenu />)

    await user.click(screen.getByRole('button'))
    const items = screen.getAllByRole('menuitem')
    expect(items).toHaveLength(5)
    expect(items.map((item) => item.textContent)).toEqual([
      'Yorug‘',
      'Tungi',
      'Galaktika',
      'Amber',
      'Zumrad',
    ])
    expect(THEMES).toHaveLength(5)
  })

  it('applies the theme to the document and remembers it', async () => {
    const user = userEvent.setup()
    render(<ThemeMenu />)

    await user.click(screen.getByRole('button'))
    await user.click(screen.getByRole('menuitem', { name: /Galaktika/ }))

    expect(document.documentElement.getAttribute('data-theme')).toBe('violet')
    expect(localStorage.getItem('davomat.theme')).toBe('violet')
    // A reload would read the same value back.
    expect(readStoredTheme()).toBe('violet')
  })

  it('marks the current palette', async () => {
    const user = userEvent.setup()
    useThemeStore.setState({ theme: 'emerald' })
    render(<ThemeMenu />)

    await user.click(screen.getByRole('button'))
    const current = screen.getByRole('menuitem', { name: /Zumrad/ })
    expect(within(current).getByText('Zumrad')).toBeInTheDocument()
    expect(current.className).toContain('bg-brand-50')
  })

  it('falls back to light when storage holds nonsense', () => {
    localStorage.setItem('davomat.theme', 'chartreuse')
    expect(readStoredTheme()).toBe('light')
  })
})

describe('the navbar on a phone', () => {
  function renderBar() {
    return render(
      <MemoryRouter initialEntries={['/']}>
        <Topbar sidebarOpen={false} onToggleSidebar={() => {}} />
        <Routes>
          <Route path="/davomat" element={<span>davomat page</span>} />
          <Route path="/" element={<span>home page</span>} />
        </Routes>
      </MemoryRouter>,
    )
  }

  /**
   * The field used to sit on a permanent second row, costing a row of content
   * on every page to save one tap on the few where it is used.
   */
  it('keeps the search behind a button until it is asked for', async () => {
    const user = userEvent.setup()
    renderBar()

    // The `md` field is in the markup but hidden by CSS; the phone's is not
    // rendered at all until the button is pressed.
    expect(screen.getAllByRole('combobox')).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: i18n.t('common.search') }))
    expect(screen.getAllByRole('combobox')).toHaveLength(2)
  })

  it('gives the row back once the search has taken you somewhere', async () => {
    const user = userEvent.setup()
    renderBar()

    await user.click(screen.getByRole('button', { name: i18n.t('common.search') }))
    const field = screen.getAllByRole('combobox')[1]!
    await user.type(field, 'dav')
    await user.click(await screen.findByRole('option', { name: /Davomat/ }))

    expect(await screen.findByText('davomat page')).toBeInTheDocument()
    expect(screen.getAllByRole('combobox')).toHaveLength(1)
  })
})
