from .base import *  # noqa: F401,F403
from .base import CACHES, REDIS_URL

DEBUG = False
ALLOWED_HOSTS = ["*", "testserver"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Tests use a dedicated Redis database so they never touch dev/prod keyspaces.
_base, _, _db = REDIS_URL.rpartition("/")
CACHES["default"]["LOCATION"] = f"{_base}/15" if _db.isdigit() else REDIS_URL
CACHES["default"]["KEY_PREFIX"] = "test"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# The manifest storage would require a collectstatic run before every test.
from .base import STORAGES  # noqa: E402

STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}

# Throttling is exercised by dedicated tests that override these rates.
from .base import REST_FRAMEWORK  # noqa: E402

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    key: "1000/hour" for key in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
}
