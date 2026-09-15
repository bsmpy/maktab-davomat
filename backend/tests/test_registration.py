"""Registration wizard: the security properties are the point of these tests."""
from __future__ import annotations

import pytest
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.accounts.models import User
from apps.guardians.constants import Relation
from apps.guardians.models import GuardianStudent

pytestmark = pytest.mark.django_db

JSHSHIR = "31234567890123"
PASSWORD = "Yangi!Parol2026"


def identify(api, student, *, jshshir=JSHSHIR, relation=Relation.FATHER, last4="4567"):
    return api.post(
        reverse("registration:identify"),
        {
            "student": str(student.id),
            "relation": relation,
            "jshshir": jshshir,
            "phone_last4": last4,
        },
        format="json",
    )


def run_full_flow(api, student):
    response = identify(api, student)
    assert response.status_code == 200, response.data
    token = response.data["session_token"]

    otp = api.post(reverse("registration:otp-request"), {"session_token": token}, format="json")
    assert otp.status_code == 200
    code = otp.data["debug_code"]

    verified = api.post(
        reverse("registration:otp-verify"), {"session_token": token, "code": code}, format="json"
    )
    assert verified.status_code == 200
    assert verified.data["phone_verified"] is True

    return api.post(
        reverse("registration:complete"),
        {"session_token": token, "password": PASSWORD, "password_confirm": PASSWORD},
        format="json",
    )


# --------------------------------------------------------------------------- #
# Catalogue + search
# --------------------------------------------------------------------------- #
def test_catalogue_is_public(api, class_groups):
    assert api.get(reverse("catalogue:grades")).status_code == 200
    assert api.get(reverse("catalogue:class-groups")).status_code == 200


def test_search_requires_a_class_group_and_a_long_enough_query(api, class_groups, student):
    url = reverse("registration:student-search")
    group_id = str(class_groups["7-A"].id)

    short = api.post(url, {"class_group": group_id, "query": "Va"}, format="json")
    assert short.status_code == 400
    assert short.data["error"]["code"] == "QUERY_TOO_SHORT"

    empty = api.post(url, {"class_group": group_id, "query": ""}, format="json")
    assert empty.status_code == 400


def test_search_is_scoped_to_one_class_and_returns_masked_names(
    api, class_groups, student, other_student
):
    response = api.post(
        reverse("registration:student-search"),
        {"class_group": str(class_groups["7-A"].id), "query": "Valiyev"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["count"] == 1
    result = response.data["results"][0]
    assert result["display_name"] == "Valiyev A."
    assert "jshshir" not in result
    # A pupil from another class is not reachable through this class group.
    assert all(item["id"] != str(other_student.id) for item in response.data["results"])


def test_search_results_carry_the_photo(api, class_groups, student, tmp_path, settings):
    """A masked surname alone cannot tell two Valiyevs apart."""
    import io

    from PIL import Image

    settings.MEDIA_ROOT = tmp_path
    settings.BACKEND_URL = "http://192.168.0.100"

    buffer = io.BytesIO()
    Image.new("RGB", (200, 260), "grey").save(buffer, format="JPEG")
    buffer.seek(0)
    student.photo.save("face.jpg", ContentFile(buffer.read()), save=True)

    response = api.post(
        reverse("registration:student-search"),
        {"class_group": str(class_groups["7-A"].id), "query": "Valiyev"},
        format="json",
    )
    result = response.data["results"][0]
    assert result["photo"].startswith("http://192.168.0.100/media/")
    # Still masked: the photo is an addition, not a relaxation.
    assert result["display_name"] == "Valiyev A."
    assert "jshshir" not in result


def test_a_pupil_without_a_photo_reports_none_in_search(api, class_groups, student):
    response = api.post(
        reverse("registration:student-search"),
        {"class_group": str(class_groups["7-A"].id), "query": "Valiyev"},
        format="json",
    )
    assert response.data["results"][0]["photo"] is None


def test_search_matches_cyrillic_spelling(api, class_groups, student):
    response = api.post(
        reverse("registration:student-search"),
        {"class_group": str(class_groups["7-A"].id), "query": "Валиев"},
        format="json",
    )
    assert response.data["count"] == 1


def test_search_result_cap(api, settings, class_groups, school):
    from apps.students.models import Student

    settings.REGISTRATION = {**settings.REGISTRATION, "STUDENT_SEARCH_MAX_RESULTS": 3}
    for index in range(10):
        Student.objects.create(
            school=school,
            class_group=class_groups["7-A"],
            first_name=f"Aziz{index}",
            last_name="Valiyev",
        )
    response = api.post(
        reverse("registration:student-search"),
        {"class_group": str(class_groups["7-A"].id), "query": "Valiyev"},
        format="json",
    )
    assert len(response.data["results"]) == 3


# --------------------------------------------------------------------------- #
# Identity check
# --------------------------------------------------------------------------- #
def test_happy_path_creates_an_account_and_logs_in(api, student, guardian, guardian_links):
    response = run_full_flow(api, student)
    assert response.status_code == 201, response.data
    assert response.data["username"] == "a.valiyev"
    assert response.data["access"]
    assert "a.valiyev" in response.data["detail"]

    user = User.objects.get(username="a.valiyev")
    assert user.check_password(PASSWORD)
    assert user.is_phone_verified
    guardian.refresh_from_db()
    assert guardian.user_id == user.id


def test_registration_verifies_every_child_of_the_guardian(
    api, student, sibling, guardian, guardian_links
):
    assert GuardianStudent.objects.filter(verified=True).count() == 0
    run_full_flow(api, student)
    assert GuardianStudent.objects.filter(guardian=guardian, verified=True).count() == 2


def test_wrong_jshshir_is_rejected(api, student, guardian_links):
    response = identify(api, student, jshshir="99999999999999")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "IDENTITY_MISMATCH"


def test_wrong_phone_tail_is_rejected(api, student, guardian_links):
    response = identify(api, student, last4="0000")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "IDENTITY_MISMATCH"


def test_wrong_relation_is_rejected(api, student, guardian_links):
    response = identify(api, student, relation=Relation.MOTHER)
    assert response.status_code == 400
    assert response.data["error"]["code"] == "IDENTITY_MISMATCH"


def test_guardian_cannot_claim_an_unrelated_child(api, other_student, guardian, guardian_links):
    """Knowing the child's name + your own JSHSHIR is not enough."""
    response = identify(api, other_student)
    assert response.status_code == 400
    assert response.data["error"]["code"] == "IDENTITY_MISMATCH"


def test_failure_messages_are_indistinguishable(api, student, other_student, guardian_links):
    wrong_jshshir = identify(api, student, jshshir="99999999999999")
    wrong_child = identify(api, other_student)
    assert wrong_jshshir.data["error"] == wrong_child.data["error"]


def test_identify_attempts_are_capped(api, settings, student, guardian_links):
    settings.REGISTRATION = {**settings.REGISTRATION, "IDENTIFY_MAX_ATTEMPTS": 3}
    for _ in range(3):
        identify(api, student, jshshir="99999999999999")
    blocked = identify(api, student)
    assert blocked.status_code == 400
    assert blocked.data["error"]["code"] == "TOO_MANY_ATTEMPTS"


def test_already_registered_guardian_is_told_to_log_in(api, student, parent_user):
    response = identify(api, student)
    assert response.status_code == 409
    assert response.data["error"]["code"] == "ALREADY_REGISTERED"


def test_identify_never_returns_the_full_phone_number(api, student, guardian_links):
    response = identify(api, student)
    assert response.data["masked_phone"] == "+998*****4567"
    assert "+998901234567" not in str(response.data)


# --------------------------------------------------------------------------- #
# OTP
# --------------------------------------------------------------------------- #
def test_otp_is_sent_to_the_registered_number_only(api, student, guardian, guardian_links):
    from apps.common.sms.providers import DummySMSProvider

    token = identify(api, student).data["session_token"]
    api.post(reverse("registration:otp-request"), {"session_token": token}, format="json")
    assert DummySMSProvider.outbox[-1].to == guardian.phone


def test_wrong_otp_is_rejected(api, student, guardian_links):
    token = identify(api, student).data["session_token"]
    api.post(reverse("registration:otp-request"), {"session_token": token}, format="json")
    response = api.post(
        reverse("registration:otp-verify"),
        {"session_token": token, "code": "000000"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "INVALID_OTP"


def test_otp_attempts_are_exhausted(api, settings, student, guardian_links):
    settings.OTP = {**settings.OTP, "MAX_ATTEMPTS": 3}
    token = identify(api, student).data["session_token"]
    api.post(reverse("registration:otp-request"), {"session_token": token}, format="json")
    url = reverse("registration:otp-verify")
    for _ in range(2):
        api.post(url, {"session_token": token, "code": "000000"}, format="json")
    final = api.post(url, {"session_token": token, "code": "000000"}, format="json")
    assert final.data["error"]["code"] == "OTP_ATTEMPTS_EXCEEDED"


def test_otp_resend_cooldown(api, student, guardian_links, settings):
    """The cooldown is configurable, so the test sets it rather than assuming.

    A deployment that turns it off (this one does) must not turn the guarantee
    itself into a failing test.
    """
    settings.OTP = {**settings.OTP, "RESEND_COOLDOWN_SECONDS": 600}

    token = identify(api, student).data["session_token"]
    url = reverse("registration:otp-request")
    assert api.post(url, {"session_token": token}, format="json").status_code == 200
    again = api.post(url, {"session_token": token}, format="json")
    assert again.status_code == 429
    assert again.data["error"]["code"] == "OTP_COOLDOWN"


def test_resend_is_immediate_when_the_cooldown_is_off(api, student, guardian_links, settings):
    settings.OTP = {**settings.OTP, "RESEND_COOLDOWN_SECONDS": 0}

    token = identify(api, student).data["session_token"]
    url = reverse("registration:otp-request")
    assert api.post(url, {"session_token": token}, format="json").status_code == 200
    assert api.post(url, {"session_token": token}, format="json").status_code == 200


def test_expired_otp_cannot_be_used(api, student, guardian_links):
    token = identify(api, student).data["session_token"]
    api.post(reverse("registration:otp-request"), {"session_token": token}, format="json")
    cache.clear()  # simulates TTL expiry
    response = api.post(
        reverse("registration:otp-verify"),
        {"session_token": token, "code": "123456"},
        format="json",
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Completion
# --------------------------------------------------------------------------- #
def test_cannot_complete_without_verifying_the_phone(api, student, guardian_links):
    token = identify(api, student).data["session_token"]
    response = api.post(
        reverse("registration:complete"),
        {"session_token": token, "password": PASSWORD, "password_confirm": PASSWORD},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "PHONE_NOT_VERIFIED"
    assert not User.objects.filter(role="PARENT").exists()


def test_mismatched_passwords_are_rejected(api, student, guardian_links):
    token = identify(api, student).data["session_token"]
    response = api.post(
        reverse("registration:complete"),
        {"session_token": token, "password": PASSWORD, "password_confirm": "Boshqa!Parol1"},
        format="json",
    )
    assert response.status_code == 400
    assert "password_confirm" in response.data["error"]["fields"]


@pytest.mark.parametrize("weak", ["1234567", "password", "11111111", "12345678"])
def test_weak_passwords_are_rejected(api, student, guardian_links, weak):
    token = identify(api, student).data["session_token"]
    response = api.post(
        reverse("registration:complete"),
        {"session_token": token, "password": weak, "password_confirm": weak},
        format="json",
    )
    assert response.status_code == 400


def test_invalid_session_token(api):
    response = api.post(
        reverse("registration:otp-request"), {"session_token": "nope"}, format="json"
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "REGISTRATION_SESSION_INVALID"


# --------------------------------------------------------------------------- #
# Resending a code
# --------------------------------------------------------------------------- #
def test_resending_issues_a_new_code_and_kills_the_old_one(db):
    """Pressing "Qayta yuborish" must not leave the previous code working."""
    from django.core.cache import cache

    from apps.common.otp import OTPInvalidError, OTPPurpose, OTPService

    service = OTPService(OTPPurpose.REGISTRATION, "session-token")
    codes: list[str] = []

    first = service.issue("+998901234567", send=lambda text: codes.append(text))
    # The cooldown is what stops flooding; a deliberate resend clears it.
    cache.delete(service._cooldown_key)
    second = service.issue("+998901234567", send=lambda text: codes.append(text))

    import re

    old = re.search(r"\d{4,6}", codes[0]).group(0)
    new = re.search(r"\d{4,6}", codes[1]).group(0)

    assert old != new
    assert first.ttl_seconds == second.ttl_seconds
    with pytest.raises(OTPInvalidError):
        service.verify(old)
    assert service.verify(new) is True


def test_the_response_says_when_nothing_was_actually_sent(db, settings):
    """A console provider prints the code; claiming it was "sent" is a lie."""
    from apps.common.otp import OTPPurpose, OTPService
    from apps.common.sms.registry import _build

    settings.SMS_PROVIDER = "console"
    _build.cache_clear()
    try:
        result = OTPService(OTPPurpose.REGISTRATION, "session-token").issue("+998901234567")
        assert result.delivered is False
    finally:
        _build.cache_clear()


def test_the_otp_request_reports_the_code_length(api, student, guardian_links):
    """The input field sizes itself from this instead of hardcoding a width."""
    from django.conf import settings as django_settings

    token = identify(api, student).data["session_token"]
    response = api.post(
        reverse("registration:otp-request"), {"session_token": token}, format="json"
    )
    assert response.status_code == 200
    assert response.data["code_length"] == django_settings.OTP["LENGTH"]
