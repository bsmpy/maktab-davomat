"""Полный профиль сотрудника — то, что открывается по клику на карточку.

Учитель и прочий сотрудник — один и тот же тип записи (``PersonRecord``), и
профиль у них один: кто это, чем он входит в кабинет, что он делает в школе и
как у него прошла неделя. Отличается только раздел «работа»: у учителя —
предметы, кураторство и расписание, у сотрудника — должность.

Всё собирается в один ответ, чтобы модалка открывалась одним запросом, а не
пятью: карточка на экране, профиль — через долю секунды.
"""
from __future__ import annotations

from collections import defaultdict

from apps.common.media import absolute_media_url

WEEKDAY_LABELS = {
    1: "Dushanba", 2: "Seshanba", 3: "Chorshanba",
    4: "Payshanba", 5: "Juma", 6: "Shanba", 7: "Yakshanba",
}


def _account(user) -> dict | None:
    """Кабинетный аккаунт — без пароля и всего, что к нему ведёт."""
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "roles": user.role_codes,
        "active_role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _identity(person, kind: str) -> dict:
    return {
        "id": str(person.id),
        "kind": kind,
        "full_name": " ".join(
            part for part in (person.last_name, person.first_name, person.middle_name) if part
        ),
        "first_name": person.first_name,
        "last_name": person.last_name,
        "middle_name": person.middle_name,
        "photo": absolute_media_url(person.photo),
        "gender": person.gender,
        "gender_label": person.get_gender_display() if person.gender else "",
        "birth_date": person.birth_date.isoformat() if person.birth_date else None,
        "passport_id": person.passport_id,
        "jshshir": person.jshshir,
        "masked_jshshir": person.masked_jshshir,
        "phone": person.phone,
        "email": person.email,
        "is_active": person.is_active,
        "school": person.school.name if person.school_id else "",
    }


def _curator_groups(user) -> list[dict]:
    if user is None:
        return []
    from apps.schools.models import CuratorAssignment
    from apps.students.models import Student

    rows = (
        CuratorAssignment.objects.filter(user=user)
        .select_related("class_group", "class_group__grade")
        .order_by("class_group__grade__level", "class_group__name")
    )
    return [
        {
            "id": str(row.class_group_id),
            "display_name": row.class_group.display_name,
            "students_count": Student.objects.active()
            .filter(class_group_id=row.class_group_id)
            .count(),
        }
        for row in rows
    ]


def _timetable(teacher) -> dict:
    """Неделя учителя по дням — прямо из ``Schedule``, отсортированная по звонкам."""
    from apps.attendance.models import Schedule

    rows = (
        Schedule.objects.filter(teacher=teacher, is_active=True)
        .select_related("subject", "class_group", "class_group__grade")
        .order_by("weekday", "start_time")
    )
    by_day: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_day[row.weekday].append({
            "lesson_number": row.lesson_number,
            "start_time": row.start_time.strftime("%H:%M"),
            "end_time": row.end_time.strftime("%H:%M"),
            "subject": row.subject.name,
            "class_group": row.class_group.display_name,
            "room": row.room,
        })
    return {
        "lessons_per_week": sum(len(items) for items in by_day.values()),
        "days": [
            {"weekday": day, "label": WEEKDAY_LABELS[day], "lessons": by_day[day]}
            for day in sorted(by_day)
        ],
    }


def _week_presence(person) -> dict | None:
    """Эта неделя у турникета. Пусто, если человек на турникет не заведён."""
    from apps.attendance.services.periods import today, week_range
    from apps.attendance.services.teacher_presence import range_summary

    span = week_range(today())
    try:
        return range_summary(person, span.start, span.end)
    except Exception:  # pragma: no cover - нет настроек терминала у школы
        return None


def teacher_profile(teacher, *, with_presence: bool = True) -> dict:
    """``with_presence=False`` leaves out the week at the gate — for a viewer
    who may read the register but not anybody's attendance (ADMIN)."""
    subjects_by_group: dict[str, list[str]] = defaultdict(list)
    for subject in (
        teacher.subjects.filter(deleted_at__isnull=True)
        .select_related("class_group", "class_group__grade")
        .order_by("class_group__grade__level", "class_group__name", "name")
    ):
        group = subject.class_group.display_name if subject.class_group_id else "—"
        subjects_by_group[group].append(subject.name)

    return {
        **_identity(teacher, "teacher"),
        "account": _account(teacher.user),
        "position": None,
        "subjects": [
            {"class_group": group, "subjects": names}
            for group, names in subjects_by_group.items()
        ],
        "subjects_count": sum(len(names) for names in subjects_by_group.values()),
        "curator_groups": _curator_groups(teacher.user),
        "homeroom_groups": [
            group.display_name
            for group in teacher.homeroom_class_groups.select_related("grade").order_by(
                "grade__level", "name"
            )
        ],
        "timetable": _timetable(teacher),
        "week": _week_presence(teacher) if with_presence else None,
    }


def staff_profile(staff, *, with_presence: bool = True) -> dict:
    position = None
    if staff.position_id:
        position = {"id": str(staff.position_id), "titles": staff.position.titles}
    return {
        **_identity(staff, "staff"),
        "account": _account(staff.user),
        "position": position,
        "subjects": [],
        "subjects_count": 0,
        "curator_groups": _curator_groups(staff.user),
        "homeroom_groups": [],
        "timetable": {"lessons_per_week": 0, "days": []},
        "week": _week_presence(staff) if with_presence else None,
    }
