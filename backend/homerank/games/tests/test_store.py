"""Storing games read from PGN, shared by file imports and syncs (services.store_games)."""

import io

import pytest

from homerank.accounts.models import User
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.games.models import Game, GamePosition
from homerank.games.services import NewGame, Stored, new_game, store_games

OPERA_GAME = """\
[White "Morphy, Paul"]
[Black "Duke Karl / Count Isouard"]
[Date "1858.??.??"]
[Result "1-0"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7 8. Nc3 c6
9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6
15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
"""

FOOLS_MATE = """\
[White "bob_b"]
[Black "alice64"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
"""

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", player_names=["alice64"])


def parsed(text: str) -> PgnGame:
    (item,) = read_pgn(io.BytesIO(text.encode()))
    assert isinstance(item, PgnGame)
    return item


def lichess_game(user: User, text: str, game_id: str) -> NewGame:
    return new_game(user, parsed(text), source=Game.Source.LICHESS, source_id=game_id)


def test_a_synced_game_keeps_its_source_and_id(alice: User) -> None:
    stored = store_games(alice, [lichess_game(alice, FOOLS_MATE, "abcd1234")])

    assert stored == Stored(imported=1, duplicate=0)
    game = Game.objects.get()
    assert (game.source, game.source_id, game.import_run) == ("lichess", "abcd1234", None)
    assert game.user_color == "black"
    positions = GamePosition.objects.filter(game=game).order_by("ply")
    assert [p.move_san for p in positions] == ["f3", "e5", "g4", "Qh4#", ""]


def test_a_synced_game_is_known_by_its_id_even_if_its_pgn_changed(alice: User) -> None:
    store_games(alice, [lichess_game(alice, FOOLS_MATE, "abcd1234")])
    # E.g. the site added a header; the dedup hash then changes, the id doesn't.
    retagged = FOOLS_MATE.replace('[Result "0-1"]', '[Result "0-1"]\n[Date "2024.01.01"]')

    stored = store_games(alice, [lichess_game(alice, retagged, "abcd1234")])

    assert stored == Stored(imported=0, duplicate=1)
    assert Game.objects.count() == 1


def test_a_game_appearing_twice_in_a_batch_is_stored_once(alice: User) -> None:
    retagged = FOOLS_MATE.replace('[Result "0-1"]', '[Result "0-1"]\n[Date "2024.01.01"]')
    batch = [lichess_game(alice, FOOLS_MATE, "abcd1234"), lichess_game(alice, retagged, "abcd1234")]

    assert store_games(alice, batch) == Stored(imported=1, duplicate=1)


def test_the_same_id_on_another_site_is_another_game(alice: User) -> None:
    store_games(alice, [lichess_game(alice, FOOLS_MATE, "1234")])
    other = new_game(alice, parsed(OPERA_GAME), source=Game.Source.CHESSCOM, source_id="1234")

    assert store_games(alice, [other]) == Stored(imported=1, duplicate=0)


def test_a_synced_game_already_imported_from_a_file_is_a_duplicate(alice: User) -> None:
    store_games(alice, [new_game(alice, parsed(FOOLS_MATE))])

    stored = store_games(alice, [lichess_game(alice, FOOLS_MATE, "abcd1234")])

    assert stored == Stored(imported=0, duplicate=1)
    assert Game.objects.get().source == "pgn"


def test_other_users_games_dont_count(alice: User) -> None:
    bob = User.objects.create_user(username="bob")
    store_games(bob, [lichess_game(bob, FOOLS_MATE, "abcd1234")])

    assert store_games(alice, [lichess_game(alice, FOOLS_MATE, "abcd1234")]).imported == 1
