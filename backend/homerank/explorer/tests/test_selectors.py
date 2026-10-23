"""Position search and the explorer, over the user's games and a reference database."""

import io
from datetime import date

import chess
import pytest

from homerank.accounts.models import User
from homerank.chesslib.bulk import BulkGame, parse_game
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.explorer.selectors import (
    InvalidFenError,
    MyGameFilters,
    ReferenceFilters,
    hash_of,
    my_explorer,
    reference_explorer,
    search_my_games,
    search_reference,
)
from homerank.games.models import GamePosition
from homerank.games.services import new_game, store_games
from homerank.reference import repository
from homerank.reference.models import ReferenceDatabase

pytestmark = pytest.mark.django_db

START = chess.STARTING_FEN
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def pgn(
    players: tuple[str, str], moves: str, *, result: str, day: str, elos: tuple[int, int]
) -> str:
    white, black = players
    ratings = "".join(
        f'[{side}Elo "{elo}"]\n' for side, elo in zip(("White", "Black"), elos, strict=True) if elo
    )
    return (
        f'[White "{white}"]\n[Black "{black}"]\n[Result "{result}"]\n[Date "{day}"]\n{ratings}\n'
        f"{moves} {result}\n"
    )


GAMES = [
    pgn(("me", "Ann"), "1. e4 e5 2. Nf3", result="1-0", day="2026.01.01", elos=(1500, 1600)),
    pgn(("Ben", "me"), "1. e4 c5", result="0-1", day="2026.02.01", elos=(1700, 1500)),
    pgn(("me", "Cid"), "1. d4 d5", result="1/2-1/2", day="2026.03.01", elos=(1500, 1400)),
]


@pytest.fixture
def me() -> User:
    user = User.objects.create_user(username="me", player_names=["me"])
    items = [item for text in GAMES for item in read_pgn(io.BytesIO(text.encode()))]
    store_games(user, [new_game(user, item) for item in items if isinstance(item, PgnGame)])
    return user


# ---------------------------------------------------------------- my games


def test_my_explorer_counts_the_moves_played_from_a_position(me: User) -> None:
    explorer = my_explorer(user=me, fen=START, filters=MyGameFilters())

    assert explorer.games == 3  # noqa: PLR2004
    e4, d4 = explorer.moves
    assert (e4.uci, e4.san, e4.games, e4.white, e4.black) == ("e2e4", "e4", 2, 1, 1)
    assert e4.average_rating == 1650  # noqa: PLR2004 - my opponents: Ann 1600, Ben 1700
    assert e4.last_played == date(2026, 2, 1)
    assert (d4.san, d4.draws) == ("d4", 1)


def test_my_explorer_filters_by_my_side(me: User) -> None:
    explorer = my_explorer(user=me, fen=AFTER_E4, filters=MyGameFilters(color="black"))

    assert [(m.san, m.games) for m in explorer.moves] == [("c5", 1)]


def test_my_explorer_ignores_other_users(me: User) -> None:
    other = User.objects.create_user(username="other")

    assert my_explorer(user=other, fen=START, filters=MyGameFilters()).games == 0


def test_searches_my_games_reaching_a_position_newest_first(me: User) -> None:
    found, total = search_my_games(user=me, fen=AFTER_E4, filters=MyGameFilters())

    assert total == 2  # noqa: PLR2004
    assert [(game.black, ply) for game, ply in found] == [("me", 1), ("Ann", 1)]


def test_a_hash_collision_isnt_shown(me: User) -> None:
    # Pretend another position had the same hash: the replay check drops the game.
    position = GamePosition.objects.filter(user=me, ply=1, move_san="e5").get()
    GamePosition.objects.filter(game=position.game, ply=2).update(zobrist=position.zobrist)

    found, total = search_my_games(user=me, fen=AFTER_E4, filters=MyGameFilters())

    assert total == 2  # noqa: PLR2004 - counted by hash...
    assert [game.black for game, _ in found] == ["me"]  # ...but only true matches shown


def test_an_invalid_position_is_refused(me: User) -> None:
    with pytest.raises(InvalidFenError):
        my_explorer(user=me, fen="not a fen", filters=MyGameFilters())


# ---------------------------------------------------------------- a reference database


@pytest.fixture
def masters() -> ReferenceDatabase:
    database = ReferenceDatabase.objects.create(name="Masters")
    repository.create_partitions(database.pk)
    repository.create_staging(database.pk)
    games = []
    for text in GAMES:
        game = parse_game(text.encode())
        assert isinstance(game, BulkGame)
        games.append(game)
    repository.copy_games(repository.game_row(database.pk, i + 1, g) for i, g in enumerate(games))
    repository.copy_positions(
        database.pk,
        (row for i, g in enumerate(games) for row in repository.position_rows(i + 1, g)),
    )
    repository.build_index(database.pk)
    return database


def test_reference_explorer_reads_the_aggregates(masters: ReferenceDatabase) -> None:
    explorer = reference_explorer(database=masters, fen=START, filters=ReferenceFilters())

    assert explorer.games == 3  # noqa: PLR2004
    e4 = explorer.moves[0]
    assert (e4.san, e4.games, e4.white, e4.black) == ("e4", 2, 1, 1)
    assert e4.average_rating == 1575  # noqa: PLR2004 - (1500 + 1600 + 1700 + 1500) / 4
    assert e4.last_played == date(2026, 1, 1)  # the year


def test_reference_explorer_applies_filters_from_the_games(masters: ReferenceDatabase) -> None:
    explorer = reference_explorer(
        database=masters, fen=START, filters=ReferenceFilters(min_rating=1450)
    )

    assert explorer.filtered
    assert [(m.san, m.games) for m in explorer.moves] == [("e4", 2)]  # Cid's 1400 is out
    assert explorer.moves[0].last_played == date(2026, 2, 1)  # the exact date


def test_a_position_of_one_game_shows_its_move(masters: ReferenceDatabase) -> None:
    after_d4 = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1"

    explorer = reference_explorer(database=masters, fen=after_d4, filters=ReferenceFilters())

    assert [(m.san, m.draws) for m in explorer.moves] == [("d5", 1)]


def test_searches_reference_games_reaching_a_position(masters: ReferenceDatabase) -> None:
    found, total, too_common = search_reference(
        database=masters, fen=AFTER_E4, filters=ReferenceFilters(date_from=date(2026, 1, 15))
    )

    assert (total, too_common) == (1, False)
    assert [(game.white, ply) for game, ply in found] == [("Ben", 1)]


def test_very_common_positions_are_not_listed(
    masters: ReferenceDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repository, "MAX_LISTED_GAMES", 1)
    repository.create_staging(masters.pk)
    repository.copy_positions(
        masters.pk,
        (
            (i + 1, p.zobrist, p.ply, p.next_move)
            for i, text in enumerate(GAMES)
            for p in parse_game(text.encode()).positions  # type: ignore[union-attr]
        ),
    )
    repository.build_index(masters.pk)

    found, total, too_common = search_reference(
        database=masters, fen=START, filters=ReferenceFilters()
    )

    assert (found, total, too_common) == ([], 0, True)


def test_a_hash_collision_in_a_reference_database_isnt_shown(masters: ReferenceDatabase) -> None:
    # Index game 3 (1. d4) as if its position after one move had the hash of 1. e4's.
    after_e4 = chess.Board(AFTER_E4)
    repository.create_staging(masters.pk)
    rows = [
        (i + 1, p.zobrist, p.ply, p.next_move)
        for i, text in enumerate(GAMES)
        for p in parse_game(text.encode()).positions  # type: ignore[union-attr]
    ]
    collided = [
        (g, hash_of(after_e4) if (g, ply) == (3, 1) else z, ply, m) for g, z, ply, m in rows
    ]
    repository.copy_positions(masters.pk, collided)
    repository.build_index(masters.pk)

    found, total, _ = search_reference(database=masters, fen=AFTER_E4, filters=ReferenceFilters())

    assert total == 3  # noqa: PLR2004 - three games carry the hash...
    assert sorted(game.white for game, _ in found) == ["Ben", "me"]  # ...two reach the position
