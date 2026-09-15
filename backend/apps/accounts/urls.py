from django.urls import path

from . import views

app_name = "accounts"

auth_patterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", views.TokenRefreshView.as_view(), name="refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path(
        "telegram/",
        views.TelegramTicketLoginView.as_view(),
        name="telegram-login",
    ),
    path("me/", views.MeView.as_view(), name="me"),
    path("active-role/", views.ActiveRoleView.as_view(), name="active-role"),
    path("password/change/", views.PasswordChangeView.as_view(), name="password-change"),
    path(
        "password/reset/request/",
        views.PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password/reset/verify/",
        views.PasswordResetVerifyView.as_view(),
        name="password-reset-verify",
    ),
    path(
        "password/reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]

registration_patterns = [
    path("relations/", views.RegistrationRelationsView.as_view(), name="relations"),
    path("students/search/", views.StudentSearchView.as_view(), name="student-search"),
    path("identify/", views.RegistrationIdentifyView.as_view(), name="identify"),
    path("otp/request/", views.RegistrationOTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", views.RegistrationOTPVerifyView.as_view(), name="otp-verify"),
    path("complete/", views.RegistrationCompleteView.as_view(), name="complete"),
]
