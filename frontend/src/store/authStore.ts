import { create } from 'zustand'

import { authApi } from '@/api/authApi'
import { refreshAccessToken, setAccessToken, setAuthLostHandler } from '@/api/client'
import { toApiError } from '@/api/errors'
import type { LoginResponse, Profile, Role, User } from '@/types/api'

type AuthStatus = 'unknown' | 'authenticating' | 'authenticated' | 'anonymous'

interface AuthState {
  status: AuthStatus
  user: User | Profile | null
  /**
   * Bootstrapping runs once on mount: if the browser still holds a valid
   * refresh cookie the session is restored without the user retyping anything.
   */
  bootstrap: () => Promise<void>
  login: (login: string, password: string) => Promise<User>
  /** Adopts the tokens a completed registration / password reset returned. */
  adoptSession: (response: LoginResponse) => void
  logout: () => Promise<void>
  refreshProfile: () => Promise<void>
  setUser: (user: User | Profile) => void
  /**
   * Work through a different one of your own roles.
   *
   * No sign-out, no second account: the server writes the active role onto the
   * account, hands back fresh tokens and the new permission list, and the
   * whole cabinet — rail, routes, buttons, API answers — follows from the user
   * object being replaced here. Because it is stored server-side, a reload
   * comes back in the same role.
   */
  switchRole: (role: Role) => Promise<User | Profile>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: 'unknown',
  user: null,

  async bootstrap() {
    if (get().status === 'authenticating') return
    set({ status: 'authenticating' })
    try {
      await refreshAccessToken()
      const profile = await authApi.me()
      set({ status: 'authenticated', user: profile })
    } catch {
      setAccessToken(null)
      set({ status: 'anonymous', user: null })
    }
  },

  async login(login, password) {
    const response = await authApi.login(login, password)
    setAccessToken(response.access)
    set({ status: 'authenticated', user: response.user })
    return response.user
  },

  adoptSession(response) {
    setAccessToken(response.access)
    set({ status: 'authenticated', user: response.user })
  },

  async logout() {
    try {
      await authApi.logout()
    } catch (error) {
      // A dead session is already "logged out" as far as the user is concerned.
      if (import.meta.env.DEV) console.warn('logout failed', toApiError(error).code)
    } finally {
      setAccessToken(null)
      set({ status: 'anonymous', user: null })
    }
  },

  async refreshProfile() {
    const profile = await authApi.me()
    set({ user: profile })
  },

  async switchRole(role) {
    const current = get().user
    if (!current || current.active_role === role) return current!

    const response = await authApi.switchRole(role)
    setAccessToken(response.access)
    set({ status: 'authenticated', user: response.user })
    return response.user
  },

  setUser(user) {
    set({ user })
  },
}))

/** A failed silent refresh drops the session instead of leaving a broken UI. */
setAuthLostHandler(() => {
  setAccessToken(null)
  useAuthStore.setState({ status: 'anonymous', user: null })
})
