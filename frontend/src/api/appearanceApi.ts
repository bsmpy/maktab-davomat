import type { AppearanceSettings } from '@/types/api'

import { api } from './client'

/**
 * The interface switches everybody shares.
 *
 * Readable by anyone signed in — a browser has to know what is on offer before
 * it draws the theme menu or starts the particles. Writable only by DEVELOPER
 * and SUPER_ADMIN; the server refuses the rest whatever the client believes.
 */
export const appearanceApi = {
  async get(): Promise<AppearanceSettings> {
    const { data } = await api.get<AppearanceSettings>('/appearance/')
    return data
  },

  async update(patch: {
    multi_theme?: boolean
    particles?: boolean
  }): Promise<AppearanceSettings> {
    const { data } = await api.patch<AppearanceSettings>('/appearance/', patch)
    return data
  },
}
