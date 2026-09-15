from .auth import (
    ActiveRoleView,
    LoginView,
    LogoutView,
    MeView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    TelegramTicketLoginView,
    TokenRefreshView,
)
from .registration import (
    RegistrationCompleteView,
    RegistrationIdentifyView,
    RegistrationOTPRequestView,
    RegistrationOTPVerifyView,
    RegistrationRelationsView,
    StudentSearchView,
)

__all__ = [
    "ActiveRoleView",
    "LoginView",
    "LogoutView",
    "MeView",
    "PasswordChangeView",
    "PasswordResetConfirmView",
    "PasswordResetRequestView",
    "PasswordResetVerifyView",
    "RegistrationCompleteView",
    "RegistrationIdentifyView",
    "RegistrationOTPRequestView",
    "RegistrationOTPVerifyView",
    "RegistrationRelationsView",
    "StudentSearchView",
    "TelegramTicketLoginView",
    "TokenRefreshView",
]
