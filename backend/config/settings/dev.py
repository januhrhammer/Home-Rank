"""Settings for local development (the default for manage.py)."""

from config import env
from config.logging_config import build_logging

from .base import *
from .base import BASE_DIR

DEBUG = True

LOGGING = build_logging(json=False)

# Not a secret: only ever used on a developer's machine. prod.py requires a real key.
SECRET_KEY = "django-insecure-local-development-only"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# The local Postgres container. Set DATABASE_URL in .env to use a different database.
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
