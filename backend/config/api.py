"""The Home-Rank API: one NinjaAPI instance, mounted at /api/v1/ in config/urls.py.

Each Django app contributes its endpoints as a Router, added here with api.add_router().
"""

from ninja import NinjaAPI
from ninja.security import django_auth

from homerank.accounts.api import router as accounts_router
from homerank.accounts.api import settings_router
from homerank.core.errors import register_problem_handlers
from homerank.games.api import collections_router, tags_router
from homerank.games.api import router as games_router
from homerank.sync.api import router as sync_router

# Every endpoint requires a logged-in session unless it opts out with auth=None.
# Session auth is also what enforces CSRF: django-ninja exempts all API views from Django's
# CSRF middleware and checks the token only in cookie-based auth such as django_auth.
api = NinjaAPI(title="Home-Rank API", version="1", auth=django_auth)
register_problem_handlers(api)

api.add_router("/auth/", accounts_router)
api.add_router("/settings", settings_router)
api.add_router("/games", games_router)
api.add_router("/collections", collections_router)
api.add_router("/tags", tags_router)
api.add_router("/sync", sync_router)
