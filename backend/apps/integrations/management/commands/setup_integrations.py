"""Create the four integration rows and register the periodic tasks."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.integrations.constants import IntegrationKind
from apps.integrations.models import Integration
from apps.integrations.services.registry import DEFAULT_CONFIG


class Command(BaseCommand):
    help = "Integratsiya yozuvlarini va davriy vazifalarni yaratadi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-beat",
            action="store_true",
            help="django-celery-beat davriy vazifalarini ham yaratadi.",
        )

    def handle(self, *args, **options):
        for kind in IntegrationKind:
            integration, created = Integration.objects.get_or_create(
                kind=kind.value,
                school=None,
                defaults={"config": dict(DEFAULT_CONFIG.get(kind.value, {}))},
            )
            if not created:
                # Backfill newly introduced defaults without touching overrides.
                merged = {**DEFAULT_CONFIG.get(kind.value, {}), **(integration.config or {})}
                if merged != integration.config:
                    integration.config = merged
                    integration.save(update_fields=["config", "updated_at"])
            self.stdout.write(
                f"  {'yaratildi' if created else 'mavjud'}: {integration.get_kind_display()}"
            )

        if options["with_beat"]:
            self._setup_beat()

        self.stdout.write(self.style.SUCCESS("Integratsiyalar tayyor."))

    def _setup_beat(self):
        from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

        every_5_min, _ = IntervalSchedule.objects.get_or_create(
            every=5, period=IntervalSchedule.MINUTES
        )
        nightly, _ = CrontabSchedule.objects.get_or_create(
            minute="30", hour="20", day_of_week="*", day_of_month="*", month_of_year="*"
        )
        daily_early, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="3", day_of_week="*", day_of_month="*", month_of_year="*"
        )

        tasks = [
            (
                "terminals: poll events",
                "apps.integrations.tasks.poll_all_terminals",
                {"interval": every_5_min},
                {},
            ),
            (
                "terminals: close school day",
                "apps.integrations.tasks.close_school_day",
                {"crontab": nightly},
                {},
            ),
            (
                "terminals: sync clocks",
                "apps.integrations.tasks.sync_terminal_clocks",
                {"crontab": daily_early},
                {},
            ),
            (
                "attendance: generate upcoming lessons",
                "apps.notifications.tasks.generate_upcoming_lessons",
                {"crontab": daily_early},
                {},
            ),
            (
                "telegram: purge expired link tokens",
                "apps.notifications.tasks.purge_expired_link_tokens",
                {"crontab": daily_early},
                {},
            ),
        ]

        for name, task, schedule, kwargs in tasks:
            PeriodicTask.objects.update_or_create(
                name=name,
                defaults={"task": task, "kwargs": json.dumps(kwargs), "enabled": True, **schedule},
            )
            self.stdout.write(f"  beat: {name}")
