from django.http import HttpRequest

from homerank.accounts.models import User


class AuthenticatedRequest(HttpRequest):
    """Type of requests to endpoints that require login, which is the API's default.

    For type checking only: django_auth has already rejected anonymous requests by the time an
    endpoint runs, so request.user is always one of our users, never AnonymousUser.
    """

    user: User
