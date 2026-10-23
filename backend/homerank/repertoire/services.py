"""Building repertoires: creating them, adding and removing moves, importing PGN. See ADR 0016.

Moves are stored by the position they are played from, with hashes as signed 64-bit numbers
like GamePosition's. Each of the user's own moves gets a review card when it is added.
"""

from collections import defaultdict, deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from http import HTTPStatus

import chess
import chess.polyglot
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Max

from homerank.accounts.models import User
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.chesslib.positions import as_bigint
from homerank.chesslib.repertoire import (
    START_ZOBRIST,
    Edge,
    NotFromStartError,
    edge,
    pgn_edges,
    reachable,
)
from homerank.core.errors import DomainError
from homerank.games.models import GamePosition
from homerank.games.services import NameTakenError
from homerank.repertoire.models import Repertoire, RepertoireMove
from homerank.training.services import new_repertoire_cards

MAX_REPERTOIRES = 50  # per user
MAX_MOVES = 20_000  # per repertoire
MAX_PGN_BYTES = 20 * 1024 * 1024  # per imported file
SEED_DEPTH = 12  # plies seeded from the user's games, unless they choose another depth
SEED_MIN_GAMES = 2  # games an opponent's reply needs to be seeded, unless the user chooses


class TooManyRepertoiresError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = f"You can have at most {MAX_REPERTOIRES} repertoires."


class TooManyMovesError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = f"A repertoire can have at most {MAX_MOVES:,} moves."


class PgnTooLargeError(DomainError):
    status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    detail = f"PGN files for a repertoire can be at most {MAX_PGN_BYTES // (1024 * 1024)} MB."


class InvalidPositionError(DomainError):
    detail = "This isn't a valid position."


class PositionNotInRepertoireError(DomainError):
    detail = "The repertoire doesn't reach this position."


class IllegalMoveError(DomainError):
    detail = "This move isn't legal in this position."


# ---------------------------------------------------------------- repertoires


def create_repertoire(*, user: User, name: str, color: str) -> Repertoire:
    if Repertoire.objects.filter(user=user).count() >= MAX_REPERTOIRES:
        raise TooManyRepertoiresError
    repertoire = Repertoire(user=user, name=name, color=color)
    _save_named(repertoire)
    return repertoire


def rename_repertoire(repertoire: Repertoire, *, name: str) -> Repertoire:
    """Only the name can change: another colour would make the user's moves the opponent's."""
    repertoire.name = name
    _save_named(repertoire)
    return repertoire


def _save_named(repertoire: Repertoire) -> None:
    try:
        with transaction.atomic():  # a savepoint, so the failed insert doesn't break the request
            repertoire.save()
    except IntegrityError as error:  # the name is unique per user
        raise NameTakenError(repertoire.name) from error


# ---------------------------------------------------------------- moves


def add_move(repertoire: Repertoire, *, fen: str, move_uci: str) -> RepertoireMove:
    """Add a move in a position the repertoire reaches. A move it already has is returned
    as it is."""
    try:
        board = chess.Board(fen)
    except ValueError as error:
        raise InvalidPositionError from error
    if not board.is_valid():
        raise InvalidPositionError
    zobrist = chess.polyglot.zobrist_hash(board)
    existing = repertoire.moves.filter(from_zobrist=as_bigint(zobrist), move_uci=move_uci).first()
    if existing is not None:
        return existing
    reached = repertoire.moves.filter(to_zobrist=as_bigint(zobrist)).exists()
    if zobrist != START_ZOBRIST and not reached:
        raise PositionNotInRepertoireError
    try:
        move = chess.Move.from_uci(move_uci)
    except ValueError as error:
        raise IllegalMoveError from error
    if not board.is_legal(move):
        raise IllegalMoveError
    (added,) = _add_edges(repertoire, [edge(board, move)])
    return added


@dataclass(frozen=True)
class PgnImport:
    moves_added: int
    games_read: int
    games_skipped: int  # unreadable, or not from the starting position


def import_pgn(repertoire: Repertoire, *, lines: Iterable[bytes]) -> PgnImport:
    """Add every move of a PGN file's games, variations included, that the repertoire doesn't
    have yet; each with the comment after it in the PGN. Moves already there stay as they are.
    The file comes as its lines, e.g. an uploaded file, and is read one game at a time."""
    seen: set[tuple[int, str]] = set()
    edges: list[Edge] = []
    read = skipped = 0
    for item in read_pgn(_limited(lines)):
        if not isinstance(item, PgnGame):
            skipped += 1
            continue
        try:
            edges.extend(pgn_edges(item.game, seen))
        except NotFromStartError:
            skipped += 1
            continue
        read += 1
        if len(edges) > MAX_MOVES:  # too many for any repertoire: no need to read on
            raise TooManyMovesError
    added = _add_edges(repertoire, edges)
    return PgnImport(moves_added=len(added), games_read=read, games_skipped=skipped)


def _limited(lines: Iterable[bytes]) -> Iterator[bytes]:
    size = 0
    for line in lines:
        size += len(line)
        if size > MAX_PGN_BYTES:
            raise PgnTooLargeError
        yield line


# ---------------------------------------------------------------- seeding from games


@dataclass(frozen=True)
class _Played:
    move_uci: str
    games: int
    last_played: date | None


def seed_from_games(
    repertoire: Repertoire, *, depth: int = SEED_DEPTH, min_games: int = SEED_MIN_GAMES
) -> int:
    """Add what the user plays in their games with the repertoire's colour, up to depth
    plies: where they are to move, their most played move (ties: the more recently played);
    where the opponent is, every reply played in at least min_games games. Where the
    repertoire already has a move of the user's, that move is followed instead. Only adds
    moves; returns how many."""
    played = _played_moves(repertoire, depth)
    known = defaultdict(list)
    for from_zobrist, move_uci in repertoire.moves.values_list("from_zobrist", "move_uci"):
        known[from_zobrist].append(move_uci)
    edges = []
    seen = set()
    todo = deque([chess.Board()])  # breadth first, so a position is first met at its shortest
    while todo:
        board = todo.popleft()
        zobrist = as_bigint(chess.polyglot.zobrist_hash(board))
        if zobrist in seen or board.ply() >= depth:
            continue
        seen.add(zobrist)
        here = played.get(zobrist, [])  # most played first
        if _users_turn(repertoire, board.turn):
            new = [here[0].move_uci] if here and not known[zobrist] else []
        else:
            new = [
                p.move_uci
                for p in here
                if p.games >= min_games and p.move_uci not in known[zobrist]
            ]
        for move_uci in [*known[zobrist], *new]:
            move = chess.Move.from_uci(move_uci)
            if not board.is_legal(move):
                continue  # only possible if two positions' hashes collide
            if move_uci in new:
                edges.append(edge(board, move))
            after = board.copy(stack=False)
            after.push(move)
            todo.append(after)
    return len(_add_edges(repertoire, edges))


def _played_moves(repertoire: Repertoire, depth: int) -> dict[int, list[_Played]]:
    """The moves played in the user's games with the repertoire's colour within the first
    depth plies, by position (signed hash), most played first."""
    rows = (
        GamePosition.objects.filter(
            user_id=repertoire.user_id, game__user_color=repertoire.color, ply__lt=depth
        )
        .exclude(move_uci="")
        .values("zobrist", "move_uci")
        # Counted per occurrence, like the explorer: a repetition counts twice. Rare.
        .annotate(games=Count("pk"), last_played=Max("game__date"))
        .order_by("-games", F("last_played").desc(nulls_last=True), "move_uci")
    )
    played = defaultdict(list)
    for row in rows:
        played[row["zobrist"]].append(_Played(row["move_uci"], row["games"], row["last_played"]))
    return played


def _add_edges(repertoire: Repertoire, edges: list[Edge]) -> list[RepertoireMove]:
    """Store the edges the repertoire doesn't have yet, with cards for the user's own moves.
    Returns the moves added."""
    with transaction.atomic():
        # Locked, so that two requests at once can't both pass the size check.
        Repertoire.objects.select_for_update().filter(pk=repertoire.pk).get()
        known = set(repertoire.moves.values_list("from_zobrist", "move_uci"))
        new = {}
        for e in edges:
            key = (as_bigint(e.from_zobrist), e.move_uci)
            if key not in known and key not in new:
                new[key] = RepertoireMove(
                    repertoire=repertoire,
                    from_zobrist=key[0],
                    from_fen=e.from_fen,
                    move_uci=e.move_uci,
                    move_san=e.move_san,
                    to_zobrist=as_bigint(e.to_zobrist),
                    comment=e.comment,
                )
        if len(known) + len(new) > MAX_MOVES:
            raise TooManyMovesError
        added = RepertoireMove.objects.bulk_create(new.values())
        new_repertoire_cards([m for m in added if _users_move(repertoire, m)])
    return added


def _users_move(repertoire: Repertoire, move: RepertoireMove) -> bool:
    return _users_turn(repertoire, move.from_fen.split()[1] == "w")


def _users_turn(repertoire: Repertoire, turn: chess.Color) -> bool:
    return (turn == chess.WHITE) == (repertoire.color == "white")


def remove_move(move: RepertoireMove) -> int:
    """Remove the move, and the moves that only it led to. Returns how many were removed."""
    repertoire = move.repertoire
    with transaction.atomic():
        move.delete()
        rest = list(repertoire.moves.values_list("pk", "from_zobrist", "move_uci", "to_zobrist"))
        keep = reachable([(f, uci, t) for _, f, uci, t in rest], start=as_bigint(START_ZOBRIST))
        orphans = [pk for pk, f, uci, _ in rest if (f, uci) not in keep]
        RepertoireMove.objects.filter(pk__in=orphans).delete()  # their cards go with them
    return 1 + len(orphans)


def set_comment(move: RepertoireMove, *, comment: str) -> RepertoireMove:
    move.comment = comment.strip()
    move.save(update_fields=["comment"])
    return move
