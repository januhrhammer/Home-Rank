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

INSTALLED_APPS: list[str] = []

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

LANGUAGE_CODE = "en-us"
USE_I18N = True

# Store and process all timestamps in UTC; the frontend converts to the user's local time.
TIME_ZONE = "UTC"
USE_TZ = True
