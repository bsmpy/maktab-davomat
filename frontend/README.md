# Frontend — Vite + React + TypeScript

The parent cabinet. See the [root README](../README.md) for the whole-project
picture.

## Run

```bash
npm install
cp .env.example .env      # VITE_API_URL=http://127.0.0.1:8000
npm run dev               # http://localhost:5173
```

| Script | What |
|---|---|
| `npm run dev` | dev server |
| `npm run build` | type-check (`tsc -b`) + production bundle |
| `npm run preview` | serve `dist/` |
| `npm run test` | vitest |
| `npm run lint` | oxlint |

## Layout

```text
src/
├── api/          axios instance + one module per domain. Components never call
│                 axios directly.
├── components/
│   ├── ui/       Button, Input, Select, Card, Modal, Toaster, Skeleton, …
│   ├── layout/   Sidebar, MobileNav, Topbar, ChildSwitcher
│   └── charts/   Recharts wrappers + the shared palette
├── features/     attendance views (daily/weekly/monthly/yearly), dashboard
│                 cards, registration steps, Telegram card
├── hooks/        useAsyncData (loading/error/retry), useDebouncedValue,
│                 useCountdown, useMediaQuery
├── layouts/      AppLayout (cabinet shell), AuthLayout
├── pages/        one file per route
├── routes/       route table + ProtectedRoute / PublicOnlyRoute
├── store/        zustand: auth, child switcher, toasts
├── types/        API response types
├── utils/        status→colour maps, date formatting, cn()
└── i18n/         uz (default), ru, en — react-i18next
```

## Auth

The access token is kept **in memory** in the zustand auth store — never in
`localStorage`. The refresh token is an HttpOnly cookie the SPA cannot read; the
axios client echoes a readable companion cookie in `X-Refresh-CSRF` on the
`/auth/` endpoints.

On a `401` the response interceptor refreshes and replays the request. All
concurrent 401s share a single refresh call, so a page firing six requests
triggers one rotation. If refreshing fails, the session is dropped and the user
lands on the login screen.

The only thing persisted to `localStorage` is the id of the currently selected
child — no credentials, nothing personal.

## Conventions

- Data fetching goes through `useAsyncData`, so every page gets the same
  skeleton → error → empty → content lifecycle with a retry button.
- Attendance percentages are **rendered, never computed**: the backend owns the
  formula. `src/utils/attendance.ts` maps statuses to labels and colours only.
- Colours come from the Tailwind theme (`brand`, `ink`, `status.*`) — muted, one
  accent, no acid.
- Layout: sidebar from `lg` up, bottom tab bar below.

## Adding a language

Drop a JSON file in `src/i18n/locales/`, register it in `src/i18n/index.ts` and
add it to `SUPPORTED_LANGUAGES`. The UI ships in Uzbek Latin; `ru` and `en`
resources are already present.
