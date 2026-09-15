"""Account-related signal receivers (audit trail, and the role table)."""
from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.audit.constants import AuditAction
from apps.audit.services import log_action

from .models import User, UserRole


@receiver(post_save, sender=User)
def ensure_active_role_is_granted(sender, instance: User, **kwargs):
    """Every account holds at least the role it is currently working through.

    Accounts are created from half a dozen places — registration, the staff
    register, the bot, fixtures, ``createsuperuser`` — and each of them sets
    ``role``. Rather than teach all of them about the role table, the table
    follows the column: whatever role an account is saved with is a role it
    genuinely holds. Roles granted *on top* of that are written explicitly by
    ``apps.accounts.rbac``.
    """
    if not instance.role:
        return
    UserRole.objects.get_or_create(user=instance, role=instance.role)


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    log_action(AuditAction.LOGIN, user=user, request=request, entity=user)


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request=None, **kwargs):
    # ``credentials`` is already password-scrubbed by Django.
    log_action(
        AuditAction.LOGIN_FAILED,
        request=request,
        success=False,
        username=str(credentials.get("username", ""))[:50],
        metadata={"reason": "invalid_credentials"},
    )
