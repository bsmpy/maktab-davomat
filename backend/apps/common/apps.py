from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"

    def ready(self):
        from . import openapi  # noqa: F401  (registers schema extensions)
        from .clock import install

        # A demo clock, if one is configured; a no-op otherwise.
        install()
