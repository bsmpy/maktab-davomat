import type { ComponentType, SVGProps } from 'react'

import { userCan, userCanAny } from '@/auth/permissions'
import type { Permission, Role, User } from '@/types/api'

import {
  BellIcon,
  CalendarIcon,
  ChartIcon,
  FileTextIcon,
  GateIcon,
  HomeIcon,
  PaletteIcon,
  ScanFaceIcon,
  SettingsIcon,
  SlidersIcon,
  UsersIcon,
  UserIcon,
} from '../ui'

export interface NavItem {
  to: string
  /**
   * A translation key, not a word. The rail, the tab bar, the navbar title and
   * the search all render the same entry, and all four have to read it in the
   * language on screen — so the nav stays data and the renderers resolve it.
   */
  labelKey: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  /** Shows the unread-notifications badge. */
  badge?: 'notifications'
  /**
   * The permissions the entry needs. Every one of them, unless `anyOf` is set.
   * This is the whole role rule: the rail is drawn from what the **active**
   * role may do, so switching hats redraws it without a reload.
   */
  requires?: Permission[]
  /** Any one of these is enough — for pages two different roles reach. */
  anyOf?: Permission[]
  /** Only for these active roles. Used where a page is a role's own cabinet. */
  activeRoles?: Role[]
  /** Exact-match highlighting, for an entry that has children below it. */
  end?: boolean
  /**
   * The page is about one pupil. Staff only see it once they actually have
   * pupils in scope — a developer with an empty register is an administrator,
   * not a parent, and a "Bosh sahifa" that can only say "no child" is noise.
   */
  childScoped?: boolean
  /**
   * Also shown to staff who mark or read the lesson register, whether or not
   * they have a child of their own — Dars davomati is their page too.
   */
  teaching?: boolean
}

/** Roles whose cabinet is administration first, not their own children. */
export const STAFF_ROLES: Role[] = [
  'DEVELOPER',
  'SUPER_ADMIN',
  'MODERATOR',
  'ADMIN',
  'TEACHER',
  'CURATOR',
  'STAFF',
]

export function isStaffRole(role: Role | undefined): boolean {
  return Boolean(role && STAFF_ROLES.includes(role))
}

/** Whoever fills in "Dars davomati" rather than only reading it. */
export function marksLessons(user: Pick<User, 'permissions'> | null | undefined): boolean {
  return userCan(user, 'attendance.mark')
}

/** Everyone lands on their own home; the page itself differs by role. */
export function homePathFor(): string {
  return '/'
}

const HOME: NavItem = { to: '/', labelKey: 'nav.home', icon: HomeIcon }

/**
 * The cabinets that belong to one role and nobody else. They sit straight under
 * Bosh sahifa because for that role they *are* the work — a curator's group, a
 * parent's children — and an administrator never sees them at all.
 */
const ROLE_CABINETS: NavItem[] = [
  {
    to: '/guruhim',
    labelKey: 'nav.myGroups',
    icon: SlidersIcon,
    activeRoles: ['CURATOR'],
    end: true,
  },
  {
    to: '/guruhim/oquvchilar',
    labelKey: 'nav.students',
    icon: UsersIcon,
    activeRoles: ['CURATOR'],
  },
  // Only a parent has children here. Holding `children.view` is not enough: a
  // DEVELOPER holds every permission and is nobody's parent.
  {
    to: '/farzandlarim',
    labelKey: 'nav.children',
    icon: UsersIcon,
    activeRoles: ['OTA-ONA'],
    requires: ['children.view'],
  },
]

/**
 * The rail, in the order the school asked for.
 *
 * Every entry still asks for its own permission, so each role sees the subset it
 * may open — always in this same order. Lavozimlar is absent on purpose: it
 * lives inside Sozlamalar, and its old address redirects there.
 */
const ORDERED_ITEMS: NavItem[] = [
  {
    to: '/maktab',
    labelKey: 'nav.school',
    icon: GateIcon,
    requires: ['register.access', 'school.view'],
  },
  {
    to: '/sinflar',
    labelKey: 'nav.classes',
    icon: SlidersIcon,
    requires: ['register.access', 'classes.view'],
  },
  {
    to: '/fanlar',
    labelKey: 'nav.subjects',
    icon: PaletteIcon,
    requires: ['register.access', 'subjects.view'],
  },
  {
    to: '/dars-jadvali',
    labelKey: 'nav.schedule',
    icon: CalendarIcon,
    requires: ['register.access', 'timetable.view'],
  },
  {
    to: '/davomat',
    labelKey: 'nav.attendance',
    icon: ChartIcon,
    anyOf: ['attendance.view', 'children.view'],
    childScoped: true,
    teaching: true,
  },
  {
    to: '/kalendar',
    labelKey: 'nav.calendar',
    icon: CalendarIcon,
    anyOf: ['attendance.view', 'children.view'],
    childScoped: true,
    teaching: true,
  },
  // The day at the gate, hour by hour: an employee's own, or the child's.
  {
    to: '/xronologiya',
    labelKey: 'nav.chronology',
    icon: CalendarIcon,
    activeRoles: ['STAFF', 'OTA-ONA'],
  },
  { to: '/foydalanuvchilar', labelKey: 'nav.users', icon: UsersIcon, requires: ['users.view'] },
  {
    to: '/oqituvchilar',
    labelKey: 'nav.teachers',
    icon: ScanFaceIcon,
    requires: ['register.access', 'teachers.view'],
  },
  {
    to: '/xodimlar',
    labelKey: 'nav.staff',
    icon: UsersIcon,
    requires: ['register.access', 'staff.view'],
  },
  {
    to: '/kuratorlar',
    labelKey: 'nav.curators',
    icon: UsersIcon,
    requires: ['register.access', 'curators.view'],
  },
  {
    to: '/oquvchilar',
    labelKey: 'nav.students',
    icon: UsersIcon,
    requires: ['register.access', 'students.view'],
  },
  { to: '/export', labelKey: 'nav.export', icon: FileTextIcon, requires: ['export.run'] },
  { to: '/audit', labelKey: 'nav.audit', icon: FileTextIcon, requires: ['audit.view'] },
  { to: '/bildirishnomalar', labelKey: 'nav.notifications', icon: BellIcon, badge: 'notifications' },
  { to: '/sozlamalar', labelKey: 'nav.settings', icon: SettingsIcon, requires: ['settings.view'] },
  { to: '/profil', labelKey: 'nav.profile', icon: UserIcon },
]

export const NAV_ITEMS: NavItem[] = [HOME, ...ROLE_CABINETS, ...ORDERED_ITEMS]

/** What the viewer's session makes visible. */
export interface NavContext {
  user: Pick<User, 'permissions' | 'active_role'> | null | undefined
  hasChildren?: boolean
}

/**
 * The nav a given session actually sees.
 *
 * Bosh sahifa is always first — for staff it is the school's numbers, for a
 * parent their child's day. The person's own pages close the list. Everything
 * between is whatever the active role's permissions allow, which is why
 * switching roles redraws the rail and nothing else has to know about it.
 */
export function navItemsFor(context: NavContext): NavItem[] {
  const { user, hasChildren = true } = context
  const activeRole = user?.active_role

  const allowed = (item: NavItem) => {
    if (item.activeRoles && !(activeRole && item.activeRoles.includes(activeRole))) {
      return false
    }
    if (item.requires && !userCan(user, ...item.requires)) return false
    if (item.anyOf && !userCanAny(user, ...item.anyOf)) return false
    if (item.childScoped && !hasChildren && !(item.teaching && userCan(user, 'attendance.view'))) {
      return false
    }
    return true
  }

  return NAV_ITEMS.filter(allowed)
}

/**
 * How many tabs the bottom bar keeps once something has to move under "Yana".
 *
 * The bar is five slots wide either way: four tabs and the overflow button, or
 * five tabs when the whole menu fits — hiding a single entry behind a button
 * that costs the same slot would only add a tap. What it never becomes is a
 * developer's fourteen entries laid out as tabs, which on a 360px screen is
 * 25px each: too small to read and too small to hit.
 */
export const MOBILE_TAB_LIMIT = 4

/**
 * The order the bottom bar fills its slots in, most-used first.
 *
 * It is a preference, not a whitelist: anything not named here keeps its rail
 * order behind the ones that are, so a role with a short menu still fills the
 * bar.
 */
const MOBILE_PRIORITY = [
  '/',
  '/davomat',
  '/kalendar',
  '/guruhim',
  '/farzandlarim',
  '/bildirishnomalar',
]

/**
 * Splits the nav into the tabs the phone shows and the rest, which go into the
 * "Yana" sheet. Both keep the rail's own order, so a menu the user learned on a
 * desktop reads the same way on a phone.
 */
export function mobileNavSplit(context: NavContext): {
  tabs: NavItem[]
  overflow: NavItem[]
} {
  const items = navItemsFor(context)
  if (items.length <= MOBILE_TAB_LIMIT + 1) return { tabs: items, overflow: [] }

  const rank = (item: NavItem) => {
    const index = MOBILE_PRIORITY.indexOf(item.to)
    return index === -1 ? MOBILE_PRIORITY.length : index
  }
  const chosen = new Set(
    [...items]
      .sort((a, b) => rank(a) - rank(b))
      .slice(0, MOBILE_TAB_LIMIT)
      .map((item) => item.to),
  )

  return {
    tabs: items.filter((item) => chosen.has(item.to)),
    overflow: items.filter((item) => !chosen.has(item.to)),
  }
}
