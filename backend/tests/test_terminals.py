"""Hikvision turnstile integration: ingestion, idempotency and the
pass → visit → presence derivation."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.urls import reverse

from apps.integrations.constants import EventDirection, TerminalDirection
from apps.integrations.models import DailyPresence, Terminal, TerminalEvent
from apps.integrations.services.hikvision import AccessEvent
from apps.integrations.services.ingest import ingest_events, parse_push_payload, store_event
from apps.integrations.services.presence import close_open_visits, rebuild_daily_presence
from tests.conftest import TODAY, at

pytestmark = pytest.mark.django_db


def event(person_code: str, moment: datetime, *, serial: int, status: str = "checkIn", minor: int = 75):
    return AccessEvent(
        external_id=f"sn:{serial}",
        occurred_at=moment,
        person_code=person_code,
        person_name="Valiyev Azizbek",
        minor=minor,
        attendance_status=status,
        verify_mode="face",
        picture_url="",
        raw={"serialNo": serial},
    )


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #
def test_event_is_linked_to_the_pupil_by_person_code(terminal, person, student):
    stored = store_event(terminal, event("S1001", at(8, 25), serial=1))
    assert stored is not None
    assert stored.student == student
    assert stored.direction == EventDirection.IN
    assert stored.date == TODAY


def test_unknown_person_code_is_kept_but_unlinked(terminal, person):
    stored = store_event(terminal, event("S9999", at(8, 25), serial=2))
    assert stored is not None
    assert stored.student is None


def test_the_same_event_can_never_be_stored_twice(terminal, person):
    """Push and poll overlap by design — the constraint is what makes it safe."""
    first = store_event(terminal, event("S1001", at(8, 25), serial=7))
    duplicate = store_event(terminal, event("S1001", at(8, 25), serial=7))
    assert first is not None
    assert duplicate is None
    assert TerminalEvent.objects.count() == 1


def test_denied_attempts_are_not_arrivals(terminal, person):
    """An unrecognised face must never mark a pupil present."""
    assert store_event(terminal, event("S1001", at(8, 25), serial=3, minor=6)) is None
    assert TerminalEvent.objects.count() == 0


def test_a_one_way_reader_overrides_the_device_label(school, person):
    exit_only = Terminal(
        school=school, name="Chiqish", host="192.168.1.65", direction=TerminalDirection.OUT
    )
    exit_only.save()
    stored = store_event(exit_only, event("S1001", at(14, 0), serial=9, status="checkIn"))
    assert stored.direction == EventDirection.OUT


def test_ingest_updates_the_last_event_marker(terminal, person):
    ingest_events(terminal, [event("S1001", at(8, 25), serial=11)])
    terminal.refresh_from_db()
    assert terminal.last_event_at == at(8, 25)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "dateTime": f"{TODAY.isoformat()}T08:31:02+05:00",
            "AccessControllerEvent": {
                "minor": 75, "employeeNoString": "S1001", "serialNo": 4711,
                "attendanceStatus": "checkIn", "currentVerifyMode": "face",
            },
        },
        {
            "AcsEvent": {
                "InfoList": [
                    {
                        "time": f"{TODAY.isoformat()}T08:31:02+05:00", "employeeNoString": "S1001",
                        "minor": 75, "serialNo": 4711, "attendanceStatus": "checkIn",
                    }
                ]
            }
        },
    ],
)
def test_push_payload_shapes_are_all_understood(payload):
    events = parse_push_payload(payload)
    assert len(events) == 1
    assert events[0].person_code == "S1001"
    assert events[0].external_id == "sn:4711"


def test_push_webhook_accepts_a_device_notification(api, terminal, person, student):
    url = reverse("terminals:terminal-ingest", args=[terminal.ingest_token])
    response = api.post(
        url,
        {
            "dateTime": f"{TODAY.isoformat()}T08:31:02+05:00",
            "AccessControllerEvent": {
                "minor": 75, "employeeNoString": "S1001", "serialNo": 5001,
                "attendanceStatus": "checkIn",
            },
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["stored"] == 1
    assert TerminalEvent.objects.filter(student=student).count() == 1


def test_push_webhook_rejects_a_wrong_token(api, terminal):
    response = api.post(
        reverse("terminals:terminal-ingest", args=["not-a-real-token"]), {}, format="json"
    )
    assert response.status_code == 404


def test_rotating_the_token_invalidates_the_old_url(api, terminal, person):
    old = terminal.ingest_token
    terminal.rotate_ingest_token()
    response = api.post(reverse("terminals:terminal-ingest", args=[old]), {}, format="json")
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Presence: prihod / uhod
# --------------------------------------------------------------------------- #
def test_presence_collapses_a_day_into_first_in_and_last_out(terminal, person, student):
    for index, (moment, status) in enumerate(
        [
            (at(8, 25), "checkIn"),
            (at(12, 10), "checkOut"),
            (at(12, 40), "checkIn"),
            (at(14, 5), "checkOut"),
        ]
    ):
        store_event(terminal, event("S1001", moment, serial=100 + index, status=status))

    presence = rebuild_daily_presence(student, TODAY)
    assert presence.first_in_at == at(8, 25)
    assert presence.last_out_at == at(14, 5)
    assert presence.entries_count == 2
    assert presence.exits_count == 2
    assert presence.duration_minutes == 340


def test_repeat_reads_within_the_debounce_window_are_one_arrival(terminal, person, student):
    """A pupil fumbling their bag triggers three reads, not three arrivals."""
    for index, moment in enumerate([at(8, 25), at(8, 25, ), at(8, 25)]):
        store_event(
            terminal, event("S1001", moment + timedelta(seconds=index * 10), serial=200 + index)
        )
    presence = rebuild_daily_presence(student, TODAY)
    assert presence.entries_count == 1


def test_presence_is_removed_when_the_events_are(terminal, person, student):
    store_event(terminal, event("S1001", at(8, 25), serial=300))
    rebuild_daily_presence(student, TODAY)
    assert DailyPresence.objects.filter(student=student, date=TODAY).exists()

    TerminalEvent.objects.all().delete()
    assert rebuild_daily_presence(student, TODAY) is None
    assert not DailyPresence.objects.filter(student=student, date=TODAY).exists()


def test_late_minutes_are_measured_against_the_school_day(terminal, person, student):
    """The school day starts 08:10; arriving 08:32 is 22 minutes late."""
    store_event(terminal, event("S1001", at(8, 32), serial=400))
    presence = rebuild_daily_presence(student, TODAY)
    assert presence.late_minutes == 22


def test_arriving_before_the_start_is_not_late(terminal, person, student):
    store_event(terminal, event("S1001", at(8, 5), serial=401))
    presence = rebuild_daily_presence(student, TODAY)
    assert presence.late_minutes == 0


def test_leaving_before_the_school_day_ends_is_flagged(terminal, person, student):
    store_event(terminal, event("S1001", at(8, 25), serial=402))
    store_event(terminal, event("S1001", at(11, 0), serial=403, status="checkOut"))
    presence = rebuild_daily_presence(student, TODAY)
    assert presence.left_early is True


# --------------------------------------------------------------------------- #
# Visits: how long the pupil was actually inside
# --------------------------------------------------------------------------- #
def test_a_day_is_split_into_entry_exit_visits(terminal, person, student):
    for index, (moment, status) in enumerate(
        [
            (at(8, 25), "checkIn"),
            (at(12, 10), "checkOut"),
            (at(12, 40), "checkIn"),
            (at(14, 5), "checkOut"),
        ]
    ):
        store_event(terminal, event("S1001", moment, serial=600 + index, status=status))

    presence = rebuild_daily_presence(student, TODAY)
    assert [(visit["minutes"]) for visit in presence.sessions] == [225, 85]
    assert presence.inside_minutes == 310
    # 12:10 → 12:40 is the only stretch spent outside.
    assert presence.outside_minutes == 30
    # The whole span is longer than the time inside, because of that gap.
    assert presence.duration_minutes == 340


def test_a_pupil_who_has_not_left_yet_is_still_inside(terminal, person, student):
    store_event(terminal, event("S1001", at(8, 25), serial=610))
    presence = rebuild_daily_presence(student, TODAY)

    assert presence.is_inside is True
    assert presence.last_out_at is None
    assert presence.sessions[-1]["out"] is None


def test_an_exit_with_no_matching_entry_is_ignored(terminal, person, student):
    """The device came online mid-morning: the arrival was never recorded."""
    store_event(terminal, event("S1001", at(13, 0), serial=620, status="checkOut"))
    presence = rebuild_daily_presence(student, TODAY)

    assert presence.exits_count == 1
    assert presence.sessions == []
    assert presence.inside_minutes == 0


def test_two_entries_in_a_row_keep_the_earlier_arrival(terminal, person, student):
    """A missed exit must not restart the clock."""
    store_event(terminal, event("S1001", at(8, 30), serial=630))
    store_event(terminal, event("S1001", at(10, 0), serial=631))
    store_event(terminal, event("S1001", at(12, 0), serial=632, status="checkOut"))

    presence = rebuild_daily_presence(student, TODAY)
    assert len(presence.sessions) == 1
    assert datetime.fromisoformat(presence.sessions[0]["in"]) == at(8, 30)
    assert presence.inside_minutes == 210


def test_an_undirected_reader_alternates_in_and_out(school, student):
    """A BOTH reader that does not label the pass: in, out, in, out …"""
    from apps.integrations.models import TerminalPerson

    device = Terminal(
        school=school, name="Turniket", host="192.168.1.70",
        direction=TerminalDirection.BOTH,
    )
    device.save()
    TerminalPerson.objects.create(school=school, student=student, person_code="S2001")

    for index, moment in enumerate([at(8, 0), at(11, 0), at(11, 30), at(14, 0)]):
        store_event(terminal=device, event=event("S2001", moment, serial=640 + index, status=""))

    presence = rebuild_daily_presence(student, TODAY)
    assert presence.entries_count == 2
    assert presence.exits_count == 2
    assert len(presence.sessions) == 2


def test_rebuilding_a_day_is_idempotent(terminal, person, student):
    store_event(terminal, event("S1001", at(8, 25), serial=650))
    store_event(terminal, event("S1001", at(13, 0), serial=651, status="checkOut"))

    first = rebuild_daily_presence(student, TODAY)
    second = rebuild_daily_presence(student, TODAY)

    assert DailyPresence.objects.filter(student=student, date=TODAY).count() == 1
    assert first.inside_minutes == second.inside_minutes
    assert first.sessions == second.sessions


def test_closing_the_day_settles_an_open_visit(terminal, person, student, school):
    store_event(terminal, event("S1001", at(8, 25), serial=660))
    rebuild_daily_presence(student, TODAY)
    assert DailyPresence.objects.get(student=student, date=TODAY).is_inside is True

    assert close_open_visits(school, TODAY) == 1
    # Still open — nobody recorded them leaving — but the day is settled.
    presence = DailyPresence.objects.get(student=student, date=TODAY)
    assert presence.inside_minutes > 0


# --------------------------------------------------------------------------- #
# Enrolment API
# --------------------------------------------------------------------------- #
@pytest.fixture
def developer_client(api, db):
    from apps.accounts.constants import Role
    from apps.accounts.models import User
    from apps.accounts.services.auth import issue_tokens

    user = User.objects.create_user(
        username="bsm", password="Test!Parol2026", role=Role.DEVELOPER,
        first_name="Developer", last_name="BSM", is_staff=True, is_superuser=True,
    )
    access, _refresh, _ttl = issue_tokens(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


def test_an_empty_enrol_request_is_refused(developer_client, student):
    """A stray POST must not push the whole school onto the devices."""
    response = developer_client.post(reverse("settings:face-enroll"), {}, format="json")
    assert response.status_code == 400


def test_enrolling_everyone_has_to_be_asked_for_by_name(
    developer_client, student, sibling, terminal, monkeypatch
):
    seen = []
    monkeypatch.setattr(
        "apps.integrations.services.enrollment.enroll_student",
        lambda s, *a, **k: (
            seen.append(s.id)
            or {"person_code": "S1", "terminals": 1, "faces": 1, "errors": []}
        ),
    )

    response = developer_client.post(
        reverse("settings:face-enroll"), {"all": True}, format="json"
    )
    assert response.status_code == 200
    assert response.data["enrolled"] == len(seen)
    assert student.id in seen and sibling.id in seen


def test_enrolling_one_class_touches_only_that_class(
    developer_client, student, other_student, terminal, monkeypatch
):
    seen = []
    monkeypatch.setattr(
        "apps.integrations.services.enrollment.enroll_student",
        lambda s, *a, **k: (
            seen.append(s.id)
            or {"person_code": "S1", "terminals": 1, "faces": 0, "errors": []}
        ),
    )

    response = developer_client.post(
        reverse("settings:face-enroll"),
        {"class_group": str(student.class_group_id)},
        format="json",
    )
    assert response.status_code == 200
    assert seen == [student.id]


def test_a_bulk_enrol_is_audited(developer_client, student, terminal, monkeypatch):
    from apps.audit.constants import AuditAction
    from apps.audit.models import AuditLog

    monkeypatch.setattr(
        "apps.integrations.services.enrollment.enroll_student",
        lambda s, *a, **k: {"person_code": "S1", "terminals": 1, "faces": 1, "errors": []},
    )
    developer_client.post(reverse("settings:face-enroll"), {"all": True}, format="json")

    entry = AuditLog.objects.filter(action=AuditAction.SENSITIVE_DATA_ACCESS).first()
    assert entry is not None
    assert entry.metadata["operation"] == "face_enroll"


# --------------------------------------------------------------------------- #
# Talking to the device: what its 400s actually mean
# --------------------------------------------------------------------------- #
class FakeResponse:
    """Just enough of an httpx response for the client's error path."""

    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.content = b"{}" if payload is not None else b""
        self.text = ""

    def json(self):
        if self._payload is None:
            raise ValueError("no body")
        return self._payload


def client_with(responses):
    """A HikvisionClient whose transport replays the given responses in order."""
    from apps.integrations.services.hikvision import HikvisionClient

    client = HikvisionClient.__new__(HikvisionClient)
    client.base_url = "http://device"
    sent: list[tuple[str, str]] = []

    class Transport:
        def request(self, method, path, **kwargs):
            sent.append((method, path))
            return responses.pop(0)

    client._client = Transport()
    return client, sent


def test_a_device_error_carries_its_own_explanation():
    """"HTTP 400" on its own is undiagnosable; the device says why."""
    from apps.integrations.services.hikvision import HikvisionError

    client, _ = client_with([
        FakeResponse(400, {"statusCode": 6, "subStatusCode": "employeeNoAlreadyExist"})
    ])
    with pytest.raises(HikvisionError) as caught:
        client._get("/anything")

    assert caught.value.sub_status == "employeeNoAlreadyExist"
    assert "employeeNoAlreadyExist" in str(caught.value)
    assert caught.value.is_duplicate is True


def test_an_existing_person_is_updated_not_reported_as_a_failure():
    """The device answers a duplicate with 400, so it has to be caught."""
    client, sent = client_with([
        FakeResponse(400, {"statusCode": 6, "subStatusCode": "employeeNoAlreadyExist"}),
        FakeResponse(200, {"statusCode": 1}),
    ])
    client.upsert_person("S000001", "Samir Hasanov")

    assert [path.split("?")[0] for _method, path in sent] == [
        "/ISAPI/AccessControl/UserInfo/Record",
        "/ISAPI/AccessControl/UserInfo/Modify",
    ]


def test_a_real_person_error_still_raises():
    from apps.integrations.services.hikvision import HikvisionError

    client, _ = client_with([
        FakeResponse(400, {"statusCode": 4, "subStatusCode": "badParameters"})
    ])
    with pytest.raises(HikvisionError):
        client.upsert_person("S000001", "Samir Hasanov")


def test_faces_go_to_the_access_terminal_endpoint():
    """`FDSetUp` is the camera spelling; access terminals want FaceDataRecord."""
    client, sent = client_with([FakeResponse(200, {"statusCode": 1})])
    client.upload_face("S000001", b"jpeg-bytes")

    assert sent[0][1].split("?")[0] == "/ISAPI/Intelligent/FDLib/FaceDataRecord"


def test_camera_firmware_falls_back_to_the_old_endpoint():
    client, sent = client_with([
        FakeResponse(400, {"statusCode": 4, "subStatusCode": "methodNotAllowed"}),
        FakeResponse(200, {"statusCode": 1}),
    ])
    client.upload_face("S000001", b"jpeg-bytes")

    assert [path.split("?")[0] for _method, path in sent] == [
        "/ISAPI/Intelligent/FDLib/FaceDataRecord",
        "/ISAPI/Intelligent/FDLib/FDSetUp",
    ]


def test_re_enrolling_replaces_an_existing_face():
    """A second upload means the photo changed — swap it, do not fail."""
    client, sent = client_with([
        FakeResponse(400, {"statusCode": 4, "subStatusCode": "deviceUserAlreadyExistFace"}),
        FakeResponse(200, {"statusCode": 1}),  # delete
        FakeResponse(200, {"statusCode": 1}),  # upload again
    ])
    client.upload_face("S000001", b"jpeg-bytes")

    assert [path.split("?")[0] for _method, path in sent] == [
        "/ISAPI/Intelligent/FDLib/FaceDataRecord",
        "/ISAPI/Intelligent/FDLib/FDSearch/Delete",
        "/ISAPI/Intelligent/FDLib/FaceDataRecord",
    ]


# --------------------------------------------------------------------------- #
# Staff are enrolled the same way pupils are
# --------------------------------------------------------------------------- #
def test_a_teacher_gets_a_device_identity_of_their_own(school, teaching_teacher):
    from apps.integrations.services.enrollment import ensure_person_code

    person = ensure_person_code(teaching_teacher)
    assert person.teacher_id == teaching_teacher.id
    assert person.student_id is None
    # Prefixed so a glance at the device says which register the person is in.
    assert person.person_code.startswith("T")
    # Idempotent: a second call returns the same row, not a second code.
    assert ensure_person_code(teaching_teacher).pk == person.pk


def test_a_pupil_keeps_their_register_code(school, student):
    from apps.integrations.services.enrollment import ensure_person_code

    person = ensure_person_code(student)
    assert person.person_code == student.student_code
    assert person.teacher_id is None


def test_one_code_belongs_to_one_person(school, student, teaching_teacher):
    from apps.integrations.services.enrollment import ensure_person_code

    pupil = ensure_person_code(student)
    staff = ensure_person_code(teaching_teacher)
    assert pupil.person_code != staff.person_code


def test_a_terminal_person_cannot_be_both(school, student, teaching_teacher):
    from django.db.utils import IntegrityError

    from apps.integrations.models import TerminalPerson

    with pytest.raises(IntegrityError):
        TerminalPerson.objects.create(
            school=school, student=student, teacher=teaching_teacher, person_code="X1"
        )


@pytest.fixture
def dev_client(db):
    from rest_framework.test import APIClient

    from apps.accounts.constants import Role
    from apps.accounts.models import User
    from apps.accounts.services.auth import issue_tokens
    from tests.conftest import PASSWORD

    user = User.objects.create_user(
        username="bsm", password=PASSWORD, role=Role.DEVELOPER,
        first_name="Behruz", last_name="Sattorov",
    )
    client = APIClient()
    access, _refresh, _ttl = issue_tokens(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def test_adding_a_teacher_queues_the_terminal_push(
    dev_client, school, monkeypatch, django_capture_on_commit_callbacks
):
    """The console is the whole action — nobody should have to open Face ID."""
    queued = []
    from apps.integrations import tasks

    monkeypatch.setattr(
        tasks.enroll_teacher_on_terminals, "delay", lambda teacher_id: queued.append(teacher_id)
    )

    # The push waits for the write to commit, so nothing is sent for a teacher
    # whose creation then fails.
    with django_capture_on_commit_callbacks(execute=True):
        response = dev_client.post(
            reverse("management:teachers"),
            {"first_name": "Sardor", "last_name": "Yusupov"},
            format="json",
        )
    assert response.status_code == 201
    assert queued == [response.data["id"]]
