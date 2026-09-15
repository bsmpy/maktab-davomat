from __future__ import annotations

from functools import cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import SMSProvider
from .eskiz import EskizSMSProvider
from .providers import ConsoleSMSProvider, DummySMSProvider, HTTPSMSProvider

PROVIDERS: dict[str, type[SMSProvider]] = {
    "console": ConsoleSMSProvider,
    "dummy": DummySMSProvider,
    "http": HTTPSMSProvider,
    "eskiz": EskizSMSProvider,
}


@cache
def _build(name: str) -> SMSProvider:
    try:
        provider_class = PROVIDERS[name]
    except KeyError as exc:
        raise ImproperlyConfigured(
            f"Unknown SMS_PROVIDER '{name}'. Available: {', '.join(sorted(PROVIDERS))}"
        ) from exc
    return provider_class(**settings.SMS_PROVIDER_SETTINGS)


def get_sms_provider() -> SMSProvider:
    """Provider chosen in Sozlamalar → Integratsiyalar, else from the env."""
    return _build(_configured_provider_name())


def _configured_provider_name() -> str:
    try:
        from apps.integrations.constants import IntegrationKind
        from apps.integrations.services.registry import get_integration

        integration = get_integration(IntegrationKind.SMS_ESKIZ)
        if integration is not None and integration.is_enabled:
            return "eskiz"
    except Exception:  # pragma: no cover - during migrations the app may not be ready
        pass
    return settings.SMS_PROVIDER
