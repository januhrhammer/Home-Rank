"""Seeding a repertoire from the user's games, and the gap report."""

import io

import chess
import pytest

from homerank.accounts.models import User
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.games.models import Game
from homerank.games.services import new_game, store_games
from homerank.repertoire import selectors
from homerank.repertoire.models import Repertoire
from homerank.repertoire.services import add_move, create_repertoire, seed_from_games

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", player_names=["alice64"])


@pytest.fixture
def white(alice: User) -> Repertoire:
    return create_repertoire(user=alice, name="Queen's Gambit", color="white")


def store(user: User, *games: tuple[str, str]) -> list[Game]:
    """Store games of the user's as White, each given as (date, moves)."""
    text = "\n\n".join(
        f'[White "alice64"]\n[Black "bob_b"]\n[Date "{day}"]\n[Result "*"]\n\n{moves} *'
        for day, moves in games
    )
    items = [item for item in read_pgn(io.BytesIO(text.encode())) if isinstance(item, PgnGame)]
    store_games(user, [new_game(user, item) for item in items])
    return list(Game.objects.filter(user=user).order_by("pk"))


def play(repertoire: Repertoire, *sans: str) -> None:
    board = chess.Board()
    for san in sans:
        move = board.parse_san(san)
        add_move(repertoire, fen=board.fen(), move_uci=move.uci())
        board.push(move)


def sans(repertoire: Repertoire) -> list[str]:
    return [m.move_san for m in selectors.moves(repertoire)]


@pytest.fixture
def games(alice: User) -> list[Game]:
    played = store(
        alice,
        ("2026.01.01", "1. d4 d5 2. c4 e6 3. Nc3"),
        ("2026.02.01", "1. d4 d5 2. c4 c6 3. Nf3"),
        ("2026.03.01", "1. d4 d5 2. c4 e6 3. Nf3"),  # 3. Nc3 and 3. Nf3 once each: Nf3 is later
        ("2026.01.15", "1. d4 Nf6 2. c4"),
        ("2025.06.01", "1. e4 e5"),
    )
    # A game as Black, which a repertoire for White leaves out.
    text = '[White "bob_b"]\n[Black "alice64"]\n[Result "*"]\n\n1. d4 d5 2. c4 e6 *'
    (item,) = read_pgn(io.BytesIO(text.encode()))
    assert isinstance(item, PgnGame)
    store_games(alice, [new_game(alice, item)])
    return played


# ---------------------------------------------------------------- seeding


@pytest.mark.usefixtures("games")
def test_seeding_adds_my_main_moves_and_common_replies(white: Repertoire) -> None:
    added = seed_from_games(white)

    assert added == 5  # noqa: PLR2004
    assert sans(white) == ["d4", "d5", "c4", "e6", "Nf3"]


@pytest.mark.usefixtures("games")
def test_seeding_takes_rarer_replies_and_stops_at_the_depth(white: Repertoire) -> None:
    seed_from_games(white, depth=3, min_games=1)

    assert sorted(sans(white)) == ["Nf6", "c4", "c4", "d4", "d5"]


@pytest.mark.usefixtures("games")
def test_seeding_follows_my_own_moves_already_there(white: Repertoire) -> None:
    play(white, "d4", "d5", "Nf3")

    added = seed_from_games(white)

    assert added == 0  # 2. c4, which the games play, isn't added next to 2. Nf3
    assert sans(white) == ["d4", "d5", "Nf3"]


def test_seeding_from_no_games_adds_nothing(white: Repertoire) -> None:
    assert seed_from_games(white) == 0


# ---------------------------------------------------------------- gap report


def test_gaps_are_the_first_moves_outside_the_repertoire(
    alice: User, white: Repertoire, games: list[Game]
) -> None:
    play(white, "d4", "d5", "c4", "e6", "Nc3")
    late_e4, ends_inside = store(
        alice, ("2026.04.01", "1. e4 c5"), ("2026.05.01", "1. d4 d5 2. c4")
    )[-2:]
    bob = User.objects.create_user(username="bob", player_names=["alice64"])
    store(bob, ("2026.01.01", "1. b3"))  # someone else's game

    result = selectors.gaps(white)

    summary = [(g.move_san, g.by_user, g.games, g.game_ids) for g in result]
    assert summary == [
        ("e4", True, 2, [late_e4.pk, games[4].pk]),  # newest first
        ("c6", False, 1, [games[1].pk]),
        ("Nf3", True, 1, [games[2].pk]),
        ("Nf6", False, 1, [games[3].pk]),
    ]
    assert result[0].fen == chess.STARTING_FEN
    assert str(result[0].last_played) == "2026-04-01"
    assert ends_inside.pk not in {pk for g in result for pk in g.game_ids}


def test_an_empty_repertoire_has_no_gaps(white: Repertoire, games: list[Game]) -> None:
    assert selectors.gaps(white) == []
