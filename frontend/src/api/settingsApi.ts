import type {
  Choice,
  DailyPresence,
  Integration,
  IntegrationKind,
  IntegrationTestResult,
  Paginated,
  SettingsOverview,
  Terminal,
  TerminalEvent,
  TerminalPayload,
  TerminalPerson,
  TerminalTestResult,
} from '@/types/api'

import { api } from './client'

export const settingsApi = {
  async overview(): Promise<SettingsOverview> {
    const { data } = await api.get<SettingsOverview>('/settings/')
    return data
  },

  async integrations(): Promise<{ kinds: Choice[]; results: Integration[] }> {
    const { data } = await api.get('/settings/integrations/')
    return data
  },

  async integration(kind: IntegrationKind): Promise<Integration> {
    const { data } = await api.get<Integration>(`/settings/integrations/${kind}/`)
    return data
  },

  /**
   * Only send the secrets that changed. An omitted key keeps its stored value,
   * so the UI never has to hold a real credential to save a config change.
   */
  async saveIntegration(
    kind: IntegrationKind,
    payload: {
      is_enabled?: boolean
      config?: Record<string, unknown>
      secrets?: Record<string, string | null>
    },
  ): Promise<Integration> {
    const { data } = await api.put<Integration>(`/settings/integrations/${kind}/`, payload)
    return data
  },

  async testIntegration(kind: IntegrationKind): Promise<IntegrationTestResult> {
    const { data } = await api.post<IntegrationTestResult>(
      `/settings/integrations/${kind}/test/`,
      {},
    )
    return data
  },
}

export const terminalApi = {
  async list(): Promise<{ directions: Choice[]; vendors: Choice[]; results: Terminal[] }> {
    const { data } = await api.get('/settings/terminals/')
    return data
  },

  async create(payload: TerminalPayload): Promise<Terminal> {
    const { data } = await api.post<Terminal>('/settings/terminals/', payload)
    return data
  },

  async update(id: string, payload: Partial<TerminalPayload>): Promise<Terminal> {
    const { data } = await api.patch<Terminal>(`/settings/terminals/${id}/`, payload)
    return data
  },

  async remove(id: string): Promise<void> {
    await api.delete(`/settings/terminals/${id}/`)
  },

  async test(id: string): Promise<TerminalTestResult> {
    const { data } = await api.post<TerminalTestResult>(`/settings/terminals/${id}/test/`, {})
    return data
  },

  /** Try credentials before the terminal record exists. */
  async testConnection(payload: {
    host: string
    port: number
    use_https: boolean
    username: string
    password: string
  }): Promise<TerminalTestResult> {
    const { data } = await api.post<TerminalTestResult>(
      '/settings/terminals/test-connection/',
      payload,
    )
    return data
  },

  async sync(id: string, start: string, end?: string) {
    const { data } = await api.post(`/settings/terminals/${id}/sync/`, { start, end })
    return data
  },

  async rotateToken(id: string): Promise<Terminal> {
    const { data } = await api.post<Terminal>(`/settings/terminals/${id}/rotate-token/`, {})
    return data
  },

  async events(params?: {
    terminal?: string
    date?: string
    student?: string
    page?: number
  }): Promise<Paginated<TerminalEvent>> {
    const { data } = await api.get<Paginated<TerminalEvent>>('/settings/terminals/events/', {
      params,
    })
    return data
  },
}

export const faceIdApi = {
  async people(params?: { class_group?: string; page?: number }): Promise<Paginated<TerminalPerson>> {
    const { data } = await api.get<Paginated<TerminalPerson>>('/settings/face-id/people/', {
      params,
    })
    return data
  },

  async enroll(payload: { students?: string[]; class_group?: string; all?: boolean }) {
    const { data } = await api.post('/settings/face-id/enroll/', payload)
    return data
  },

  async uploadPhoto(studentId: string, file: File) {
    const form = new FormData()
    form.append('photo', file)
    const { data } = await api.post(`/settings/face-id/students/${studentId}/photo/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
}

export const presenceApi = {
  async list(params: { date?: string; class_group?: string; page?: number }): Promise<
    Paginated<DailyPresence>
  > {
    const { data } = await api.get<Paginated<DailyPresence>>('/settings/presence/', { params })
    return data
  },

  async recompute(payload: { date: string; class_group?: string; school?: string }) {
    const { data } = await api.post('/settings/presence/recompute/', payload)
    return data
  },
}
