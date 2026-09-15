import { lazy, Suspense, type ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { Spinner } from '@/components/ui'
import type { Permission, Role } from '@/types/api'
import { AppLayout } from '@/layouts/AppLayout'
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { TelegramLoginPage } from '@/pages/TelegramLoginPage'

import { useAuth } from '@/auth/permissions'

import { ProtectedRoute, PublicOnlyRoute, RequirePermission } from './ProtectedRoute'

// Cabinet pages are code-split: the login screen should not carry Recharts.
const DashboardPage = lazy(() =>
  import('@/pages/DashboardPage').then((module) => ({ default: module.DashboardPage })),
)
const AttendancePage = lazy(() =>
  import('@/pages/AttendancePage').then((module) => ({ default: module.AttendancePage })),
)
const CalendarPage = lazy(() =>
  import('@/pages/CalendarPage').then((module) => ({ default: module.CalendarPage })),
)
const NotificationsPage = lazy(() =>
  import('@/pages/NotificationsPage').then((module) => ({ default: module.NotificationsPage })),
)
const ProfilePage = lazy(() =>
  import('@/pages/ProfilePage').then((module) => ({ default: module.ProfilePage })),
)
const SettingsPage = lazy(() =>
  import('@/pages/SettingsPage').then((module) => ({ default: module.SettingsPage })),
)
const AdminHomePage = lazy(() =>
  import('@/pages/AdminHomePage').then((module) => ({ default: module.AdminHomePage })),
)
const AuditPage = lazy(() =>
  import('@/pages/AuditPage').then((module) => ({ default: module.AuditPage })),
)
const registerPage = (name: keyof typeof import('@/pages/RegisterPages')) =>
  lazy(() =>
    import('@/pages/RegisterPages').then((module) => ({ default: module[name] })),
  )

/** The cabinets that belong to one role: a curator's groups, a parent's children. */
const rolePage = (name: keyof typeof import('@/pages/RolePages')) =>
  lazy(() => import('@/pages/RolePages').then((module) => ({ default: module[name] })))

const MyGroupsPage = rolePage('MyGroupsPage')
const MyGroupPupilsPage = rolePage('MyGroupPupilsPage')
const MyChildrenPage = rolePage('MyChildrenPage')
const ChronologyPage = rolePage('ChronologyPage')

const ClassesPage = registerPage('ClassesPage')
const SchoolSettingsPage = registerPage('SchoolSettingsPage')
const SubjectsPage = registerPage('SubjectsPage')
const TeachersPage = registerPage('TeachersPage')
const StaffPage = registerPage('StaffPage')
const SchedulePage = registerPage('SchedulePage')
const ExportPage = registerPage('ExportPage')
const UsersPage = registerPage('UsersPage')
const CuratorsPage = registerPage('CuratorsPage')
const StudentsPage = registerPage('StudentsPage')
const TeacherDashboardPage = lazy(() =>
  import('@/pages/TeacherDashboardPage').then((module) => ({
    default: module.TeacherDashboardPage,
  })),
)

/**
 * The landing page depends on who signed in: an administrator's cabinet is the
 * console, a parent's is their child's day.
 */
/**
 * Everyone lands here; what they see depends on the role they are working in.
 *
 * Switching roles re-renders this with no navigation at all, which is the
 * point: an ADMIN who becomes a TEACHER lands on their own week rather than on
 * the school's numbers, without touching the address bar.
 */
function Home() {
  const { activeRole, can } = useAuth()

  const page =
    // A parent's home is their child's day.
    activeRole === 'OTA-ONA' ? (
      <DashboardPage />
    ) : // An employee whose cabinet is their own day at school: a teacher, a
    // curator, or anybody else on the payroll.
    activeRole === 'TEACHER' || activeRole === 'CURATOR' || activeRole === 'STAFF' ? (
      <TeacherDashboardPage />
    ) : can('reports.view') ? (
      // Whoever may read the school's attendance gets its numbers.
      <AdminHomePage />
    ) : can('staff.cabinet') ? (
      // An ADMIN runs the register but reads nobody's attendance but their own.
      <TeacherDashboardPage />
    ) : (
      <DashboardPage />
    )

  return <Suspense fallback={<PageFallback />}>{page}</Suspense>
}

function PageFallback() {
  return (
    <div className="grid min-h-[50vh] place-items-center text-ink-300">
      <Spinner className="h-6 w-6" />
    </div>
  )
}

/**
 * Every gated page, with what it costs to open.
 *
 * `all` is "every one of these permissions", `any` is "at least one of them",
 * and `roles` gates on the role being worked through — used only where a page
 * *is* a role's own cabinet and has no meaning outside it.
 */
const ROUTES: {
  path: string
  element: ReactElement
  all?: Permission[]
  any?: Permission[]
  roles?: Role[]
}[] = [
  { path: '/sinflar', element: <ClassesPage />, all: ['register.access', 'classes.view'] },
  { path: '/maktab', element: <SchoolSettingsPage />, all: ['register.access', 'school.view'] },
  { path: '/fanlar', element: <SubjectsPage />, all: ['register.access', 'subjects.view'] },
  { path: '/oqituvchilar', element: <TeachersPage />, all: ['register.access', 'teachers.view'] },
  { path: '/xodimlar', element: <StaffPage />, all: ['register.access', 'staff.view'] },
  { path: '/kuratorlar', element: <CuratorsPage />, all: ['register.access', 'curators.view'] },
  { path: '/oquvchilar', element: <StudentsPage />, all: ['register.access', 'students.view'] },
  { path: '/dars-jadvali', element: <SchedulePage />, all: ['register.access', 'timetable.view'] },
  { path: '/export', element: <ExportPage />, all: ['export.run'] },
  { path: '/foydalanuvchilar', element: <UsersPage />, all: ['users.view'] },
  { path: '/audit', element: <AuditPage />, all: ['audit.view'] },
  // A curator's own section.
  { path: '/guruhim', element: <MyGroupsPage />, roles: ['CURATOR'] },
  { path: '/guruhim/oquvchilar', element: <MyGroupPupilsPage />, roles: ['CURATOR'] },
  // A parent's own section.
  { path: '/farzandlarim', element: <MyChildrenPage />, all: ['children.view'] },
  // The day at the gate — an employee's own, or the child being looked at.
  { path: '/xronologiya', element: <ChronologyPage />, any: ['staff.cabinet', 'children.view'] },
]

export function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/kirish"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/royxatdan-otish"
        element={
          <PublicOnlyRoute>
            <RegisterPage />
          </PublicOnlyRoute>
        }
      />
      {/* The bot's one-time sign-in link lands here. */}
      <Route path="/kirish/telegram" element={<TelegramLoginPage />} />
      <Route
        path="/parolni-tiklash"
        element={
          <PublicOnlyRoute>
            <ForgotPasswordPage />
          </PublicOnlyRoute>
        }
      />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Home />} />
        {/* Attendance: read by whoever holds it, or by a parent for their own
            child. Guarded like the rail, so an ADMIN typing the address gets
            the same answer as the menu. */}
        <Route
          path="/davomat"
          element={
            <RequirePermission any={['attendance.view', 'children.view']}>
              <Suspense fallback={<PageFallback />}>
                <AttendancePage />
              </Suspense>
            </RequirePermission>
          }
        />
        <Route
          path="/kalendar"
          element={
            <RequirePermission any={['attendance.view', 'children.view']}>
              <Suspense fallback={<PageFallback />}>
                <CalendarPage />
              </Suspense>
            </RequirePermission>
          }
        />
        <Route
          path="/bildirishnomalar"
          element={
            <Suspense fallback={<PageFallback />}>
              <NotificationsPage />
            </Suspense>
          }
        />
        <Route
          path="/profil"
          element={
            <Suspense fallback={<PageFallback />}>
              <ProfilePage />
            </Suspense>
          }
        />
        {/* The register and the role cabinets, each behind the permission it
            needs. The guard is the same object the rail reads, so a page that
            is not in the menu cannot be reached by typing its address either —
            and the server refuses it a third time regardless. */}
        {ROUTES.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={
              <RequirePermission all={route.all} any={route.any} roles={route.roles}>
                <Suspense fallback={<PageFallback />}>{route.element}</Suspense>
              </RequirePermission>
            }
          />
        ))}
        <Route
          path="/sozlamalar"
          element={
            <RequirePermission all={['settings.view']}>
              <Suspense fallback={<PageFallback />}>
                <SettingsPage />
              </Suspense>
            </RequirePermission>
          }
        />
      </Route>

      {/* Legacy/aliased paths */}
      <Route path="/login" element={<Navigate to="/kirish" replace />} />
      <Route path="/register" element={<Navigate to="/royxatdan-otish" replace />} />
      {/* The console's tabs became pages, and Lavozimlar then moved into
          Sozlamalar. Every old address still lands somewhere real. */}
      <Route path="/admin" element={<Navigate to="/oquvchilar" replace />} />
      <Route path="/boshqaruv" element={<Navigate to="/oquvchilar" replace />} />
      <Route path="/lavozimlar" element={<Navigate to="/sozlamalar?bolim=lavozimlar" replace />} />

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
