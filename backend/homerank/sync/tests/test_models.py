import pytest
from django.db import IntegrityError, connection, transaction

from homerank.accounts.models import User
from homerank.sync.models import LinkedAccount, SyncRun

pytestmark = pytest.mark.django_db

LICHESS = LinkedAccount.Platform.LICHESS
CHESSCOM = LinkedAccount.Platform.CHESSCOM


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice")


def test_an_account_is_linked_once_per_user_whatever_its_case(alice: User) -> None:
    bob = User.objects.create_user(username="bob")
    LinkedAccount.objects.create(user=alice, platform=LICHESS, username="Alice64")
    LinkedAccount.objects.create(user=alice, platform=CHESSCOM, username="Alice64")
    LinkedAccount.objects.create(user=bob, platform=LICHESS, username="Alice64")

    with pytest.raises(IntegrityError), transaction.atomic():
        LinkedAccount.objects.create(user=alice, platform=LICHESS, username="alice64")


def test_unlinking_an_account_deletes_its_runs(alice: User) -> None:
    account = LinkedAccount.objects.create(user=alice, platform=LICHESS, username="alice64")
    SyncRun.objects.create(account=account)

    account.delete()

    assert not SyncRun.objects.exists()


def test_runs_have_no_index_of_their_own_on_the_account() -> None:
    # The (account, created_at) index serves lookups by account; a second one would only
    # slow down writes.
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, SyncRun._meta.db_table)
    indexes = [c["columns"] for c in constraints.values() if c["index"] and not c["primary_key"]]

    assert indexes == [["account_id", "created_at"]]
