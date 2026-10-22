"""Settings for production (the Docker image).

Everything deployment-specific comes from the environment, with deliberately no defaults:
a missing variable stops Django at startup instead of running with an insecure fallback.
"""

from config import env

from .base import *
from .base import FRONTEND_DIR, MIDDLEWARE

SECRET_KEY = env.string("SECRET_KEY")

# Hostnames this instance answers to, comma-separated, e.g. "chess.example.org". localhost is
# always allowed, for the container's own health check (http://localhost/healthz).
ALLOWED_HOSTS = [*env.strings("ALLOWED_HOSTS"), "localhost"]

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

# HTTPS=true: users reach Home-Rank over https:// (usually through a reverse proxy).
# HTTPS=false: plain http:// on a local network. Required, because each setting is wrong for the
# other case: secure cookies are never sent over http, and over the internet http exposes them.
HTTPS = env.boolean("HTTPS")
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
SECURE_SSL_REDIRECT = HTTPS
# Container health checks use plain http from inside; redirecting them would fail them.
SECURE_REDIRECT_EXEMPT = [r"^healthz$", r"^readyz$"]
# Browsers remember to use only HTTPS for a year (HSTS). Not for subdomains, which may run
# other services without HTTPS, and not on the browsers' preload list, which is hard to undo;
# hence the two silenced warnings that recommend both.
SECURE_HSTS_SECONDS = 365 * 24 * 60 * 60 if HTTPS else 0
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]

# Behind a reverse proxy, believe its X-Forwarded-Proto (was the request HTTPS?) and
# X-Forwarded-For (the visitor's address, for login rate limiting). Never without a proxy that
# sets them, or any visitor could fake them.
TRUST_PROXY_HEADERS = env.boolean("TRUST_PROXY_HEADERS", default=False)
if TRUST_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Further origins allowed to submit forms, e.g. "https://chess.example.org" if the proxy can't
# report HTTPS. Usually not needed.
CSRF_TRUSTED_ORIGINS = env.strings("CSRF_TRUSTED_ORIGINS", default=[])
