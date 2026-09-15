import type {
  LessonMark,
  PresenceStats,
  SearchHit,
  LessonRoster,
  TeacherDashboard,
  TeacherLesson,
  TeacherProfile,
  TeacherProfilePayload,
  TeachingCalendar,
  TeachingClass,
  TeachingClassDay,
  TeachingDay,
} from '@/types/api'

import { api } from './client'

/**
 * Dars davomati, from the teacher's side. The backend decides which subjects
 * are theirs — the cards it returns are the whole of what they may mark.
 */
export const teachingApi = {
  /** One search across everything this user is allowed to see. */
  async search(term: string): Promise<SearchHit[]> {
    const { data } = await api.get<{ results: SearchHit[] }>('/teaching/search/', {
      params: { q: term },
    })
    return data.results
  },

  /** Everything the teacher's home screen shows, in one request. */
  async dashboard(date?: string): Promise<TeacherDashboard> {
    const { data } = await api.get<TeacherDashboard>('/teaching/me/dashboard/', {
      params: date ? { date } : undefined,
    })
    return data
  },

  /**
   * The signed-in employee's own week, month and school year at the gate.
   *
   * One request for all three: the page shows them side by side, and the
   * server computes each span in a single pass over the turnstile records.
   */
  async stats(date?: string): Promise<PresenceStats> {
    const { data } = await api.get<PresenceStats>('/teaching/me/stats/', {
      params: date ? { date } : undefined,
    })
    return data
  },

  /** Today's lessons across every class — what Davomat opens on. */
  async myLessons(date?: string): Promise<TeacherLesson[]> {
    const { data } = await api.get<{ results: TeacherLesson[] }>('/teaching/me/lessons/', {
      params: date ? { date } : undefined,
    })
    return data.results
  },

  /** The month grid: which days this teacher stands in front of a class. */
  async calendar(year: number, month: number): Promise<TeachingCalendar> {
    const { data } = await api.get<TeachingCalendar>('/teaching/me/calendar/', {
      params: { year, month },
    })
    return data
  },

  /** One day of it: the classes taught, each with its lessons. */
  async calendarDay(date: string): Promise<TeachingDay> {
    const { data } = await api.get<TeachingDay>(`/teaching/me/calendar/${date}/`)
    return data
  },

  async profile(): Promise<TeacherProfile> {
    const { data } = await api.get<TeacherProfile>('/teaching/me/')
    return data
  },

  async saveProfile(payload: TeacherProfilePayload): Promise<TeacherProfile> {
    const { data } = await api.patch<TeacherProfile>('/teaching/me/', payload)
    return data
  },

  async uploadPhoto(file: File): Promise<{ photo: string }> {
    const form = new FormData()
    form.append('photo', file)
    const { data } = await api.post<{ photo: string }>('/teaching/me/photo/', form)
    return data
  },

  /** The classes this teacher is in, each flagged today / tomorrow / neither. */
  async classes(date?: string): Promise<TeachingClass[]> {
    const { data } = await api.get<{ results: TeachingClass[] }>('/teaching/classes/', {
      params: date ? { date } : undefined,
    })
    return data.results
  },

  async classDay(classGroupId: string, date: string): Promise<TeachingClassDay> {
    const { data } = await api.get<TeachingClassDay>(`/teaching/classes/${classGroupId}/`, {
      params: { date },
    })
    return data
  },

  async roster(subjectId: string, date: string): Promise<LessonRoster> {
    const { data } = await api.get<LessonRoster>(
      `/teaching/subjects/${subjectId}/roster/`,
      { params: { date } },
    )
    return data
  },

  async saveMarks(
    subjectId: string,
    date: string,
    marks: LessonMark[],
  ): Promise<LessonRoster> {
    const { data } = await api.post<LessonRoster>(
      `/teaching/subjects/${subjectId}/roster/`,
      { date, marks },
    )
    return data
  },
}
