"""Provider-agnostic SMS abstraction.

Swapping in a real gateway later means adding one subclass and one entry in
``registry.PROVIDERS`` — no call site changes.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass


class SMSSendError(Exception):
    pass


@dataclass(frozen=True)
class SMSMessage:
    to: str
    text: str
    # Free-form tag used for logging/metrics ("otp", "notification", ...).
    purpose: str = "generic"


class SMSProvider(abc.ABC):
    name: str = "base"
    #: False for the development providers, which print or discard the message.
    #: Callers use it to tell the operator that nothing actually left the
    #: server — an OTP that silently goes nowhere is an unexplainable dead end.
    delivers: bool = True

    def __init__(self, **options):
        self.options = options

    @abc.abstractmethod
    def send(self, message: SMSMessage) -> str:
        """Send the message and return a provider message id."""
