import type { Notification, Paginated } from '@/types/api'

import { api } from './client'

export const notificationApi = {
  async list(params?: {
    page?: number
    is_read?: boolean
    student?: string
  }): Promise<Paginated<Notification>> {
    const { data } = await api.get<Paginated<Notification>>('/notifications/', { params })
    return data
  },

  async unreadCount(): Promise<number> {
    const { data } = await api.get<{ unread_count: number }>('/notifications/unread-count/')
    return data.unread_count
  },

  async markAsRead(ids: string[]): Promise<number> {
    const { data } = await api.post<{ updated: number }>('/notifications/mark-as-read/', { ids })
    return data.updated
  },

  async markAllAsRead(): Promise<number> {
    const { data } = await api.post<{ updated: number }>('/notifications/mark-all-as-read/', {})
    return data.updated
  },
}
