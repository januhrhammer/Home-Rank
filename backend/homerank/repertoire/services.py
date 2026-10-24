"""Building repertoires: creating them and their lines, adding and removing moves, importing
PGN. See ADRs 0016 and 0020.

Moves are stored by the position they are played from, with hashes as signed 64-bit numbers
like GamePosition's. Each of the user's own moves gets a review card when it is added. Moves
are added to and removed from a line; every line stays a path from the starting position, and a
move that no line has any more is deleted, with its card.
"""

from collections import defaultdict, deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from http import HTTPStatus

import chess
import chess.pgn
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
from homerank.repertoire.models import Repertoire, RepertoireLine, RepertoireMove
from homerank.training.services import new_repertoire_cards

MAX_REPERTOIRES = 50  # per user
MAX_LINES = 100  # per repertoire
MAX_MOVES = 20_000  # per repertoire
MAIN_LINE = "Main line"  # the line a new repertoire starts with
MAX_PGN_BYTES = 20 * 1024 * 1024  # per imported file
SEED_DEPTH = 12  # plies seeded from the user's games, unless they choose another depth
SEED_MIN_GAMES = 2  # games an opponent's reply needs to be seeded, unless the user chooses


class TooManyRepertoiresError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = f"You can have at most {MAX_REPERTOIRES} repertoires."


class TooManyLinesError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = f"A repertoire can have at most {MAX_LINES} lines."


class LastLineError(DomainError):
    status = HTTPStatus.CONFLICT
    detail = "A repertoire keeps at least one line: delete the repertoire instead."


class InvalidLineOrderError(DomainError):
    detail = "The new order must name each of the repertoire's lines once."


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
    """A new repertoire, with one empty line to add moves to."""
    if Repertoire.objects.filter(user=user).count() >= MAX_REPERTOIRES:
        raise TooManyRepertoiresError
    repertoire = Repertoire(user=user, name=name, color=color)
    with transaction.atomic():
        _save_named(repertoire)
        RepertoireLine.objects.create(repertoire=repertoire, name=MAIN_LINE)
    return repertoire


def rename_repertoire(repertoire: Repertoire, *, name: str) -> Repertoire:
    """Only the name can change: another colour would make the user's moves the opponent's."""
    repertoire.name = name
    _save_named(repertoire)
    return repertoire


def _save_named(named: Repertoire | RepertoireLine) -> None:
    try:
        with transaction.atomic():  # a savepoint, so the failed insert doesn't break the request
            named.save()
    except IntegrityError as error:  # the name is unique per user, or per repertoire
        raise NameTakenError(named.name) from error


# ---------------------------------------------------------------- lines


def create_line(repertoire: Repertoire, *, name: str) -> RepertoireLine:
    """A new, empty line after the repertoire's others."""
    if repertoire.lines.count() >= MAX_LINES:
        raise TooManyLinesError
    last = repertoire.lines.aggregate(last=Max("position"))["last"]
    line = RepertoireLine(repertoire=repertoire, name=name, position=(last or 0) + 1)
    _save_named(line)
    return line


def rename_line(line: RepertoireLine, *, name: str) -> RepertoireLine:
    line.name = name
    _save_named(line)
    return line


def reorder_lines(repertoire: Repertoire, *, line_ids: list[int]) -> None:
    """Put the repertoire's lines in this order; it must name each of them once."""
    lines = {line.pk: line for line in repertoire.lines.all()}
    if sorted(line_ids) != sorted(lines):
        raise InvalidLineOrderError
    for position, pk in enumerate(line_ids):
        lines[pk].position = position
    RepertoireLine.objects.bulk_update(lines.values(), ["position"])


def delete_line(line: RepertoireLine) -> int:
    """Delete the line, and the moves no other line has. Returns how many moves were deleted."""
    repertoire = line.repertoire
    if repertoire.lines.count() <= 1:
        raise LastLineError
    with transaction.atomic():
        line.delete()
        return _delete_unlined(repertoire)


def _first_line(repertoire: Repertoire) -> RepertoireLine:
    """Where moves go when no line is named: until the API names lines (ADR 0020, step 2)."""
    return repertoire.lines.order_by("position", "pk")[0]


def _delete_unlined(repertoire: Repertoire) -> int:
    """Delete the moves no line has any more, and with them their cards."""
    unlined = repertoire.moves.filter(lines__isnull=True)
    count = unlined.count()
    unlined.delete()
    return count


# ---------------------------------------------------------------- moves


def add_move(
    repertoire: Repertoire, *, fen: str, move_uci: str, line: RepertoireLine | None = None
) -> RepertoireMove:
    """Add a move to a line, in a position the line reaches. A move the line already has is
    returned as it is; one another line has joins this one."""
    line = line or _first_line(repertoire)
    try:
        board = chess.Board(fen)
    except ValueError as error:
        raise InvalidPositionError from error
    if not board.is_valid():
        raise InvalidPositionError
    zobrist = chess.polyglot.zobrist_hash(board)
    existing = line.moves.filter(from_zobrist=as_bigint(zobrist), move_uci=move_uci).first()
    if existing is not None:
        return existing
    reached = line.moves.filter(to_zobrist=as_bigint(zobrist)).exists()
    if zobrist != START_ZOBRIST and not reached:
        raise PositionNotInRepertoireError
    try:
        move = chess.Move.from_uci(move_uci)
    except ValueError as error:
        raise IllegalMoveError from error
    if not board.is_legal(move):
        raise IllegalMoveError
    _add_edges(repertoire, [edge(board, move)], line)
    return repertoire.moves.get(from_zobrist=as_bigint(zobrist), move_uci=move_uci)


@dataclass(frozen=True)
class PgnImport:
    moves_added: int
    games_read: int
    games_skipped: int  # unreadable, or not from the starting position
    lines_created: int = 0


def import_pgn(
    repertoire: Repertoire, *, lines: Iterable[bytes], into: RepertoireLine | None = None
) -> PgnImport:
    """Add every move of a PGN file's games, variations included, to a line: those the
    repertoire doesn't have yet with the comment after them in the PGN, those it has as they
    are. The file comes as its lines, e.g. an uploaded file, and is read one game at a time."""
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
    added = _add_edges(repertoire, edges, into or _first_line(repertoire))
    return PgnImport(moves_added=len(added), games_read=read, games_skipped=skipped)


def import_pgn_chapters(repertoire: Repertoire, *, lines: Iterable[bytes]) -> PgnImport:
    """Add each game of a PGN file as a new line, as courses and Lichess studies come: one
    chapter per game. A line is named after the game's ChapterName or Event header, or else
    "Chapter n"; a name the repertoire has already gets a number."""
    added = read = skipped = 0
    taken = set(repertoire.lines.values_list("name", flat=True))
    with transaction.atomic():
        for item in read_pgn(_limited(lines)):
            if not isinstance(item, PgnGame):
                skipped += 1
                continue
            try:
                edges = pgn_edges(item.game)
            except NotFromStartError:
                skipped += 1
                continue
            read += 1
            name = _free_name(_chapter_name(item.game.headers, read), taken)
            taken.add(name)
            added += len(_add_edges(repertoire, edges, create_line(repertoire, name=name)))
    return PgnImport(moves_added=added, games_read=read, games_skipped=skipped, lines_created=read)


def _chapter_name(headers: chess.pgn.Headers, number: int) -> str:
    for key in ("ChapterName", "Event"):
        value = headers.get(key, "").strip()
        if value and value != "?":
            return value[:90]  # room for a number if the name is taken
    return f"Chapter {number}"


def _free_name(name: str, taken: set[str]) -> str:
    number = 2
    free = name
    while free in taken:
        free = f"{name} ({number})"
        number += 1
    return free


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
    repertoire: Repertoire,
    *,
    depth: int = SEED_DEPTH,
    min_games: int = SEED_MIN_GAMES,
    into: RepertoireLine | None = None,
) -> int:
    """Add to a line what the user plays in their games with the repertoire's colour, up to
    depth plies: where they are to move, their most played move (ties: the more recently
    played); where the opponent is, every reply played in at least min_games games. Where the
    line already has a move of the user's, that move is followed instead. Only adds moves;
    returns how many are new to the repertoire."""
    line = into or _first_line(repertoire)
    played = _played_moves(repertoire, depth)
    known = defaultdict(list)
    for from_zobrist, move_uci in line.moves.values_list("from_zobrist", "move_uci"):
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
    return len(_add_edges(repertoire, edges, line))


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


def _add_edges(
    repertoire: Repertoire, edges: list[Edge], line: RepertoireLine
) -> list[RepertoireMove]:
    """Store the edges the repertoire doesn't have yet, with cards for the user's own moves,
    and put all of them into the line. Returns the moves new to the repertoire."""
    with transaction.atomic():
        # Locked, so that two requests at once can't both pass the size check.
        Repertoire.objects.select_for_update().filter(pk=repertoire.pk).get()
        known = {
            (f, uci): pk
            for pk, f, uci in repertoire.moves.values_list("pk", "from_zobrist", "move_uci")
        }
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
        ids = {**known, **{(m.from_zobrist, m.move_uci): m.pk for m in added}}
        line.moves.add(*{ids[(as_bigint(e.from_zobrist), e.move_uci)] for e in edges})
    return added


def _users_move(repertoire: Repertoire, move: RepertoireMove) -> bool:
    return _users_turn(repertoire, move.from_fen.split()[1] == "w")


def _users_turn(repertoire: Repertoire, turn: chess.Color) -> bool:
    return (turn == chess.WHITE) == (repertoire.color == "white")


def remove_move(move: RepertoireMove, *, line: RepertoireLine | None = None) -> int:
    """Take the move out of the line, or out of every line, together with the moves the line
    reached only through it; moves left in no line are deleted, with their cards. Returns how
    many moves were taken out."""
    repertoire = move.repertoire
    with transaction.atomic():
        taken = {move.pk} if line is None else set()
        for each in [line] if line is not None else list(move.lines.all()):
            if not each.moves.filter(pk=move.pk).exists():
                continue
            each.moves.remove(move)
            rest = list(each.moves.values_list("pk", "from_zobrist", "move_uci", "to_zobrist"))
            keep = reachable([(f, uci, t) for _, f, uci, t in rest], start=as_bigint(START_ZOBRIST))
            orphans = [pk for pk, f, uci, _ in rest if (f, uci) not in keep]
            each.moves.remove(*orphans)
            taken.update([move.pk, *orphans])
        _delete_unlined(repertoire)
    return len(taken)


def set_comment(move: RepertoireMove, *, comment: str) -> RepertoireMove:
    move.comment = comment.strip()
    move.save(update_fields=["comment"])
    return move
