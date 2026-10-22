"""Serves the built frontend's index.html for every address the frontend handles.

The frontend decides which page to show from the address (React Router), so /login or
/games/42 all get the same index.html. Its assets are served by WhiteNoise (see prod.py).
"""

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

FRONTEND_MISSING = (
    "The frontend hasn't been built. In development, use the Vite dev server on port 5173 "
    "(`just dev`); to build it, run `pnpm build` in frontend/."
)


@require_safe
@never_cache  # so a new release is picked up at once; the assets it loads are cached for good
def frontend(request: HttpRequest) -> HttpResponse:
    try:
        index = (settings.FRONTEND_DIR / "index.html").read_bytes()
    except FileNotFoundError:
        return HttpResponse(FRONTEND_MISSING, status=404, content_type="text/plain")
    return HttpResponse(index, content_type="text/html; charset=utf-8")
