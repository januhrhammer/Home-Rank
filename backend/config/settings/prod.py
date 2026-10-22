"""Settings for production (the Docker image).

Everything deployment-specific comes from the environment, with deliberately no defaults:
a missing variable stops Django at startup instead of running with an insecure fallback.
"""

from config import env

from .base import *

SECRET_KEY = env.string("SECRET_KEY")

# Hostnames this instance answers to, comma-separated, e.g. "chess.example.org".
ALLOWED_HOSTS = env.strings("ALLOWED_HOSTS")

DATABASES = {"default": env.database("DATABASE_URL")}
