from aiogram.fsm.state import State, StatesGroup


class LinkStates(StatesGroup):
    """Waiting for the 6-digit code from the web cabinet (the older path)."""

    waiting_for_code = State()


class AuthStates(StatesGroup):
    """Signing in by sharing a contact.

    ``waiting_for_contact`` — the greeting is on screen, the share button is
    waiting. ``waiting_for_code`` — the number matched and a four-digit code is
    on its way; the phone is kept in the FSM so the code can be checked against
    the same number that asked for it.
    """

    waiting_for_contact = State()
    waiting_for_code = State()


class PhoneChangeStates(StatesGroup):
    """Replacing the number on file, confirmed the same way."""

    waiting_for_contact = State()
    waiting_for_code = State()
