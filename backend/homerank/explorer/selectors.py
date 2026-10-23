"""Position search and the opening explorer, over the user's games and reference databases.

A position is given as FEN and found by its Polyglot hash: in the user's games through
games.GamePosition, in a reference database through its explorer aggregates and packed position
index (ADR 0015). 64-bit hashes can collide, so games found are checked by replaying them to
the position before they are shown.
"""

import io
from dataclasses import dataclass, field
from datetime import date

import chess
import chess.pgn
import chess.polyglot
from django.db.models import Avg, Case, Count, F, Max, Q, QuerySet, When

from homerank.accounts.models import User
from homerank.chesslib.packed import decode_move, unpack_moves
from homerank.chesslib.positions import as_bigint
from homerank.games.models import Game, GamePosition
from homerank.reference import repository
from homerank.reference.models import ExplorerMove, ReferenceDatabase, ReferenceGame

PAGE_SIZE = 50


class InvalidFenError(ValueError):
    def __init__(self, fen: str) -> None:
        super().__init__(f"Not a valid position: {fen}")


def board_of(fen: str) -> chess.Board:
    try:
        board = chess.Board(fen)
    except ValueError as error:
        raise InvalidFenError(fen) from error
    if not board.is_valid():
        raise InvalidFenError(fen)
    return board


def hash_of(board: chess.Board) -> int:
    return as_bigint(chess.polyglot.zobrist_hash(board))


def _same_position(a: chess.Board, b: chess.Board) -> bool:
    """Equal pieces, side to move, castling rights and en passant square (not move counters)."""
    return a._transposition_key() == b._transposition_key()


@dataclass
class MoveStats:
    uci: str
    san: str
    games: int
    white: int  # White won
    draws: int
    black: int  # Black won
    average_rating: float | None  # the opponent's in your games; both players' in a reference
    last_played: date | None  # the latest game's date (a reference database knows the year)


@dataclass
class Explorer:
    games: int
    moves: list[MoveStats] = field(default_factory=list)
    filtered: bool = True  # False if the filters couldn't be applied (a very common position)


@dataclass
class MyGameFilters:
    color: str | None = None  # the side the user played
    time_class: str | None = None
    source: str | None = None
    date_from: date | None = None
    date_to: date | None = None


def _my_games(user: User, filters: MyGameFilters, prefix: str = "") -> Q:
    conditions = {
        "user_color": filters.color,
        "time_class": filters.time_class,
        "source": filters.source,
        "date__gte": filters.date_from,
        "date__lte": filters.date_to,
    }
    q = Q(**{f"{prefix}user": user})
    for lookup, value in conditions.items():
        if value is not None:
            q &= Q(**{f"{prefix}{lookup}": value})
    return q


def _san(board: chess.Board, uci: str) -> str:
    try:
        return board.san(chess.Move.from_uci(uci))
    except (ValueError, AssertionError):  # a hash collision with another position
        return uci


def my_explorer(*, user: User, fen: str, filters: MyGameFilters) -> Explorer:
    """The moves played from the position in the user's games, most played first."""
    board = board_of(fen)
    positions = GamePosition.objects.filter(
        _my_games(user, filters, prefix="game__"), zobrist=hash_of(board)
    )
    opponent_rating = Case(
        When(game__user_color="white", then=F("game__black_elo")),
        When(game__user_color="black", then=F("game__white_elo")),
    )
    rows = (
        positions.exclude(move_uci="")
        .values("move_uci")
        .annotate(
            games=Count("game", distinct=True),
            white=Count("game", distinct=True, filter=Q(game__result="1-0")),
            draws=Count("game", distinct=True, filter=Q(game__result="1/2-1/2")),
            black=Count("game", distinct=True, filter=Q(game__result="0-1")),
            average_rating=Avg(opponent_rating),
            last_played=Max("game__date"),
        )
        .order_by("-games", "move_uci")
    )
    moves = [
        MoveStats(
            uci=row["move_uci"],
            san=_san(board, row["move_uci"]),
            games=row["games"],
            white=row["white"],
            draws=row["draws"],
            black=row["black"],
            average_rating=row["average_rating"],
            last_played=row["last_played"],
        )
        for row in rows
    ]
    return Explorer(games=positions.values("game").distinct().count(), moves=moves)


@dataclass
class FoundGame:
    game_id: int
    ply: int  # where the game reached the position


def search_my_games(
    *, user: User, fen: str, filters: MyGameFilters, page: int = 1
) -> tuple[list[tuple[Game, int]], int]:
    """The user's games reaching the position, newest first, a page at a time, each with the
    ply it reached it at; and how many there are."""
    board = board_of(fen)
    plies = dict(
        GamePosition.objects.filter(user=user, zobrist=hash_of(board))
        .values("game_id")
        .annotate(first=Max("ply"))
        .values_list("game_id", "first")
    )
    games: QuerySet[Game] = (
        Game.objects.filter(_my_games(user, filters), pk__in=plies)
        .prefetch_related("tags")
        .order_by(F("date").desc(nulls_last=True), "-pk")
    )
    total = games.count()
    found = []
    for game in games[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]:
        if _reaches(game, board, plies[game.pk]):
            found.append((game, plies[game.pk]))
    return found, total


def _reaches(game: Game, board: chess.Board, ply: int) -> bool:
    parsed = chess.pgn.read_game(io.StringIO(game.pgn))
    if parsed is None:
        return False
    position = parsed.board()
    for move in list(parsed.mainline_moves())[:ply]:
        position.push(move)
    return _same_position(position, board)


# ---------------------------------------------------------------- reference databases


@dataclass
class ReferenceFilters:
    min_rating: int | None = None  # both players at least
    max_rating: int | None = None  # both players at most
    date_from: date | None = None
    date_to: date | None = None

    @property
    def any(self) -> bool:
        return any(
            v is not None for v in (self.min_rating, self.max_rating, self.date_from, self.date_to)
        )


def _reference_games(
    database: ReferenceDatabase, ids: list[int], filters: ReferenceFilters
) -> QuerySet[ReferenceGame]:
    """The database's games with these ids that pass the filters."""
    games = ReferenceGame.objects.filter(database=database, id__in=ids)
    for lookup, value in (
        ("white_elo__gte", filters.min_rating),
        ("black_elo__gte", filters.min_rating),
        ("white_elo__lte", filters.max_rating),
        ("black_elo__lte", filters.max_rating),
        ("date__gte", filters.date_from),
        ("date__lte", filters.date_to),
    ):
        if value is not None:
            games = games.filter(**{lookup: value})
    return games


def reference_explorer(
    *, database: ReferenceDatabase, fen: str, filters: ReferenceFilters
) -> Explorer:
    """The moves played from the position in the reference database, most played first.

    Without filters from the precomputed aggregates. With filters from the games themselves,
    which the position index lists for positions in up to repository.MAX_LISTED_GAMES games;
    more common positions show their unfiltered counts (filtered=False).
    """
    board = board_of(fen)
    zobrist = hash_of(board)
    entries = repository.games_at(database.pk, zobrist)
    if filters.any and entries:
        return _explorer_from_games(database, board, entries, filters)
    aggregates = ExplorerMove.objects.filter(database=database, zobrist=zobrist)
    if aggregates.exists() or not entries:
        moves = [
            MoveStats(
                uci=(uci := decode_move(a.move).uci()),
                san=_san(board, uci),
                games=a.white + a.draws + a.black,
                white=a.white,
                draws=a.draws,
                black=a.black,
                average_rating=a.rating_sum / a.rating_count if a.rating_count else None,
                last_played=date(a.last_year, 1, 1) if a.last_year else None,
            )
            for a in aggregates
        ]
        moves.sort(key=lambda m: (-m.games, m.uci))
        return Explorer(games=sum(m.games for m in moves), moves=moves, filtered=not filters.any)
    return _explorer_from_games(database, board, entries, filters)  # a position of one game


def _explorer_from_games(
    database: ReferenceDatabase,
    board: chess.Board,
    entries: list[repository.Entry],
    filters: ReferenceFilters,
) -> Explorer:
    """Count the moves from the games reaching the position: each game's move at its ply is the
    two bytes there in its packed moves."""
    plies = {e.game_id: e.ply for e in entries}
    rows = _reference_games(database, list(plies), filters).values_list(
        "id", "moves", "result", "white_elo", "black_elo", "date"
    )
    stats: dict[str, MoveStats] = {}
    ratings: dict[str, list[int]] = {}
    games = 0
    for game_id, packed, result, white_elo, black_elo, played in rows:
        games += 1
        data = bytes(packed)
        ply = plies[game_id]
        if 2 * ply + 2 > len(data):
            continue  # the game ends in the position
        uci = unpack_moves(data[2 * ply : 2 * ply + 2])[0].uci()
        move = stats.setdefault(uci, MoveStats(uci, _san(board, uci), 0, 0, 0, 0, None, None))
        move.games += 1
        move.white += result == "1-0"
        move.draws += result == "1/2-1/2"
        move.black += result == "0-1"
        ratings.setdefault(uci, []).extend(r for r in (white_elo, black_elo) if r)
        if played and (move.last_played is None or played > move.last_played):
            move.last_played = played
    for uci, move in stats.items():
        values = ratings[uci]
        move.average_rating = sum(values) / len(values) if values else None
    moves = sorted(stats.values(), key=lambda m: (-m.games, m.uci))
    return Explorer(games=games, moves=moves)


def search_reference(
    *, database: ReferenceDatabase, fen: str, filters: ReferenceFilters, page: int = 1
) -> tuple[list[tuple[ReferenceGame, int]], int, bool]:
    """The database's games reaching the position, newest first, a page at a time, each with its
    ply; how many there are; and whether the position is too common to list."""
    board = board_of(fen)
    zobrist = hash_of(board)
    entries = repository.games_at(database.pk, zobrist)
    if not entries:
        common = ExplorerMove.objects.filter(database=database, zobrist=zobrist).exists()
        return [], 0, common
    plies = {e.game_id: e.ply for e in entries}
    games = _reference_games(database, list(plies), filters).order_by(
        F("date").desc(nulls_last=True), "-id"
    )
    total = games.count()
    found = []
    for game in games[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]:
        position = chess.Board(game.start_fen) if game.start_fen else chess.Board()
        for move in unpack_moves(bytes(game.moves))[: plies[game.id]]:
            position.push(move)
        if _same_position(position, board):
            found.append((game, plies[game.id]))
    return found, total, False
