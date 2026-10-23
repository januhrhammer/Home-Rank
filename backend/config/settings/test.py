"""Settings for the test suite.

Built on base.py, not dev.py, so development-only tools never leak into tests.
"""

from config import env
from config.logging_config import build_logging

from .base import *
from .base import BASE_DIR

SECRET_KEY = "django-insecure-tests-only"

LOGGING = build_logging(json=False)

# Argon2 is deliberately expensive and tests create many users. Test passwords are fake,
# so a fast, insecure hasher is fine here.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Same local Postgres as development; CI points DATABASE_URL at its own database service.
# Tests run in a separate, throwaway test_* database, so development data is never touched.
DATABASES = {
    "default": env.database(
        "DATABASE_URL", default="postgres://homerank:homerank@localhost:5432/homerank"
    ),
}

# Downloaded by `just stockfish`.
STOCKFISH_PATH = env.string(
    "STOCKFISH_PATH", default=str(BASE_DIR.parent / ".tools" / "stockfish" / "stockfish")
)
MAIA_PATH = env.string(
    "MAIA_PATH", default=str(BASE_DIR.parent / ".tools" / "maia" / "maia3-5m.onnx")
)
