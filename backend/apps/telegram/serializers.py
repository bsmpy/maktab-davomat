from __future__ import annotations

from rest_framework import serializers


class TelegramProfileSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True, default="")
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    language_code = serializers.CharField(required=False, allow_blank=True, default="uz")


class BotIdentitySerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()


class BotLinkSerializer(BotIdentitySerializer):
    token = serializers.CharField(max_length=128)
    profile = TelegramProfileSerializer(required=False)


class BotActiveChildSerializer(BotIdentitySerializer):
    student = serializers.UUIDField()


class BotAttendanceSerializer(BotIdentitySerializer):
    student = serializers.UUIDField(required=False, allow_null=True, default=None)
    period = serializers.ChoiceField(
        choices=("daily", "weekly", "monthly", "yearly"), default="daily"
    )
    date = serializers.DateField(required=False, allow_null=True, default=None)


class BotNotificationsSerializer(BotIdentitySerializer):
    limit = serializers.IntegerField(min_value=1, max_value=20, default=5)
    only_unread = serializers.BooleanField(default=False)


class BotSettingsSerializer(BotIdentitySerializer):
    notifications_enabled = serializers.BooleanField()


class TelegramLinkStatusSerializer(serializers.Serializer):
    linked = serializers.BooleanField()
    username = serializers.CharField(allow_blank=True)
    notifications_enabled = serializers.BooleanField()
    bot_username = serializers.CharField(allow_blank=True)


class BotContactSerializer(serializers.Serializer):
    """The contact Telegram itself vouched for — never a typed-in number."""

    telegram_id = serializers.IntegerField()
    phone = serializers.CharField(max_length=32)


class BotAuthVerifySerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    phone = serializers.CharField(max_length=32)
    code = serializers.CharField(max_length=8)
    profile = serializers.DictField(required=False, default=dict)
