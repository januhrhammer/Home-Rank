"""Settings for local development (the default for manage.py)."""

from config.logging_config import build_logging

from .base import *
from .base import env

DEBUG = True

LOGGING = build_logging(json=False)

# Not a secret: only ever used on a developer's machine. prod.py requires a real key.
SECRET_KEY = "django-insecure-local-development-only"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# The local Postgres container. Set DATABASE_URL in .env to use a different database.
DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://homerank:homerank@localhost:5432/homerank"
    ),
}
