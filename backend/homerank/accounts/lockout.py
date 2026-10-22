"""How django-axes, which limits failed logins, fits into Home-Rank.

- lockout_response (AXES_LOCKOUT_CALLABLE): what a blocked client gets. Axes' own responses
  don't suit us: plain text for the API, or JSON that any website may read.
- client_ip (AXES_CLIENT_IP_CALLABLE): the address axes counts failed logins by.
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


def client_ip(request: HttpRequest) -> str | None:
    """The visitor's IP address.

    Behind a reverse proxy, REMOTE_ADDR is the proxy's own address, so every visitor would
    share one lockout counter. With TRUST_PROXY_HEADERS, the proxy's X-Forwarded-For is used
    instead: its last entry is the address the proxy saw. Earlier entries come from the visitor
    and could be faked to dodge the lockout.
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for: str = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.rsplit(",", maxsplit=1)[-1].strip()
    remote_addr: str | None = request.META.get("REMOTE_ADDR")
    return remote_addr
