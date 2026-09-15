"""Versioned API surface: everything lives under ``/api/v1/``."""
from django.urls import include, path

from apps.accounts.urls import auth_patterns, registration_patterns
from apps.attendance import teacher_views
from apps.attendance import views as attendance_views
from apps.common import views as common_views
from apps.guardians import views as guardian_views
from apps.integrations.urls import ingest_patterns, settings_patterns
from apps.notifications import views as notification_views
from apps.schools import views as school_views
from apps.schools.management_urls import management_patterns
from apps.telegram import bot_api
from apps.telegram import views as telegram_views

# --- pupil-scoped reports (parents, teachers, admins) ---------------------- #
child_patterns = [
    path("", guardian_views.ChildDetailView.as_view(), name="child-detail"),
    path("dashboard/", guardian_views.ChildDashboardView.as_view(), name="child-dashboard"),
    path(
        "attendance/daily/",
        attendance_views.DailyPresenceView.as_view(),
        name="attendance-daily",
    ),
    path(
        "attendance/weekly/",
        attendance_views.WeeklyPresenceView.as_view(),
        name="attendance-weekly",
    ),
    path(
        "attendance/monthly/",
        attendance_views.MonthlyPresenceView.as_view(),
        name="attendance-monthly",
    ),
    path(
        "attendance/yearly/",
        attendance_views.YearlyPresenceView.as_view(),
        name="attendance-yearly",
    ),
    path(
        "attendance/lessons/",
        attendance_views.ChildLessonAttendanceView.as_view(),
        name="attendance-lessons",
    ),
    path("calendar/", attendance_views.CalendarView.as_view(), name="child-calendar"),
    path(
        "absence-requests/",
        attendance_views.StudentAbsenceRequestView.as_view(),
        name="child-absence-requests",
    ),
]

# --- catalogue (public: the registration wizard needs it) ------------------ #
catalogue_patterns = [
    path("schools/", school_views.SchoolListView.as_view(), name="schools"),
    path("grades/", school_views.GradeListView.as_view(), name="grades"),
    path("class-groups/", school_views.ClassGroupListView.as_view(), name="class-groups"),
    path("academic-years/", school_views.AcademicYearListView.as_view(), name="academic-years"),
]

notification_patterns = [
    path("", notification_views.NotificationListView.as_view(), name="notifications"),
    path(
        "unread-count/",
        notification_views.NotificationUnreadCountView.as_view(),
        name="notifications-unread-count",
    ),
    path(
        "mark-as-read/",
        notification_views.NotificationMarkReadView.as_view(),
        name="notifications-mark-read",
    ),
    path(
        "mark-all-as-read/",
        notification_views.NotificationMarkAllReadView.as_view(),
        name="notifications-mark-all-read",
    ),
]

telegram_patterns = [
    path("status/", telegram_views.TelegramStatusView.as_view(), name="telegram-status"),
    path("link-code/", telegram_views.TelegramLinkCodeView.as_view(), name="telegram-link-code"),
    path("unlink/", telegram_views.TelegramUnlinkView.as_view(), name="telegram-unlink"),
    path(
        "notifications/",
        telegram_views.TelegramNotificationToggleView.as_view(),
        name="telegram-notifications",
    ),
]

# --- server-to-server (aiogram) ------------------------------------------- #
bot_patterns = [
    path("link/", bot_api.BotLinkView.as_view(), name="bot-link"),
    path("me/", bot_api.BotMeView.as_view(), name="bot-me"),
    path("children/", bot_api.BotChildrenView.as_view(), name="bot-children"),
    path("active-child/", bot_api.BotSetActiveChildView.as_view(), name="bot-active-child"),
    path("attendance/", bot_api.BotAttendanceView.as_view(), name="bot-attendance"),
    path("notifications/", bot_api.BotNotificationsView.as_view(), name="bot-notifications"),
    path("settings/", bot_api.BotSettingsView.as_view(), name="bot-settings"),
    path("unlink/", bot_api.BotUnlinkView.as_view(), name="bot-unlink"),
    # --- signing in by sharing a contact ---------------------------------- #
    path("auth/phone/", bot_api.BotKnownPhoneView.as_view(), name="bot-known-phone"),
    path("auth/contact/", bot_api.BotAuthContactView.as_view(), name="bot-auth-contact"),
    path("auth/verify/", bot_api.BotAuthVerifyView.as_view(), name="bot-auth-verify"),
    path(
        "phone/request/",
        bot_api.BotPhoneChangeRequestView.as_view(),
        name="bot-phone-request",
    ),
    path(
        "phone/verify/",
        bot_api.BotPhoneChangeVerifyView.as_view(),
        name="bot-phone-verify",
    ),
]

# --- teacher / admin workflows -------------------------------------------- #
teaching_patterns = [
    # The teacher's own cabinet: their presence, their profile, their lessons.
    path("me/", teacher_views.TeacherProfileView.as_view(), name="teacher-profile"),
    path("me/photo/", teacher_views.TeacherPhotoView.as_view(), name="teacher-photo"),
    path(
        "me/dashboard/",
        teacher_views.TeacherDashboardView.as_view(),
        name="teacher-dashboard",
    ),
    path("me/lessons/", teacher_views.TeacherLessonListView.as_view(), name="teacher-lessons"),
    # The employee's own week, month and year at the gate.
    path(
        "me/stats/",
        teacher_views.TeacherPresenceStatsView.as_view(),
        name="teacher-stats",
    ),
    path("search/", teacher_views.TeachingSearchView.as_view(), name="search"),
    path(
        "me/calendar/",
        teacher_views.TeacherCalendarView.as_view(),
        name="teacher-calendar",
    ),
    path(
        "me/calendar/<str:day>/",
        teacher_views.TeacherCalendarDayView.as_view(),
        name="teacher-calendar-day",
    ),
    # Dars davomati: a teacher opens a class, then one of its lessons.
    path(
        "classes/",
        attendance_views.TeachingClassListView.as_view(),
        name="teaching-classes",
    ),
    path(
        "classes/<uuid:class_group_id>/",
        attendance_views.TeachingClassDayView.as_view(),
        name="teaching-class-day",
    ),
    path(
        "subjects/",
        attendance_views.TeachingSubjectListView.as_view(),
        name="teaching-subjects",
    ),
    path(
        "subjects/<uuid:subject_id>/roster/",
        attendance_views.TeachingRosterView.as_view(),
        name="teaching-roster",
    ),
    path(
        "absence-requests/",
        attendance_views.PendingAbsenceRequestListView.as_view(),
        name="pending-absence-requests",
    ),
    path(
        "absence-requests/<uuid:pk>/<str:action>/",
        attendance_views.AbsenceRequestReviewView.as_view(),
        name="review-absence-request",
    ),
]

urlpatterns = [
    # The clock the app runs on; the browser reads it so both agree on the day.
    path("clock/", common_views.ClockView.as_view(), name="clock"),
    # What the interface offers everyone. Deliberately *not* under /settings/,
    # which only the unscoped roles may open: every signed-in browser has to be
    # able to read these two switches before it draws anything.
    path("appearance/", common_views.AppearanceView.as_view(), name="appearance"),
    path("auth/", include((auth_patterns, "auth"))),
    path("registration/", include((registration_patterns, "registration"))),
    path("", include((catalogue_patterns, "catalogue"))),
    path("children/", guardian_views.ChildrenListView.as_view(), name="children"),
    path("children/<uuid:student_id>/", include(child_patterns)),
    path(
        "attendance/reasons/",
        attendance_views.AttendanceReasonListView.as_view(),
        name="attendance-reasons",
    ),
    path("notifications/", include(notification_patterns)),
    path("telegram/", include(telegram_patterns)),
    path("teaching/", include((teaching_patterns, "teaching"))),
    path("management/", include((management_patterns, "management"))),
    path("settings/", include((settings_patterns, "settings"))),
    path("terminals/", include((ingest_patterns, "terminals"))),
    path("bot/", include((bot_patterns, "bot"))),
]
