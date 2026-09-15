import type { Child, Dashboard } from '@/types/api'

import { api } from './client'

export const childrenApi = {
  async list(): Promise<Child[]> {
    const { data } = await api.get<{ count: number; results: Child[] }>('/children/')
    return data.results
  },

  async detail(childId: string): Promise<Child> {
    const { data } = await api.get<Child>(`/children/${childId}/`)
    return data
  },

  async dashboard(childId: string): Promise<Dashboard> {
    const { data } = await api.get<Dashboard>(`/children/${childId}/dashboard/`)
    return data
  },
}
