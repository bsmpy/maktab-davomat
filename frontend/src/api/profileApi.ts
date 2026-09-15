import type { Profile, TelegramLinkCode, TelegramStatus } from '@/types/api'

import { api } from './client'

export const profileApi = {
  async me(): Promise<Profile> {
    const { data } = await api.get<Profile>('/auth/me/')
    return data
  },
}

export const telegramApi = {
  async status(): Promise<TelegramStatus> {
    const { data } = await api.get<TelegramStatus>('/telegram/status/')
    return data
  },

  async requestLinkCode(): Promise<TelegramLinkCode> {
    const { data } = await api.post<TelegramLinkCode>('/telegram/link-code/', {})
    return data
  },

  async unlink(): Promise<TelegramStatus> {
    const { data } = await api.post<TelegramStatus>('/telegram/unlink/', {})
    return data
  },

  async toggleNotifications(enabled: boolean): Promise<TelegramStatus> {
    const { data } = await api.post<TelegramStatus>('/telegram/notifications/', { enabled })
    return data
  },
}
