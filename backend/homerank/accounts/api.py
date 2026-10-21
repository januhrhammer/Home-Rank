from http import HTTPStatus

from django.http import HttpRequest
from django.views.decorators.csrf import ensure_csrf_cookie
from ninja import Router, Status
from ninja.decorators import decorate_view

from homerank.accounts.auth import AuthenticatedRequest
from homerank.accounts.models import User
from homerank.accounts.schemas import UserOut

router = Router(tags=["auth"])


@router.get("/csrf", auth=None, response={HTTPStatus.NO_CONTENT: None})
@decorate_view(ensure_csrf_cookie)
def csrf(request: HttpRequest) -> Status[None]:
    """Set the CSRF cookie.

    The frontend calls this before its first state-changing request (such as login) and sends
    the cookie's value back in the X-CSRFToken header.
    """
    return Status(HTTPStatus.NO_CONTENT, None)


@router.get("/me", response=UserOut)
def me(request: AuthenticatedRequest) -> User:
    """The logged-in user."""
    return request.user
