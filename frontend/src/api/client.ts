import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'

import { config } from '@/config'

import { toApiError } from './errors'

/**
 * Token strategy
 * --------------
 * The **access token lives in memory only** — never in localStorage, so an
 * injected script has nothing durable to steal. The **refresh token** is an
 * HttpOnly cookie scoped to `/api/v1/auth/`, which JavaScript cannot read at
 * all; a readable companion cookie is echoed back in a header as a
 * double-submit CSRF proof.
 *
 * On a 401 the client transparently refreshes and replays the request. All
 * concurrent 401s share one refresh call (`refreshPromise`), so a page that
 * fires six requests at once does not trigger six rotations.
 */

let accessToken: string | null = null
let refreshPromise: Promise<string> | null = null
let onAuthLost: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

/** Called when refreshing fails — the app logs the user out. */
export function setAuthLostHandler(handler: () => void): void {
  onAuthLost = handler
}

export function readCsrfCookie(): string {
  const match = document.cookie.match(
    new RegExp(`(?:^|;\\s*)${config.csrfCookieName}=([^;]*)`),
  )
  return match ? decodeURIComponent(match[1]) : ''
}

export const api = axios.create({
  baseURL: config.apiBaseUrl,
  // Needed so the browser sends the refresh cookie to the API subdomain.
  withCredentials: true,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((request: InternalAxiosRequestConfig) => {
  if (accessToken) {
    request.headers.set('Authorization', `Bearer ${accessToken}`)
  }
  // Cookie-authenticated endpoints additionally require the double-submit token.
  if (request.url?.startsWith('/auth/')) {
    const csrf = readCsrfCookie()
    if (csrf) request.headers.set(config.csrfHeaderName, csrf)
  }
  return request
})

/** Endpoints that must never trigger a refresh-and-retry cycle. */
const NO_RETRY = ['/auth/login/', '/auth/refresh/', '/auth/logout/']

async function requestRefresh(): Promise<string> {
  const response = await axios.post<{ access: string }>(
    `${config.apiBaseUrl}/auth/refresh/`,
    {},
    {
      withCredentials: true,
      headers: { [config.csrfHeaderName]: readCsrfCookie() },
    },
  )
  return response.data.access
}

export function refreshAccessToken(): Promise<string> {
  // Single-flight: everyone awaits the same rotation.
  refreshPromise ??= requestRefresh()
    .then((token) => {
      setAccessToken(token)
      return token
    })
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined

    const isRetryable =
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !NO_RETRY.some((path) => original.url?.startsWith(path))

    if (isRetryable) {
      original._retried = true
      try {
        const token = await refreshAccessToken()
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` }
        return await api.request(original)
      } catch {
        setAccessToken(null)
        onAuthLost?.()
        return Promise.reject(toApiError(error))
      }
    }

    return Promise.reject(toApiError(error))
  },
)
