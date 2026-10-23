import pytest

from homerank.chesslib.bulk import BulkGame, parse_game
from homerank.reference import repository
from homerank.reference.models import ReferenceDatabase

MASTER_GAMES = [
    b'[Event "Paris"]\n[White "Morphy, Paul"]\n[Black "Duke Karl"]\n[Result "1-0"]\n'
    b'[Date "1858.??.??"]\n[WhiteElo "2690"]\n[ECO "C41"]\n\n'
    b"1. e4 e5 2. Nf3 d6 3. d4 Bg4 1-0\n",
    b'[Event "Club"]\n[White "Anna"]\n[Black "Ben"]\n[Result "0-1"]\n[Date "2001.05.05"]\n\n'
    b"1. f3 e5 2. g4 Qh4# 0-1\n",
]


def load_reference(name: str = "Masters") -> ReferenceDatabase:
    """A reference database with MASTER_GAMES, imported and indexed."""
    database = ReferenceDatabase.objects.create(name=name, status="ready", game_count=2)
    repository.create_partitions(database.pk)
    repository.create_staging(database.pk)
    games = [parse_game(text) for text in MASTER_GAMES]
    assert all(isinstance(g, BulkGame) for g in games)
    repository.copy_games(
        repository.game_row(database.pk, i + 1, g)  # type: ignore[arg-type]
        for i, g in enumerate(games)
    )
    repository.copy_positions(
        database.pk,
        (
            row
            for i, g in enumerate(games)
            for row in repository.position_rows(i + 1, g)  # type: ignore[arg-type]
        ),
    )
    repository.build_index(database.pk)
    return database


@pytest.fixture
def masters() -> ReferenceDatabase:
    return load_reference()
