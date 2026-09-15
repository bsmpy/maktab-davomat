import { AxiosError, AxiosHeaders } from 'axios'
import { describe, expect, it } from 'vitest'

import { ApiError, toApiError } from '@/api/errors'

function axiosError(status: number, data: unknown): AxiosError {
  const error = new AxiosError('request failed')
  error.response = {
    status,
    statusText: '',
    data,
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
  return error
}

describe('API error envelope', () => {
  it('unwraps the standard error shape', () => {
    const error = toApiError(
      axiosError(400, {
        success: false,
        error: { code: 'INVALID_OTP', message: "Tasdiqlash kodi noto'g'ri.", fields: {} },
      }),
    )
    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('INVALID_OTP')
    expect(error.message).toBe("Tasdiqlash kodi noto'g'ri.")
    expect(error.status).toBe(400)
  })

  it('exposes per-field validation messages', () => {
    const error = toApiError(
      axiosError(400, {
        success: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Xatolik',
          fields: { password: ['Parol juda oddiy.'] },
        },
      }),
    )
    expect(error.fieldError('password')).toBe('Parol juda oddiy.')
    expect(error.fieldError('login')).toBeUndefined()
  })

  it('flags a network failure', () => {
    const error = toApiError(new AxiosError('Network Error'))
    expect(error.isNetworkError).toBe(true)
    expect(error.message).toContain('Internet')
  })

  it('flags a 401 so the client can refresh', () => {
    const error = toApiError(
      axiosError(401, {
        success: false,
        error: { code: 'INVALID_CREDENTIALS', message: 'Login yoki parol noto\'g\'ri.', fields: {} },
      }),
    )
    expect(error.isUnauthorized).toBe(true)
  })

  it('never leaks a raw non-API payload', () => {
    const error = toApiError(axiosError(500, '<html>Traceback…</html>'))
    expect(error.code).toBe('UNKNOWN_ERROR')
    expect(error.message).not.toContain('Traceback')
  })
})
