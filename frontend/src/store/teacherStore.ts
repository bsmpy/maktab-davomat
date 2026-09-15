import { create } from 'zustand'

import { toApiError } from '@/api/errors'
import { teachingApi } from '@/api/teachingApi'
import type { TeacherProfile } from '@/types/api'

/**
 * The signed-in teacher's own record.
 *
 * The sidebar needs the school, the navbar needs the photo and the short name,
 * and the profile page needs all of it — one fetch, shared, instead of three.
 */
interface TeacherState {
  profile: TeacherProfile | null
  loading: boolean
  error: string | null
  load: (options?: { force?: boolean }) => Promise<void>
  set: (profile: TeacherProfile) => void
  clear: () => void
}

export const useTeacherStore = create<TeacherState>((set, get) => ({
  profile: null,
  loading: false,
  error: null,

  async load(options = {}) {
    if (get().loading) return
    if (get().profile && !options.force) return
    set({ loading: true, error: null })
    try {
      set({ profile: await teachingApi.profile(), loading: false })
    } catch (error) {
      set({ error: toApiError(error).message, loading: false })
    }
  },

  set(profile) {
    set({ profile })
  },

  clear() {
    set({ profile: null, error: null })
  },
}))
