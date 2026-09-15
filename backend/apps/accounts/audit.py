"""Audit entries for the things roles change.

The project already has a trail (:mod:`apps.audit`); this only adds the shapes
that are specific to access — who was given which role, who took one away, who
switched hats, and who put a curator in front of which class. Each entry keeps
the *old* and *new* role sets so the question an audit is actually asked — "how
did this person end up able to do that?" — is answerable from one row.
"""
from __future__ import annotations

from apps.audit.constants import AuditAction
from apps.audit.services import log_action


def log_role_change(*, actor, target, old_roles, new_roles, request=None) -> None:
    """Record a change to the set of roles on one account.

    Granting and revoking are separate actions on purpose: a security review
    filters for ``ROLE_ASSIGNED`` and wants the grants, not every edit that
    happened to touch the role list.
    """
    before = sorted(set(old_roles or ()))
    after = sorted(set(new_roles or ()))
    if before == after:
        return

    granted = sorted(set(after) - set(before))
    revoked = sorted(set(before) - set(after))
    payload = {
        "target": getattr(target, "username", ""),
        "old_roles": before,
        "new_roles": after,
    }

    if granted:
        log_action(
            AuditAction.ROLE_ASSIGNED,
            user=actor,
            entity=target,
            request=request,
            old_data={"roles": before},
            new_data={"roles": after, "granted": granted},
            metadata=payload,
        )
    if revoked:
        log_action(
            AuditAction.ROLE_REVOKED,
            user=actor,
            entity=target,
            request=request,
            old_data={"roles": before},
            new_data={"roles": after, "revoked": revoked},
            metadata=payload,
        )


def log_active_role_switch(*, user, old_role: str, new_role: str, request=None) -> None:
    """Somebody changed which of their roles they are working through."""
    if old_role == new_role:
        return
    log_action(
        AuditAction.ACTIVE_ROLE_SWITCH,
        user=user,
        entity=user,
        request=request,
        old_data={"active_role": old_role},
        new_data={"active_role": new_role},
    )


def log_curator_change(action, *, actor, target, class_group, request=None) -> None:
    """A curator was put in front of a class group, or taken off one."""
    log_action(
        action,
        user=actor,
        entity=target,
        request=request,
        metadata={
            "curator": getattr(target, "username", ""),
            "class_group": getattr(class_group, "display_name", str(class_group)),
            "class_group_id": str(getattr(class_group, "id", "")),
        },
    )
