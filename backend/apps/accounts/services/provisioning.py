"""Provisioning staff accounts from the cabinet.

Who may create whom is decided in one place —
:func:`apps.accounts.constants.manageable_roles` — and enforced on every write,
so a SUPER_ADMIN cannot mint a peer and an ADMIN cannot provision at all.

**On passwords.** They are stored as Argon2 hashes, which is a one-way
function: there is no code path, for any role, that can read an existing
password back. That is deliberate — a readable password store turns one leaked
backup into every family's credentials, and it destroys non-repudiation, since
nobody could then tell a parent's own action from an operator's. What an
operator actually needs is to get a locked-out person back in, so that is what
this module provides: :func:`issue_temporary_password` mints a fresh one, shows
it exactly once to the person who asked, forces a change at next login, and
records who did it in the audit trail.
"""
from __future__ import annotations

import logging
import re
import secrets

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.exceptions import ConflictError, PermissionError_
from apps.common.phone import InvalidPhoneNumber, normalize_phone

from .. import rbac
from ..audit import log_role_change
from ..constants import DEFAULT_STAFF_ROLE, Role
from ..models import User
from .username import create_user_with_username

#: Same shape the login form accepts: latin letters, digits and . _ -
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,48}[a-z0-9]$")

logger = logging.getLogger(__name__)

#: Unambiguous alphabet — no O/0, l/1/I — so a password read aloud still works.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
TEMPORARY_PASSWORD_LENGTH = 14


def generate_temporary_password() -> str:
    """A strong one-off password that satisfies the project's validators."""
    while True:
        candidate = "".join(
            secrets.choice(_ALPHABET) for _ in range(TEMPORARY_PASSWORD_LENGTH)
        )
        # Guarantee the character classes the strength validator asks for
        # instead of looping on a rejection.
        if (
            any(character.isupper() for character in candidate)
            and any(character.islower() for character in candidate)
            and any(character.isdigit() for character in candidate)
        ):
            return candidate


def normalize_roles(roles) -> list[str]:
    """Clean a submitted role list, falling back to ``STAFF``.

    A staff account created with nothing ticked is an employee — that is what
    everybody who works at the school is at minimum, and a role-less login can
    see nothing at all.
    """
    cleaned = []
    for role in roles or ():
        value = str(role).strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned or [str(DEFAULT_STAFF_ROLE)]


def assert_may_manage(actor: User, target_role: str) -> None:
    """One role the actor is about to hand out."""
    if not rbac.can_assign_role(actor, target_role):
        raise PermissionError_(
            "Bu rol bilan foydalanuvchi yaratish yoki o'zgartirish huquqingiz yo'q."
        )


def assert_may_assign(actor: User, roles) -> list[str]:
    """Every role in one submission, checked before anything is written."""
    cleaned = normalize_roles(roles)
    for role in cleaned:
        assert_may_manage(actor, role)
    return cleaned


def assert_may_manage_user(actor: User, target: User, *, allow_self: bool = False) -> None:
    """Guard an edit of an existing account.

    Everyone may be edited by someone above them, and only a DEVELOPER may
    touch another DEVELOPER — a SUPER_ADMIN cannot even see one, so the check
    below reads as "not found" to them rather than as a refusal.

    Your own account is refused unless the caller says otherwise: resetting
    your own password or deleting yourself from the console stays impossible.
    Editing yourself is allowed by :func:`update_staff_user`, which applies its
    own rules (see :func:`_assert_self_edit`).
    """
    if actor.pk == target.pk:
        if allow_self:
            return
        raise ConflictError(
            "O'z akkauntingizni bu yerdan o'zgartirib bo'lmaydi.", code="SELF_MANAGEMENT"
        )
    if not rbac.can_manage_user(actor, target):
        raise PermissionError_(
            "Bu foydalanuvchini o'zgartirish huquqingiz yo'q."
        )


def _assert_self_edit(actor: User, wanted_roles, is_active) -> None:
    """What a person may not do to their own account from the console.

    Name, phone and the roles below their own are theirs to change. Two things
    are not, because each would lock them out of the very screen they are on:
    switching the account off, and dropping the highest role they hold. Adding
    a role above that is already impossible — every role in the submission has
    passed :func:`assert_may_assign`, so a SUPER_ADMIN still cannot tick
    DEVELOPER for themselves.
    """
    if is_active is False:
        raise ConflictError(
            "O'z akkauntingizni o'chirib bo'lmaydi.", code="SELF_DEACTIVATION"
        )
    if wanted_roles is not None:
        top = rbac._preferred_active(actor.role_codes)
        if top not in wanted_roles:
            raise ConflictError(
                f"O'zingizdan eng yuqori rolingizni ({top}) olib tashlab bo'lmaydi.",
                code="SELF_TOP_ROLE",
            )


def validate_new_username(username: str) -> str:
    """A login the operator typed: normalised, checked for shape and for clashes."""
    candidate = (username or "").strip().lower()
    if not USERNAME_RE.match(candidate):
        raise ConflictError(
            "Login 3-50 ta belgidan iborat bo'lishi va faqat lotin harflari, "
            "raqamlar va . _ - belgilaridan tashkil topishi kerak.",
            code="INVALID_USERNAME",
        )
    if User.objects.filter(username__iexact=candidate).exists():
        raise ConflictError("Bu login band.", code="USERNAME_TAKEN")
    return candidate


def validate_chosen_password(password: str, *, user: User | None = None) -> str:
    """Run the project's password validators over an operator-typed password."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise ConflictError(" ".join(exc.messages), code="WEAK_PASSWORD") from None
    return password


@transaction.atomic
def create_staff_user(
    *,
    actor: User,
    role: str = "",
    roles=None,
    first_name: str,
    last_name: str,
    middle_name: str = "",
    phone: str = "",
    school=None,
    request=None,
    username: str = "",
    password: str = "",
) -> tuple[User, str]:
    """Create a staff account. Returns ``(user, password)``.

    One person, several roles: ``roles=["TEACHER", "CURATOR", "STAFF"]`` grants
    all three and the account opens on the most privileged of them. ``role=``
    is the single-role spelling of the same thing, kept for the call sites that
    only ever hand out one. Neither given, the account becomes ``STAFF``.

    With no ``username``/``password`` the login is derived from the name and a
    one-off password is minted, shown to the operator once and flagged
    ``must_change_password``. When the operator types both — as the teacher
    form does — they are used as given and no forced change follows: the person
    whose account it is already knows the password.
    """
    wanted = assert_may_assign(actor, roles if roles is not None else ([role] if role else []))
    active = rbac._preferred_active(wanted)

    normalized_phone = ""
    if phone:
        try:
            normalized_phone = normalize_phone(phone)
        except InvalidPhoneNumber as exc:
            raise ConflictError(str(exc), code="INVALID_PHONE") from None
        if User.objects.filter(phone=normalized_phone).exists():
            raise ConflictError(
                "Bu telefon raqami boshqa akkauntga biriktirilgan.", code="PHONE_TAKEN"
            )

    chosen = bool(username and password)
    if chosen:
        username = validate_new_username(username)
        validate_chosen_password(password)
    else:
        password = generate_temporary_password()

    owner = Role.DEVELOPER in wanted
    attributes = {
        "first_name": first_name,
        "last_name": last_name,
        "middle_name": middle_name,
        "phone": normalized_phone or None,
        "role": active,
        "password": password,
        # Only the platform owner gets the Django admin.
        "is_staff": owner,
        "is_superuser": owner,
        "must_change_password": not chosen,
    }
    user = (
        User.objects.create_user(username=username, **attributes)
        if chosen
        else create_user_with_username(**attributes)
    )
    rbac.set_roles(user, wanted, actor=actor)

    # A school-scoped role needs a register row to be scoped *by*; without one
    # the account would read as unscoped.
    if school is not None and {Role.ADMIN, Role.TEACHER, Role.CURATOR} & set(wanted):
        _attach_to_school(user, school)

    log_action(
        AuditAction.USER_CREATE,
        user=actor,
        entity=user,
        request=request,
        new_data={"username": user.username, "role": user.role, "roles": wanted},
    )
    log_role_change(
        actor=actor, target=user, old_roles=[], new_roles=wanted, request=request
    )
    return user, password


def _attach_to_school(user: User, school) -> None:
    """Scope an ADMIN/TEACHER to a school via their teacher profile.

    ``apps.guardians.selectors`` resolves an admin's school through this row,
    so an account without one would see every school.
    """
    from apps.schools.models import Teacher

    Teacher.objects.get_or_create(
        user=user,
        defaults={
            "school": school,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "middle_name": user.middle_name,
            "phone": user.phone or "",
        },
    )


@transaction.atomic
def issue_temporary_password(*, actor: User, target: User, request=None) -> str:
    """Reset an account to a fresh one-off password and return it once."""
    assert_may_manage_user(actor, target)

    password = generate_temporary_password()
    try:
        validate_password(password, target)
    except DjangoValidationError:  # pragma: no cover - generator guarantees this
        logger.warning("Generated temporary password failed validation; regenerating.")
        password = generate_temporary_password()

    target.set_password(password)
    target.must_change_password = True
    target.save(update_fields=["password", "must_change_password", "updated_at"])

    # A reset must not leave an old session alive.
    from .password_reset import revoke_all_sessions

    revoke_all_sessions(target)

    log_action(
        AuditAction.USER_PASSWORD_RESET,
        user=actor,
        entity=target,
        request=request,
        metadata={"target": target.username, "role": target.role, "roles": target.role_codes},
    )
    return password


@transaction.atomic
def update_staff_user(
    *,
    actor: User,
    target: User,
    first_name: str | None = None,
    last_name: str | None = None,
    middle_name: str | None = None,
    phone: str | None = None,
    role: str | None = None,
    roles=None,
    is_active: bool | None = None,
    request=None,
) -> User:
    """Edit an account. ``roles`` replaces the whole set; ``role`` sets one.

    Both are checked against what the actor may hand out *before* anything is
    written, so a request that names one permitted role and one forbidden one
    changes nothing at all.

    The account may be the actor's own; then :func:`_assert_self_edit` decides
    what is off limits.
    """
    editing_self = actor.pk == target.pk
    assert_may_manage_user(actor, target, allow_self=True)

    old_roles = list(target.role_codes)
    wanted = None
    if roles is not None:
        wanted = assert_may_assign(actor, roles)
    elif role is not None and role != target.role:
        assert_may_manage(actor, role)
        if editing_self:
            wanted = assert_may_assign(actor, [*old_roles, role])
            role = None
    if editing_self:
        _assert_self_edit(actor, wanted, is_active)

    old = {"role": target.role, "roles": old_roles, "is_active": target.is_active}

    if first_name is not None:
        target.first_name = first_name
    if last_name is not None:
        target.last_name = last_name
    if middle_name is not None:
        target.middle_name = middle_name
    if phone is not None:
        if phone:
            try:
                normalized = normalize_phone(phone)
            except InvalidPhoneNumber as exc:
                raise ConflictError(str(exc), code="INVALID_PHONE") from None
            if User.objects.filter(phone=normalized).exclude(pk=target.pk).exists():
                raise ConflictError(
                    "Bu telefon raqami boshqa akkauntga biriktirilgan.", code="PHONE_TAKEN"
                )
            target.phone = normalized
        else:
            target.phone = None
    if wanted is not None:
        rbac.set_roles(target, wanted, actor=actor)
        target.refresh_from_db(fields=["role"])
    elif role is not None:
        rbac.grant_role(target, role, actor=actor)
        target.role = role
    owner = Role.DEVELOPER in (wanted if wanted is not None else target.role_codes)
    target.is_staff = owner
    target.is_superuser = owner
    if is_active is not None:
        target.is_active = is_active

    target.save()

    if is_active is False:
        # A disabled account must not keep a live refresh token.
        from .password_reset import revoke_all_sessions

        revoke_all_sessions(target)

    new_roles = list(target.role_codes)
    log_action(
        AuditAction.USER_UPDATE,
        user=actor,
        entity=target,
        request=request,
        old_data=old,
        new_data={
            "role": target.role,
            "roles": new_roles,
            "is_active": target.is_active,
        },
    )
    log_role_change(
        actor=actor,
        target=target,
        old_roles=old_roles,
        new_roles=new_roles,
        request=request,
    )
    return target
