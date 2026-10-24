"""Cross-origin isolation, so the browser lets live analysis use several threads (ADR 0018).

Stockfish in the browser shares memory between its threads (SharedArrayBuffer), which browsers
only allow on cross-origin isolated pages: those sent with Cross-Origin-Opener-Policy:
same-origin (Django's SecurityMiddleware does that by default) and Cross-Origin-Embedder-Policy:
require-corp, added here. Home-Rank loads nothing from other sites, so the second header blocks
nothing.
"""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponseBase

HEADER = "Cross-Origin-Embedder-Policy"
VALUE = "require-corp"


def cross_origin_isolation(
    get_response: Callable[[HttpRequest], HttpResponseBase],
) -> Callable[[HttpRequest], HttpResponseBase]:
    """Middleware: the header on every response Django makes."""

    def middleware(request: HttpRequest) -> HttpResponseBase:
        response = get_response(request)
        response.headers.setdefault(HEADER, VALUE)
        return response

    return middleware


def add_static_headers(headers: dict[str, str], path: str, url: str) -> None:
    """WhiteNoise's hook (WHITENOISE_ADD_HEADERS_FUNCTION): the header on the static files it
    serves before any middleware runs, the engine's scripts among them."""
    headers[HEADER] = VALUE
