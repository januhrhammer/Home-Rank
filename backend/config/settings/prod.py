"""Settings for production (the Docker image).

Everything deployment-specific comes from the environment, with deliberately no defaults:
a missing variable stops Django at startup instead of running with an insecure fallback.
"""

from .base import *
from .base import env

SECRET_KEY = env.str("SECRET_KEY")

# Hostnames this instance answers to, comma-separated, e.g. "chess.example.org".
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

DATABASES = {"default": env.db("DATABASE_URL")}
