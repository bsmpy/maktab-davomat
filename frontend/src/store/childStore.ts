import { create } from 'zustand'

import { childrenApi } from '@/api/childrenApi'
import { toApiError } from '@/api/errors'
import type { Child } from '@/types/api'

const ACTIVE_CHILD_KEY = 'davomat.activeChildId'

function readStoredChildId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_CHILD_KEY)
  } catch {
    return null
  }
}

function storeChildId(id: string | null): void {
  try {
    if (id) localStorage.setItem(ACTIVE_CHILD_KEY, id)
    else localStorage.removeItem(ACTIVE_CHILD_KEY)
  } catch {
    /* private mode – the switcher just won't be remembered */
  }
}

interface ChildState {
  children: Child[]
  activeChildId: string | null
  loading: boolean
  error: string | null
  load: (options?: { force?: boolean }) => Promise<void>
  setActiveChild: (id: string) => void
  reset: () => void
  activeChild: () => Child | null
}

export const useChildStore = create<ChildState>((set, get) => ({
  children: [],
  // Only an id — never anything sensitive — is persisted.
  activeChildId: readStoredChildId(),
  loading: false,
  error: null,

  async load(options) {
    if (get().loading) return
    if (!options?.force && get().children.length > 0) return

    set({ loading: true, error: null })
    try {
      const children = await childrenApi.list()
      const stored = get().activeChildId
      const active =
        children.find((child) => child.id === stored)?.id ?? children[0]?.id ?? null
      storeChildId(active)
      set({ children, activeChildId: active, loading: false })
    } catch (error) {
      set({ loading: false, error: toApiError(error).message })
    }
  },

  setActiveChild(id) {
    storeChildId(id)
    set({ activeChildId: id })
  },

  reset() {
    storeChildId(null)
    set({ children: [], activeChildId: null, error: null, loading: false })
  },

  activeChild() {
    const { children, activeChildId } = get()
    return children.find((child) => child.id === activeChildId) ?? null
  },
}))

/** Selector helper so components re-render on the child object, not the whole store. */
export function useActiveChild(): Child | null {
  return useChildStore((state) =>
    state.children.find((child) => child.id === state.activeChildId) ?? null,
  )
}
