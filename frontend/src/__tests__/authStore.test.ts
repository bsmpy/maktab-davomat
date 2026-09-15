import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAccessToken, setAccessToken } from '@/api/client'
import { useAuthStore } from '@/store/authStore'

vi.mock('@/api/authApi', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
    refresh: vi.fn(),
  },
}))

const { authApi } = await import('@/api/authApi')

const { makeUser } = await import('./session')

const USER = makeUser('OTA-ONA', {
  full_name: 'Valiyev Alisher',
  first_name: 'Alisher',
  last_name: 'Valiyev',
})

describe('auth store', () => {
  beforeEach(() => {
    setAccessToken(null)
    useAuthStore.setState({ status: 'unknown', user: null })
  })

  it('keeps the access token in memory, never in storage', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access: 'access-token',
      expires_in: 900,
      csrf: 'csrf-token',
      user: USER,
    })

    await useAuthStore.getState().login('a.valiyev', 'secret')

    expect(getAccessToken()).toBe('access-token')
    expect(useAuthStore.getState().status).toBe('authenticated')
    expect(localStorage.getItem('access')).toBeNull()
    expect(JSON.stringify(localStorage)).not.toContain('access-token')
  })

  it('drops the session when logging out, even if the API call fails', async () => {
    setAccessToken('access-token')
    useAuthStore.setState({ status: 'authenticated', user: USER })
    vi.mocked(authApi.logout).mockRejectedValue(new Error('network down'))

    await useAuthStore.getState().logout()

    expect(getAccessToken()).toBeNull()
    expect(useAuthStore.getState().status).toBe('anonymous')
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('falls back to anonymous when the refresh cookie is gone', async () => {
    vi.mocked(authApi.me).mockRejectedValue(new Error('401'))
    await useAuthStore.getState().bootstrap()
    expect(useAuthStore.getState().status).toBe('anonymous')
  })
})
