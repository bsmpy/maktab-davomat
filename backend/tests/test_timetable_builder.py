"""Решатель расписания: часы, звонки и отсутствие накладок.

Тесты написаны против ``audit``, а не против внутренностей: проверяется не то,
что алгоритм думал, а то, что получилось. Два случая здесь не декоративные —
на них он ломался:

* один предмет дважды в день даёт два ребра с одинаковыми концами, и переворот
  α/β-цепочки принимал их за одно, теряя час;
* две смены используют одни и те же номера звонков, и накладку надо считать
  внутри смены, иначе половина расписания выглядит конфликтом.
"""
from __future__ import annotations

import pytest

from apps.attendance.services.timetable_builder import (
    SLOTS_PER_DAY,
    Course,
    GroupPlan,
    TimetableError,
    audit,
    build,
)

WEEK = (1, 2, 3, 4, 5)
SIX_DAYS = (1, 2, 3, 4, 5, 6)


def plan(group: str, courses, *, shift: int = 1, days=WEEK) -> GroupPlan:
    return GroupPlan(group=group, shift=shift, days=days, courses=tuple(courses))


def test_one_group_fills_every_day():
    """Тридцать часов ложатся ровно по шесть в каждый из пяти дней."""
    plans = [plan("1-A", [
        Course("ona", "t1", 10), Course("mat", "t1", 10),
        Course("sport", "t2", 5), Course("musiqa", "t3", 5),
    ])]
    placements = build(plans)

    assert len(placements) == 30
    assert audit(plans, placements) == {}
    for day in WEEK:
        assert sum(1 for row in placements if row.weekday == day) == SLOTS_PER_DAY


def test_a_subject_twice_a_day_keeps_both_hours():
    """Сдвоенный урок — два ребра с одинаковыми концами, и оба должны выжить.

    Именно здесь терялся час: рёбра были неразличимы, и переворот α/β-цепочки
    затирал одно из них. Три предмета по десять часов на пять дней — это ровно
    по два урока каждого каждый день, то есть сплошные сдвоенные пары.
    """
    plans = [plan("1-A", [
        Course("ona", "t1", 10), Course("mat", "t1", 10), Course("sport", "t2", 10),
    ])]
    placements = build(plans)

    assert audit(plans, placements) == {}
    hours: dict[str, int] = {}
    for row in placements:
        hours[row.subject] = hours.get(row.subject, 0) + 1
    assert hours == {"ona": 10, "mat": 10, "sport": 10}


def test_a_teacher_is_never_in_two_places_at_once():
    """Один учитель на три группы: расписание обязано его развести."""
    shared = "t-shared"
    plans = [
        plan(f"5-{letter}", [
            Course(f"{letter}-mat", shared, 10),
            Course(f"{letter}-til", f"t-{letter}-1", 10),
            Course(f"{letter}-sport", f"t-{letter}-2", 10),
        ])
        for letter in "ABC"
    ]
    placements = build(plans)

    assert audit(plans, placements) == {}
    busy = {}
    for row in placements:
        if row.teacher != shared:
            continue
        key = (row.weekday, row.slot)
        assert key not in busy, f"{shared} занят дважды в {key}"
        busy[key] = row.group


def test_the_two_shifts_do_not_collide():
    """Смены идут в разное время, поэтому один номер звонка — не накладка.

    Учитель ведёт и в первой смене, и во второй; шесть уроков там и шесть
    здесь должны уложиться без жалоб.
    """
    teacher = "t-both"
    plans = [
        plan("10-A", [
            Course("a-mat", teacher, 10), Course("a-til", teacher, 10),
            Course("a-fizika", teacher, 10),
        ], shift=1),
        plan("5-A", [
            Course("b-mat", teacher, 10), Course("b-til", teacher, 10),
            Course("b-fizika", teacher, 10),
        ], shift=2),
    ]
    placements = build(plans)

    assert audit(plans, placements) == {}
    assert len(placements) == 60
    # В каждой смене у него ровно шесть уроков в день — и это законно.
    first = [row for row in placements if row.group == "10-A"]
    second = [row for row in placements if row.group == "5-A"]
    assert len(first) == len(second) == 30


def test_hours_are_kept_exactly():
    plans = [
        plan("7-A", [
            Course("til", "t1", 5), Course("mat", "t2", 5), Course("fizika", "t3", 4),
            Course("kimyo", "t4", 4), Course("sport", "t5", 3), Course("tarix", "t6", 3),
            Course("geo", "t7", 3), Course("bio", "t8", 3), Course("info", "t9", 6),
        ], days=SIX_DAYS)
    ]
    placements = build(plans)

    assert audit(plans, placements) == {}
    counted = {}
    for row in placements:
        counted[row.subject] = counted.get(row.subject, 0) + 1
    assert counted == {
        "til": 5, "mat": 5, "fizika": 4, "kimyo": 4, "sport": 3,
        "tarix": 3, "geo": 3, "bio": 3, "info": 6,
    }


def test_a_subject_cannot_take_a_whole_week_three_times_a_day():
    """Больше двух одинаковых уроков в день — это уже не расписание."""
    plans = [plan("1-A", [Course("ona", "t1", 30)])]
    with pytest.raises(TimetableError):
        build(plans)


def test_an_impossible_teacher_load_is_refused_not_fudged():
    """Семь групп на одного учителя в одной смене не сходятся — и это говорится.

    Шесть звонков в смене; седьмую группу в тот же час поставить некуда, и
    решатель обязан отказать, а не выдать расписание с накладкой.
    """
    teacher = "t-one"
    plans = [
        plan(f"5-{letter}", [
            Course(f"{letter}-mat", teacher, 10),
            Course(f"{letter}-til", teacher, 10),
            Course(f"{letter}-sport", teacher, 10),
        ], shift=2)
        for letter in "ABCDEFG"
    ]
    with pytest.raises(TimetableError):
        build(plans)


def test_audit_catches_a_broken_timetable():
    """Проверка должна ловить подделку, иначе она ничего не стоит."""
    from apps.attendance.services.timetable_builder import Placement

    plans = [plan("1-A", [Course("ona", "t1", 30)], days=(1,))]
    fake = [Placement("1-A", 1, slot, "ona", "t1") for slot in range(1, 4)]

    problems = audit(plans, fake)
    assert "soat mos kelmadi" in problems
    assert "kunda oltita emas" in problems


def test_no_plans_is_no_timetable():
    assert build([]) == []
