"""Settings shared by every environment.

dev.py, test.py and prod.py import everything from here and add what differs between them:
debug mode, the secret key, allowed hosts and the database. Environment variables are read
here and in those modules only, through config/env.py; the rest of the code uses
django.conf.settings.
"""

from datetime import timedelta
from pathlib import Path

import environ

from config import env
from config.logging_config import build_logging

# backend/, the directory that contains manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# For local development, variables can live in a .env file at the repository root; this copies
# them into the environment. In Docker there is no such file.
environ.Env.read_env(BASE_DIR.parent / ".env")

DEBUG = False

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Serves the API docs' JavaScript ourselves; without it the docs page loads it from a CDN.
    "ninja",
    "axes",
    # Job queue in PostgreSQL; finds tasks in each app's tasks.py. See docs/adr/0004-job-queue.md.
    "procrastinate.contrib.django",
    "homerank.accounts",
]

AUTH_USER_MODEL = "accounts.User"

# Argon2id is memory-hard, which makes stolen password hashes far more expensive to crack on
# GPUs than with Django's default PBKDF2. See docs/adr/0003-user-accounts.md.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        # NIST SP 800-63B-4 requires 15 characters when the password is the only login factor.
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 15},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    # First, so blocked attempts are rejected before any password hash is computed.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Login rate limiting with django-axes; covers both the API login and the admin login.
# Count failures per IP address, so trying one password on many usernames is caught too.
# The limit is generous because a household shares one IP address.
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_FAILURE_LIMIT = 10
# Axes' default (None) keeps a block until an admin lifts it.
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
# Don't keep a permanent record, with IP addresses, of every successful login.
AXES_DISABLE_ACCESS_LOG = True
AXES_LOCKOUT_CALLABLE = "homerank.accounts.lockout.lockout_response"
AXES_CLIENT_IP_CALLABLE = "homerank.accounts.lockout.client_ip"

# Whether a reverse proxy's X-Forwarded-* headers can be believed; prod.py reads it from the
# environment. Without a proxy, any visitor could send these headers themselves.
TRUST_PROXY_HEADERS = False

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Last: replaces the response of a blocked login attempt (see AXES_* below).
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Only the Django admin renders HTML templates; the app's UI is a separate frontend.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

STATIC_URL = "static/"
# Where `manage.py collectstatic` gathers static files (the admin's CSS and JavaScript).
STATIC_ROOT = BASE_DIR / "staticfiles"

# The built frontend (index.html and assets/), which Django serves in production.
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "dist"

# Where the Django admin lives. A less obvious path keeps bots probing /admin/ away.
ADMIN_URL = env.string("ADMIN_URL", default="admin/")

LANGUAGE_CODE = "en-us"
USE_I18N = True

# Store and process all timestamps in UTC; the frontend converts to the user's local time.
TIME_ZONE = "UTC"
USE_TZ = True

# One JSON object per log line, for log tools; dev.py and test.py switch to readable lines.
LOGGING = build_logging(json=True)
