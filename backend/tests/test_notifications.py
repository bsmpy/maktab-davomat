"""Notification fan-out, idempotency and delivery.

A notification is raised by a turnstile pass: the pupil walked in, or walked
out. Both directions reach the guardians, and neither can be sent twice.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.integrations.models import TerminalEvent
from apps.notifications.constants import DeliveryStatus, NotificationChannel, NotificationType
from apps.notifications.models import Notification, NotificationDelivery
from apps.notifications.services import deliver_to_telegram, notify_presence
from apps.notifications.tasks import notify_presence_event
from tests.conftest import at, pass_through

pytestmark = pytest.mark.django_db


@pytest.fixture
def entry(terminal, person, student) -> TerminalEvent:
    """The pupil walked in at 08:24."""
    event = pass_through(terminal, "S1001", at(8, 24), serial=800, direction="IN")
    TerminalEvent.objects.filter(pk=event.pk).update(student=student)
    event.refresh_from_db()
    return event


@pytest.fixture
def exit_(terminal, person, student) -> TerminalEvent:
    """The pupil walked out at 13:40."""
    event = pass_through(terminal, "S1001", at(13, 40), serial=801, direction="OUT")
    TerminalEvent.objects.filter(pk=event.pk).update(student=student)
    event.refresh_from_db()
    return event


# --------------------------------------------------------------------------- #
# Fan-out
# --------------------------------------------------------------------------- #
def test_entering_notifies_every_verified_guardian(entry, student, parent_user):
    created = notify_presence(entry)
    assert len(created) == 1

    notification = created[0]
    assert notification.user == parent_user
    assert notification.type == NotificationType.SCHOOL_ENTRY
    assert notification.student == student
    assert "kirdi" in notification.message
    assert "08:24" in notification.message
    assert notification.payload["direction"] == "IN"


def test_leaving_notifies_too(exit_, student, parent_user):
    notification = notify_presence(exit_)[0]
    assert notification.type == NotificationType.SCHOOL_EXIT
    assert "chiqdi" in notification.message
    assert "13:40" in notification.message


def test_both_directions_produce_separate_messages(entry, exit_, parent_user):
    notify_presence(entry)
    notify_presence(exit_)
    assert Notification.objects.filter(user=parent_user).count() == 2


def test_notifications_are_idempotent(entry, parent_user):
    """Re-running the fan-out (a Celery retry, a device resync) sends once."""
    notify_presence(entry)
    notify_presence(entry)
    notify_presence(entry)
    assert Notification.objects.filter(user=parent_user).count() == 1


def test_task_retries_do_not_duplicate(entry, parent_user):
    notify_presence_event(str(entry.id))
    notify_presence_event(str(entry.id))
    assert Notification.objects.count() == 1


def test_a_pass_with_no_pupil_notifies_nobody(terminal, person):
    stranger = pass_through(terminal, "S9999", at(8, 24), serial=802)
    assert notify_presence(stranger) == []
    assert Notification.objects.count() == 0


def test_unverified_guardians_are_not_notified(entry, student):
    from apps.guardians.models import GuardianStudent

    GuardianStudent.objects.filter(student=student).update(verified=False)
    assert notify_presence(entry) == []


def test_guardians_can_mute_a_child(entry, student):
    from apps.guardians.models import GuardianStudent

    GuardianStudent.objects.filter(student=student).update(notifications_enabled=False)
    assert notify_presence(entry) == []


def test_entry_messages_can_be_switched_off(entry, school, parent_user):
    from apps.integrations.constants import IntegrationKind
    from apps.integrations.models import Integration

    Integration.objects.create(
        kind=IntegrationKind.TELEGRAM_BOT,
        school=school,
        is_enabled=True,
        config={"send_entry": False},
    )
    assert notify_presence(entry) == []


def test_exit_messages_can_be_switched_off_independently(entry, exit_, school, parent_user):
    from apps.integrations.constants import IntegrationKind
    from apps.integrations.models import Integration

    Integration.objects.create(
        kind=IntegrationKind.TELEGRAM_BOT,
        school=school,
        is_enabled=True,
        config={"send_exit": False},
    )
    assert len(notify_presence(entry)) == 1
    assert notify_presence(exit_) == []


def test_ingesting_a_pass_enqueues_the_notification(terminal, person, student, parent_user):
    """CELERY_TASK_ALWAYS_EAGER in tests makes the pipeline path observable."""
    from django.test import TestCase

    from apps.integrations.services.presence import process_events

    event = pass_through(terminal, "S1001", at(8, 24), serial=803)
    TerminalEvent.objects.filter(pk=event.pk).update(student=student)
    event.refresh_from_db()

    with TestCase.captureOnCommitCallbacks(execute=True):
        process_events([event])

    assert Notification.objects.filter(user=parent_user).count() == 1


# --------------------------------------------------------------------------- #
# Delivery
# --------------------------------------------------------------------------- #
def test_telegram_delivery_is_recorded_once(entry, student, parent_user, monkeypatch):
    from apps.telegram.models import TelegramAccount

    TelegramAccount.objects.create(user=parent_user, telegram_id=555001)
    sent = []

    def fake_send(chat_id, text, **kwargs):
        sent.append((chat_id, text))
        return {"message_id": len(sent)}

    monkeypatch.setattr("apps.telegram.services.send_message", fake_send)

    notification = notify_presence(entry)[0]
    deliver_to_telegram(notification)
    deliver_to_telegram(notification)  # a retry must be a no-op

    assert len(sent) == 1
    assert sent[0][0] == 555001
    assert student.display_name in sent[0][1]
    delivery = NotificationDelivery.objects.get(
        notification=notification, channel=NotificationChannel.TELEGRAM
    )
    assert delivery.status == DeliveryStatus.SENT


def test_delivery_is_skipped_when_the_user_blocked_the_bot(entry, parent_user, monkeypatch):
    from apps.telegram.models import TelegramAccount
    from apps.telegram.services import TelegramError

    account = TelegramAccount.objects.create(user=parent_user, telegram_id=555002)

    def blocked(chat_id, text, **kwargs):
        raise TelegramError("Forbidden: bot was blocked by the user", blocked=True)

    monkeypatch.setattr("apps.telegram.services.send_message", blocked)

    notification = notify_presence(entry)[0]
    delivery = deliver_to_telegram(notification)

    assert delivery.status == DeliveryStatus.SKIPPED
    account.refresh_from_db()
    assert account.is_active is False


def test_muted_telegram_account_receives_nothing(entry, parent_user):
    from apps.telegram.models import TelegramAccount

    TelegramAccount.objects.create(
        user=parent_user, telegram_id=555003, notifications_enabled=False
    )
    notification = notify_presence(entry)[0]
    assert deliver_to_telegram(notification) is None


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def test_list_and_mark_as_read(auth_client, entry, parent_user):
    notification = notify_presence(entry)[0]

    listed = auth_client.get(reverse("notifications"))
    assert listed.status_code == 200
    assert listed.data["count"] == 1
    assert listed.data["unread_count"] == 1

    marked = auth_client.post(
        reverse("notifications-mark-read"), {"ids": [str(notification.id)]}, format="json"
    )
    assert marked.data["updated"] == 1
    assert auth_client.get(reverse("notifications-unread-count")).data["unread_count"] == 0


def test_mark_all_as_read(auth_client, terminal, person, student, parent_user):
    for index in range(3):
        event = pass_through(terminal, "S1001", at(8 + index, 0), serial=810 + index)
        TerminalEvent.objects.filter(pk=event.pk).update(student=student)
        event.refresh_from_db()
        notify_presence(event)

    response = auth_client.post(reverse("notifications-mark-all-read"), {}, format="json")
    assert response.data["updated"] == 3


def test_a_parent_never_sees_another_parents_notifications(auth_client, other_parent):
    Notification.objects.create(
        user=other_parent,
        type=NotificationType.SYSTEM,
        title="Boshqa ota-onaga",
        message="Maxfiy",
    )
    response = auth_client.get(reverse("notifications"))
    assert response.data["count"] == 0
