from http import HTTPStatus

from django.http import HttpRequest
from ninja.utils import check_csrf

from homerank.accounts.models import User
from homerank.core.errors import DomainError


class CsrfError(DomainError):
    status = HTTPStatus.FORBIDDEN
    detail = "CSRF check failed. Fetch a token from /api/v1/auth/csrf and send it as X-CSRFToken."


def require_csrf_token(request: HttpRequest) -> None:
    """Run Django's CSRF check by hand, for endpoints open to anonymous users (auth=None).

    django-ninja checks CSRF only as part of session authentication, so an endpoint without
    authentication has no CSRF protection unless it calls this.
    """
    if check_csrf(request) is not None:
        raise CsrfError


class AuthenticatedRequest(HttpRequest):
    """Type of requests to endpoints that require login, which is the API's default.

    For type checking only: django_auth has already rejected anonymous requests by the time an
    endpoint runs, so request.user is always one of our users, never AnonymousUser.
    """

    user: User
