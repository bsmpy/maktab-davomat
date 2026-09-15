from __future__ import annotations

from django.contrib.auth.models import BaseUserManager
from django.db import models

from apps.common.phone import InvalidPhoneNumber, normalize_phone


class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def parents(self):
        from .constants import Role

        return self.filter(role=Role.PARENT)


class UserManager(BaseUserManager.from_queryset(UserQuerySet)):
    use_in_migrations = True

    def _create_user(self, username: str, password: str | None, **extra):
        if not username:
            raise ValueError("Username is required.")
        phone = extra.get("phone")
        if phone:
            try:
                extra["phone"] = normalize_phone(phone)
            except InvalidPhoneNumber:
                raise ValueError("Invalid phone number.") from None
        user = self.model(username=username.strip().lower(), **extra)
        # ``set_password`` hashes with Argon2; plaintext never touches the DB.
        user.set_password(password)
        user.full_clean(exclude=["password"], validate_unique=False)
        user.save(using=self._db)
        return user

    def create_user(self, username: str, password: str | None = None, **extra):
        from .constants import Role

        extra.setdefault("role", Role.PARENT)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(username, password, **extra)

    def create_superuser(self, username: str, password: str | None = None, **extra):
        from .constants import Role

        # The bootstrap account gets the unrestricted role.
        extra.setdefault("role", Role.DEVELOPER)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if extra["is_staff"] is not True or extra["is_superuser"] is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(username, password, **extra)
