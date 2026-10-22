"""Settings for production (the Docker image).

Everything deployment-specific comes from the environment, with deliberately no defaults:
a missing variable stops Django at startup instead of running with an insecure fallback.
"""

from config import env

from .base import *
from .base import FRONTEND_DIR, MIDDLEWARE

SECRET_KEY = env.string("SECRET_KEY")

# Hostnames this instance answers to, comma-separated, e.g. "chess.example.org".
ALLOWED_HOSTS = env.strings("ALLOWED_HOSTS")

DATABASES = {"default": env.database("DATABASE_URL")}

# WhiteNoise serves static files: the admin's (collected into STATIC_ROOT) and the built
# frontend. Only in production: in development Vite and runserver do this, and WhiteNoise
# warns about folders that don't exist there.
MIDDLEWARE = [
    MIDDLEWARE[0],  # SecurityMiddleware, which WhiteNoise must follow directly
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]
WHITENOISE_ROOT = FRONTEND_DIR
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Adds a content hash to each file name and stores compressed copies.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
# Files with a content hash in their name never change, so browsers may cache them for good:
# Vite's (index-BxkfFJoz.js) and Django's (base.3f2a1c9e8b7d.css). Pattern from WhiteNoise's docs.
WHITENOISE_IMMUTABLE_FILE_TEST = r"^.+[.-][0-9a-zA-Z_-]{8,12}\..+$"
