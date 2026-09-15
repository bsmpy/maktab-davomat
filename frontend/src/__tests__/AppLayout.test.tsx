import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AppLayout } from '@/layouts/AppLayout'
import { useAuthStore } from '@/store/authStore'
import { useChildStore } from '@/store/childStore'
import type { Role } from '@/types/api'

import { makeUser } from './session'

vi.mock('@/api/notificationApi', () => ({
  notificationApi: { unreadCount: () => Promise.resolve(0) },
}))

vi.mock('@/api/teachingApi', () => ({
  teachingApi: { profile: () => Promise.reject(new Error('no register row')) },
}))

function renderShell(role: Role) {
  useAuthStore.setState({ status: 'authenticated', user: makeUser(role) })
  useChildStore.setState({
    children: [],
    activeChildId: null,
    loading: false,
    error: null,
    // The shell calls this on mount; an empty register resolves to nothing.
    load: () => Promise.resolve(),
  })
  return render(
    <MemoryRouter>
      <AppLayout />
    </MemoryRouter>,
  )
}

describe('cabinet shell with an empty register', () => {
  beforeEach(() => {
    useChildStore.setState({ children: [], activeChildId: null, loading: false, error: null })
  })

  it('tells a parent that no child is linked to them', async () => {
    renderShell('OTA-ONA')
    expect(
      await screen.findByText('Sizga farzand biriktirilmagan'),
    ).toBeInTheDocument()
  })

  /**
   * The bootstrapping deadlock: on a fresh install nobody has children yet, so
   * locking staff out of the shell would leave no way to reach the admin
   * console and add the first pupil.
   */
  it.each(['DEVELOPER', 'SUPER_ADMIN', 'ADMIN', 'TEACHER'] as const)(
    'lets a %s into the cabinet anyway',
    async (role) => {
      renderShell(role)
      // The navigation rendered, so the admin console is reachable. Awaiting it
      // also lets the shell's unread-count fetch settle inside act().
      expect((await screen.findAllByRole('navigation')).length).toBeGreaterThan(0)
      expect(screen.queryByText('Sizga farzand biriktirilmagan')).not.toBeInTheDocument()
    },
  )
})
