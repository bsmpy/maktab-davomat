from aiogram import Router

from . import attendance, auth, children, fallback, notifications, start


def build_router() -> Router:
    """Order matters: the fallback router must be registered last.

    ``auth`` sits high up because its handlers are state-scoped — they only
    fire while somebody is midway through signing in.
    """
    router = Router(name="root")
    router.include_router(start.router)
    router.include_router(auth.router)
    router.include_router(attendance.router)
    router.include_router(children.router)
    router.include_router(notifications.router)
    router.include_router(fallback.router)
    return router


__all__ = ["build_router"]
