from django.apps import AppConfig


class TelegramConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.telegram"
    label = "telegram_link"
    verbose_name = "Telegram"
