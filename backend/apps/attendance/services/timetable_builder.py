"""Построение недельного расписания без накладок по учителям.

Задача решается в два шага, и второй шаг гарантированно решаем, если первый
сделан правильно.

**Шаг 1 — разложить часы по дням.** У группы 6 уроков в день, у предмета —
своё число часов в неделю. Надо разнести часы так, чтобы каждый день у группы
было ровно шесть уроков, один предмет не стоял в один день больше двух раз, и
ни у одного учителя не набралось больше шести уроков за одну смену одного дня.
Последнее — не удобство, а условие разрешимости второго шага.

**Шаг 2 — разложить дневные уроки по звонкам.** Внутри одной смены одного дня
это в точности раскраска рёбер двудольного мультиграфа: с одной стороны
группы, с другой учителя, каждое ребро — урок, цвет — номер звонка. По теореме
Кёнига такой граф красится в Δ цветов, где Δ — максимальная степень вершины.
Если после первого шага и у групп, и у учителей степень не больше шести, то
шести звонков достаточно **всегда** — расписание не «почти получилось», оно
строится гарантированно.

Модуль ничего не знает про базу: на входе план, на выходе расстановка.
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field

#: Уроков в день у каждой группы — и, значит, цветов в раскраске.
SLOTS_PER_DAY = 6
#: Один и тот же предмет дважды в день — предел; трижды это уже не расписание.
MAX_SAME_SUBJECT_PER_DAY = 2


class TimetableError(RuntimeError):
    """Расписание при заданных ограничениях не сходится."""


@dataclass(frozen=True)
class Course:
    """Один предмет одной группы: кто ведёт и сколько часов в неделю."""

    subject: str
    teacher: str
    hours: int


@dataclass(frozen=True)
class GroupPlan:
    """Учебная неделя одной группы."""

    group: str
    shift: int
    days: tuple[int, ...]
    courses: tuple[Course, ...]

    @property
    def total_hours(self) -> int:
        return sum(course.hours for course in self.courses)


@dataclass(frozen=True)
class _Edge:
    """Один урок как ребро «группа — учитель».

    ``index`` нужен не для порядка, а для различимости: у группы один предмет
    может стоять в день дважды, и тогда два урока — это два ребра с одинаковыми
    концами. Без собственного лица переворот α/β-цепочки принимал их за одно
    ребро и терял час.
    """

    group: str
    teacher: str
    subject: str
    index: int


@dataclass(frozen=True)
class Placement:
    group: str
    weekday: int
    slot: int
    subject: str
    teacher: str


@dataclass
class _DayGrid:
    """Что у группы стоит в каждый день — до раскладки по звонкам."""

    by_day: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))

    def count(self, day: int, subject: str) -> int:
        return self.by_day[day].count(subject)


# --------------------------------------------------------------------------- #
# Шаг 1: часы по дням
# --------------------------------------------------------------------------- #
def _spread_over_days(plan: GroupPlan, rng: random.Random) -> _DayGrid:
    """Разложить часы группы по дням: ровно шесть уроков в каждый.

    Каждый час кладётся в наименее загруженный день, который ещё не набрал шести
    уроков и где этого предмета меньше двух. Так как всего часов ровно
    ``6 × дней``, а день не может взять больше шести, все дни заполняются
    полностью.
    """
    grid = _DayGrid()
    load = dict.fromkeys(plan.days, 0)

    # Сначала «тяжёлые» предметы: им нужнее свободные дни.
    courses = sorted(plan.courses, key=lambda c: (-c.hours, c.subject))
    for course in courses:
        for _ in range(course.hours):
            candidates = [
                day for day in plan.days
                if load[day] < SLOTS_PER_DAY
                and grid.count(day, course.subject) < MAX_SAME_SUBJECT_PER_DAY
            ]
            if not candidates:
                raise TimetableError(
                    f"{plan.group}: {course.subject} ({course.hours} soat) "
                    f"{len(plan.days)} kunga sig'maydi"
                )
            # Меньше всего уроков; при равенстве — где этого предмета ещё нет.
            day = min(
                candidates,
                key=lambda d: (load[d], grid.count(d, course.subject), rng.random()),
            )
            grid.by_day[day].append(course.subject)
            load[day] += 1

    for day in plan.days:
        if load[day] != SLOTS_PER_DAY:
            raise TimetableError(f"{plan.group}: {day}-kunda {load[day]} dars")
    return grid


def _teacher_day_load(
    grids: dict[str, _DayGrid], plans: dict[str, GroupPlan], owner: dict
) -> dict[tuple[str, int, int], int]:
    """Сколько уроков у учителя в каждой смене каждого дня."""
    load: dict[tuple[str, int, int], int] = defaultdict(int)
    for group, grid in grids.items():
        shift = plans[group].shift
        for day, subjects in grid.by_day.items():
            for subject in subjects:
                load[(owner[(group, subject)], shift, day)] += 1
    return load


def _relieve_teachers(
    grids: dict[str, _DayGrid],
    plans: dict[str, GroupPlan],
    owner: dict,
    rng: random.Random,
    rounds: int = 4000,
) -> None:
    """Убрать у учителей седьмой урок в смене, обменивая часы между днями.

    Перегруз возникает потому, что группы раскладывали свои часы независимо
    друг от друга. Лечится обменом: урок перегруженного учителя уезжает в день,
    где у него есть место, а навстречу приезжает урок, чей учитель в исходном
    дне свободен. Так сумма по дню у группы остаётся равной шести.
    """
    load = _teacher_day_load(grids, plans, owner)

    for _ in range(rounds):
        over = [key for key, value in load.items() if value > SLOTS_PER_DAY]
        if not over:
            return
        teacher, shift, day = rng.choice(over)

        # Кто в этот день даёт этому учителю урок.
        donors = [
            (group, subject)
            for group, grid in grids.items()
            if plans[group].shift == shift
            for subject in set(grid.by_day[day])
            if owner[(group, subject)] == teacher
        ]
        rng.shuffle(donors)

        for group, subject in donors:
            grid = grids[group]
            other_days = [d for d in plans[group].days if d != day]
            rng.shuffle(other_days)
            moved = False
            for target in other_days:
                if load[(teacher, shift, target)] >= SLOTS_PER_DAY:
                    continue
                if grid.count(target, subject) >= MAX_SAME_SUBJECT_PER_DAY:
                    continue
                # Навстречу — предмет, чей учитель свободен в исходном дне.
                for swap in sorted(set(grid.by_day[target]), key=lambda _: rng.random()):
                    if swap == subject:
                        continue
                    swap_teacher = owner[(group, swap)]
                    if load[(swap_teacher, shift, day)] >= SLOTS_PER_DAY:
                        continue
                    if grid.count(day, swap) >= MAX_SAME_SUBJECT_PER_DAY:
                        continue

                    grid.by_day[day].remove(subject)
                    grid.by_day[target].append(subject)
                    grid.by_day[target].remove(swap)
                    grid.by_day[day].append(swap)
                    load[(teacher, shift, day)] -= 1
                    load[(teacher, shift, target)] += 1
                    load[(swap_teacher, shift, target)] -= 1
                    load[(swap_teacher, shift, day)] += 1
                    moved = True
                    break
                if moved:
                    break
            if moved:
                break

    remaining = {key: value for key, value in load.items() if value > SLOTS_PER_DAY}
    raise TimetableError(f"Yuklamani tenglashtirib bo'lmadi: {remaining}")


# --------------------------------------------------------------------------- #
# Шаг 2: раскраска рёбер — уроки по звонкам
# --------------------------------------------------------------------------- #
def _colour_day(edges: list[_Edge]) -> dict[int, list[_Edge]]:
    """Разложить уроки одного дня одной смены по шести звонкам.

    ``edges`` — уроки этого дня. Возвращает ``{звонок: [уроки]}``.

    Алгоритм Кёнига: для каждого урока ищем звонок, свободный и у группы, и у
    учителя. Если общего нет, берём α, свободный у группы, и β, свободный у
    учителя, и переворачиваем α/β-цепочку, идущую от учителя. Цепочка не может
    прийти в группу — граф двудольный, — поэтому после переворота α освобождается
    у учителя, остаётся свободным у группы, и урок встаёт на α.
    """
    at_group: dict[str, dict[int, _Edge]] = defaultdict(dict)
    at_teacher: dict[str, dict[int, _Edge]] = defaultdict(dict)
    slots = range(1, SLOTS_PER_DAY + 1)

    def free(table: dict[int, tuple]) -> list[int]:
        return [slot for slot in slots if slot not in table]

    def flip(teacher: str, alpha: int, beta: int) -> None:
        """Перевернуть α/β-цепочку, идущую от учителя.

        Цепочка сначала собирается целиком и только потом перекрашивается:
        если менять цвета на ходу, следующий шаг находит то же ребро, которое
        только что перекрасил, и обход уходит не туда. Каждое ребро меняет цвет
        сразу на двух концах — иначе у группы и у учителя остаются разные
        представления об одном и том же уроке.
        """
        path: list[tuple[_Edge, int]] = []
        node, on_teacher, colour = teacher, True, alpha
        while True:
            table = at_teacher[node] if on_teacher else at_group[node]
            edge = table.get(colour)
            if edge is None:
                break
            path.append((edge, colour))
            node = edge.group if on_teacher else edge.teacher
            on_teacher = not on_teacher
            colour = beta if colour == alpha else alpha

        # Сначала снять всю цепочку, потом разложить заново. Если делать это по
        # одному ребру, соседнее ребро цепочки ещё сидит на цвете, который мы
        # как раз занимаем, и один из двух уроков теряется.
        for edge, old_colour in path:
            del at_group[edge.group][old_colour]
            del at_teacher[edge.teacher][old_colour]
        for edge, old_colour in path:
            new_colour = beta if old_colour == alpha else alpha
            at_group[edge.group][new_colour] = edge
            at_teacher[edge.teacher][new_colour] = edge

    for edge in edges:
        group, teacher = edge.group, edge.teacher
        free_group, free_teacher = free(at_group[group]), free(at_teacher[teacher])
        if not free_group or not free_teacher:
            raise TimetableError(f"{group}/{teacher}: kunda oltidan ortiq dars")

        common = sorted(set(free_group) & set(free_teacher))
        if common:
            slot = common[0]
        else:
            # α свободен у группы, β у учителя, общего нет — значит α занят у
            # учителя, и цепочка от него существует. После переворота α
            # освобождается у учителя и остаётся свободным у группы: цепочка
            # не может прийти в группу, потому что в каждую группу на ней
            # входит именно α-ребро, а у этой группы α свободен.
            alpha, beta = free_group[0], free_teacher[0]
            flip(teacher, alpha, beta)
            slot = alpha

        # Молча затереть урок нельзя: это потерянный час в чьём-то плане.
        if slot in at_group[group] or slot in at_teacher[teacher]:
            raise TimetableError(
                f"{group}/{teacher}: {slot}-qo'ng'iroq band bo'lib qoldi"
            )
        at_group[group][slot] = edge
        at_teacher[teacher][slot] = edge

    out: dict[int, list[_Edge]] = defaultdict(list)
    placed = 0
    for table in at_group.values():
        for slot, edge in table.items():
            out[slot].append(edge)
            placed += 1
    if placed != len(edges):
        raise TimetableError(f"{len(edges)} darsdan {placed} tasi joylashdi")
    return out


# --------------------------------------------------------------------------- #
# Всё вместе
# --------------------------------------------------------------------------- #
def build(plans: list[GroupPlan], *, seed: int = 0, attempts: int = 12) -> list[Placement]:
    """Собрать расписание. Бросает :class:`TimetableError`, если не сошлось."""
    if not plans:
        return []
    by_group = {plan.group: plan for plan in plans}
    owner = {
        (plan.group, course.subject): course.teacher
        for plan in plans for course in plan.courses
    }

    last: Exception | None = None
    for attempt in range(attempts):
        rng = random.Random(seed + attempt)
        try:
            grids = {plan.group: _spread_over_days(plan, rng) for plan in plans}
            _relieve_teachers(grids, by_group, owner, rng)

            placements: list[Placement] = []
            # Дни и смены независимы: накладка возможна только внутри одной
            # смены одного дня, потому что в разных сменах разные часы.
            days = sorted({day for plan in plans for day in plan.days})
            shifts = sorted({plan.shift for plan in plans})
            for day in days:
                for shift in shifts:
                    edges = [
                        _Edge(group, owner[(group, subject)], subject, index)
                        for group, grid in grids.items()
                        if by_group[group].shift == shift and day in by_group[group].days
                        for index, subject in enumerate(grid.by_day[day])
                    ]
                    if not edges:
                        continue
                    for slot, lessons in _colour_day(edges).items():
                        for edge in lessons:
                            placements.append(Placement(
                                edge.group, day, slot, edge.subject, edge.teacher
                            ))
            return placements
        except TimetableError as error:      # попробуем с другого случайного старта
            last = error
    raise TimetableError(f"{attempts} urinishdan keyin ham sig'madi: {last}")


# --------------------------------------------------------------------------- #
# Проверка
# --------------------------------------------------------------------------- #
def audit(plans: list[GroupPlan], placements: list[Placement]) -> dict:
    """Пересчитать готовое расписание и вернуть найденные нарушения.

    Проверяется не то, что алгоритм думает, а то, что получилось: часы по плану,
    шесть уроков в день, занятость учителя и повторы предмета внутри дня.
    """
    by_group = {plan.group: plan for plan in plans}
    problems: dict[str, list] = defaultdict(list)

    seen_slot: dict[tuple, tuple] = {}
    busy: dict[tuple, tuple] = {}
    hours: dict[tuple, int] = defaultdict(int)
    per_day: dict[tuple, int] = defaultdict(int)
    same: dict[tuple, int] = defaultdict(int)

    for row in placements:
        plan = by_group[row.group]
        key = (row.group, row.weekday, row.slot)
        if key in seen_slot:
            problems["ikki dars bir vaqtda"].append((key, seen_slot[key], row.subject))
        seen_slot[key] = row.subject

        # Накладка учителя считается по смене: в разных сменах разные часы.
        slot_key = (row.teacher, row.weekday, plan.shift, row.slot)
        if slot_key in busy:
            problems["o'qituvchi bandligi"].append((slot_key, busy[slot_key], row.group))
        busy[slot_key] = row.group

        hours[(row.group, row.subject)] += 1
        per_day[(row.group, row.weekday)] += 1
        same[(row.group, row.weekday, row.subject)] += 1

    for plan in plans:
        for course in plan.courses:
            got = hours[(plan.group, course.subject)]
            if got != course.hours:
                problems["soat mos kelmadi"].append(
                    (plan.group, course.subject, course.hours, got)
                )
        for day in plan.days:
            if per_day[(plan.group, day)] != SLOTS_PER_DAY:
                problems["kunda oltita emas"].append(
                    (plan.group, day, per_day[(plan.group, day)])
                )

    for key, count in same.items():
        if count > MAX_SAME_SUBJECT_PER_DAY:
            problems["bir kunda takrorlandi"].append((key, count))

    teacher_day: dict[tuple, int] = defaultdict(int)
    for row in placements:
        teacher_day[(row.teacher, by_group[row.group].shift, row.weekday)] += 1
    overloaded = {k: v for k, v in teacher_day.items() if v > SLOTS_PER_DAY}
    if overloaded:
        problems["smenada oltidan ortiq"].append(overloaded)

    return dict(problems)
