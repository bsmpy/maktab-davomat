import { api } from './client'

export interface ServerClock {
  now: string
  date: string
  weekday: number
  offset_seconds: number
  is_shifted: boolean
}

export const clockApi = {
  async read(): Promise<ServerClock> {
    const { data } = await api.get<ServerClock>('/clock/')
    return data
  },
}
