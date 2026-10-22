from http import HTTPStatus

import structlog
from django.contrib.auth import authenticate, login, logout
from django.contrib.sessions.models import Session
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone
from procrastinate.contrib.django import app

from homerank.accounts.models import User
from homerank.chesslib.players import normalise_name
from homerank.core.errors import DomainError

logger = structlog.get_logger(__name__)


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


def clear_expired_sessions() -> None:
    """Delete expired sessions. Django keeps them in the database forever otherwise."""
    deleted, _ = Session.objects.filter(expire_date__lt=timezone.now()).delete()
    logger.info("Deleted expired sessions", count=deleted)


def set_player_names(*, user: User, names: list[str]) -> User:
    """Save the names the user plays under, and find their side in all their games again.

    Spaces are trimmed and collapsed; empty names and spelling variants of an earlier name
    ("uhrhammer, jan" after "Uhrhammer, Jan") are left out.
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for typed in names:
        name = " ".join(typed.split())
        key = normalise_name(name)
        if key and key not in seen:
            seen.add(key)
            cleaned.append(name)
    if cleaned == user.player_names:
        return user
    with transaction.atomic():
        user.player_names = cleaned
        user.save(update_fields=["player_names"])
        # Queued in this transaction, so it runs if and only if the names were saved. Named,
        # not imported: the games app builds on accounts, not the other way round. The lock is
        # the one the user's imports take (games.services.start_import): an import running now
        # would store sides with the old names, so the recompute waits for it.
        task = app.configure_task(
            "homerank.games.tasks.recompute_user_colors", lock=f"user-{user.pk}"
        )
        task.defer(user_id=user.pk)
    logger.info("Player names changed", user_id=user.pk, count=len(cleaned))
    return user
