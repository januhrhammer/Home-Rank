"""What a client gets when django-axes blocks it after too many failed logins.

Configured as AXES_LOCKOUT_CALLABLE. Axes' own responses don't suit us: plain text for the
API, or JSON that any website may read (Access-Control-Allow-Origin: *).
"""

from http import HTTPStatus
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from homerank.core.errors import problem_response


def lockout_response(
    request: HttpRequest, original_response: HttpResponse | None, credentials: Any
) -> HttpResponse:
    minutes = int(settings.AXES_COOLOFF_TIME.total_seconds() // 60)
    detail = f"Too many failed login attempts. Try again in {minutes} minutes."

    if request.path.startswith("/api/"):
        return problem_response(HTTPStatus.TOO_MANY_REQUESTS, detail)
    # The Django admin is used in a browser, so it gets readable text rather than JSON.
    return HttpResponse(detail, status=HTTPStatus.TOO_MANY_REQUESTS, content_type="text/plain")
