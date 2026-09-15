import type {
  LoginResponse,
  OtpSent,
  Relation,
  RegistrationSession,
  StudentSearchResult,
} from '@/types/api'

import { api } from './client'

export const registrationApi = {
  async relations(): Promise<{ value: Relation; label: string }[]> {
    const { data } = await api.get<{ results: { value: Relation; label: string }[] }>(
      '/registration/relations/',
    )
    return data.results
  },

  async searchStudents(payload: {
    class_group: string
    query?: string
    student_code?: string
  }): Promise<StudentSearchResult[]> {
    const { data } = await api.post<{ count: number; results: StudentSearchResult[] }>(
      '/registration/students/search/',
      payload,
    )
    return data.results
  },

  async identify(payload: {
    student: string
    relation: Relation
    jshshir: string
    phone_last4: string
  }): Promise<RegistrationSession> {
    const { data } = await api.post<RegistrationSession>('/registration/identify/', payload)
    return data
  },

  async requestOtp(sessionToken: string): Promise<OtpSent> {
    const { data } = await api.post<OtpSent>('/registration/otp/request/', {
      session_token: sessionToken,
    })
    return data
  },

  async verifyOtp(sessionToken: string, code: string): Promise<RegistrationSession> {
    const { data } = await api.post<RegistrationSession>('/registration/otp/verify/', {
      session_token: sessionToken,
      code,
    })
    return data
  },

  async complete(payload: {
    session_token: string
    password: string
    password_confirm: string
  }): Promise<LoginResponse> {
    const { data } = await api.post<LoginResponse>('/registration/complete/', payload)
    return data
  },
}
