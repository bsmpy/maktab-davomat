from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.common.text import normalize_name

from .constants import Role
from .managers import UserManager
from .validators import validate_username


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Accounts are addressed by an auto-generated username (``a.valiyev``).

    Parents may also sign in with their verified phone number; both are unique.
    """

    username = models.CharField(
        "Login",
        max_length=50,
        unique=True,
        validators=[validate_username],
        help_text="Ro'yxatdan o'tishda avtomatik yaratiladi.",
    )
    phone = models.CharField(
        "Telefon",
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="E.164 formatida, masalan +998901234567.",
    )
    phone_verified_at = models.DateTimeField("Telefon tasdiqlangan", null=True, blank=True)

    first_name = models.CharField("Ism", max_length=100, blank=True)
    last_name = models.CharField("Familiya", max_length=100, blank=True)
    middle_name = models.CharField("Otasining ismi", max_length=100, blank=True)

    #: The role the person is *working through* right now. What they are
    #: *allowed* to be is the set of ``UserRole`` rows below; this column says
    #: which of them the cabinet and the API are currently obeying. Switching
    #: it is a write to this field and nothing else — no re-registration, no
    #: second account — and the server refuses any value the user does not
    #: actually hold (see ``apps.accounts.rbac.set_active_role``).
    role = models.CharField(
        "Faol rol", max_length=20, choices=Role.choices, default=Role.PARENT
    )

    is_active = models.BooleanField("Faol", default=True)
    is_staff = models.BooleanField("Xodim", default=False)
    must_change_password = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        indexes = [
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["phone"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(username=models.functions.Lower("username")),
                name="user_username_is_lowercase",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.username})"

    def save(self, *args, **kwargs):
        self.username = (self.username or "").strip().lower()
        self.first_name = normalize_name(self.first_name)
        self.last_name = normalize_name(self.last_name)
        self.middle_name = normalize_name(self.middle_name)
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(part for part in parts if part).strip() or self.username

    @property
    def short_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.short_name

    @property
    def is_phone_verified(self) -> bool:
        return self.phone_verified_at is not None

    # --- roles ---------------------------------------------------------- #
    @property
    def active_role(self) -> str:
        """The role this session is working through. Alias of ``role``."""
        return self.role

    @active_role.setter
    def active_role(self, value: str) -> None:
        self.role = value

    @property
    def role_codes(self) -> list[str]:
        """Every role granted to this account, most privileged first.

        The active one is always among them: an account whose ``UserRole`` rows
        were never written (an old row, a fixture) still answers truthfully
        rather than claiming no roles at all.
        """
        from .constants import rank

        codes = {row.role for row in self.user_roles.all()}
        if self.role:
            codes.add(self.role)
        return sorted(codes, key=rank, reverse=True)

    def has_role(self, role: str) -> bool:
        """Is this role *granted* — whether or not it is the active one?"""
        return role in self.role_codes

    def has_any_role(self, *roles: str) -> bool:
        granted = set(self.role_codes)
        return any(role in granted for role in roles)

    def has_permission(self, permission: str) -> bool:
        """Does the **active** role carry this permission?

        Deliberately not the union of every granted role: somebody working as a
        TEACHER is a teacher, even if they are also an ADMIN on Mondays. They
        switch roles to get the other set.
        """
        from .catalog import role_has_permission

        return role_has_permission(self.role, permission)

    @property
    def permission_codes(self) -> list[str]:
        from .catalog import permissions_for

        return sorted(permissions_for(self.role))

    @property
    def is_parent(self) -> bool:
        return self.role == Role.PARENT

    @property
    def is_teacher(self) -> bool:
        return self.role == Role.TEACHER

    @property
    def is_curator(self) -> bool:
        return self.role == Role.CURATOR

    @property
    def is_school_admin(self) -> bool:
        return self.role in Role.admin_roles()

    @property
    def is_developer(self) -> bool:
        """True for the platform owner — whether or not it is their active role.

        DEVELOPER is an identity, not a hat: a developer who switched to
        TEACHER to check a screen must still be invisible to a SUPER_ADMIN, and
        must still be the only account able to edit another developer.
        """
        return self.has_role(Role.DEVELOPER)

    @property
    def can_open_settings(self) -> bool:
        from .catalog import Perm

        return self.has_permission(Perm.SETTINGS_VIEW)

    @property
    def can_manage_integrations(self) -> bool:
        """Only the developer role may write integration credentials."""
        from .catalog import Perm

        return self.has_permission(Perm.INTEGRATIONS_MANAGE)

    def mark_phone_verified(self) -> None:
        self.phone_verified_at = timezone.now()
        self.save(update_fields=["phone_verified_at", "updated_at"])


class UserRole(TimeStampedModel):
    """One role granted to one account.

    The table is the answer to "what may this person be"; ``User.role`` is the
    answer to "what are they being right now". Keeping them apart is what lets
    one person be TEACHER + CURATOR + STAFF without three logins and without
    the cabinet showing all three at once.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_roles", verbose_name="Foydalanuvchi"
    )
    role = models.CharField("Rol", max_length=20, choices=Role.choices, db_index=True)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_roles",
        verbose_name="Kim bergan",
    )

    class Meta:
        verbose_name = "Foydalanuvchi roli"
        verbose_name_plural = "Foydalanuvchi rollari"
        ordering = ("user", "role")
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uniq_role_per_user"),
        ]
        indexes = [models.Index(fields=["role"])]

    def __str__(self) -> str:
        return f"{self.user.username} → {self.role}"
