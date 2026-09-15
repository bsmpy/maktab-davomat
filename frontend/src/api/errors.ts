import { AxiosError } from 'axios'

/**
 * The API always fails in the same shape:
 *   { success: false, error: { code, message, fields } }
 * This turns that (and network/timeout failures) into one predictable object.
 */
export interface ApiErrorPayload {
  code: string
  message: string
  fields: Record<string, string[]>
}

export class ApiError extends Error {
  readonly code: string
  readonly fields: Record<string, string[]>
  readonly status: number

  constructor(payload: ApiErrorPayload, status = 0) {
    super(payload.message)
    this.name = 'ApiError'
    this.code = payload.code
    this.fields = payload.fields ?? {}
    this.status = status
  }

  /** First message for a field, if the server flagged one. */
  fieldError(name: string): string | undefined {
    return this.fields[name]?.[0]
  }

  get isNetworkError(): boolean {
    return this.code === 'NETWORK_ERROR'
  }

  get isUnauthorized(): boolean {
    return this.status === 401
  }
}

const NETWORK_MESSAGE =
  "Serverga ulanib bo'lmadi. Internet aloqangizni tekshirib, qayta urinib ko'ring."

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (error instanceof AxiosError) {
    const data = error.response?.data as { error?: ApiErrorPayload } | undefined
    if (data?.error) {
      return new ApiError(data.error, error.response?.status ?? 0)
    }
    if (!error.response) {
      return new ApiError(
        { code: 'NETWORK_ERROR', message: NETWORK_MESSAGE, fields: {} },
        0,
      )
    }
    return new ApiError(
      {
        code: 'UNKNOWN_ERROR',
        message: "Kutilmagan xatolik yuz berdi. Qayta urinib ko'ring.",
        fields: {},
      },
      error.response.status,
    )
  }

  return new ApiError(
    {
      code: 'UNKNOWN_ERROR',
      message: error instanceof Error ? error.message : 'Kutilmagan xatolik.',
      fields: {},
    },
    0,
  )
}
