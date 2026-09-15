import type {
  AuditEntry,
  Choice,
  ImportReport,
  ManagedAcademicYear,
  ManagedHoliday,
  ManagedPosition,
  ManagedSchool,
  ManagedStaff,
  ManagedSubject,
  ManagedTeacher,
  PersonProfile,
  Paginated,
  PositionPayload,
  SchoolOverview,
  ScheduleEntry,
  StaffPayload,
  TeacherPayload,
} from '@/types/api'

import { api } from './client'

/**
 * The admin console at `/admin`. This is what replaced the Django admin — same
 * `/api/v1/management/` prefix, same role checks, no second login surface.
 */
export const adminApi = {
  /** Register size, today at the gate, and the state of the devices. */
  async overview(): Promise<SchoolOverview> {
    const { data } = await api.get<SchoolOverview>('/management/overview/')
    return data
  },

  /** The whole register as a workbook, as a Blob the browser can save. */
  async exportRegister(): Promise<Blob> {
    const { data } = await api.get('/management/export/', { responseType: 'blob' })
    return data as Blob
  },

  // --- school profile -----------------------------------------------------
  async schools(): Promise<ManagedSchool[]> {
    const { data } = await api.get<{ results: ManagedSchool[] }>('/management/schools/')
    return data.results
  },

  async createSchool(payload: { name: string; short_name?: string }): Promise<ManagedSchool> {
    const { data } = await api.post<ManagedSchool>('/management/schools/', payload)
    return data
  },

  async updateSchool(
    id: string,
    payload: Partial<Omit<ManagedSchool, 'id' | 'students_count' | 'class_groups_count'>>,
  ): Promise<ManagedSchool> {
    const { data } = await api.patch<ManagedSchool>(`/management/schools/${id}/`, payload)
    return data
  },

  // --- academic years -----------------------------------------------------
  async academicYears(): Promise<ManagedAcademicYear[]> {
    const { data } = await api.get<{ results: ManagedAcademicYear[] }>(
      '/management/academic-years/',
    )
    return data.results
  },

  async createAcademicYear(payload: {
    name: string
    start_date: string
    end_date: string
    is_current?: boolean
  }): Promise<ManagedAcademicYear> {
    const { data } = await api.post<ManagedAcademicYear>(
      '/management/academic-years/',
      payload,
    )
    return data
  },

  async updateAcademicYear(
    id: string,
    payload: Partial<{ name: string; start_date: string; end_date: string; is_current: boolean }>,
  ): Promise<ManagedAcademicYear> {
    const { data } = await api.patch<ManagedAcademicYear>(
      `/management/academic-years/${id}/`,
      payload,
    )
    return data
  },

  async deleteAcademicYear(id: string): Promise<void> {
    await api.delete(`/management/academic-years/${id}/`)
  },

  // --- holidays -----------------------------------------------------------
  async holidays(): Promise<ManagedHoliday[]> {
    const { data } = await api.get<{ results: ManagedHoliday[] }>('/management/holidays/')
    return data.results
  },

  async createHoliday(payload: {
    date: string
    name: string
    is_working_day?: boolean
  }): Promise<ManagedHoliday> {
    const { data } = await api.post<ManagedHoliday>('/management/holidays/', payload)
    return data
  },

  async deleteHoliday(id: string): Promise<void> {
    await api.delete(`/management/holidays/${id}/`)
  },

  // --- subjects -----------------------------------------------------------
  async subjects(): Promise<ManagedSubject[]> {
    const { data } = await api.get<{ results: ManagedSubject[] }>('/management/subjects/')
    return data.results
  },

  async createSubject(payload: {
    name: string
    class_group?: string | null
    short_name?: string
    color?: string
  }): Promise<ManagedSubject> {
    const { data } = await api.post<ManagedSubject>('/management/subjects/', payload)
    return data
  },

  async deleteSubject(id: string): Promise<void> {
    await api.delete(`/management/subjects/${id}/`)
  },

  // --- dars jadvali -------------------------------------------------------
  async schedule(classGroupId: string, weekday?: number): Promise<ScheduleEntry[]> {
    const { data } = await api.get<{ results: ScheduleEntry[] }>('/management/schedule/', {
      params: { class_group: classGroupId, ...(weekday ? { weekday } : {}) },
    })
    return data.results
  },

  async addScheduleEntry(payload: {
    class_group: string
    weekday: number
    subject: string
    start_time: string
    end_time: string
    room?: string
  }): Promise<ScheduleEntry> {
    const { data } = await api.post<ScheduleEntry>('/management/schedule/', payload)
    return data
  },

  async deleteScheduleEntry(id: string): Promise<void> {
    await api.delete(`/management/schedule/${id}/`)
  },

  // --- teachers -----------------------------------------------------------
  async teachers(q?: string): Promise<ManagedTeacher[]> {
    const { data } = await api.get<{ results: ManagedTeacher[] }>('/management/teachers/', {
      params: q ? { q } : undefined,
    })
    return data.results
  },

  async createTeacher(
    payload: TeacherPayload,
    photo?: File | null,
  ): Promise<ManagedTeacher> {
    // With a photo the whole record travels as a form: the device needs the
    // face at the same moment the register gets the teacher.
    if (photo) {
      const form = new FormData()
      Object.entries(payload).forEach(([key, value]) => {
        if (value === undefined || value === null) return
        if (Array.isArray(value)) value.forEach((item) => form.append(key, String(item)))
        else form.append(key, String(value))
      })
      form.append('photo', photo)
      const { data } = await api.post<ManagedTeacher>('/management/teachers/', form)
      return data
    }
    const { data } = await api.post<ManagedTeacher>('/management/teachers/', payload)
    return data
  },

  async uploadTeacherPhoto(id: string, photo: File): Promise<ManagedTeacher> {
    const form = new FormData()
    form.append('photo', photo)
    const { data } = await api.patch<ManagedTeacher>(`/management/teachers/${id}/`, form)
    return data
  },

  async updateTeacher(
    id: string,
    payload: Partial<TeacherPayload> & { is_active?: boolean },
  ): Promise<ManagedTeacher> {
    const { data } = await api.patch<ManagedTeacher>(`/management/teachers/${id}/`, payload)
    return data
  },

  /** The full profile a teacher card opens: account, subjects, timetable, week. */
  async teacherProfile(id: string): Promise<PersonProfile> {
    const { data } = await api.get<PersonProfile>(`/management/teachers/${id}/`)
    return data
  },

  /** The same profile for any other employee. */
  async staffProfile(id: string): Promise<PersonProfile> {
    const { data } = await api.get<PersonProfile>(`/management/staff/${id}/`)
    return data
  },

  async deleteTeacher(id: string): Promise<void> {
    await api.delete(`/management/teachers/${id}/`)
  },

  // --- positions ----------------------------------------------------------
  async positions(): Promise<ManagedPosition[]> {
    const { data } = await api.get<{ results: ManagedPosition[] }>('/management/positions/')
    return data.results
  },

  async createPosition(payload: PositionPayload): Promise<ManagedPosition> {
    const { data } = await api.post<ManagedPosition>('/management/positions/', payload)
    return data
  },

  async updatePosition(
    id: string,
    payload: Partial<PositionPayload>,
  ): Promise<ManagedPosition> {
    const { data } = await api.patch<ManagedPosition>(`/management/positions/${id}/`, payload)
    return data
  },

  async deletePosition(id: string): Promise<void> {
    await api.delete(`/management/positions/${id}/`)
  },

  // --- staff --------------------------------------------------------------
  /** The register, and which roles this caller is allowed to hand out. */
  async staff(q?: string): Promise<{ results: ManagedStaff[]; assignable_roles: Choice[] }> {
    const { data } = await api.get<{ results: ManagedStaff[]; assignable_roles: Choice[] }>(
      '/management/staff/',
      { params: q ? { q } : undefined },
    )
    return data
  },

  async createStaff(payload: StaffPayload, photo?: File | null): Promise<ManagedStaff> {
    // With a photo the whole record travels as a form, the same way a
    // teacher's does.
    if (photo) {
      const form = new FormData()
      Object.entries(payload).forEach(([key, value]) => {
        if (value === undefined || value === null) return
        form.append(key, String(value))
      })
      form.append('photo', photo)
      const { data } = await api.post<ManagedStaff>('/management/staff/', form)
      return data
    }
    const { data } = await api.post<ManagedStaff>('/management/staff/', payload)
    return data
  },

  async updateStaff(
    id: string,
    payload: Partial<StaffPayload> & { is_active?: boolean },
  ): Promise<ManagedStaff> {
    const { data } = await api.patch<ManagedStaff>(`/management/staff/${id}/`, payload)
    return data
  },

  async deleteStaff(id: string): Promise<void> {
    await api.delete(`/management/staff/${id}/`)
  },

  // --- Excel import -------------------------------------------------------
  /** The blank workbook, as a Blob the browser can save. */
  async importTemplate(): Promise<Blob> {
    const { data } = await api.get('/management/import/template/', {
      responseType: 'blob',
    })
    return data as Blob
  },

  /**
   * Two-phase by design: `commit: false` validates and previews the whole
   * workbook without writing a single row.
   */
  async importStudents(
    file: File,
    options: { commit: boolean; academic_year?: string },
  ): Promise<ImportReport> {
    const form = new FormData()
    form.append('file', file)
    form.append('commit', String(options.commit))
    if (options.academic_year) form.append('academic_year', options.academic_year)

    const { data } = await api.post<ImportReport>('/management/import/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  // --- audit --------------------------------------------------------------
  async audit(
    params: { action?: string; q?: string; page?: number } = {},
  ): Promise<Paginated<AuditEntry> & { actions: Choice[] }> {
    const { data } = await api.get('/management/audit/', { params })
    return data
  },
}
