# Maktab davomat — ota-onalar shaxsiy kabineti

Parent-facing school attendance system: a Django REST backend, a React SPA and
an aiogram Telegram bot. A parent registers, proves they are the guardian the
school already has on file, and can then follow their child at the school gate —
when they walked in, when they walked out, how many times, how long they were
inside and how long outside — day by day, week by week, month by month and
across the whole academic year, on the web and in Telegram. Every pass also
raises a Telegram message the moment it happens.

```text
project/
├── backend/     Django 5 + DRF + Celery      (API, business logic, admin)
├── frontend/    Vite + React + TypeScript    (parent cabinet SPA)
├── tgbot/       aiogram 3                    (Telegram bot — talks to the API only)
├── deploy/      nginx configuration
└── docker-compose.yml
```

**Data flow — the bot never touches the database:**

```text
Telegram  →  aiogram bot  →  Django REST API  →  PostgreSQL
Browser   →  React SPA    →  Django REST API  →  PostgreSQL
```

---

## Contents

1. [Requirements](#1-requirements)
2. [Quick start](#2-quick-start)
3. [Environment files](#3-environment-files)
4. [Backend](#4-backend)
5. [Frontend](#5-frontend)
6. [Telegram bot](#6-telegram-bot)
7. [Celery and Redis](#7-celery-and-redis)
8. [Docker](#8-docker)
9. [Demo data and test credentials](#9-demo-data-and-test-credentials)
10. [Roles](#10-roles)
11. [Settings and integrations](#11-settings-and-integrations)
12. [Access terminals (Hikvision)](#12-access-terminals-hikvision)
13. [Architecture notes](#13-architecture-notes)
14. [Security model](#14-security-model)
15. [Testing](#15-testing)
16. [Production checklist](#16-production-checklist)

---

## 1. Requirements

| Component | Version |
|---|---|
| Python | 3.11+ (3.12 recommended) |
| Node.js | 20+ |
| PostgreSQL | 14+ (16 recommended) |
| Redis | 6+ |
| Docker / Compose | optional, for the containerised stack |

PostgreSQL is required — not optional. The project uses `ArrayField`, JSONB,
partial/functional unique constraints and the `pg_trgm` extension for the fuzzy
pupil search. SQLite will not work.

---

## 2. Quick start

```bash
git clone <repo> project && cd project

# 1. Databases — the compose file below starts PostgreSQL on 127.0.0.1:55432
#    and Redis on 127.0.0.1:56379 (non-standard ports so they cannot collide
#    with anything already running). These are the values backend/.env expects.
docker compose -f docker-compose.dev.yml up -d
#    …or bring your own and point DATABASE_URL / REDIS_URL at them.

# 2. Backend
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                     # then fill it in — see §3
python manage.py migrate
python manage.py seed_demo               # demo school, pupils, guardians, attendance
python manage.py runserver 0.0.0.0:8000

# 3. Frontend (new terminal)
cd frontend
npm install
cp .env.example .env                     # VITE_API_URL=http://127.0.0.1:8000
npm run dev                              # http://localhost:5173

# 4. Telegram bot (new terminal, optional)
cd tgbot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                     # BOT_TOKEN + BOT_SERVICE_TOKEN
python main.py

# 5. Celery worker (new terminal, needed for Telegram notifications)
cd backend && . .venv/bin/activate
celery -A config worker -l INFO
```

A `Makefile` wraps all of the above — run `make help`.

Once it is up:

| URL | What |
|---|---|
| <http://localhost:5173> | parent cabinet |
| <http://localhost:5173/admin> | admin console |
| <http://localhost:8000/api/docs/> | Swagger UI |
| <http://localhost:8000/api/redoc/> | ReDoc |
| <http://localhost:8000/api/schema/> | OpenAPI schema |
| <http://localhost:8000/api/health/> | health probe |

---

## 3. Environment files

Nothing is hardcoded: every secret, credential and URL comes from the
environment. Three `.env.example` files describe every variable.

### `backend/.env` — the ones you must fill in

| Variable | Notes |
|---|---|
| `DJANGO_SECRET_KEY` | `python -c "import secrets;print(secrets.token_urlsafe(64))"` |
| `DJANGO_DEBUG` | `False` in production |
| `DJANGO_ALLOWED_HOSTS` | e.g. `192.168.0.100,localhost,127.0.0.1` |
| `DATABASE_URL` | `postgres://user:pass@host:5432/attendance` |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` |
| `CORS_ALLOWED_ORIGINS` | e.g. `http://192.168.0.100` — never `*` |
| `CSRF_TRUSTED_ORIGINS` | the public origin, e.g. `http://192.168.0.100` |
| `FIELD_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
| `JSHSHIR_HASH_KEY` | long random string — **rotating it invalidates every JSHSHIR lookup** |
| `AUTH_COOKIE_DOMAIN` | empty — the SPA and the API share one origin |
| `TELEGRAM_BOT_TOKEN` | from @BotFather |
| `TELEGRAM_BOT_USERNAME` | without the `@` |
| `BOT_SERVICE_TOKEN` | shared secret; must match `tgbot/.env` |
| `SMS_PROVIDER` | `console` in dev, `http` in production |
| `SMS_API_URL` / `SMS_API_TOKEN` / `SMS_SENDER` | your SMS gateway |
| `OTP_EXPOSE_IN_RESPONSE` | dev only — the production settings refuse to boot if it is on |

### `frontend/.env`

| Variable | Notes |
|---|---|
| `VITE_API_URL` | API root without a trailing slash, e.g. `http://127.0.0.1:8000`; empty for a same-origin build behind nginx |
| `VITE_APP_NAME` | shown on the auth screens |

Vite inlines these at build time, so the Docker image takes them as build args.

### `tgbot/.env`

| Variable | Notes |
|---|---|
| `BOT_TOKEN` | from @BotFather |
| `BOT_USERNAME` | without the `@` |
| `BACKEND_API_URL` | e.g. `http://127.0.0.1:8000` |
| `BOT_SERVICE_TOKEN` | must equal the backend's value |
| `FRONTEND_URL` | linked from the bot |
| `REDIS_URL` | FSM storage; leave empty for in-memory (single instance only) |

---

## 4. Backend

```bash
cd backend
python manage.py check                       # system checks
python manage.py makemigrations --check      # no drifting models
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo                   # demo dataset
python manage.py generate_lessons --from 2026-09-01 --to 2026-09-30
python manage.py import_students --make-template namuna.xlsx
python manage.py import_students data.xlsx            # preview only
python manage.py import_students data.xlsx --commit   # write
python manage.py reset_data --keep-user bsm --yes     # start from empty
python -m pytest                             # tests
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4   # production
```

### Layout

```text
backend/
├── config/                 settings (base/dev/prod/test), urls, celery, wsgi
├── apps/
│   ├── common/             base models, error envelope, OTP, SMS providers,
│   │                       throttles, crypto, pagination, permissions
│   ├── accounts/           User, JWT auth, registration wizard, passwords
│   ├── schools/            School, AcademicYear, Grade, ClassGroup, Subject,
│   │                       Teacher, Holiday, Excel import
│   ├── students/           Student (+ admin import screen)
│   ├── guardians/          Guardian, GuardianStudent, access selectors
│   ├── attendance/         Schedule, Lesson, Attendance, AttendanceHistory,
│   │                       AttendanceReason, AbsenceRequest, all reports
│   ├── notifications/      Notification, NotificationDelivery, Celery tasks
│   ├── telegram/           TelegramAccount, link tokens, bot service API
│   ├── integrations/       Sozlamalar → Integratsiyalar: Telegram/SMS/Face ID
│   │                       settings, Hikvision ISAPI client, turnstile events,
│   │                       arrival/departure → attendance rule engine
│   └── audit/              AuditLog + request context middleware
└── tests/
```

### API surface (`/api/v1/`)

| Group | Endpoints |
|---|---|
| Auth | `auth/login/`, `auth/refresh/`, `auth/logout/`, `auth/me/`, `auth/password/change/`, `auth/password/reset/{request,verify,confirm}/` |
| Registration | `registration/relations/`, `registration/students/search/`, `registration/identify/`, `registration/otp/{request,verify}/`, `registration/complete/` |
| Catalogue | `schools/`, `grades/`, `class-groups/`, `academic-years/` |
| Children | `children/`, `children/{id}/`, `children/{id}/dashboard/` |
| Attendance | `children/{id}/attendance/{daily,weekly,monthly,yearly}/`, `children/{id}/calendar/`, `children/{id}/absence-requests/`, `attendance/reasons/` |
| Notifications | `notifications/`, `notifications/unread-count/`, `notifications/mark-as-read/`, `notifications/mark-all-as-read/` |
| Telegram (web) | `telegram/status/`, `telegram/link-code/`, `telegram/unlink/`, `telegram/notifications/` |
| Teaching | `teaching/absence-requests/`, `teaching/absence-requests/{id}/{approve,reject}/` |
| Management (admin) | `management/grades/`, `management/grades/{id}/`, `management/class-groups/`, `management/class-groups/{id}/`, `management/students/`, `management/students/{id}/`, `management/students/{id}/photo/`, `management/guardians/`, `management/relations/` |
| Users (super admin+) | `management/users/`, `management/users/{id}/`, `management/users/{id}/reset-password/` |
| Admin console | `management/schools/`, `management/academic-years/`, `management/holidays/`, `management/subjects/`, `management/teachers/`, `management/import/`, `management/import/template/`, `management/audit/` |
| Bot (service token) | `bot/link/`, `bot/me/`, `bot/children/`, `bot/active-child/`, `bot/attendance/`, `bot/notifications/`, `bot/settings/`, `bot/unlink/` |
| Settings | `settings/`, `settings/integrations/`, `settings/integrations/{kind}/`, `settings/integrations/{kind}/test/` |
| Terminals | `settings/terminals/`, `settings/terminals/{id}/{test,sync,rotate-token}/`, `settings/terminals/test-connection/`, `settings/terminals/events/`, `settings/presence/`, `settings/presence/recompute/` |
| Face ID | `settings/face-id/people/`, `settings/face-id/enroll/`, `settings/face-id/students/{id}/photo/` |
| Device push (ingest token) | `terminals/events/{token}/` |

Errors always arrive in one shape:

```json
{
  "success": false,
  "error": { "code": "INVALID_OTP", "message": "Tasdiqlash kodi noto'g'ri.", "fields": {} }
}
```

---

## 5. Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # type-check + production bundle into dist/
npm run preview      # serve the built bundle
npm run test         # vitest
npm run lint
```

```text
frontend/src/
├── api/          axios client + one module per domain (authApi, attendanceApi, …)
├── components/   ui primitives, layout (sidebar, mobile nav, child switcher), charts
├── features/     attendance views, dashboard cards, registration steps,
│                 settings/integration forms
├── hooks/        useAsyncData (loading/error/retry), useDebouncedValue, …
├── layouts/      AppLayout (cabinet shell), AuthLayout
├── pages/        Dashboard, Attendance, Calendar, Notifications, Profile,
│                 Management (admin), auth
├── routes/       route table + auth gates
├── store/        zustand: auth, child switcher, toasts
├── types/        API response types
├── utils/        status/colour maps, date helpers
└── i18n/         uz (default), ru, en
```

Sections: **Bosh sahifa · Davomat · Kalendar · Bildirishnomalar · Profil**, plus
**Boshqaruv** for administrators. Davomat is a single module with a
`Kunlik | Haftalik | Oylik | Yillik` switch, not four separate screens: it shows
the gate record — first entry, last exit, how many times each way, time inside
and time outside — down to the individual passes. The sidebar is used from `lg`
upwards; phones get a bottom tab bar. Every page has skeleton, empty, error and
retry states.

### The admin console (`/admin`)

**There is no Django admin.** `django.contrib.admin` is not in `INSTALLED_APPS`
and no URL routes to it, so the project has exactly one login surface — the
cabinet's — and no session-cookie form to defend. Administration is a section
of the SPA, styled like the rest of it, talking to `/api/v1/management/` with
the same JWT.

Sections, each gated by role on the server as well as in the UI:

| Section | Who | What |
|---|---|---|
| **O'quvchilar** | ADMIN+ | The register: pupils, their guardians, their photo |
| **Yaqinlar** | ADMIN+ | Who has claimed an account, for which children |
| **Sinf va guruhlar** | ADMIN+ | Parallels and groups |
| **Maktab** | ADMIN+ | School profile, working weekdays, academic years, holidays |
| **Fan va o'qituvchilar** | ADMIN+ | Subjects and staff |
| **Excel import** | ADMIN+ | Bulk-load the register |
| **Foydalanuvchilar** | SUPER_ADMIN+ | Accounts and one-off passwords |
| **Audit jurnali** | SUPER_ADMIN+ | Who did what, when, from where |

**Maktab** is where the attendance arithmetic gets its calendar: a weekday
outside `working_weekdays`, or a date listed as a holiday, is not a school day
and never enters a denominator.

**Excel import** is two-phase, as it always was: the workbook is validated and
previewed first and a second, explicit click writes it. One bad row and nothing
is written.

Two of those sections deserve their own note:

* **Foydalanuvchilar** — staff accounts: add one, enable or disable it, or
  issue a one-off password. The role dropdown only offers what the caller may
  actually grant.
* **O'quvchilar** — add a pupil by surname, name and patronymic, attach any
  number of **yaqinlari** with the `+` button (each one *Otasi · Onasi ·
  Vasiysi · Boshqa*, with a phone and a JSHSHIR), and upload their photo. The
  form shows `public/shablon.png` until a real one is chosen. Saving writes the
  pupil, the guardians and the links, then pushes the person record and the face
  to every active terminal — so a pupil added in the morning passes the gate the
  same day. Deleting a pupil also removes them from the devices.

---

## 6. Telegram bot

```bash
cd tgbot
python main.py
```

```text
tgbot/
├── bot/
│   ├── handlers/     start/linking, attendance, children, notifications, fallback
│   ├── keyboards/    reply + inline keyboards
│   ├── middlewares/  API-error handling, structured logging
│   ├── services/     API client, message formatting
│   ├── states/       FSM states for the linking flow
│   └── config.py
└── main.py
```

Menu: `📊 Bugungi davomat`, `📅 Haftalik davomat`, `📈 Oylik davomat`,
`📆 Yillik davomat`, `👦 Farzandlarim`, `🔔 Bildirishnomalar`, `⚙️ Sozlamalar`.
With several children the bot offers a picker and remembers the active one.

### Linking

1. In the cabinet: **Profil → Telegram ulash** → a one-time 6-digit code and a
   `https://t.me/<bot>?start=<token>` deep link.
2. The user sends the code to the bot (or follows the deep link).
3. The bot posts it to `POST /api/v1/bot/link/` with its service token.
4. The backend validates the token, binds `telegram_id ↔ user`, and burns it.

Tokens are stored **hashed**, are single-use, and expire after 15 minutes. A
Telegram id on its own is never accepted as proof of identity.

### Automatic notifications

Every pass through the turnstile fires a Celery task that creates one
notification per verified guardian and pushes it to Telegram — on the way in and
on the way out:

```text
🟢 Azizbek Valiyev
08:24 da maktabga kirdi (Asosiy kirish).

🔴 Azizbek Valiyev
13:40 da maktabdan chiqdi (Asosiy kirish).
```

Either direction can be switched off on its own in **Sozlamalar →
Integratsiyalar → Telegram bot** (`send_entry`, `send_exit`).

Duplicates are impossible by construction: the dedupe key is the pass itself,
and `Notification(user, dedupe_key)` and `NotificationDelivery(notification,
channel)` are both unique — so a Celery retry, a device resync or a re-poll of
the same window converge on a single message. If a user blocks the bot, the
delivery is marked `SKIPPED` and the account is deactivated instead of retried
forever.

---

## 7. Celery and Redis

Redis backs the cache, OTP storage, rate limits, registration sessions and the
Celery broker.

```bash
cd backend
celery -A config worker -l INFO                    # worker
celery -A config beat  -l INFO \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler   # scheduler
```

The worker is required for Telegram notifications. Without it the in-app
notifications still appear (they are created by the same task, which you can
also run eagerly by setting `CELERY_TASK_ALWAYS_EAGER=True` in development).

Periodic tasks, registered by `python manage.py setup_integrations --with-beat`:

| Task | Suggested schedule |
|---|---|
| `apps.notifications.tasks.purge_expired_link_tokens` | daily — cleans up spent Telegram link tokens |

---

## 8. Docker

> **Развёрнутый стенд.** На этой машине проект уже работает по адресу
> `http://192.168.0.100` — но не через compose, а нативно
> (systemd + существующий aaPanel-nginx), потому что 80/443 уже заняты.
> Что именно и как обновлять — в [`deploy/README.md`](deploy/README.md).
> Compose-стек ниже остаётся рабочим вариантом для чистой машины.

```bash
cp .env.example .env               # POSTGRES_PASSWORD, VITE_API_URL
cp backend/.env.example backend/.env
cp tgbot/.env.example tgbot/.env

docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
docker compose exec backend python manage.py createsuperuser
docker compose logs -f
```

Services: `postgres`, `redis`, `backend` (gunicorn), `celery`, `celery-beat`,
`tgbot`, `frontend` (nginx-served build) and `nginx` (reverse proxy: the SPA at
`/`, the API under `/api/`). Postgres and Redis are not published to the host.

The stack's nginx listens on plain **port 80** and serves everything from **one
origin**, so it is reached by IP on the local network — e.g.
`http://192.168.0.100` — with no domain name and no certificate. Leave
`VITE_API_URL` empty so the SPA calls `/api/v1/...` on the address it was
opened from; the matching `backend/.env` values are in
[`deploy/nginx/README.md`](deploy/nginx/README.md).

---

## 9. Demo data and test credentials

> **This deployment has no demo data.** It was wiped with `reset_data` (below)
> and holds one account, `bsm` (`DEVELOPER`), plus the integration settings.
> The register is filled from **Boshqaruv** or the Excel import.

```bash
cd backend && python manage.py seed_demo   # refuses to run unless DJANGO_DEBUG=True
```

Creates one school, grades 1–11, 24 class groups (`1-A`, `1-B`, `1-D`, `2-A`, …,
`11-B`), 12 subjects, 18 teachers, a timetable, ~240 pupils, guardians, and
several months of turnstile history — raw passes plus the `DailyPresence` row
derived from each one, including pupils who step out at lunch and come back.

A disabled demo terminal is created to own those events, so Celery beat never
polls an address that is not there.

Useful flags: `--history-days` (how far back the gate history goes, default 210),
`--students-per-class`, `--flush` (wipe first).

**Shared demo password: `Demo!2026parol`**

### Starting from empty

```bash
python manage.py reset_data --keep-user bsm            # preview, deletes nothing
python manage.py reset_data --keep-user bsm --yes      # do it
python manage.py reset_data --keep-user bsm --integrations --yes   # credentials too
```

Deletes the whole register — schools, grades, groups, pupils, guardians — and
everything derived from it: turnstile passes, presence, attendance history,
notifications, the audit trail and every account except the ones named.

It refuses to run without `--yes`, and refuses to run without at least one
`--keep-user`, so it cannot leave the platform with no way in. Integration rows
carry live credentials (bot token, SMS login, terminal passwords) and the beat
schedule is setup rather than data, so both survive unless you pass
`--integrations`. **Take a dump first — this cannot be undone:**

```bash
docker exec maktab-davomat-postgres pg_dump -U attendance -d attendance --no-owner \
  | gzip > backup-$(date +%F).sql.gz
```

| Role | Login | Notes |
|---|---|---|
| `PARENT` | `a.valiyev` | three children: Azizbek 7-A, Madina 3-B, Sardor 1-A |
| `TEACHER` | `m.valiyev`, `s.yusupov`, `n.nazarov` | review absence reasons for their own pupils |
| `ADMIN` | `maktabadmin` | Maktab boshqaruvi (sinflar, guruhlar, o'quvchilar); sees Sozlamalar, not Integratsiyalar |
| `SUPER_ADMIN` | `superadmin` | all schools; reads integrations, cannot change them |
| `DEVELOPER` | `admin` | full access, owns Integratsiyalar and the admin console |

**To test registration end to end**, use the guardian the seed deliberately
leaves without an account (the exact values are printed when `seed_demo` runs):

| Field | Value |
|---|---|
| Class | `5-A` |
| Pupil | `Aliyev S.` (search for `Aliyev`) |
| Relation | `Otasi` (FATHER) |
| JSHSHIR | `31111222233334` |
| Phone last 4 | `8899` |

With `SMS_PROVIDER=console` the OTP is printed to the backend console; with
`OTP_EXPOSE_IN_RESPONSE=True` it also comes back in the API response (and the
UI shows it as a toast). **Both are development-only.**

---

## 10. Roles

Five roles, most privileged first. Everything is enforced server-side; the
frontend role only decides what to render.

| Role | Scope | Can do |
|---|---|---|
| `DEVELOPER` | unscoped | **Everything.** Provisions any account, including other `SUPER_ADMIN`s and `DEVELOPER`s. The only role that may change integration credentials (bot token, SMS password, turnstile logins) or add a school. Owns Sozlamalar → Integratsiyalar. |
| `SUPER_ADMIN` | unscoped | Everything an `ADMIN` can do, in **every** school, plus **Foydalanuvchilar**: provisions `ADMIN` and `TEACHER` accounts and issues one-off passwords for them. Sees which guardians have registered and against which child. May *read* integration settings (masked) but not change them. |
| `ADMIN` | own school(s) | **Maktab boshqaruvi**: add/edit/delete grades, class groups and pupils (with their guardians and face photo), plus reports and Excel import. Sees Sozlamalar but not Integratsiyalar. |
| `TEACHER` | own classes | Reviews absence reasons, sees their own pupils' gate records only. |
| `PARENT` | own children | Dashboard, attendance, calendar, notifications, absence reasons, profile. |

`createsuperuser` mints a `DEVELOPER` — it is the bootstrap account.

### Who may provision whom

Accounts are created from **Boshqaruv → Foydalanuvchilar**; parents never
appear there, because a parent proves who they are and registers themselves.

| Actor | May create / edit / reset |
|---|---|
| `DEVELOPER` | `DEVELOPER`, `SUPER_ADMIN`, `ADMIN`, `TEACHER` |
| `SUPER_ADMIN` | `ADMIN`, `TEACHER` |
| everyone else | nobody |

A `SUPER_ADMIN` grows the layer below them but cannot mint a peer — only the
platform owner grows the top of the ladder. `DEVELOPER` is the deliberate
exception and may create its own role, because somebody has to be able to hand
the platform over. Nobody edits their own account from here, and an account you
may not manage is not even listed.

### Passwords cannot be read back — by anyone

Passwords are Argon2 hashes. That is a one-way function: there is no endpoint,
no role and no admin screen that can show an existing password, and adding one
is not possible without storing credentials reversibly — which would turn a
single leaked backup into every family's login, and would destroy
non-repudiation, since nobody could then tell a parent's own action from an
operator's.

What an operator actually needs — getting a locked-out person back in — is
**Yangi parol**: it mints a fresh one-off password, shows it exactly once,
kills every live session, forces a change at next login, and records who did it
in `AuditLog` (`USER_PASSWORD_RESET`).

Where the rules live:

* `apps/accounts/constants.py` — the role ladder, the groupings
  (`staff_roles`, `integration_write_roles`, …) and `manageable_roles`
* `apps/accounts/services/provisioning.py` — account creation and one-off
  passwords
* `apps/guardians/selectors.py` — which pupils a user may read; every
  pupil-scoped endpoint resolves through it
* `apps/common/permissions.py` — the DRF permission classes

## 11. Settings and integrations

`Sozlamalar → Integratsiyalar` in the cabinet, `/api/v1/settings/` on the API.
Four integrations, each with an enable switch, its own options, a
**Tekshirish** button that proves the credentials work, and a status pill.

| Section | What it configures |
|---|---|
| **Telegram bot** | Bot token, bot username, which events raise a message |
| **SMS (Eskiz)** | Eskiz email/password (or a ready token), sender, whether OTP goes by SMS |
| **Face ID** | Face library id (FDID), auto-enrol on photo upload, photo limits; lists who is enrolled |
| **Terminallar** | The attendance rules (late grace, debounce, poll interval) and the device list |

**Credentials never leave the server.** They are stored as Fernet ciphertext
under `FIELD_ENCRYPTION_KEY` and the API only ever returns a mask
(`••••••4ht4`). The UI reflects that: a secret field is read-only until you
click *O'zgartirish*, and an untouched secret is not part of the save request at
all — so changing a checkbox cannot overwrite a token.

Settings resolve **database → environment**: a fresh install runs entirely from
`.env`, and anything saved in the UI takes precedence. A row scoped to a school
overrides the global one, so a second school can have its own bot or SMS
account.

```bash
# create the four rows and register the periodic tasks
python manage.py setup_integrations --with-beat
```

## 12. Access terminals (Hikvision)

The turnstile *is* the register. Tested against **DS-K1T341CMF** over ISAPI;
any Hikvision access terminal speaking `AcsEvent` should work.

### How a pass becomes a day

```text
turnstile  →  TerminalEvent  →  visits             →  DailyPresence
(raw pass)    (kept verbatim)   (entry + its exit)    (the day, aggregated)
```

1. **Ingest.** Raw passes are stored exactly as the device reported them, so the
   day can always be rebuilt from source. Repeat reads inside the debounce
   window are one pass, not three — a pupil fumbling their bag is one entry.
2. **Visits.** Each entry is paired with the exit that follows it. Two entries
   in a row mean a missed exit: the earlier arrival is kept, so the clock is
   never restarted. An exit with no entry (the device came online mid-morning)
   is counted but measures nothing.
3. **The day.** First entry, last exit, how many times each way, minutes inside
   (summed over the visits) and minutes outside (the gaps between them).
   Arriving more than the grace period after `school_start_time` is late.

A pupil who is still inside has an open visit that is measured against the clock
while the day runs, and against `school_end_time` once it is over — so a
forgotten exit cannot inflate the total. The `close_school_day` beat task
settles those at 20:30.

Every step is idempotent: a late-syncing event, a device resync or a manual
re-run rebuild the whole day from the raw passes and converge on the same
answer.

### Two ingestion paths (run both)

| | How | When it works |
|---|---|---|
| **Push** | The device's *HTTP Listening* notification posts to `/api/v1/terminals/events/<token>/` | The device can reach the backend |
| **Pull** | A Celery beat task calls `AcsEvent` every few minutes | The backend can reach the device |

Duplicates are impossible — `(terminal, external_id)` is unique — so push gives
low latency while polling guarantees nothing is lost while the backend is down.

The push URL is shown (and copyable) on each terminal's card; paste it into the
device's *Event → HTTP Listening* settings. The long token in the path is the
only credential, and it can be rotated from the UI.

### Adding a device

1. Sozlamalar → Integratsiyalar → **Terminallar** → *Terminal qo'shish*
2. Enter the IP, port, ISAPI login and password, and whether the reader records
   entry, exit or both. **Ulanishni tekshirish** talks to the device before you
   save anything.
3. Enrol pupils: upload a photo (Face ID section) or enrol a whole class. The
   backend creates the person record on every active device and uploads the
   face into its library.
4. Denied reads (`minor` outside the granted set) are dropped — an unrecognised
   face at the turnstile must never mark a pupil present.

### Operations

```bash
celery -A config worker -l INFO     # required: ingestion + enrolment
celery -A config beat   -l INFO     # polling, end-of-day sweep, clock sync
```

Beat tasks registered by `setup_integrations --with-beat`:

| Task | Schedule | Why |
|---|---|---|
| `poll_all_terminals` | every 5 min | pull new passes |
| `close_school_day` | 20:30 daily | settle days that still have an open visit |
| `sync_terminal_clocks` | 03:00 daily | clock drift corrupts attendance |

## 13. Architecture notes

### Attendance is entry and exit, not lessons

The product measures *being at school*. There is no per-subject register: a
pupil's day is the passes they made through the gate.

```text
TerminalEvent      →  visits              →  DailyPresence
(one raw pass)        (entry + its exit)     (the day, aggregated)
```

One `DailyPresence` per pupil per day carries the first entry, the last exit,
how many times they went each way, the minutes spent inside (summed over every
visit) and the minutes spent outside (the gaps between visits). The visits
themselves are stored alongside, so the UI can show the day hour by hour, and
the raw passes are kept verbatim so the whole day can always be rebuilt from
source.

### One attendance formula

Every percentage in the product — web, Telegram, dashboard — is produced by
`apps/attendance/services/presence_stats.py`. The frontend renders
`summary.rate` and never recomputes it.

```text
rate = days_present / school_days
```

A **school day** is a working weekday that is neither a holiday nor in the
future. Days the school was closed never enter the denominator, so a term that
has not started yet reads 0 of 0 rather than a wall of absences.

The school day itself (`school_start_time`, `school_end_time`) and the grace
period before an arrival counts as late live in
**Sozlamalar → Integratsiyalar → Terminallar**, not in code.

### Guardians ↔ pupils

`GuardianStudent` is a real model, not a bare M2M: one parent can have several
children, one child several guardians, and the link carries `relation`,
`is_primary`, `verified`/`verified_at` and a per-link notification switch.

### Soft delete

`Student`, `Guardian`, `Grade`, `ClassGroup`, `Subject`, `Teacher` and `School`
are soft-deleted. `objects` hides deleted rows; `all_objects` sees everything,
so historical attendance is never lost to an accidental delete.

This is what makes "delete grade 11" safe: retiring a parallel retires its class
groups and their pupils, every row survives, and creating the grade again
revives it. The uniqueness constraints are conditional on `deleted_at IS NULL`,
so a retired `3-G` never blocks a new one.

### Timezone

Everything is timezone-aware and anchored to `Asia/Tashkent`.

---

## 14. Security model

**Tokens.** The access token (15 min) lives **in memory in the SPA** and is sent
as `Authorization: Bearer`. The refresh token (14 days) is an **HttpOnly,
Secure, SameSite=Lax cookie** scoped to `/api/v1/auth/`, so script injection
cannot read it. Refresh **rotates** and the old token is **blacklisted**; the
`/auth/` endpoints additionally require a double-submit CSRF header, so the
cookie alone cannot be replayed cross-site. Changing or resetting a password
revokes every outstanding session.

**Registration.** Knowing a pupil's name is not a credential. The applicant must
also (1) supply a JSHSHIR that hashes to a guardian in that pupil's school,
(2) already be linked to that exact pupil with the kinship they claim,
(3) match the last four digits of the *registered* phone, and (4) enter an OTP
sent to that registered number — never to a number they typed. Every failure
returns one identical message, so the endpoint cannot be used to probe for
whether a JSHSHIR or a link exists. Attempts are counted per pupil and per IP.

**JSHSHIR.** Stored twice, never in the clear: a peppered HMAC-SHA256 for
lookups and Fernet ciphertext for privileged retrieval, plus the last four
digits for display. No API returns more than `**********1234`, and a logging
filter scrubs 14-digit numbers, JWTs, passwords and OTP codes before they can
reach a handler.

**Pupil search.** Scoped to one class group, a minimum query length, a hard
result cap and an IP rate limit; results carry a masked name (`Valiyev A.`).
The register cannot be enumerated.

**Authorisation.** Roles are `SUPER_ADMIN | ADMIN | TEACHER | PARENT`, and every
pupil-scoped endpoint resolves its target through
`apps/guardians/selectors.get_accessible_student`. Asking for another parent's
child returns `404` — identical to a genuinely missing pupil. The frontend role
is presentation only.

**Rate limits.** OTP request, OTP verify, login, registration, pupil search and
password reset are throttled per IP, all configurable via env.

**Audit.** `AuditLog` records logins, failed logins, logouts, registration,
password changes/resets, attendance create/update/delete, guardian↔pupil links,
absence-reason approvals and Telegram link/unlink — with IP and user agent, and
with every payload scrubbed of secrets. Attendance edits additionally keep a
dedicated `AttendanceHistory` trail (who, when, old → new).

---

## 15. Testing

```bash
cd backend  && python -m pytest              # ~300 tests
cd frontend && npm run test                  # vitest
```

Backend coverage includes: registration (including every way it must fail),
OTP issue/verify/expiry/attempt limits, username generation and collisions,
login by username and phone, refresh rotation and blacklisting, CSRF on the
cookie endpoints, parent/teacher object-level permissions (including the
attempt to read someone else's child), the presence formula, all four report
periods, absence-reason approval, notification idempotency on both directions
and Telegram delivery, Telegram linking (reuse, expiry, hijack attempts), the
Excel import (validation, duplicates, preview), the security guarantees
(masking, log scrubbing, error envelope, throttling, soft delete), the
role/permission matrix for Sozlamalar and for Maktab boshqaruvi, the management
API (retiring a grade with everything under it, reviving it, guardians matched
by id or JSHSHIR, photo validation and enrolment), the provisioning ladder
(who may create whom, that a super admin cannot mint a peer, that nobody edits
themselves, that a one-off password works but is never stored readable, and
that a reset kills every live session and is audited), and the whole turnstile
pipeline — event ingestion, deduplication, denied-read filtering, pairing
entries with exits, missed exits, undirected readers, and the end-of-day sweep.

The fixture day tracks the real calendar rather than a pinned date, so a report
that defaults to "today" cannot start failing once the clock moves past it.

---

## 16. Production checklist

**Before you deploy**

- [ ] `DJANGO_DEBUG=False` and `DJANGO_SETTINGS_MODULE=config.settings.prod`
- [ ] Fresh `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY`, `FIELD_ENCRYPTION_KEY`,
      `JSHSHIR_HASH_KEY`, `BOT_SERVICE_TOKEN` — none reused from development
- [ ] `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` list real hosts, no `*`
- [ ] `OTP_EXPOSE_IN_RESPONSE=False` (the prod settings assert on this)
- [ ] `SMS_PROVIDER=http` with a real gateway — `console` never reaches a parent
- [ ] One origin, no domain: `AUTH_COOKIE_DOMAIN` empty; over plain `http://`
      also `AUTH_COOKIE_SECURE=False` and `SECURE_SSL_REDIRECT=False`
- [ ] Plain HTTP stays on the local network — never expose it to the internet
- [ ] `python manage.py check --deploy` reports no issues
- [ ] `python manage.py collectstatic --noinput`
- [ ] Postgres and Redis are not reachable from the public internet

**Operations**

- [ ] Automated `pg_dump` backups, with a tested restore
- [ ] Back up `FIELD_ENCRYPTION_KEY` separately — **without it, encrypted
      JSHSHIR values are unrecoverable**, and rotating `JSHSHIR_HASH_KEY`
      invalidates every lookup
- [ ] Run Celery worker + beat under a supervisor (systemd / compose restart)
- [ ] Schedule `purge_expired_link_tokens`
- [ ] Ship logs somewhere durable; monitor `/api/health/`
- [ ] Error tracking (Sentry or similar) wired into `LOGGING`
- [ ] Set the bot webhook instead of long polling if you run several replicas
- [ ] Load the real register via the Excel import before inviting parents —
      registration only works for guardians the school has already recorded

**Terminals**

- [ ] Give each device a dedicated ISAPI account, not the shared `admin` login
- [ ] Keep the devices on a management VLAN; the backend reaches *them*, not the
      other way round, if you rely on polling
- [ ] Paste the push URL into each device and confirm the first event arrives
- [ ] Check `sync_terminal_clocks` is scheduled — clock drift silently corrupts
      attendance
- [ ] Rotate an ingest token if a device is replaced or its config is exposed
