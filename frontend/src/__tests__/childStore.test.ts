import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useChildStore } from '@/store/childStore'
import type { Child } from '@/types/api'

vi.mock('@/api/childrenApi', () => ({
  childrenApi: { list: vi.fn(), dashboard: vi.fn(), detail: vi.fn(), schedule: vi.fn() },
}))

const { childrenApi } = await import('@/api/childrenApi')

function child(id: string, name: string, group: string): Child {
  return {
    id,
    first_name: name,
    last_name: 'Valiyev',
    middle_name: '',
    full_name: `Valiyev ${name}`,
    display_name: `${name} Valiyev`,
    initials: name[0] + 'V',
    class_group: group,
    class_group_id: `cg-${group}`,
    grade_level: Number(group.split('-')[0]),
    school: 'Test',
    relation: 'FATHER',
  }
}

const CHILDREN = [
  child('c1', 'Azizbek', '7-A'),
  child('c2', 'Madina', '3-B'),
  child('c3', 'Sardor', '1-A'),
]

describe('child switcher store', () => {
  beforeEach(() => {
    localStorage.clear()
    useChildStore.setState({ children: [], activeChildId: null, loading: false, error: null })
  })

  it('loads every child and selects the first by default', async () => {
    vi.mocked(childrenApi.list).mockResolvedValue(CHILDREN)
    await useChildStore.getState().load()

    expect(useChildStore.getState().children).toHaveLength(3)
    expect(useChildStore.getState().activeChildId).toBe('c1')
  })

  it('remembers the selected child across reloads', async () => {
    vi.mocked(childrenApi.list).mockResolvedValue(CHILDREN)
    await useChildStore.getState().load()
    useChildStore.getState().setActiveChild('c2')

    useChildStore.setState({ children: [], activeChildId: 'c2', loading: false })
    await useChildStore.getState().load({ force: true })

    expect(useChildStore.getState().activeChildId).toBe('c2')
    expect(useChildStore.getState().activeChild()?.display_name).toBe('Madina Valiyev')
  })

  it('falls back to the first child when the remembered one is gone', async () => {
    localStorage.setItem('davomat.activeChildId', 'no-longer-mine')
    useChildStore.setState({ activeChildId: 'no-longer-mine' })
    vi.mocked(childrenApi.list).mockResolvedValue(CHILDREN)

    await useChildStore.getState().load({ force: true })
    expect(useChildStore.getState().activeChildId).toBe('c1')
  })

  it('surfaces a load failure instead of hanging', async () => {
    vi.mocked(childrenApi.list).mockRejectedValue(new Error('boom'))
    await useChildStore.getState().load({ force: true })

    expect(useChildStore.getState().loading).toBe(false)
    expect(useChildStore.getState().error).toBeTruthy()
  })
})
