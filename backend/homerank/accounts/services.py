from http import HTTPStatus

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest

from homerank.accounts.models import User
from homerank.core.errors import DomainError


class InvalidCredentialsError(DomainError):
    # Deliberately the same for an unknown username, a wrong password and an inactive account,
    # so the login form can't be used to find out which usernames exist.
    status = HTTPStatus.UNAUTHORIZED
    detail = "Invalid username or password."


def log_in(*, request: HttpRequest, username: str, password: str) -> User:
    """Check the credentials and start a session for the user.

    Django's login() also issues a new session ID and a new CSRF token, so a session ID planted
    before login (session fixation) is useless afterwards.
    """
    user = authenticate(request, username=username, password=password)
    if not isinstance(user, User):  # None when the credentials are wrong
        raise InvalidCredentialsError
    login(request, user)
    return user


def log_out(*, request: HttpRequest) -> None:
    logout(request)
