"""``/api/v1/management/`` — the admin console's write surface.

The cabinet replaced the Django admin, so everything the built-in one used to
do is reachable from here.
"""
from django.urls import path

from . import admin_views, curator_views
from . import management_views as views

management_patterns = [
    path("grades/", views.ManagedGradeListView.as_view(), name="grades"),
    path("grades/<uuid:pk>/", views.ManagedGradeDetailView.as_view(), name="grade-detail"),
    path("class-groups/", views.ManagedClassGroupListView.as_view(), name="class-groups"),
    path(
        "class-groups/<uuid:pk>/",
        views.ManagedClassGroupDetailView.as_view(),
        name="class-group-detail",
    ),
    path("students/", views.ManagedStudentListView.as_view(), name="students"),
    path("students/<uuid:pk>/", views.ManagedStudentDetailView.as_view(), name="student-detail"),
    path(
        "students/<uuid:pk>/photo/",
        views.ManagedStudentPhotoView.as_view(),
        name="student-photo",
    ),
    path("guardians/", views.ManagedGuardianListView.as_view(), name="guardians"),
    path("users/", views.ManagedUserListView.as_view(), name="users"),
    path("users/<int:pk>/", views.ManagedUserDetailView.as_view(), name="user-detail"),
    path(
        "users/<int:pk>/reset-password/",
        views.ManagedUserPasswordView.as_view(),
        name="user-reset-password",
    ),
    path("relations/", views.RelationChoicesView.as_view(), name="relations"),
    # --- Kuratorlar: a person, a class group, and the role that follows --- #
    path("curators/", curator_views.CuratorListView.as_view(), name="curators"),
    path(
        "curators/<uuid:pk>/",
        curator_views.CuratorDetailView.as_view(),
        name="curator-detail",
    ),

    # --- what the Django admin used to own ------------------------------- #
    path("schools/", admin_views.ManagedSchoolListView.as_view(), name="schools"),
    path(
        "schools/<uuid:pk>/",
        admin_views.ManagedSchoolDetailView.as_view(),
        name="school-detail",
    ),
    path(
        "academic-years/",
        admin_views.ManagedAcademicYearListView.as_view(),
        name="academic-years",
    ),
    path(
        "academic-years/<uuid:pk>/",
        admin_views.ManagedAcademicYearDetailView.as_view(),
        name="academic-year-detail",
    ),
    path("holidays/", admin_views.ManagedHolidayListView.as_view(), name="holidays"),
    path(
        "holidays/<uuid:pk>/",
        admin_views.ManagedHolidayDetailView.as_view(),
        name="holiday-detail",
    ),
    path("overview/", admin_views.SchoolOverviewView.as_view(), name="overview"),
    path("export/", admin_views.RegisterExportView.as_view(), name="export"),
    path("schedule/", admin_views.ManagedScheduleListView.as_view(), name="schedule"),
    path(
        "schedule/<uuid:pk>/",
        admin_views.ManagedScheduleDetailView.as_view(),
        name="schedule-detail",
    ),
    path("subjects/", admin_views.ManagedSubjectListView.as_view(), name="subjects"),
    path(
        "subjects/<uuid:pk>/",
        admin_views.ManagedSubjectDetailView.as_view(),
        name="subject-detail",
    ),
    path("positions/", admin_views.ManagedPositionListView.as_view(), name="positions"),
    path(
        "positions/<uuid:pk>/",
        admin_views.ManagedPositionDetailView.as_view(),
        name="position-detail",
    ),
    path("staff/", admin_views.ManagedStaffListView.as_view(), name="staff"),
    path("staff/<uuid:pk>/", admin_views.ManagedStaffDetailView.as_view(), name="staff-detail"),
    path("teachers/", admin_views.ManagedTeacherListView.as_view(), name="teachers"),
    path(
        "teachers/<uuid:pk>/",
        admin_views.ManagedTeacherDetailView.as_view(),
        name="teacher-detail",
    ),
    path("import/template/", admin_views.ImportTemplateView.as_view(), name="import-template"),
    path("import/", admin_views.StudentImportView.as_view(), name="import"),
    path("audit/", admin_views.AuditLogListView.as_view(), name="audit"),
]
