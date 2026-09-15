"""Username generation: format, transliteration and collision handling."""
from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.accounts.services.username import build_username_base, generate_username

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        ("Ali", "Valiyev", "a.valiyev"),
        ("  ali  ", "  VALIYEV ", "a.valiyev"),
        ("Алишер", "Валиев", "a.valiev"),
        ("Ozod", "G'ulomov", "o.gulomov"),
        ("Oʻktam", "Toʻrayev", "o.torayev"),
        ("Şahzoda", "Üsmanova", "s.usmanova"),
        ("Anna-Maria", "O'Brien", "a.obrien"),
    ],
)
def test_base_is_lowercase_ascii(first, last, expected):
    assert build_username_base(first, last) == expected


def test_collisions_get_numeric_suffixes():
    for expected in ("a.valiyev", "a.valiyev2", "a.valiyev3", "a.valiyev4"):
        username = generate_username("Ali", "Valiyev")
        assert username == expected
        User.objects.create_user(username=username, password="Test!Parol2026")


def test_different_people_can_share_a_base():
    first = generate_username("Aziz", "Valiyev")
    User.objects.create_user(username=first, password="Test!Parol2026")
    second = generate_username("Anvar", "Valiyev")
    assert first == "a.valiyev"
    assert second == "a.valiyev2"


def test_missing_surname_falls_back_to_given_name():
    assert build_username_base("Aziz", "") == "aziz"
    assert build_username_base("", "Valiyev") == "valiyev"


def test_username_is_stored_lowercase():
    user = User.objects.create_user(username="A.Valiyev", password="Test!Parol2026")
    user.refresh_from_db()
    assert user.username == "a.valiyev"
