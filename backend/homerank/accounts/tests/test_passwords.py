import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from pytest_django import Settings

from config.settings import base
from homerank.accounts.models import User


def test_passwords_are_hashed_with_argon2id(settings: Settings) -> None:
    # The test settings use a fast hasher; switch to the real one for this test.
    settings.PASSWORD_HASHERS = base.PASSWORD_HASHERS

    hashed = make_password("correct horse battery staple")

    assert hashed.startswith("argon2$argon2id$")
    assert check_password("correct horse battery staple", hashed)


@pytest.mark.parametrize(
    ("password", "username"),
    [
        pytest.param("chess-openings", "alice", id="shorter than 15 characters"),
        pytest.param("1q2w3e4r5t6y7u8i9o0p", "alice", id="common password"),
        pytest.param("847295038461739", "alice", id="only digits"),
        pytest.param("chessmaster99!!", "chessmaster99", id="too similar to the username"),
    ],
)
def test_weak_passwords_are_rejected(password: str, username: str) -> None:
    with pytest.raises(ValidationError):
        validate_password(password, user=User(username=username))


def test_long_passphrase_is_accepted() -> None:
    # Raises ValidationError if any validator rejects the password.
    validate_password("correct horse battery staple", user=User(username="alice"))
