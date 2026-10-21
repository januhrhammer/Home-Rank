import pytest
from django.contrib.auth import get_user_model

from homerank.accounts.models import User


def test_django_uses_our_user_model() -> None:
    assert get_user_model() is User


@pytest.mark.django_db
def test_email_is_optional() -> None:
    user = User.objects.create_user(username="alice", password="correct-horse-battery")

    user.full_clean()  # raises ValidationError if a required field is missing

    assert user.email == ""
