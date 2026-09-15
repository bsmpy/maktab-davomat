/** Runtime configuration. Never hardcode a URL anywhere else. */
const rawApiUrl = import.meta.env.VITE_API_URL ?? ''

export const config = {
  apiBaseUrl: `${rawApiUrl.replace(/\/+$/, '')}/api/v1`,
  appName: import.meta.env.VITE_APP_NAME ?? 'Maktab davomat',
  /** Bot that confirms a parent's identity; without it there is no sign-up. */
  botUsername: import.meta.env.VITE_BOT_USERNAME ?? '',
  /** Name of the readable double-submit cookie set alongside the refresh token. */
  csrfCookieName: 'refresh_csrf',
  /** Header the API expects that cookie to be echoed in. */
  csrfHeaderName: 'X-Refresh-CSRF',
  isDev: import.meta.env.DEV,
} as const
