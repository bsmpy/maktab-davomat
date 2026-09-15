import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/errors'
import { LoginPage } from '@/pages/LoginPage'
import { useAuthStore } from '@/store/authStore'

const navigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

function renderPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

describe('login screen', () => {
  beforeEach(() => {
    useAuthStore.setState({ status: 'anonymous', user: null })
  })

  it('accepts a username or a phone number', () => {
    renderPage()
    expect(screen.getByLabelText('Login yoki telefon')).toBeInTheDocument()
    expect(screen.getByLabelText('Parol')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Kirish' })).toBeInTheDocument()
  })

  it('signs in and lands on the dashboard', async () => {
    const login = vi.fn().mockResolvedValue({ username: 'a.valiyev' })
    useAuthStore.setState({ login } as never)

    renderPage()
    await userEvent.type(screen.getByLabelText('Login yoki telefon'), 'a.valiyev')
    await userEvent.type(screen.getByLabelText('Parol'), 'Demo!2026parol')
    await userEvent.click(screen.getByRole('button', { name: 'Kirish' }))

    await waitFor(() => expect(login).toHaveBeenCalledWith('a.valiyev', 'Demo!2026parol'))
    expect(navigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('shows the server message on bad credentials', async () => {
    const login = vi.fn().mockRejectedValue(
      new ApiError(
        { code: 'INVALID_CREDENTIALS', message: "Login yoki parol noto'g'ri.", fields: {} },
        401,
      ),
    )
    useAuthStore.setState({ login } as never)

    renderPage()
    await userEvent.type(screen.getByLabelText('Login yoki telefon'), 'a.valiyev')
    await userEvent.type(screen.getByLabelText('Parol'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Kirish' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Login yoki parol noto'g'ri.")
  })

  it('surfaces per-field validation errors next to the field', async () => {
    const login = vi.fn().mockRejectedValue(
      new ApiError(
        {
          code: 'VALIDATION_ERROR',
          message: 'Xatolik',
          fields: { password: ['Bu maydon majburiy.'] },
        },
        400,
      ),
    )
    useAuthStore.setState({ login } as never)

    renderPage()
    await userEvent.type(screen.getByLabelText('Login yoki telefon'), 'a.valiyev')
    await userEvent.type(screen.getByLabelText('Parol'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Kirish' }))

    expect(await screen.findByText('Bu maydon majburiy.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('lets the user reveal the password', async () => {
    renderPage()
    const password = screen.getByLabelText('Parol')
    expect(password).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: "Parolni ko'rsatish" }))
    expect(password).toHaveAttribute('type', 'text')
  })
})
