from http import HTTPStatus

from django.http import HttpRequest
from django.views.decorators.csrf import ensure_csrf_cookie
from ninja import Router, Status
from ninja.decorators import decorate_view

from homerank.accounts import services
from homerank.accounts.auth import AuthenticatedRequest, require_csrf_token
from homerank.accounts.models import User
from homerank.accounts.schemas import LoginIn, UserOut

router = Router(tags=["auth"])


@router.get("/csrf", auth=None, response={HTTPStatus.NO_CONTENT: None})
@decorate_view(ensure_csrf_cookie)
def csrf(request: HttpRequest) -> Status[None]:
    """Set the CSRF cookie.

    The frontend calls this before its first state-changing request (such as login) and sends
    the cookie's value back in the X-CSRFToken header.
    """
    return Status(HTTPStatus.NO_CONTENT, None)


@router.post("/login", auth=None, response=UserOut)
def login(request: HttpRequest, credentials: LoginIn) -> User:
    """Log in and start a session. The response sets new session and CSRF cookies."""
    # auth=None, so django-ninja doesn't check CSRF here. Without this check, another website
    # could log your browser into an account of its choosing (login CSRF).
    require_csrf_token(request)
    return services.log_in(
        request=request, username=credentials.username, password=credentials.password
    )


@router.post("/logout", response={HTTPStatus.NO_CONTENT: None})
def logout(request: AuthenticatedRequest) -> Status[None]:
    """End the session."""
    services.log_out(request=request)
    return Status(HTTPStatus.NO_CONTENT, None)


@router.get("/me", response=UserOut)
def me(request: AuthenticatedRequest) -> User:
    """The logged-in user."""
    return request.user
