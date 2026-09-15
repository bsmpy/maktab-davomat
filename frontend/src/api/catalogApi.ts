import type { ClassGroup, Grade, School } from '@/types/api'

import { api } from './client'

/** Public catalogue used by the registration wizard — nothing is hardcoded. */
export const catalogApi = {
  async schools(): Promise<School[]> {
    const { data } = await api.get<School[]>('/schools/')
    return data
  },

  async grades(): Promise<Grade[]> {
    const { data } = await api.get<Grade[]>('/grades/')
    return data
  },

  async classGroups(gradeId: string): Promise<ClassGroup[]> {
    const { data } = await api.get<ClassGroup[]>('/class-groups/', {
      params: { grade: gradeId },
    })
    return data
  },
}
