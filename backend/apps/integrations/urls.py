from django.urls import path

from . import views

app_name = "integrations"

#: Sozlamalar → Integratsiyalar (authenticated, role-restricted)
settings_patterns = [
    path("", views.SettingsOverviewView.as_view(), name="overview"),
    path("integrations/", views.IntegrationListView.as_view(), name="integrations"),
    path("integrations/<str:kind>/", views.IntegrationDetailView.as_view(), name="integration"),
    path(
        "integrations/<str:kind>/test/",
        views.IntegrationTestView.as_view(),
        name="integration-test",
    ),
    # Terminals
    path("terminals/", views.TerminalListView.as_view(), name="terminals"),
    path(
        "terminals/test-connection/",
        views.TerminalAdHocTestView.as_view(),
        name="terminal-test-connection",
    ),
    path("terminals/events/", views.TerminalEventListView.as_view(), name="terminal-events"),
    path("terminals/<uuid:pk>/", views.TerminalDetailView.as_view(), name="terminal"),
    path("terminals/<uuid:pk>/test/", views.TerminalTestView.as_view(), name="terminal-test"),
    path("terminals/<uuid:pk>/sync/", views.TerminalSyncView.as_view(), name="terminal-sync"),
    path(
        "terminals/<uuid:pk>/rotate-token/",
        views.TerminalRotateTokenView.as_view(),
        name="terminal-rotate-token",
    ),
    # Face ID
    path("face-id/people/", views.TerminalPersonListView.as_view(), name="face-people"),
    path("face-id/enroll/", views.EnrollView.as_view(), name="face-enroll"),
    path(
        "face-id/students/<uuid:student_id>/photo/",
        views.StudentPhotoView.as_view(),
        name="face-photo",
    ),
    # Arrival / departure
    path("presence/", views.DailyPresenceListView.as_view(), name="presence"),
    path("presence/recompute/", views.RecomputePresenceView.as_view(), name="presence-recompute"),
]

#: Device push endpoint — authenticated by the ingest token in the path.
ingest_patterns = [
    path(
        "events/<str:ingest_token>/",
        views.TerminalIngestView.as_view(),
        name="terminal-ingest",
    ),
]
