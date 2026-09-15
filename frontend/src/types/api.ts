/** Shapes returned by the Django API. Kept in one place so pages never guess. */

/**
 * Most privileged first. DEVELOPER is unscoped and invisible to every other
 * role; OTA-ONA is the parent role, written the way the interface shows it.
 *
 * The codes are never translated — TEACHER reads as TEACHER in all three
 * languages — so they are rendered as-is wherever a role is named.
 */
export type Role =
  | 'DEVELOPER'
  | 'SUPER_ADMIN'
  | 'MODERATOR'
  | 'ADMIN'
  | 'TEACHER'
  | 'CURATOR'
  | 'STAFF'
  | 'OTA-ONA'

/**
 * A permission code as the server spells it, `<area>.<action>`.
 *
 * The list is not exhaustive on purpose: the server owns the catalogue, and a
 * permission it adds should not need a frontend release to be readable. The
 * named ones are the ones this app actually branches on, so a typo in those is
 * a compile error rather than a silently hidden button.
 */
export type Permission =
  | 'system.developer'
  | 'users.view'
  | 'users.manage'
  | 'roles.assign'
  | 'audit.view'
  | 'settings.view'
  | 'settings.appearance'
  | 'integrations.view'
  | 'integrations.manage'
  | 'register.access'
  | 'school.view'
  | 'school.manage'
  | 'students.view'
  | 'students.manage'
  | 'teachers.view'
  | 'teachers.manage'
  | 'staff.view'
  | 'staff.manage'
  | 'positions.view'
  | 'positions.manage'
  | 'classes.view'
  | 'classes.manage'
  | 'subjects.view'
  | 'subjects.manage'
  | 'timetable.view'
  | 'timetable.manage'
  | 'curators.view'
  | 'curators.manage'
  | 'guardians.view'
  | 'attendance.view'
  | 'attendance.mark'
  | 'absence.review'
  | 'reports.view'
  | 'export.run'
  | 'import.run'
  | 'self.view'
  | 'staff.cabinet'
  | 'children.view'
  | (string & {})

/** The signed-in person's own world, as the server scopes it. */
export interface SessionScope {
  teacher_subjects: {
    id: string
    name: string
    display_name: string
    class_group: string
    class_group_id: string | null
  }[]
  teacher_groups: { id: string; display_name: string }[]
  curator_groups: { id: string; display_name: string }[]
  children: { id: string; full_name: string; class_group: string }[]
}

export type AttendanceStatus = 'PRESENT' | 'ABSENT' | 'LATE' | 'EXCUSED'

export type DayState =
  | AttendanceStatus
  | 'NO_LESSONS'
  /** A school day that has not produced a gate pass yet (today, pre-arrival). */
  | 'NO_DATA'
  | 'HOLIDAY'
  | 'WEEKEND'
  | 'FUTURE'

/** Which way a pupil went through the turnstile. */
export type PassDirection = 'IN' | 'OUT' | 'UNKNOWN'

export type Relation = 'FATHER' | 'MOTHER' | 'GUARDIAN' | 'OTHER'

export type AbsenceRequestStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface User {
  id: number
  username: string
  full_name: string
  first_name: string
  last_name: string
  middle_name: string
  /** The role being worked through; identical to `active_role`. */
  role: Role
  active_role: Role
  /** Every role granted to the account, most privileged first. */
  roles: Role[]
  /** The role code itself — role names are not translated. */
  role_label: string
  /** What the *active* role may do. `can()` reads this and nothing else. */
  permissions: Permission[]
  /** The subjects, groups or children this session is about. */
  scope: SessionScope
  /** True when the account has a teacher or staff row behind it. */
  has_staff_record: boolean
  /** Always masked, e.g. `+998*****4567`. */
  phone: string
  is_phone_verified: boolean
  must_change_password: boolean
}

export interface Profile extends User {
  /** Always masked, e.g. `**********1234`. */
  /** The number itself, shown in full to its owner and to the register's
   *  administrators. */
  jshshir: string
  masked_jshshir: string
  telegram: {
    linked: boolean
    username: string
    notifications_enabled: boolean
    linked_at?: string
  }
  children_count: number
}

/**
 * What the interface offers everyone, decided once for the installation.
 *
 * Not a browser preference: the two unscoped roles set it and every signed-in
 * person reads it. `can_edit` says which side of that the viewer is on.
 */
export interface AppearanceSettings {
  multi_theme: boolean
  particles: boolean
  can_edit: boolean
}

export interface LoginResponse {
  access: string
  expires_in: number
  csrf: string
  user: User
  /** Only present right after registration. */
  username?: string
  detail?: string
}

/**
 * Presence totals for a period. `rate` is `days_present / school_days` and is
 * computed by the backend only — the UI never derives a percentage.
 */
export interface AttendanceSummary {
  school_days: number
  days_present: number
  days_absent: number
  days_late: number
  entries: number
  exits: number
  inside_minutes: number
  outside_minutes: number
  late_minutes: number
  avg_inside_minutes: number
  rate: number
}

export interface Child {
  id: string
  first_name: string
  last_name: string
  middle_name: string
  full_name: string
  display_name: string
  initials: string
  class_group: string
  class_group_id: string
  grade_level: number
  school: string
  relation: Relation | null
  relation_label?: string | null
  is_primary?: boolean
  photo?: string | null
  current_month?: AttendanceSummary
}

/** One entry→exit stretch inside the building. `out` is null while inside. */
export interface Visit {
  in: string | null
  out: string | null
  minutes: number
  open: boolean
}

/** One raw turnstile pass, as the device reported it. */
export interface GatePass {
  id: string
  time: string | null
  direction: PassDirection
  verify_mode: string
  terminal: string
  location: string
}

/** Everything one day contributes to any presence report. */
export interface PresenceDay {
  date: string
  weekday: number
  weekday_short: string
  weekday_name: string
  state: DayState
  holiday: string | null
  is_school_day: boolean
  /** False for an arrival past the cutoff: shown, but not counted as a day. */
  was_present: boolean
  /** They did turn up, but too late for the day to count. */
  arrived_too_late: boolean
  /** The arrival time even when it did not count. */
  arrived_at: string | null
  /** True while the pupil is inside: the last entry has no exit yet. */
  is_inside: boolean
  first_in: string | null
  last_out: string | null
  first_out: string | null
  last_in: string | null
  entries: number
  exits: number
  inside_minutes: number
  outside_minutes: number
  late_minutes: number
  left_early: boolean
  visits: Visit[]
}

export interface DailyReport extends PresenceDay {
  passes: GatePass[]
  summary: AttendanceSummary
}

export type WeeklyDay = PresenceDay

export interface WeeklyReport {
  start_date: string
  end_date: string
  days: PresenceDay[]
  summary: AttendanceSummary
}

export interface CalendarDay extends PresenceDay {
  day: number
  in_month: boolean
  is_today: boolean
  absence_request?: {
    id: string
    status: AbsenceRequestStatus
    reason: string
    comment: string
  } | null
}

export interface MonthlyReport {
  year: number
  month: number
  month_name: string
  start_date: string
  end_date: string
  grid_start: string
  grid_end: string
  weekday_labels: string[]
  days: CalendarDay[]
  summary: AttendanceSummary
}

export interface YearlyMonth {
  year: number
  month: number
  month_name: string
  summary: AttendanceSummary
}

export interface YearlyReport {
  academic_year: string
  start_date: string
  end_date: string
  months: YearlyMonth[]
  summary: AttendanceSummary
}

export interface Dashboard {
  student: Child
  today: {
    date: string
    state: DayState
    was_present: boolean
    arrived_too_late: boolean
    arrived_at: string | null
    is_inside: boolean
    first_in: string | null
    last_out: string | null
    entries: number
    exits: number
    inside_minutes: number
    outside_minutes: number
    late_minutes: number
    visits: Visit[]
    passes: GatePass[]
    summary: AttendanceSummary
  }
  current_month: {
    year: number
    month: number
    start_date: string
    end_date: string
    summary: AttendanceSummary
  }
  recent_days: PresenceDay[]
  notifications_count: number
  pending_absence_requests: number
}

export interface Notification {
  id: string
  type: string
  title: string
  message: string
  payload: Record<string, unknown>
  is_read: boolean
  read_at: string | null
  created_at: string
  student: string | null
  student_name: string | null
  student_class: string | null
}

export interface Paginated<T> {
  count: number
  page: number
  page_size: number
  total_pages: number
  next: string | null
  previous: string | null
  results: T[]
  unread_count?: number
}

export interface AttendanceReason {
  id: string
  code: string
  name: string
  requires_comment: boolean
  requires_document: boolean
  order: number
}

export interface AbsenceRequest {
  id: string
  student: string
  student_name: string
  date: string
  reason: string
  reason_name: string
  comment: string
  status: AbsenceRequestStatus
  submitted_at: string
  reviewed_at: string | null
  reviewed_by_name: string | null
  review_comment: string
  lesson_ids: string[]
}

export interface TelegramStatus {
  linked: boolean
  username: string
  notifications_enabled: boolean
  linked_at: string | null
  bot_username: string
}

export interface TelegramLinkCode {
  code: string
  deep_link: string
  bot_username: string
  expires_at: string
}

/* --- registration ------------------------------------------------------- */

export interface School {
  id: string
  name: string
  short_name: string
  region: string
  district: string
}

export interface Grade {
  id: string
  level: number
  display_name: string
  school: string
  class_groups_count: number
}

export interface ClassGroup {
  id: string
  name: string
  display_name: string
  grade: string
  grade_level: number
  school: string
  room: string
}

export interface StudentSearchResult {
  id: string
  display_name: string
  full_name: string
  class_group: string
  birth_year: number | null
  /** So a parent can recognise their child among similar surnames. */
  photo: string | null
  has_registered_guardian: boolean
}

export interface RegistrationSession {
  session_token: string
  guardian_name: string
  masked_phone: string
  student_name: string
  class_group: string
  relation: Relation
  phone_verified: boolean
}

export interface OtpSent {
  sent: boolean
  /**
   * False when the configured SMS provider only prints the message — the code
   * exists but nothing reached a phone, so the UI has to say so instead of
   * letting the parent guess.
   */
  delivered?: boolean
  masked_phone: string
  ttl_seconds: number
  resend_after_seconds: number
  /** How many digits the code has; the input sizes itself from it. */
  code_length?: number
  /** Development only (OTP_EXPOSE_IN_RESPONSE). */
  debug_code: string | null
}

export interface PasswordResetStart extends OtpSent {
  session_token: string
  detail: string
}

/* --- settings & integrations -------------------------------------------- */

export type IntegrationKind = 'TELEGRAM_BOT' | 'SMS_ESKIZ' | 'FACE_ID' | 'TERMINALS'

export type IntegrationStatus = 'UNKNOWN' | 'OK' | 'ERROR' | 'DISABLED'

export type TerminalDirection = 'IN' | 'OUT' | 'BOTH'

export type EventDirection = 'IN' | 'OUT' | 'UNKNOWN'

export type SyncState = 'PENDING' | 'SYNCED' | 'FAILED'

export interface SettingsSection {
  key: string
  label: string
  description: string
  available: boolean
  children?: { key: string; label: string }[]
}

export interface SettingsOverview {
  role: Role
  roles: Role[]
  permissions: Permission[]
  can_manage_integrations: boolean
  sections: SettingsSection[]
}

export interface Integration {
  id: string
  kind: IntegrationKind
  kind_display: string
  school: string | null
  school_name: string | null
  is_enabled: boolean
  config: Record<string, unknown>
  /** Values are masked (`••••••1234`) — the real secret never leaves the server. */
  secrets: Record<string, string>
  status: IntegrationStatus
  status_display: string
  effective_status: IntegrationStatus
  last_checked_at: string | null
  last_error: string
  updated_at: string
  effective_config?: Record<string, unknown>
  defaults?: Record<string, unknown>
}

export interface IntegrationTestResult {
  ok: boolean
  status?: IntegrationStatus
  message?: string
  details?: Record<string, unknown>
}

export interface Terminal {
  id: string
  school: string
  school_name: string
  name: string
  vendor: string
  model: string
  serial_number: string
  host: string
  port: number
  use_https: boolean
  username: string
  has_password: boolean
  direction: TerminalDirection
  direction_display: string
  location: string
  is_active: boolean
  base_url: string
  /** Paste into the device's HTTP Listening settings. */
  ingest_url: string
  firmware: string
  status: IntegrationStatus
  status_display: string
  last_error: string
  last_seen_at: string | null
  last_event_at: string | null
  last_polled_at: string | null
  enrolled_count: number
  events_today: number
  created_at: string
}

export interface TerminalPayload {
  school: string
  name: string
  host: string
  port?: number
  use_https?: boolean
  username?: string
  password?: string
  direction?: TerminalDirection
  location?: string
  is_active?: boolean
  vendor?: string
  model?: string
}

export interface TerminalTestResult {
  ok: boolean
  message?: string
  device?: {
    name: string
    model: string
    serial_number: string
    firmware: string
    mac?: string
  }
  people_on_device?: number
}

export interface TerminalEvent {
  id: string
  terminal: string
  terminal_name: string
  occurred_at: string
  date: string
  direction: EventDirection
  direction_display: string
  verify_mode: string
  verify_mode_display: string
  person_code: string
  person_name: string
  student: string | null
  student_name: string | null
  student_class: string | null
  processed: boolean
}

export interface TerminalPerson {
  id: string
  student: string
  student_name: string
  student_class: string
  person_code: string
  card_no: string
  has_face: boolean
  has_photo: boolean
  face_synced_at: string | null
  sync_state: SyncState
  sync_error: string
}

export interface DailyPresence {
  id: string
  student: string
  student_name: string
  student_class: string
  date: string
  first_in_at: string | null
  last_out_at: string | null
  entries_count: number
  exits_count: number
  late_minutes: number
  left_early: boolean
  duration_minutes: number
  source: string
}

export interface Choice {
  value: string
  label: string
}

// --------------------------------------------------------------------------
// Management (ADMIN cabinet): grades, class groups, pupils and their guardians
// --------------------------------------------------------------------------
export interface ManagedGrade {
  id: string
  level: number
  label: string
  class_groups_count: number
  students_count: number
}

export interface ManagedClassGroup {
  id: string
  name: string
  display_name: string
  room: string
  grade_id: string
  grade_level: number
  students_count: number
}

export interface ManagedGuardian {
  id: string
  link_id: string
  full_name: string
  first_name: string
  last_name: string
  middle_name: string
  relation: Relation
  relation_label: string
  phone: string
  /** The number itself, shown in full to its owner and to the register's
   *  administrators. */
  jshshir: string
  masked_jshshir: string
  is_primary: boolean
  verified: boolean
  has_account: boolean
}

export interface ManagedStudent {
  id: string
  first_name: string
  last_name: string
  middle_name: string
  full_name: string
  display_name: string
  initials: string
  photo: string | null
  birth_date: string | null
  gender: string
  student_code: string
  class_group: string
  class_group_id: string
  is_active: boolean
  guardians: ManagedGuardian[]
  /** How many of the pupil's guardians have claimed an account. */
  registered_guardians: number
  terminal: {
    person_code: string
    has_face: boolean
    sync_state: 'PENDING' | 'SYNCED' | 'FAILED'
    sync_error: string
    terminals: number
  } | null
}

/**
 * One "yaqini" row from the + button on the pupil form. An existing guardian
 * carries `id` (their stored JSHSHIR never reaches the browser); a new one
 * must supply `jshshir`.
 */
export interface GuardianInput {
  id?: string
  last_name: string
  first_name: string
  middle_name: string
  relation: Relation
  phone: string
  jshshir: string
  is_primary: boolean
}

export interface StudentInput {
  last_name: string
  first_name: string
  middle_name: string
  class_group: string
  birth_date?: string | null
  gender?: string
  student_code?: string
  guardians: GuardianInput[]
}

// --------------------------------------------------------------------------
// Staff accounts and registration visibility (SUPER_ADMIN / DEVELOPER)
// --------------------------------------------------------------------------
/** Roles that can be provisioned by hand. Parents register themselves. */
export type StaffRole = Exclude<Role, 'OTA-ONA'>

/**
 * An employee's own presence over one span — a week, a month, a school year.
 *
 * `rate` is `days_present / school_days`, computed by the server only: the UI
 * never derives a percentage, here or anywhere else.
 */
export interface PresenceSummary {
  start_date: string
  end_date: string
  school_days: number
  days_present: number
  days_absent: number
  active_minutes: number
  inactive_minutes: number
  late_days: number
  rate: number
}

export interface PresenceStats {
  date: string
  week: PresenceSummary
  month: PresenceSummary
  year: PresenceSummary
}

/** One curator link: a person, and the class group they watch. */
export interface CuratorAssignment {
  id: string
  user: number
  /** The register row behind the curator — whichever of the two exists. */
  teacher_id: string | null
  staff_id: string | null
  photo: string | null
  roles: Role[]
  username: string
  full_name: string
  phone: string
  class_group: string
  class_group_name: string
  grade_level: number
  students_count: number
  created_at: string
}

export interface CuratorSection {
  results: CuratorAssignment[]
  class_groups: {
    id: string
    display_name: string
    grade_level: number
    students_count: number
  }[]
  candidates: { id: number; username: string; full_name: string; roles: Role[] }[]
}

export interface StaffUser {
  id: number
  username: string
  full_name: string
  first_name: string
  last_name: string
  middle_name: string
  /** The role they are working through, and every role they hold. */
  role: Role
  active_role: Role
  roles: Role[]
  role_label: string
  phone: string
  is_active: boolean
  /** True until they have replaced the temporary password they were given. */
  must_change_password: boolean
  last_login: string | null
  created_at: string
  school: string | null
  /** Whether the signed-in user may disable, reset or delete this account. */
  can_manage: boolean
  /** The row is the signed-in user's own account. */
  is_self: boolean
  /** Name, phone and roles may be edited — the user's own row included. */
  can_edit: boolean
  /** On your own row: your highest role, which you cannot take away from yourself. */
  locked_role: Role | null
}

/**
 * The response to creating an account or resetting one. `temporary_password` is
 * the only moment it exists in readable form — the store holds an Argon2 hash.
 */
export interface ProvisionedUser {
  user: StaffUser
  temporary_password: string
  detail: string
}

export interface GuardianRow {
  id: string
  full_name: string
  phone: string
  /** The number itself, shown in full to its owner and to the register's
   *  administrators. */
  jshshir: string
  masked_jshshir: string
  is_active: boolean
  has_account: boolean
  username: string | null
  registered_at: string | null
  last_login: string | null
  children: {
    id: string
    full_name: string
    class_group: string
    relation: Relation
    relation_label: string
    is_primary: boolean
    verified: boolean
  }[]
}

// --------------------------------------------------------------------------
// Admin console — what the Django admin used to own
// --------------------------------------------------------------------------
export interface ManagedSchool {
  id: string
  name: string
  short_name: string
  region: string
  district: string
  address: string
  phone: string
  /** ISO weekdays the school is open (Mon=1). Everything else is a weekend. */
  working_weekdays: number[]
  is_active: boolean
  students_count: number
  class_groups_count: number
}

export interface ManagedAcademicYear {
  id: string
  name: string
  start_date: string
  end_date: string
  is_current: boolean
}

export interface ManagedHoliday {
  id: string
  date: string
  name: string
  /** A working Saturday: listed, but still counts as a school day. */
  is_working_day: boolean
  academic_year: string
}

export interface ManagedSubject {
  id: string
  name: string
  /** `Matematika 1-A` — the label every list and picker shows. */
  display_name: string
  class_group: string | null
  class_group_name: string
  grade_level: number | null
  short_name: string
  color: string
  is_active: boolean
}

export interface ManagedTeacher {
  id: string
  full_name: string
  first_name: string
  last_name: string
  middle_name: string
  /** `AA1234567`. Blank when the document was not recorded. */
  passport_id: string
  /** The number itself, shown in full to its owner and to the register's
   *  administrators. */
  jshshir: string
  masked_jshshir: string
  has_jshshir: boolean
  birth_date: string | null
  gender: '' | 'MALE' | 'FEMALE'
  gender_label: string
  phone: string
  email: string
  /** The face pushed to the turnstile. */
  photo: string | null
  is_active: boolean
  username: string | null
  subjects: { id: string; name: string; display_name: string }[]
}

export interface TeacherPayload {
  first_name: string
  last_name: string
  middle_name?: string
  passport_id?: string
  jshshir?: string
  birth_date?: string | null
  gender?: string
  phone?: string
  email?: string
  subjects?: string[]
  /** Cabinet credentials. All three travel together, or none of them. */
  username?: string
  password?: string
  password_confirm?: string
}

/**
 * A job title, written once per interface language.
 *
 * `titles` carries all three at once so a list can be labelled in whichever
 * language the browser is running in without asking the server again. A title
 * left blank falls back to the Uzbek one rather than rendering empty.
 */
export interface ManagedPosition {
  id: string
  title_uz: string
  title_ru: string
  title_en: string
  titles: { uz: string; ru: string; en: string }
  /** How many people currently hold it — a position in use cannot be removed. */
  staff_count: number
}

export interface PositionPayload {
  title_uz: string
  title_ru?: string
  title_en?: string
}

/** A school employee who is not a teacher: the same person fields, plus a job. */
export interface ManagedStaff {
  id: string
  full_name: string
  first_name: string
  last_name: string
  middle_name: string
  /** `AA1234567`. Blank when the document was not recorded. */
  passport_id: string
  jshshir: string
  masked_jshshir: string
  has_jshshir: boolean
  birth_date: string | null
  gender: '' | 'MALE' | 'FEMALE'
  gender_label: string
  phone: string
  email: string
  photo: string | null
  is_active: boolean
  username: string | null
  position: {
    id: string
    title_uz: string
    title_ru: string
    title_en: string
    titles: { uz: string; ru: string; en: string }
  } | null
  /** The access roles of their cabinet account, when they have one at all. */
  role: Role | null
  roles: Role[]
  role_label: string | null
}

/**
 * Everything a card opens: who the person is, how they sign in, what they do
 * at the school and how their week looks. One shape for a teacher and for any
 * other employee — the "work" half is simply empty where it does not apply.
 */
export interface PersonProfile {
  id: string
  kind: 'teacher' | 'staff'
  full_name: string
  first_name: string
  last_name: string
  middle_name: string
  photo: string | null
  gender: '' | 'MALE' | 'FEMALE'
  gender_label: string
  birth_date: string | null
  passport_id: string
  jshshir: string
  masked_jshshir: string
  phone: string
  email: string
  is_active: boolean
  school: string
  account: {
    id: number
    username: string
    roles: Role[]
    active_role: Role
    is_active: boolean
    must_change_password: boolean
    last_login: string | null
    created_at: string | null
  } | null
  position: { id: string; titles: { uz: string; ru: string; en: string } } | null
  subjects: { class_group: string; subjects: string[] }[]
  subjects_count: number
  curator_groups: { id: string; display_name: string; students_count: number }[]
  homeroom_groups: string[]
  timetable: {
    lessons_per_week: number
    days: {
      weekday: number
      label: string
      lessons: {
        lesson_number: number
        start_time: string
        end_time: string
        subject: string
        class_group: string
        room: string
      }[]
    }[]
  }
  week: PresenceSummary | null
}

export interface StaffPayload {
  first_name: string
  last_name: string
  middle_name?: string
  passport_id?: string
  jshshir?: string
  birth_date?: string | null
  gender?: string
  phone?: string
  email?: string
  /** Optional, and clearable: the person is entered first and labelled after.
   *  `null` takes the label back off. */
  position?: string | null
  /** The access roles for their account. Optional in the same way — most of the
   *  staff never sign in. One person may hold several; DEVELOPER is never
   *  accepted here. */
  roles?: string[]
  /** Cabinet credentials. All three travel together, or none of them. */
  username?: string
  password?: string
  password_confirm?: string
}

export interface ImportReport {
  dry_run: boolean
  ok: boolean
  total_rows: number
  students_created: number
  students_updated: number
  guardians_created: number
  guardians_updated: number
  links_created: number
  links_skipped: number
  errors: { row: number; column: string; message: string }[]
  preview: Record<string, unknown>[]
}

export interface AuditEntry {
  id: string
  created_at: string
  action: string
  action_label: string
  username: string
  entity_type: string
  entity_id: string
  ip_address: string | null
  success: boolean
  metadata: Record<string, unknown>
  old_data: Record<string, unknown> | null
  new_data: Record<string, unknown> | null
}


// --------------------------------------------------------------------------- //
// Dars davomati — the register a teacher fills in
// --------------------------------------------------------------------------- //
/** `null` means the pupil has not been marked yet. */
export type LessonStatus = 'PRESENT' | 'LATE' | 'ABSENT' | 'EXCUSED' | null

export interface TeachingSubject {
  id: string
  name: string
  /** `Matematika 1-A`. */
  display_name: string
  class_group: string
  class_group_name: string
  grade_level: number
  students_count: number
  /** How many of the pupils already carry a mark for the chosen day. */
  marked_count: number
  teachers: string[]
}

export interface LessonRosterStudent {
  id: string
  full_name: string
  display_name: string
  initials: string
  photo: string | null
  status: LessonStatus
  status_label: string
  late_minutes: number
  /** Why the pupil was away — only ever set on an excused absence. */
  comment: string
}

export interface LessonRoster {
  subject: TeachingSubject
  date: string
  /** False until the lesson has actually started. */
  can_mark: boolean
  /** `10:20` — when the register unlocks; null once it is open. */
  opens_at: string | null
  students: LessonRosterStudent[]
}

export interface LessonMark {
  student: string
  status: LessonStatus | ''
  late_minutes?: number
  comment?: string
}

export interface LessonRow {
  id: string
  date: string
  lesson_number: number
  subject: string
  subject_display: string
  subject_id: string
  teacher: string
  status: Exclude<LessonStatus, null>
  status_label: string
  late_minutes: number
  comment: string
  is_canceled: boolean
}

export interface LessonTotals {
  lessons: number
  present: number
  late: number
  absent: number
  excused: number
  attended: number
  rate: number
}

export interface LessonSubjectTotals extends LessonTotals {
  id: string
  name: string
  display_name: string
  teacher: string
}

export interface LessonAttendanceReport {
  start_date: string
  end_date: string
  summary: LessonTotals
  subjects: LessonSubjectTotals[]
  days: { date: string; lessons: LessonRow[] }[]
  today: string
}


// --------------------------------------------------------------------------- //
// Dars jadvali
// --------------------------------------------------------------------------- //
export interface ScheduleEntry {
  id: string
  weekday: number
  weekday_label: string
  lesson_number: number
  /** `08:00`. */
  start_time: string
  end_time: string
  room: string
  subject: string
  subject_name: string
  subject_display: string
  teacher: string | null
  teacher_name: string
}

/** Green today, amber tomorrow, grey any other day. */
export type ScheduleState = 'TODAY' | 'TOMORROW' | 'NONE'

export interface TeachingClass {
  id: string
  display_name: string
  grade_level: number
  students_count: number
  marked_count: number
  schedule_state: ScheduleState
  subjects: { id: string; name: string; display_name: string }[]
}

export interface TeachingClassLesson {
  /** `null` when there is no timetable and the subject is offered on its own. */
  id: string | null
  lesson_number: number
  start_time: string | null
  end_time: string | null
  room: string
  subject: string
  subject_name: string
  subject_display: string
  teacher: string | null
  teacher_name: string
  is_mine: boolean
  marked_count: number
  students_count: number
  /** False until the lesson has started. */
  can_mark: boolean
}

export interface TeachingClassDay {
  class_group: {
    id: string
    display_name: string
    grade_level: number
    students_count: number
  }
  date: string
  weekday: number
  has_timetable: boolean
  lessons: TeachingClassLesson[]
}


// --------------------------------------------------------------------------- //
// The teacher's own cabinet
// --------------------------------------------------------------------------- //
export interface TeacherSchool {
  id: string
  name: string
  short_name: string
  logo: string | null
}

export interface TeacherCard {
  id: string
  first_name: string
  last_name: string
  middle_name: string
  full_name: string
  photo: string | null
  email: string
  school: TeacherSchool
}

export interface TeacherWeek {
  start_date: string
  end_date: string
  school_days: number
  active_minutes: number
  inactive_minutes: number
  late_days: number
}

/** One stretch of the day: inside the school, or not. */
export interface TimelineSegment {
  state: 'IN' | 'OUT'
  start: string
  end: string
  minutes: number
  /** Percentages across the 06:00–00:00 band. */
  left: number
  width: number
}

export interface TeacherTimeline {
  date: string
  start_hour: number
  end_hour: number
  segments: TimelineSegment[]
  first_in: string | null
  last_out: string | null
  is_inside: boolean
  inside_minutes: number
}

export interface TurnstilePass {
  id: string
  direction: 'IN' | 'OUT'
  label: string
  at: string
  time: string
  date: string
  terminal: string
}

export interface TeacherDashboard {
  teacher: TeacherCard
  week: TeacherWeek
  timeline: TeacherTimeline
  recent_passes: TurnstilePass[]
  /** Working as a TEACHER: the lessons they give today. `null` in any other role. */
  lessons_today?: TodayLesson[] | null
  /** Working as a CURATOR: their own groups' day. `null` in any other role. */
  groups_today?: CuratorGroupToday[] | null
}

/** One lesson the timetable puts this teacher in front of today. */
export interface TodayLesson {
  id: string
  subject: string
  subject_name: string
  class_group: string
  class_group_name: string
  lesson_number: number
  start_time: string
  end_time: string
  room: string
  students_count: number
  marked_count: number
}

/** A group's day at the gate: the same figures the school's home screen shows. */
export interface GroupPupilsToday {
  total: number
  arrived: number
  absent: number
  inside: number
  late: number
  rate: number
  avg_active_minutes: number
  avg_inactive_minutes: number
  avg_late_minutes: number
}

export interface CuratorGroupToday {
  id: string
  display_name: string
  grade_level: number
  pupils: GroupPupilsToday
  lessons: { marked: number; absent: number; excused: number }
}

export interface TeacherSubjectCard {
  id: string
  name: string
  display_name: string
  class_group_name: string
}

export interface TeacherProfile extends TeacherCard {
  birth_date: string | null
  passport_id: string
  /** The number itself, shown in full to its owner and to the register's
   *  administrators. */
  jshshir: string
  masked_jshshir: string
  has_jshshir: boolean
  gender: '' | 'MALE' | 'FEMALE'
  gender_label: string
  phone: string
  username: string
  role_label: string
  subjects: TeacherSubjectCard[]
  genders: { value: string; label: string }[]
}

export interface TeacherProfilePayload {
  first_name?: string
  last_name?: string
  middle_name?: string
  birth_date?: string | null
  passport_id?: string
  jshshir?: string
  gender?: string
  phone?: string
  email?: string
  password?: string
  password_confirm?: string
}

export interface TeacherLesson {
  subject: string
  subject_name: string
  class_group_name: string
  grade_level: number
  lesson_number: number
  start_time: string | null
  end_time: string | null
  room: string
  can_mark: boolean
  opens_at: string | null
}


/** One square of the teacher's month grid. */
export interface TeachingCalendarDay {
  date: string
  weekday: number
  in_month: boolean
  is_school_day: boolean
  holiday: string | null
  /** Green when the timetable puts them in front of a class that day. */
  teaches: boolean
  groups_count: number
}

export interface TeachingCalendar {
  year: number
  month: number
  start_date: string
  end_date: string
  today: string
  days: TeachingCalendarDay[]
}

export interface TeachingDayLesson {
  subject: string
  subject_name: string
  lesson_number: number
  start_time: string
  end_time: string
  room: string
  marked_count: number
  students_count: number
}

export interface TeachingDayGroup {
  id: string
  display_name: string
  grade_level: number
  students_count: number
  lessons: TeachingDayLesson[]
}

export interface TeachingDay {
  date: string
  weekday: number
  holiday: string | null
  groups: TeachingDayGroup[]
}

/** One row of the navbar search: a class, a subject, a pupil or a colleague. */
export interface SearchHit {
  kind: 'class' | 'subject' | 'student' | 'teacher'
  id: string
  title: string
  subtitle: string
  is_mine?: boolean
}


/** The numbers an administrator's home screen opens on. */
/**
 * One day at the gate for one group of people.
 *
 * The teachers and the pupils answer the same four questions and carry the
 * same three averages, so the home screen lays both out with one component.
 * The averages describe the people they are about: time inside is averaged
 * over those who came, lateness over those who were late.
 */
export interface AttendanceToday {
  total: number
  arrived: number
  absent: number
  inside: number
  late: number
  rate: number
  avg_active_minutes: number
  avg_inactive_minutes: number
  avg_late_minutes: number
}

export interface SchoolOverview {
  school: string
  date: string
  register: {
    students: number
    teachers: number
    staff: number
    positions: number
    class_groups: number
    subjects: number
    guardians: number
    lessons_scheduled: number
  }
  /** The pupils, under the name the older screens already read. */
  today: AttendanceToday
  students_today: AttendanceToday
  teachers_today: AttendanceToday
  lessons: { marked: number; absent: number; excused: number }
  terminals: { total: number; online: number; offline: number }
}
