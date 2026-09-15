"""Pushing people (and their faces) onto the access terminals.

Pupils and staff walk through the same gate, so both are enrolled the same way:
one ``TerminalPerson`` row per person, holding the code the device knows them
by. Enrolment is idempotent per device — ``synced_terminals`` records where the
person already exists, so a re-sync only touches what is missing or changed.
"""
from __future__ import annotations

import io
import logging

from django.utils import timezone

from ..constants import IntegrationKind, SyncState
from ..models import Terminal, TerminalPerson
from .hikvision import HikvisionClient, HikvisionError
from .registry import integration_config

logger = logging.getLogger(__name__)

#: Devices reject very large pictures; downscale before uploading.
MAX_FACE_DIMENSION = 800
JPEG_QUALITY = 88


class EnrollmentError(Exception):
    pass


#: Which column of ``TerminalPerson``/``TerminalEvent`` a register row lands in.
PERSON_FIELDS = {
    "students.Student": "student",
    "schools.Teacher": "teacher",
    "schools.StaffMember": "staff",
}


def person_field(person) -> str:
    """Whose column this person belongs in — pupils, teachers and staff differ."""
    try:
        return PERSON_FIELDS[person._meta.label]
    except KeyError:  # pragma: no cover - a model nobody enrols
        raise EnrollmentError(f"Bu yozuvni terminalga qo'shib bo'lmaydi: {person!r}") from None


def person_link(person) -> dict:
    """``{"teacher": row}`` and friends — the lookup/creation kwargs for a person."""
    return {person_field(person): person}


def is_teacher(person) -> bool:
    """Staff and pupils are told apart by which model they came from.

    Kept for the call sites that only need "is this an adult"; anything that
    writes a column should use :func:`person_link`.
    """
    return person_field(person) != "student"


def ensure_person_code(person) -> TerminalPerson:
    """Get or create the mapping between a person and their device identity.

    A pupil's own code is preferred when the register has one; staff and pupils
    without one get a generated code, prefixed so a glance at the device tells
    you which register the person is in.
    """
    field = person_field(person)
    staff = field != "student"
    existing = TerminalPerson.objects.filter(**person_link(person)).first()
    if existing is not None:
        return existing

    candidate = "" if staff else (person.student_code or "").strip()
    taken = set(
        TerminalPerson.objects.filter(school_id=person.school_id).values_list(
            "person_code", flat=True
        )
    )
    if not candidate or candidate in taken:
        prefix = "T" if staff else "S"
        index = len(taken) + 1
        candidate = f"{prefix}{index:06d}"
        while candidate in taken:
            index += 1
            candidate = f"{prefix}{index:06d}"

    return TerminalPerson.objects.create(
        school_id=person.school_id,
        person_code=candidate[:64],
        card_no="",
        **person_link(person),
    )


def prepare_face_image(raw: bytes) -> bytes:
    """Validate and normalise a photo for the device's face library."""
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        image = Image.open(io.BytesIO(raw))
    except (UnidentifiedImageError, OSError) as exc:
        raise EnrollmentError("Rasm formati noto'g'ri yoki fayl buzilgan.") from exc

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")

    largest = max(image.size)
    if largest > MAX_FACE_DIMENSION:
        ratio = MAX_FACE_DIMENSION / largest
        image = image.resize(
            (int(image.width * ratio), int(image.height * ratio)), Image.LANCZOS
        )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def enroll_person(holder, terminals: list[Terminal] | None = None) -> dict:
    """Create the person record (and upload the face) on every active terminal.

    ``holder`` is a pupil or a member of staff — the flow is identical, which is
    the point: a teacher who walks through the gate should be recognised the
    same way a pupil is.
    """
    person = ensure_person_code(holder)
    config = integration_config(IntegrationKind.FACE_ID, holder.school)
    fdid = str(config.get("fdid", "1"))

    if terminals is None:
        terminals = list(
            Terminal.objects.filter(school_id=holder.school_id, is_active=True)
        )
    if not terminals:
        return {"person_code": person.person_code, "terminals": 0, "faces": 0, "errors": []}

    face_bytes: bytes | None = None
    if holder.photo:
        try:
            with holder.photo.open("rb") as handle:
                face_bytes = prepare_face_image(handle.read())
        except (EnrollmentError, OSError, ValueError) as exc:
            logger.warning("Face image unusable for %s: %s", holder.id, exc)
            face_bytes = None

    # A pupil is shown by their short display name; staff by their full one.
    display_name = getattr(holder, "display_name", None) or holder.full_name
    synced, faces, errors = 0, 0, []
    for terminal in terminals:
        try:
            with HikvisionClient.for_terminal(terminal) as client:
                client.upsert_person(person.person_code, display_name)
                synced += 1
                if face_bytes:
                    client.upload_face(person.person_code, face_bytes, fdid=fdid)
                    faces += 1
            person.synced_terminals.add(terminal)
            terminal.mark_online()
        except HikvisionError as error:
            errors.append(f"{terminal.name}: {error}")
            terminal.mark_offline(str(error))

    person.has_face = faces > 0 or person.has_face
    if faces:
        person.face_synced_at = timezone.now()
    person.sync_state = SyncState.SYNCED if synced and not errors else (
        SyncState.FAILED if not synced else SyncState.PENDING
    )
    person.sync_error = "; ".join(errors)[:500]
    person.save(
        update_fields=[
            "has_face", "face_synced_at", "sync_state", "sync_error", "updated_at",
        ]
    )

    return {
        "person_code": person.person_code,
        "terminals": synced,
        "faces": faces,
        "errors": errors,
    }


def enroll_student(student, terminals: list[Terminal] | None = None) -> dict:
    """Kept for the pupil call sites; enrolment itself is person-agnostic."""
    return enroll_person(student, terminals)


def remove_student(student) -> dict:
    """Kept for the pupil call sites."""
    return remove_person(student)


def remove_person(holder) -> dict:
    """Delete a person from every device they were pushed to."""
    person = TerminalPerson.objects.filter(**person_link(holder)).first()
    if person is None:
        return {"removed": 0, "errors": []}

    removed, errors = 0, []
    for terminal in person.synced_terminals.all():
        try:
            with HikvisionClient.for_terminal(terminal) as client:
                client.delete_face(person.person_code)
                client.delete_person(person.person_code)
            removed += 1
        except HikvisionError as error:
            errors.append(f"{terminal.name}: {error}")

    person.synced_terminals.clear()
    person.has_face = False
    person.sync_state = SyncState.PENDING
    person.save(update_fields=["has_face", "sync_state", "updated_at"])
    return {"removed": removed, "errors": errors}


def sync_class_group(class_group) -> dict:
    """Enrol a whole class — the usual bulk operation at the start of a year."""
    from apps.students.models import Student

    terminals = list(Terminal.objects.filter(school_id=class_group.school_id, is_active=True))
    students = Student.objects.active().filter(class_group=class_group).select_related("school")

    total = {"students": 0, "terminals": len(terminals), "faces": 0, "errors": []}
    for student in students:
        result = enroll_student(student, terminals)
        total["students"] += 1
        total["faces"] += result["faces"]
        total["errors"].extend(result["errors"])
    return total
