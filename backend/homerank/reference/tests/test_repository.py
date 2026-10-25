"""Partitions, bulk loading and the explorer and position index of reference databases."""

import chess
import chess.polyglot
import pytest
from django.db import connection

from homerank.chesslib.bulk import BulkGame, parse_game
from homerank.chesslib.packed import encode_move
from homerank.chesslib.positions import as_bigint
from homerank.reference import repository
from homerank.reference.models import ExplorerMove, ReferenceDatabase, ReferenceGame
from homerank.reference.repository import ENTRY, Entry, find_entries, games_at

pytestmark = pytest.mark.django_db

SCHOLARS_MATE = (
    b'[White "A"]\n[Black "B"]\n[Result "1-0"]\n[Date "1990.01.01"]\n[WhiteElo "2000"]\n\n'
    b"1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0\n"
)
FOOLS_MATE = (
    b'[White "C"]\n[Black "D"]\n[Result "0-1"]\n[Date "2001.05.05"]\n\n1. f3 e5 2. g4 Qh4# 0-1\n'
)
START = as_bigint(chess.polyglot.zobrist_hash(chess.Board()))
AFTER_F3 = as_bigint(
    chess.polyglot.zobrist_hash(
        chess.Board("rnbqkbnr/pppppppp/8/8/8/5P2/PPPPP1PP/RNBQKBNR b KQkq - 0 1")
    )
)


def parsed(text: bytes) -> BulkGame:
    game = parse_game(text)
    assert isinstance(game, BulkGame)
    return game


@pytest.fixture
def database() -> ReferenceDatabase:
    db = ReferenceDatabase.objects.create(name="Masters")
    repository.create_partitions(db.pk)
    repository.create_staging(db.pk)
    return db


def load(database: ReferenceDatabase, *texts: bytes) -> None:
    games = [parsed(text) for text in texts]
    first = repository.next_game_id(database.pk)
    repository.copy_games(
        repository.game_row(database.pk, first + i, g) for i, g in enumerate(games)
    )
    repository.copy_positions(
        database.pk,
        (row for i, g in enumerate(games) for row in repository.position_rows(first + i, g)),
    )


def tables() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE tablename LIKE 'reference_%'")
        return {name for (name,) in cursor.fetchall()}


def test_games_are_stored_in_the_databases_partition(database: ReferenceDatabase) -> None:
    load(database, SCHOLARS_MATE, FOOLS_MATE)

    games = ReferenceGame.objects.filter(database=database).order_by("id")
    assert [(g.id, g.white, g.result, g.ply_count) for g in games] == [
        (1, "A", "1-0", 7),
        (2, "C", "0-1", 4),
    ]
    assert str(games[0].date) == "1990-01-01"
    assert f"reference_game_{database.pk}" in tables()
    assert repository.next_game_id(database.pk) == 3  # noqa: PLR2004


def test_duplicates_are_removed_with_their_positions(database: ReferenceDatabase) -> None:
    load(database, FOOLS_MATE, SCHOLARS_MATE, FOOLS_MATE)

    assert repository.remove_duplicates(database.pk) == 1

    assert sorted(ReferenceGame.objects.values_list("id", flat=True)) == [1, 2]  # first kept
    repository.build_index(database.pk)
    assert {e.game_id for e in games_at(database.pk, START)} == {1, 2}


def test_the_explorer_counts_moves_from_positions_seen_in_several_games(
    database: ReferenceDatabase,
) -> None:
    load(database, SCHOLARS_MATE, FOOLS_MATE)

    repository.build_index(database.pk)

    moves = {m.move: m for m in ExplorerMove.objects.filter(database=database, zobrist=START)}
    e4 = moves[encode_move(chess.Move.from_uci("e2e4"))]
    f3 = moves[encode_move(chess.Move.from_uci("f2f3"))]
    assert (e4.white, e4.draws, e4.black, e4.rating_sum, e4.rating_count) == (1, 0, 0, 2000, 1)
    assert (f3.white, f3.black, f3.last_year) == (0, 1, 2001)
    # A position of a single game has no aggregate: its game is all there is.
    assert not ExplorerMove.objects.filter(zobrist=AFTER_F3).exists()
    assert f"reference_staging_{database.pk}" not in tables()  # dropped after the build


def test_the_position_index_finds_every_game_reaching_a_position(
    database: ReferenceDatabase,
) -> None:
    load(database, SCHOLARS_MATE, FOOLS_MATE)

    repository.build_index(database.pk)

    assert sorted(games_at(database.pk, START), key=lambda e: e.game_id) == [
        Entry(1, 0),
        Entry(2, 0),
    ]
    assert games_at(database.pk, AFTER_F3) == [Entry(2, 1)]
    assert games_at(database.pk, 12345) == []


def test_very_common_positions_keep_no_game_list(
    database: ReferenceDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repository, "MAX_LISTED_GAMES", 1)
    load(database, SCHOLARS_MATE, FOOLS_MATE)

    repository.build_index(database.pk)

    assert games_at(database.pk, START) == []  # in two games: too common
    assert games_at(database.pk, AFTER_F3) == [Entry(2, 1)]


def test_deleting_a_database_drops_its_partitions(database: ReferenceDatabase) -> None:
    load(database, FOOLS_MATE)

    repository.drop_partitions(database.pk)

    assert not {name for name in tables() if name.endswith(f"_{database.pk}")}
    assert "reference_game" in tables()  # the parent stays


def test_entries_are_found_by_binary_search() -> None:
    entries = b"".join(
        ENTRY.pack(z, g, p) for z, g, p in [(-5, 1, 0), (3, 2, 4), (3, 7, 6), (9, 3, 1)]
    )

    assert find_entries(entries, 3) == [Entry(2, 4), Entry(7, 6)]
    assert find_entries(entries, -5) == [Entry(1, 0)]
    assert find_entries(entries, 4) == []
    assert find_entries(b"", 3) == []


def test_an_imported_databases_games_are_indexed_newest_first(masters: ReferenceDatabase) -> None:
    # The game list's order: without this index, every page sorted all of the database's games.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = %s",
            [f"reference_game_{masters.pk}_newest"],
        )
        (definition,) = cursor.fetchone() or ("",)

    assert "(date DESC NULLS LAST, id DESC)" in definition
