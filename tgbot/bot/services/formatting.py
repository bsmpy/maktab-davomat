"""Turns API payloads into the messages users actually read.

All numbers come from the backend verbatim — the bot never recomputes a
percentage or a duration, so Telegram and the web cabinet can never disagree.
"""
from __future__ import annotations

from html import escape

DAY_STATE_LABEL = {
    "PRESENT": "Maktabda bo'ldi",
    "LATE": "Kechikib keldi",
    "ABSENT": "Maktabga kelmadi",
    "EXCUSED": "Sababli qoldirdi",
    "NO_DATA": "Hali kelmagan",
    "NO_LESSONS": "Ma'lumot yo'q",
    "HOLIDAY": "Bayram kuni",
    "WEEKEND": "Dam olish kuni",
    "FUTURE": "Bu kun hali kelmagan",
}

DIRECTION_LABEL = {
    "IN": ("🟢", "Kirdi"),
    "OUT": ("🔴", "Chiqdi"),
    "UNKNOWN": ("⚪", "O'tdi"),
}


def format_duration(minutes: int | None) -> str:
    """``312`` → ``5 soat 12 daqiqa``."""
    minutes = int(minutes or 0)
    if minutes <= 0:
        return "—"
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} daqiqa"
    if not rest:
        return f"{hours} soat"
    return f"{hours} soat {rest} daqiqa"


def student_header(student: dict) -> str:
    icon = "👧" if student.get("gender") == "FEMALE" else "👦"
    return (
        f"{icon} <b>{escape(student['display_name'])}</b>\n"
        f"🏫 {escape(student['class_group'])}"
    )


def _summary_line(summary: dict) -> str:
    return (
        f"Davomat: <b>{summary['rate']}%</b>  "
        f"({summary['days_present']}/{summary['school_days']} kun)"
    )


def format_daily(payload: dict) -> str:
    student = payload["student"]
    report = payload["report"]
    lines = [
        student_header(student),
        "",
        f"📊 <b>Bugungi davomat</b> — {report['date']}",
        "",
    ]

    if not report["was_present"]:
        lines.append(f"<i>{DAY_STATE_LABEL.get(report['state'], 'Maʼlumot yoʻq')}</i>")
        return "\n".join(lines)

    lines.append(f"🟢 Birinchi kirish:  <b>{report['first_in'] or '—'}</b>")
    if report["is_inside"]:
        lines.append("🏫 Hozir maktabda")
    else:
        lines.append(f"🔴 Oxirgi chiqish:   <b>{report['last_out'] or '—'}</b>")
    lines += [
        f"🔁 Kirish/chiqish:   {report['entries']} / {report['exits']}",
        f"⏱ Maktabda:         {format_duration(report['inside_minutes'])}",
    ]
    if report["outside_minutes"]:
        lines.append(f"🚶 Tashqarida:       {format_duration(report['outside_minutes'])}")
    if report["late_minutes"]:
        lines.append(f"🟡 Kechikish:        {report['late_minutes']} daqiqa")

    passes = report.get("passes") or []
    if passes:
        lines += ["", "<b>Turniket yozuvlari</b>"]
        for item in passes:
            emoji, label = DIRECTION_LABEL.get(item["direction"], DIRECTION_LABEL["UNKNOWN"])
            lines.append(f"{emoji} {item['time']} — {label}")
    return "\n".join(lines)


def format_weekly(payload: dict) -> str:
    student = payload["student"]
    report = payload["report"]
    lines = [
        student_header(student),
        "",
        "📅 <b>Haftalik davomat</b>",
        f"<i>{report['start_date']} — {report['end_date']}</i>",
        "",
    ]

    school_days = [day for day in report["days"] if day["is_school_day"]]
    if not school_days:
        lines.append("<i>Bu haftada o‘quv kunlari yo‘q.</i>")
        return "\n".join(lines)

    for day in school_days:
        if not day["was_present"]:
            lines.append(f"{day['weekday_name']:<12} ❌ kelmadi")
            continue
        finish = "hozir" if day["is_inside"] else (day["last_out"] or "—")
        lines.append(
            f"{day['weekday_name']:<12} {day['first_in'] or '—'}–{finish}"
            f"   {format_duration(day['inside_minutes'])}"
        )

    summary = report["summary"]
    lines += [
        "",
        _summary_line(summary),
        f"🔁 {summary['entries']} kirish / {summary['exits']} chiqish   "
        f"🟡 {summary['days_late']} kun kechikdi",
    ]
    return "\n".join(lines)


def format_monthly(payload: dict) -> str:
    student = payload["student"]
    report = payload["report"]
    summary = report["summary"]
    lines = [
        student_header(student),
        "",
        f"📈 <b>Oylik davomat</b> — {report['month_name']} {report['year']}",
        "",
        _summary_line(summary),
        "",
        f"✅ Kelgan kunlar:   {summary['days_present']}",
        f"❌ Kelmagan:        {summary['days_absent']}",
        f"🟡 Kechikkan:       {summary['days_late']}",
        f"⏱ Maktabda jami:   {format_duration(summary['inside_minutes'])}",
        f"📊 Kuniga o'rtacha: {format_duration(summary['avg_inside_minutes'])}",
    ]
    if summary["outside_minutes"]:
        lines.append(f"🚶 Tashqarida:      {format_duration(summary['outside_minutes'])}")
    if summary["late_minutes"]:
        lines.append(f"⏱ Jami kechikish:  {summary['late_minutes']} daqiqa")
    return "\n".join(lines)


def format_yearly(payload: dict) -> str:
    student = payload["student"]
    report = payload["report"]
    lines = [
        student_header(student),
        "",
        f"📆 <b>Yillik davomat</b> — {escape(report['academic_year'])}",
        "",
    ]

    months = [month for month in report["months"] if month["summary"]["school_days"]]
    if not months:
        lines.append("<i>Bu o‘quv yili uchun ma’lumot yo‘q.</i>")
        return "\n".join(lines)

    for month in months:
        lines.append(f"{month['month_name']:<10} {month['summary']['rate']}%")

    summary = report["summary"]
    lines += [
        "",
        f"O'quv kunlari:  {summary['school_days']}",
        f"Kelgan kunlar:  {summary['days_present']}",
        f"Kelmagan:       {summary['days_absent']}",
        f"Kechikkan:      {summary['days_late']}",
        f"Maktabda jami:  {format_duration(summary['inside_minutes'])}",
        "",
        f"<b>Davomat: {summary['rate']}%</b>",
    ]
    return "\n".join(lines)


FORMATTERS = {
    "daily": format_daily,
    "weekly": format_weekly,
    "monthly": format_monthly,
    "yearly": format_yearly,
}


def format_report(payload: dict) -> str:
    return FORMATTERS[payload["period"]](payload)


def format_children(children: list[dict], active_id: str | None) -> str:
    if not children:
        return "Sizga biriktirilgan farzand topilmadi."
    lines = ["👨‍👩‍👧 <b>Farzandlarim</b>", ""]
    for child in children:
        marker = "▶️ " if child["id"] == active_id else "   "
        relation = f" · {child['relation_label']}" if child.get("relation_label") else ""
        lines.append(
            f"{marker}<b>{escape(child['display_name'])}</b> — {escape(child['class_group'])}{relation}"
        )
    lines += ["", "<i>Faol farzandni tanlash uchun quyidagi tugmalardan foydalaning.</i>"]
    return "\n".join(lines)


def format_notifications(payload: dict) -> str:
    results = payload.get("results", [])
    if not results:
        return "🔔 <b>Bildirishnomalar</b>\n\n<i>Yangi bildirishnomalar yo‘q.</i>"

    lines = [
        f"🔔 <b>Bildirishnomalar</b>  ({payload.get('unread_count', 0)} ta o‘qilmagan)",
        "",
    ]
    for item in results:
        mark = "🔵" if not item["is_read"] else "▫️"
        lines.append(f"{mark} <b>{escape(item['title'])}</b>")
        lines.append(f"   {escape(item['message'])}")
        if item.get("student"):
            lines.append(f"   <i>{escape(item['student'])}</i>")
        lines.append("")
    return "\n".join(lines).rstrip()
