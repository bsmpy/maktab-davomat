import type { LoginResponse, PasswordResetStart, Profile, Role } from '@/types/api'

import { api } from './client'

export const authApi = {
  async login(login: string, password: string): Promise<LoginResponse> {
    const { data } = await api.post<LoginResponse>('/auth/login/', { login, password })
    return data
  },

  /** Uses the HttpOnly refresh cookie; returns a fresh access token. */
  async refresh(): Promise<LoginResponse> {
    const { data } = await api.post<LoginResponse>('/auth/refresh/', {})
    return data
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout/', {})
  },

  async me(): Promise<Profile> {
    const { data } = await api.get<Profile>('/auth/me/')
    return data
  },

  /**
   * Switch which of your own roles you are working through.
   *
   * The server refuses any role the account does not hold, so this cannot be
   * used to climb; it answers with new tokens and the profile the rest of the
   * cabinet re-renders from.
   */
  async switchRole(role: Role): Promise<LoginResponse & { user: Profile }> {
    const { data } = await api.post<LoginResponse & { user: Profile }>(
      '/auth/active-role/',
      { role },
    )
    return data
  },

  /**
   * Also sets the *first* password: an account created through the bot has
   * none, so `current_password` is omitted in that case.
   */
  async changePassword(payload: {
    current_password?: string
    password: string
    password_confirm: string
  }): Promise<LoginResponse> {
    const { data } = await api.post<LoginResponse>('/auth/password/change/', payload)
    return data
  },

  /** Exchange the bot's one-time link for a real session. */
  async loginWithTicket(ticket: string): Promise<LoginResponse & { must_set_password: boolean }> {
    const { data } = await api.post<LoginResponse & { must_set_password: boolean }>(
      '/auth/telegram/',
      { ticket },
    )
    return data
  },

  async requestPasswordReset(login: string): Promise<PasswordResetStart> {
    const { data } = await api.post<PasswordResetStart>('/auth/password/reset/request/', {
      login,
    })
    return data
  },

  async verifyPasswordReset(sessionToken: string, code: string): Promise<{ verified: boolean }> {
    const { data } = await api.post('/auth/password/reset/verify/', {
      session_token: sessionToken,
      code,
    })
    return data
  },

  async confirmPasswordReset(payload: {
    session_token: string
    password: string
    password_confirm: string
  }): Promise<LoginResponse> {
    const { data } = await api.post<LoginResponse>('/auth/password/reset/confirm/', payload)
    return data
  },
}
