"""API errors as problem details (RFC 9457).

Every error the API returns has the same JSON shape, served as application/problem+json:

    {"type": "about:blank", "title": "Not Found", "status": 404, "detail": "..."}

"about:blank" means the HTTP status says it all; we have no custom problem types yet.
Validation errors add an "errors" list that describes each invalid field.

One exception: calling an existing endpoint with the wrong HTTP method gets django-ninja's
plain-text 405 (with the standard Allow header). django-ninja builds it before any error
handler runs, and only a programming error can cause it.
"""

import logging
from http import HTTPStatus
from typing import Any

from django.http import Http404, HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ninja import NinjaAPI
from ninja.errors import HttpError, ValidationError

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Base for errors that the API reports to clients as problem details.

    Subclasses set the HTTP status and a detail message that is safe to show to users.
    """

    status: HTTPStatus = HTTPStatus.BAD_REQUEST
    detail: str = "The request could not be processed."


def problem_response(status: HTTPStatus, detail: str, **extensions: Any) -> JsonResponse:
    body = {
        "type": "about:blank",
        "title": status.phrase,
        "status": status.value,
        "detail": detail,
        **extensions,
    }
    return JsonResponse(body, status=status, content_type="application/problem+json")


def handle_domain_error(request: HttpRequest, exc: DomainError) -> JsonResponse:
    return problem_response(exc.status, exc.detail)


def handle_validation_error(request: HttpRequest, exc: ValidationError) -> JsonResponse:
    return problem_response(
        HTTPStatus.UNPROCESSABLE_ENTITY, "The request contains invalid data.", errors=exc.errors
    )


def handle_http_error(request: HttpRequest, exc: HttpError) -> JsonResponse:
    """Errors raised by django-ninja itself: 401 login required, 403 CSRF failed, 429, ..."""
    return problem_response(HTTPStatus(exc.status_code), exc.message)


def handle_not_found(request: HttpRequest, exc: Http404) -> JsonResponse:
    return problem_response(HTTPStatus.NOT_FOUND, "The requested resource was not found.")


def handle_unexpected_error(request: HttpRequest, exc: Exception) -> JsonResponse:
    # Clients only learn that something went wrong; the details go to the log.
    logger.error("Unhandled error in API request", exc_info=exc)
    return problem_response(HTTPStatus.INTERNAL_SERVER_ERROR, "An unexpected error occurred.")


@csrf_exempt  # changes nothing, and an unknown POST should get a 404, not a CSRF error
def api_not_found(request: HttpRequest) -> JsonResponse:
    """URLs under /api/ that match no endpoint; Django itself would answer with an HTML page."""
    return problem_response(HTTPStatus.NOT_FOUND, "There is no API endpoint at this URL.")


def register_problem_handlers(api: NinjaAPI) -> None:
    """Replace django-ninja's default error responses with problem details."""
    # django-ninja's type hints claim a handler may also receive an exception *class*. It never
    # does: every caller passes an exception instance. Hence the ignores.
    api.add_exception_handler(DomainError, handle_domain_error)  # type: ignore[arg-type]
    api.add_exception_handler(ValidationError, handle_validation_error)  # type: ignore[arg-type]
    api.add_exception_handler(HttpError, handle_http_error)  # type: ignore[arg-type]
    api.add_exception_handler(Http404, handle_not_found)  # type: ignore[arg-type]
    api.add_exception_handler(Exception, handle_unexpected_error)  # type: ignore[arg-type]
