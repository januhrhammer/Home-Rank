"""Raw SQL for reference databases' data: partitions, bulk loading with COPY, and the explorer
and position index built from it (ADR 0015).

Each database has a partition of reference_game, reference_explorer and reference_bucket,
named after its id. While an import reads files, the positions of the games it stores go into
an unlogged staging table; build_index turns them into the explorer's aggregates and the packed
position index, then drops it.
"""

import struct
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from django.db import connection
from psycopg import sql

from homerank.chesslib.bulk import BulkGame

# The position index: entries of hash (8 bytes, signed), game (4) and ply (1), sorted, in
# buckets by the hash's top bits. 17 bits make buckets of a few hundred entries for a database
# of millions of games.
ENTRY = struct.Struct(">qiB")
BUCKET_SHIFT = 64 - 17
# Positions seen in more games than this keep no game list: the explorer counts them.
MAX_LISTED_GAMES = 10_000

TABLES = ("reference_game", "reference_explorer", "reference_bucket")


def _partition(table: str, database_id: int) -> sql.Identifier:
    return sql.Identifier(f"{table}_{database_id}")


def _staging(database_id: int) -> sql.Identifier:
    return sql.Identifier(f"reference_staging_{database_id}")


def _execute(query: sql.Composable) -> None:
    with connection.cursor() as cursor:
        cursor.execute(query.as_string(cursor.connection))


def _scalar(query: sql.Composable) -> int:
    with connection.cursor() as cursor:
        cursor.execute(query.as_string(cursor.connection))
        row = cursor.fetchone()
    return int(row[0])


def create_partitions(database_id: int) -> None:
    for table in TABLES:
        _execute(
            sql.SQL("CREATE TABLE {} PARTITION OF {} FOR VALUES IN ({})").format(
                _partition(table, database_id), sql.Identifier(table), sql.Literal(database_id)
            )
        )


def drop_partitions(database_id: int) -> None:
    """Drop the database's data at once, instead of deleting it row by row."""
    drop_staging(database_id)
    for table in TABLES:
        _execute(sql.SQL("DROP TABLE IF EXISTS {}").format(_partition(table, database_id)))


def create_staging(database_id: int) -> None:
    _execute(
        sql.SQL(
            "CREATE UNLOGGED TABLE IF NOT EXISTS {} "
            "(game_id integer NOT NULL, zobrist bigint NOT NULL, ply smallint NOT NULL, "
            "move smallint)"
        ).format(_staging(database_id))
    )


def drop_staging(database_id: int) -> None:
    _execute(sql.SQL("DROP TABLE IF EXISTS {}").format(_staging(database_id)))


GAME_COLUMNS = (
    "database_id",
    "id",
    "white",
    "black",
    "white_elo",
    "black_elo",
    "result",
    "date",
    "date_pgn",
    "event",
    "site",
    "eco",
    "opening",
    "ply_count",
    "start_fen",
    "moves",
    "dedup_hash",
)


def game_row(database_id: int, game_id: int, game: BulkGame) -> tuple[object, ...]:
    """A parsed game as a row for copy_games."""
    headers = game.headers
    return (
        database_id,
        game_id,
        headers.white,
        headers.black,
        headers.white_elo,
        headers.black_elo,
        headers.result,
        headers.date.earliest(),
        str(headers.date),
        headers.event,
        headers.site,
        headers.eco,
        headers.opening,
        game.ply_count,
        game.start_fen,
        game.moves,
        bytes.fromhex(game.dedup_hash)[:16],
    )


def position_rows(game_id: int, game: BulkGame) -> Iterator[tuple[int, int, int, int | None]]:
    """A parsed game's positions as rows for copy_positions."""
    for position in game.positions:
        yield (game_id, position.zobrist, position.ply, position.next_move)


def copy_games(rows: Iterable[tuple[object, ...]]) -> None:
    """Write games with COPY, each a tuple in the order of GAME_COLUMNS."""
    query = sql.SQL("COPY reference_game ({}) FROM STDIN").format(
        sql.SQL(", ").join(map(sql.Identifier, GAME_COLUMNS))
    )
    with connection.cursor() as cursor, cursor.copy(query.as_string(cursor.connection)) as copy:
        for row in rows:
            copy.write_row(row)


def copy_positions(database_id: int, rows: Iterable[tuple[int, int, int, int | None]]) -> None:
    """Write positions to the staging table: (game id, hash, ply, packed move or None)."""
    query = sql.SQL("COPY {} (game_id, zobrist, ply, move) FROM STDIN").format(
        _staging(database_id)
    )
    with connection.cursor() as cursor, cursor.copy(query.as_string(cursor.connection)) as copy:
        for row in rows:
            copy.write_row(row)


def next_game_id(database_id: int) -> int:
    return _scalar(
        sql.SQL("SELECT coalesce(max(id), 0) + 1 FROM {}").format(
            _partition("reference_game", database_id)
        )
    )


def remove_duplicates(database_id: int) -> int:
    """Delete games that are already in the database (same dedup hash), keeping the first one,
    and their staged positions. Returns how many were deleted."""
    game = _partition("reference_game", database_id)
    query = sql.SQL(
        "WITH doomed AS ("
        "  DELETE FROM {game} g USING ("
        "    SELECT id FROM ("
        "      SELECT id, row_number() OVER (PARTITION BY dedup_hash ORDER BY id) AS n FROM {game}"
        "    ) numbered WHERE n > 1"
        "  ) dup WHERE g.id = dup.id RETURNING g.id"
        ") DELETE FROM {staging} s USING doomed WHERE s.game_id = doomed.id"
    ).format(game=game, staging=_staging(database_id))
    count = sql.SQL("SELECT count(*) FROM {}").format(game)
    before = _scalar(count)
    _execute(query)
    return before - _scalar(count)


# The game partitions' indexes besides the primary key, by name suffix.
BROWSE_INDEXES = (
    ("white", "lower(white)"),
    ("black", "lower(black)"),
    ("eco", "eco"),
    ("date", "date"),
    ("newest", "date DESC NULLS LAST, id DESC"),
    ("dedup", "dedup_hash"),
)


def build_index(database_id: int) -> None:
    """Build the explorer's aggregates and the packed position index from the staged positions,
    replacing what was there, and the games' search indexes; then drop the staging table."""
    staging = _staging(database_id)
    explorer = _partition("reference_explorer", database_id)
    bucket = _partition("reference_bucket", database_id)
    game = _partition("reference_game", database_id)
    counts = sql.Identifier(f"reference_counts_{database_id}")
    statements = [
        sql.SQL("TRUNCATE {}, {}").format(explorer, bucket),
        # How many games reach each position (a game may pass a position twice).
        sql.SQL(
            "CREATE TEMPORARY TABLE {counts} AS "
            "SELECT zobrist, count(DISTINCT game_id) AS games FROM {staging} GROUP BY zobrist"
        ).format(counts=counts, staging=staging),
        sql.SQL("CREATE INDEX ON {} (zobrist)").format(counts),
        sql.SQL(
            "INSERT INTO {explorer} SELECT {db}, s.zobrist, s.move,"
            " count(*) FILTER (WHERE g.result = '1-0'),"
            " count(*) FILTER (WHERE g.result = '1/2-1/2'),"
            " count(*) FILTER (WHERE g.result = '0-1'),"
            " coalesce(sum(coalesce(g.white_elo, 0) + coalesce(g.black_elo, 0)), 0),"
            " count(g.white_elo) + count(g.black_elo),"
            " max(extract(year FROM g.date))::smallint"
            " FROM {staging} s JOIN {counts} c USING (zobrist)"
            " JOIN {game} g ON g.id = s.game_id"
            " WHERE c.games >= 2 AND s.move IS NOT NULL GROUP BY s.zobrist, s.move"
        ).format(
            explorer=explorer,
            db=sql.Literal(database_id),
            staging=staging,
            counts=counts,
            game=game,
        ),
        sql.SQL(
            "INSERT INTO {bucket} SELECT {db}, (s.zobrist >> {shift})::integer,"
            " string_agg(int8send(s.zobrist) || int4send(s.game_id)"
            "   || substring(int2send(s.ply) FROM 2 FOR 1), ''::bytea"
            "   ORDER BY s.zobrist, s.game_id, s.ply)"
            " FROM {staging} s JOIN {counts} c USING (zobrist)"
            " WHERE c.games <= {max_listed} GROUP BY 2"
        ).format(
            bucket=bucket,
            db=sql.Literal(database_id),
            shift=sql.Literal(BUCKET_SHIFT),
            staging=staging,
            counts=counts,
            max_listed=sql.Literal(MAX_LISTED_GAMES),
        ),
        sql.SQL("DROP TABLE {}").format(counts),
        # For browsing and searching the games: by players, opening, date and duplicates, and
        # in the game list's order, newest first (the plain date index runs the other way).
        *(
            sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} ({})").format(
                sql.Identifier(f"reference_game_{database_id}_{name}"), game, sql.SQL(expression)
            )
            for name, expression in BROWSE_INDEXES
        ),
        sql.SQL("ANALYZE {}").format(game),
        sql.SQL("ANALYZE {}").format(explorer),
    ]
    for statement in statements:
        _execute(statement)
    drop_staging(database_id)


@dataclass(frozen=True)
class Entry:
    game_id: int
    ply: int


def games_at(database_id: int, zobrist: int) -> list[Entry]:
    """The games reaching a position, by its hash, from the packed index; [] for a position
    seen in more than MAX_LISTED_GAMES games (see explorer_moves)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT entries FROM reference_bucket WHERE database_id = %s AND bucket = %s",
            [database_id, zobrist >> BUCKET_SHIFT],
        )
        row = cursor.fetchone()
    return find_entries(bytes(row[0]), zobrist) if row else []


def find_entries(entries: bytes, zobrist: int) -> list[Entry]:
    """The entries of a hash in a bucket's sorted entries, by binary search."""
    size = ENTRY.size
    low, high = 0, len(entries) // size
    while low < high:
        middle = (low + high) // 2
        if ENTRY.unpack_from(entries, middle * size)[0] < zobrist:
            low = middle + 1
        else:
            high = middle
    found = []
    for index in range(low, len(entries) // size):
        hash_, game_id, ply = ENTRY.unpack_from(entries, index * size)
        if hash_ != zobrist:
            break
        found.append(Entry(game_id, ply))
    return found
