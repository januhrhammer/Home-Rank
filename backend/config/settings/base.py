"""Settings shared by every environment.

dev.py, test.py and prod.py import everything from here and add what differs between them:
debug mode, the secret key, allowed hosts and the database. Environment variables are read
here and in those modules only; the rest of the code uses django.conf.settings.
"""

from pathlib import Path

import environ

# backend/, the directory that contains manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# For local development, variables can live in a .env file at the repository root.
# In Docker there is no such file and the variables come from the container environment.
env.read_env(BASE_DIR.parent / ".env")

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

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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

# Where the Django admin lives. A less obvious path keeps bots probing /admin/ away.
ADMIN_URL = env.str("ADMIN_URL", default="admin/")

LANGUAGE_CODE = "en-us"
USE_I18N = True

# Store and process all timestamps in UTC; the frontend converts to the user's local time.
TIME_ZONE = "UTC"
USE_TZ = True
