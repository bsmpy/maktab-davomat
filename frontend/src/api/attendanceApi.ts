import type {
  AbsenceRequest,
  AttendanceReason,
  DailyReport,
  LessonAttendanceReport,
  MonthlyReport,
  WeeklyReport,
  YearlyReport,
} from '@/types/api'

import { api } from './client'

export const attendanceApi = {
  async daily(childId: string, date?: string): Promise<DailyReport> {
    const { data } = await api.get<DailyReport>(`/children/${childId}/attendance/daily/`, {
      params: date ? { date } : undefined,
    })
    return data
  },

  async weekly(childId: string, date?: string): Promise<WeeklyReport> {
    const { data } = await api.get<WeeklyReport>(`/children/${childId}/attendance/weekly/`, {
      params: date ? { date } : undefined,
    })
    return data
  },

  async monthly(childId: string, year: number, month: number): Promise<MonthlyReport> {
    const { data } = await api.get<MonthlyReport>(`/children/${childId}/attendance/monthly/`, {
      params: { year, month },
    })
    return data
  },

  async yearly(childId: string): Promise<YearlyReport> {
    const { data } = await api.get<YearlyReport>(`/children/${childId}/attendance/yearly/`)
    return data
  },

  /** Dars davomati for one pupil over a range. */
  async lessons(
    childId: string,
    params: { start: string; end?: string; includeDays?: boolean },
  ): Promise<LessonAttendanceReport> {
    const { data } = await api.get<LessonAttendanceReport>(
      `/children/${childId}/attendance/lessons/`,
      {
        params: {
          start: params.start,
          end: params.end ?? params.start,
          include_days: params.includeDays === false ? 'false' : 'true',
        },
      },
    )
    return data
  },

  async calendar(childId: string, year: number, month: number): Promise<MonthlyReport> {
    const { data } = await api.get<MonthlyReport>(`/children/${childId}/calendar/`, {
      params: { year, month },
    })
    return data
  },

  async reasons(): Promise<AttendanceReason[]> {
    const { data } = await api.get<AttendanceReason[]>('/attendance/reasons/')
    return data
  },

  async absenceRequests(childId: string): Promise<AbsenceRequest[]> {
    const { data } = await api.get<{ results: AbsenceRequest[] }>(
      `/children/${childId}/absence-requests/`,
    )
    return data.results
  },

  async submitAbsenceReason(
    childId: string,
    payload: { date: string; reason: string; comment?: string },
  ): Promise<AbsenceRequest> {
    const { data } = await api.post<AbsenceRequest>(
      `/children/${childId}/absence-requests/`,
      payload,
    )
    return data
  },
}
