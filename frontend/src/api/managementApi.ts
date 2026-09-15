import type {
  Choice,
  CuratorAssignment,
  CuratorSection,
  GuardianRow,
  ManagedClassGroup,
  ManagedGrade,
  ManagedStudent,
  Paginated,
  ProvisionedUser,
  StaffUser,
  StudentInput,
} from '@/types/api'

import { api } from './client'

/**
 * The ADMIN cabinet's write surface. Every call is `IsSchoolAdmin` server-side
 * and scoped to the caller's school — the UI role only decides what to render.
 */
export const managementApi = {
  async grades(): Promise<ManagedGrade[]> {
    const { data } = await api.get<{ results: ManagedGrade[] }>('/management/grades/')
    return data.results
  },

  async createGrade(level: number): Promise<ManagedGrade> {
    const { data } = await api.post<ManagedGrade>('/management/grades/', { level })
    return data
  },

  /** Retires the parallel together with its groups and their pupils. */
  async deleteGrade(id: string): Promise<void> {
    await api.delete(`/management/grades/${id}/`)
  },

  async classGroups(gradeId?: string): Promise<ManagedClassGroup[]> {
    const { data } = await api.get<{ results: ManagedClassGroup[] }>(
      '/management/class-groups/',
      { params: gradeId ? { grade: gradeId } : undefined },
    )
    return data.results
  },

  async createClassGroup(payload: {
    grade?: string
    level?: number
    name: string
    room?: string
  }): Promise<ManagedClassGroup> {
    const { data } = await api.post<ManagedClassGroup>('/management/class-groups/', payload)
    return data
  },

  async updateClassGroup(
    id: string,
    payload: { name?: string; room?: string },
  ): Promise<ManagedClassGroup> {
    const { data } = await api.patch<ManagedClassGroup>(
      `/management/class-groups/${id}/`,
      payload,
    )
    return data
  },

  async deleteClassGroup(id: string): Promise<void> {
    await api.delete(`/management/class-groups/${id}/`)
  },

  async students(params: {
    class_group?: string
    q?: string
    registered?: 'yes' | 'no'
    page?: number
  }): Promise<Paginated<ManagedStudent>> {
    const { data } = await api.get<Paginated<ManagedStudent>>('/management/students/', {
      params,
    })
    return data
  },

  async student(id: string): Promise<ManagedStudent> {
    const { data } = await api.get<ManagedStudent>(`/management/students/${id}/`)
    return data
  },

  async createStudent(payload: StudentInput): Promise<ManagedStudent> {
    const { data } = await api.post<ManagedStudent>('/management/students/', payload)
    return data
  },

  async updateStudent(id: string, payload: Partial<StudentInput>): Promise<ManagedStudent> {
    const { data } = await api.patch<ManagedStudent>(`/management/students/${id}/`, payload)
    return data
  },

  async deleteStudent(id: string): Promise<void> {
    await api.delete(`/management/students/${id}/`)
  },

  /** Saves the face photo and queues the push to every active terminal. */
  async uploadPhoto(id: string, file: File): Promise<{ photo: string }> {
    const form = new FormData()
    form.append('photo', file)
    const { data } = await api.post<{ photo: string }>(
      `/management/students/${id}/photo/`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return data
  },

  async relations(): Promise<Choice[]> {
    const { data } = await api.get<{ results: Choice[] }>('/management/relations/')
    return data.results
  },
}

/**
 * Staff accounts. Only SUPER_ADMIN and DEVELOPER reach these; which *roles*
 * each may touch is decided server-side and echoed back in `assignable_roles`.
 */
export const userApi = {
  async list(params: { role?: string; q?: string } = {}): Promise<{
    assignable_roles: Choice[]
    results: StaffUser[]
  }> {
    const { data } = await api.get('/management/users/', { params })
    return data
  },

  async create(payload: {
    last_name: string
    first_name: string
    middle_name?: string
    /** One person, several roles — the form sends every box that was ticked. */
    roles: string[]
    phone?: string
    school?: string
  }): Promise<ProvisionedUser> {
    const { data } = await api.post<ProvisionedUser>('/management/users/', payload)
    return data
  },

  async update(
    id: number,
    payload: Partial<{
      last_name: string
      first_name: string
      middle_name: string
      /** Replaces the whole set; leave it out to change nothing about roles. */
      roles: string[]
      phone: string
      is_active: boolean
    }>,
  ): Promise<StaffUser> {
    const { data } = await api.patch<StaffUser>(`/management/users/${id}/`, payload)
    return data
  },

  /**
   * Remove an account.
   *
   * The server deletes the row when nothing in the history points at it and
   * disables the account when something does — either way the login stops
   * working at once. The answer says which of the two happened.
   */
  async remove(id: number): Promise<{ deleted: boolean; disabled: boolean; detail: string }> {
    const { data } = await api.delete<{
      deleted: boolean
      disabled: boolean
      detail: string
    }>(`/management/users/${id}/`)
    return data
  },

  /**
   * Issue a fresh one-off password. Existing passwords are hashes and cannot be
   * read back by anyone — this replaces one and shows it a single time.
   */
  async resetPassword(id: number): Promise<ProvisionedUser> {
    const { data } = await api.post<ProvisionedUser>(
      `/management/users/${id}/reset-password/`,
      {},
    )
    return data
  },
}

/**
 * Kuratorlar — a person, a class group, and the role that follows.
 *
 * Assigning a group grants CURATOR; removing somebody's last group takes it
 * back. Both happen server-side, so the panel only has to say what changed.
 */
export const curatorApi = {
  async list(): Promise<CuratorSection> {
    const { data } = await api.get<CuratorSection>('/management/curators/')
    return data
  },

  async assign(userId: number, classGroupId: string): Promise<CuratorAssignment> {
    const { data } = await api.post<CuratorAssignment>('/management/curators/', {
      user: userId,
      class_group: classGroupId,
    })
    return data
  },

  async changeGroup(id: string, classGroupId: string): Promise<CuratorAssignment> {
    const { data } = await api.patch<CuratorAssignment>(`/management/curators/${id}/`, {
      class_group: classGroupId,
    })
    return data
  },

  async remove(id: string): Promise<{ role_revoked: boolean }> {
    const { data } = await api.delete<{ role_revoked: boolean }>(
      `/management/curators/${id}/`,
    )
    return data
  },
}

/** The parent register, and who out of it has claimed an account. */
export const guardianApi = {
  async list(params: {
    registered?: 'yes' | 'no'
    class_group?: string
    q?: string
    page?: number
  }): Promise<Paginated<GuardianRow>> {
    const { data } = await api.get<Paginated<GuardianRow>>('/management/guardians/', {
      params,
    })
    return data
  },
}
