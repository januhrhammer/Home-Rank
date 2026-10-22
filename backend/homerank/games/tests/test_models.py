from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from homerank.accounts.admin import HomeRankUserChangeForm
from homerank.accounts.models import User
from homerank.games.models import Collection, Game, GamePosition, Tag

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", password="correct-horse-battery")


@pytest.fixture
def bob() -> User:
    return User.objects.create_user(username="bob", password="correct-horse-battery")


def make_game(user: User, **fields: Any) -> Game:
    values = {
        "source": Game.Source.PGN,
        "pgn": "1. e4 e5 *\n",
        "result": "*",
        "date_pgn": "????.??.??",
        "time_class": "unknown",
        "ply_count": 2,
        "dedup_hash": "a" * 64,
        **fields,
    }
    return Game.objects.create(user=user, **values)


def test_a_game_is_stored_once_per_user(alice: User, bob: User) -> None:
    make_game(alice, dedup_hash="a" * 64)
    make_game(bob, dedup_hash="a" * 64)  # another user may have the same game

    with pytest.raises(IntegrityError), transaction.atomic():
        make_game(alice, dedup_hash="a" * 64)


def test_a_synced_game_is_stored_once_per_user(alice: User, bob: User) -> None:
    lichess = {"source": Game.Source.LICHESS, "source_id": "abcd1234"}
    make_game(alice, dedup_hash="a" * 64, **lichess)
    make_game(bob, dedup_hash="a" * 64, **lichess)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_game(alice, dedup_hash="b" * 64, **lichess)


def test_games_from_pgn_files_have_no_source_id(alice: User) -> None:
    """The source id is only unique where there is one."""
    first = make_game(alice, dedup_hash="a" * 64, source_id="")
    second = make_game(alice, dedup_hash="b" * 64, source_id="")

    assert set(Game.objects.filter(user=alice)) == {first, second}


def test_a_position_is_stored_once_per_ply(alice: User) -> None:
    game = make_game(alice)
    GamePosition.objects.create(game=game, user=alice, ply=0, zobrist=1, move_san="e4")

    with pytest.raises(IntegrityError), transaction.atomic():
        GamePosition.objects.create(game=game, user=alice, ply=0, zobrist=2)


@pytest.mark.parametrize("model", [Collection, Tag])
def test_names_are_unique_per_user_ignoring_case(
    model: type[Collection | Tag], alice: User, bob: User
) -> None:
    model.objects.create(user=alice, name="Openings")
    model.objects.create(user=bob, name="Openings")

    with pytest.raises(IntegrityError), transaction.atomic():
        model.objects.create(user=alice, name="openings")


def test_deleting_a_game_deletes_its_positions_without_loading_them(alice: User) -> None:
    """Imports create millions of positions; deleting them must not load each one first."""
    game = make_game(alice)
    GamePosition.objects.bulk_create(
        GamePosition(game=game, user=alice, ply=ply, zobrist=ply) for ply in range(3)
    )

    with CaptureQueriesContext(connection) as queries:
        game.delete()

    position_queries = [q["sql"] for q in queries if "games_gameposition" in q["sql"]]
    assert len(position_queries) == 1
    assert position_queries[0].startswith('DELETE FROM "games_gameposition"')
    assert not GamePosition.objects.exists()


def test_deleting_a_user_deletes_their_data(alice: User, bob: User) -> None:
    game = make_game(alice)
    GamePosition.objects.create(game=game, user=alice, ply=0, zobrist=1)
    Collection.objects.create(user=alice, name="Openings").games.add(game)
    Tag.objects.create(user=alice, name="won").games.add(game)
    kept = make_game(bob)

    alice.delete()

    assert list(Game.objects.all()) == [kept]
    assert not GamePosition.objects.exists()
    assert not Collection.objects.exists()
    assert not Tag.objects.exists()


def test_player_names_start_empty(alice: User) -> None:
    alice.refresh_from_db()

    assert alice.player_names == []


def test_admin_takes_one_player_name_per_line(alice: User) -> None:
    """Django's default would split "Carlsen, Magnus" at the comma."""
    form = HomeRankUserChangeForm(instance=alice)

    names = form.fields["player_names"].clean("Uhrhammer, Jan\njanuhrhammer")

    assert names == ["Uhrhammer, Jan", "januhrhammer"]
