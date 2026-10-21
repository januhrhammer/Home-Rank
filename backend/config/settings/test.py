"""Settings for the test suite.

Built on base.py, not dev.py, so development-only tools never leak into tests.
"""

from .base import *
from .base import env

SECRET_KEY = "django-insecure-tests-only"

# Same local Postgres as development; CI points DATABASE_URL at its own database service.
# Tests run in a separate, throwaway test_* database, so development data is never touched.
DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://homerank:homerank@localhost:5432/homerank"
    ),
}
