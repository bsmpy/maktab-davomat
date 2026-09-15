"""Username generation: ``<first initial>.<last name>`` with collision suffixes.

    Ali Valiyev        -> a.valiyev
    (taken)            -> a.valiyev2, a.valiyev3, ...

Cyrillic and Uzbek Latin diacritics are transliterated to plain ASCII, and the
uniqueness check runs inside the caller's transaction with a row lock free
retry loop, so two concurrent registrations cannot claim the same login.
"""
from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.common.text import slugify_latin

MAX_USERNAME_LENGTH = 50
_MAX_SUFFIX = 9999


def build_username_base(first_name: str, last_name: str) -> str:
    first = slugify_latin(first_name)
    last = slugify_latin(last_name)

    if not last and not first:
        return "user"
    if not last:
        # Only a given name is known – use it whole rather than a bare initial.
        return first[: MAX_USERNAME_LENGTH - 5]
    if not first:
        return last[: MAX_USERNAME_LENGTH - 5]

    base = f"{first[0]}.{last}"
    return base[: MAX_USERNAME_LENGTH - 5]


def _candidates(base: str):
    yield base
    for index in range(2, _MAX_SUFFIX + 1):
        suffix = str(index)
        yield f"{base[: MAX_USERNAME_LENGTH - len(suffix)]}{suffix}"


def generate_username(first_name: str, last_name: str) -> str:
    """Return the first free username for this person.

    Only reserves the name logically – the caller creates the ``User`` row and
    the unique index is the real arbiter (see ``create_user_with_username``).
    """
    from apps.accounts.models import User

    base = build_username_base(first_name, last_name)
    taken = set(
        User.objects.filter(username__startswith=base).values_list("username", flat=True)
    )
    for candidate in _candidates(base):
        if candidate not in taken:
            return candidate
    raise RuntimeError(f"Could not allocate a username for base '{base}'.")


def create_user_with_username(*, first_name: str, last_name: str, **user_kwargs):
    """Create a user, retrying on the (rare) unique-username race."""
    from apps.accounts.models import User

    last_error: Exception | None = None
    for _attempt in range(5):
        username = generate_username(first_name, last_name)
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    **user_kwargs,
                )
        except IntegrityError as exc:  # pragma: no cover - concurrency guard
            last_error = exc
            continue
    raise RuntimeError("Could not allocate a unique username.") from last_error
