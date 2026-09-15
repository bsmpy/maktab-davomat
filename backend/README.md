# Backend — Django + DRF

The API, the business logic and the admin. See the [root README](../README.md)
for the whole-project picture and the production checklist.

## Run

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # fill it in
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
```

Settings modules: `config.settings.dev` (default), `.prod`, `.test`. Select with
`DJANGO_SETTINGS_MODULE`.

## Layout

```text
config/          settings, urls (config/api_urls.py holds the whole v1 surface),
                 celery, wsgi/asgi
apps/
  common/        abstract models (timestamps, UUID pk, soft delete), the error
                 envelope, pagination, throttles, permissions, crypto helpers,
                 the OTP service and the SMS provider abstraction
  accounts/      User, JWT auth + refresh cookies, the registration wizard,
                 password change/reset, username generation
  schools/       School, AcademicYear, Grade, ClassGroup, Subject, Teacher,
                 Holiday, the public catalogue API and the Excel import
  students/      Student and its admin (including the import screen)
  guardians/     Guardian, GuardianStudent, the children API and — importantly —
                 selectors.py, the single place that decides who may read whom
  attendance/    Schedule, Lesson, Attendance, AttendanceHistory,
                 AttendanceReason, AbsenceRequest; services/ holds every report
  notifications/ Notification, NotificationDelivery, Celery tasks
  telegram/      TelegramAccount, one-time link tokens, the bot service API
  audit/         AuditLog and the request-context middleware
tests/           pytest suite
```

## Where things live

| Question | File |
|---|---|
| How is the attendance % computed? | `apps/attendance/services/statistics.py` |
| Daily / weekly / monthly / yearly reports | `apps/attendance/services/reports.py` |
| The dashboard payload | `apps/attendance/services/dashboard.py` |
| Timetable → concrete lessons | `apps/attendance/services/scheduling.py` |
| Who may see which pupil | `apps/guardians/selectors.py` |
| Registration rules and threat model | `apps/accounts/services/registration.py` |
| Username generation | `apps/accounts/services/username.py` |
| Refresh cookie + CSRF | `apps/accounts/cookies.py` |
| JSHSHIR hashing/encryption | `apps/common/crypto.py` |
| OTP issue/verify | `apps/common/otp.py` |
| Swapping in a real SMS gateway | `apps/common/sms/` |
| Error envelope | `apps/common/exceptions.py` |

## Management commands

```bash
python manage.py seed_demo [--history-days 210] [--students-per-class 10] [--flush]
python manage.py generate_lessons --from 2026-09-01 --to 2026-09-30
python manage.py import_students --make-template namuna.xlsx
python manage.py import_students data.xlsx            # preview
python manage.py import_students data.xlsx --commit   # write
```

## Checks

```bash
python manage.py check
python manage.py check --deploy               # with the prod settings
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file /dev/null # OpenAPI must build cleanly
python -m pytest
ruff check apps config tests
```

## Adding an SMS gateway

Subclass `apps/common/sms/base.SMSProvider`, register it in
`apps/common/sms/registry.PROVIDERS`, and point `SMS_PROVIDER` at it. No call
site changes: `OTPService` only knows the abstraction. A generic JSON gateway
(`http`) is already implemented for Eskiz/Play-Mobile-shaped APIs.

## Integrations and terminals

`Sozlamalar → Integratsiyalar` lives in `apps/integrations`. Four kinds
(`TELEGRAM_BOT`, `SMS_ESKIZ`, `FACE_ID`, `TERMINALS`), each a row with a
non-secret `config` JSON blob and a Fernet-encrypted secrets blob.

| Question | File |
|---|---|
| Config resolution (DB → env, school → global) | `apps/integrations/services/registry.py` |
| Hikvision ISAPI calls | `apps/integrations/services/hikvision.py` |
| Push/poll ingestion + deduplication | `apps/integrations/services/ingest.py` |
| Arrival/departure → per-lesson attendance | `apps/integrations/services/presence.py` |
| Enrolling pupils and faces onto devices | `apps/integrations/services/enrollment.py` |
| Eskiz SMS gateway | `apps/common/sms/eskiz.py` |
| Celery tasks (poll, sweep, clock sync, enrol) | `apps/integrations/tasks.py` |

```bash
python manage.py setup_integrations --with-beat   # create rows + periodic tasks
```

### Adding a new integration

1. Add a value to `IntegrationKind` and its defaults to
   `services/registry.DEFAULT_CONFIG`.
2. Add a branch to `IntegrationTestView._run_check` so the *Tekshirish* button
   can prove the credentials work.
3. Add a form component under `frontend/src/features/settings/`.

Secrets go in the encrypted blob via `update_secrets()`, never in a column —
`masked_secrets()` is the only thing a serializer may expose.

### Supporting another terminal vendor

`TerminalVendor` is a choice field and `HikvisionClient` is the only
vendor-specific module. A new vendor needs a client with the same surface
(`device_info`, `search_events`, `upsert_person`, `upload_face`,
`delete_person`) plus a branch in `services/ingest.py` for its event shape.
Everything downstream — presence, the attendance rules, the UI — is
vendor-agnostic.
