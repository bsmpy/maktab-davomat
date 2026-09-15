import type { Permission, Role, SessionScope, User } from '@/types/api'

/**
 * A signed-in session, as `/auth/me/` would hand it over.
 *
 * The permission lists below mirror the server's catalogue
 * (`apps/accounts/catalog.py`). They are test data, not a second source of
 * truth: the app itself never derives permissions from a role — it reads the
 * list the server sent — so this file is the only place in the frontend that
 * knows which role carries what, and it exists so a test can say "sign in as a
 * CURATOR" in one line.
 */

const REGISTER_READ: Permission[] = [
  'register.access',
  'school.view',
  'students.view',
  'teachers.view',
  'staff.view',
  'positions.view',
  'classes.view',
  'subjects.view',
  'timetable.view',
  'curators.view',
  'guardians.view',
  'attendance.view',
  'reports.view',
  'self.view',
  'staff.cabinet',
]

const REGISTER_WRITE: Permission[] = [
  'students.manage',
  'teachers.manage',
  'staff.manage',
  'positions.manage',
  'classes.manage',
  'subjects.manage',
  'timetable.manage',
  'curators.manage',
  'school.manage',
  'attendance.mark',
  'absence.review',
  'export.run',
  'import.run',
]

const EVERYTHING: Permission[] = [
  ...REGISTER_READ,
  ...REGISTER_WRITE,
  'system.developer',
  'users.view',
  'users.manage',
  'roles.assign',
  'audit.view',
  'settings.view',
  'settings.appearance',
  'integrations.view',
  'integrations.manage',
  'children.view',
]

export const PERMISSIONS_BY_ROLE: Record<Role, Permission[]> = {
  DEVELOPER: EVERYTHING,
  SUPER_ADMIN: EVERYTHING.filter(
    (permission) => permission !== 'system.developer' && permission !== 'integrations.manage',
  ),
  MODERATOR: [...REGISTER_READ, 'users.view', 'settings.view'],
  // No attendance of anybody else: no Davomat, no Kalendar, no school figures.
  ADMIN: [...REGISTER_READ, ...REGISTER_WRITE, 'settings.view', 'settings.appearance'].filter(
    (permission) =>
      !['attendance.view', 'attendance.mark', 'absence.review', 'reports.view'].includes(
        permission,
      ),
  ),
  TEACHER: [
    'self.view',
    'staff.cabinet',
    'classes.view',
    'subjects.view',
    'students.view',
    'timetable.view',
    'attendance.view',
    'attendance.mark',
    'absence.review',
  ],
  CURATOR: [
    'self.view',
    'staff.cabinet',
    'classes.view',
    'students.view',
    'timetable.view',
    'attendance.view',
    'reports.view',
  ],
  STAFF: ['self.view', 'staff.cabinet'],
  'OTA-ONA': ['self.view', 'children.view'],
}

const EMPTY_SCOPE: SessionScope = {
  teacher_subjects: [],
  teacher_groups: [],
  curator_groups: [],
  children: [],
}

/** One signed-in person, working through `role` and holding `roles`. */
export function makeUser(role: Role, overrides: Partial<User> = {}): User {
  return {
    id: 1,
    username: role === 'OTA-ONA' ? 'a.valiyev' : 'bsm',
    full_name: 'Test Foydalanuvchi',
    first_name: 'Test',
    last_name: 'Foydalanuvchi',
    middle_name: '',
    role,
    active_role: role,
    roles: [role],
    role_label: role,
    permissions: PERMISSIONS_BY_ROLE[role],
    scope: EMPTY_SCOPE,
    has_staff_record: role !== 'OTA-ONA',
    phone: '+998*****4567',
    is_phone_verified: true,
    must_change_password: false,
    ...overrides,
  }
}
