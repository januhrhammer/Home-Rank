"""Reading a user's repertoires. Every query is filtered by the user."""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from django.db import connection
from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone

from homerank.accounts.models import User
from homerank.chesslib.positions import as_bigint
from homerank.chesslib.repertoire import START_ZOBRIST
from homerank.repertoire.models import Repertoire, RepertoireLine, RepertoireMove
from homerank.training.models import ReviewCard

# Games listed per gap at most; the count covers all of them.
GAP_GAMES = 20


def repertoires(*, user: User) -> QuerySet[Repertoire]:
    """The user's repertoires by name, each with its number of moves and of cards due now."""
    due = Q(moves__card__due_at__lte=timezone.now())
    return (
        Repertoire.objects.filter(user=user)
        .annotate(move_count=Count("moves"), due=Count("moves__card", filter=due))
        .order_by("name", "pk")
    )


def repertoire(*, user: User, repertoire_id: int) -> Repertoire:
    """One of the user's repertoires; 404 for anyone else's."""
    return get_object_or_404(Repertoire.objects.filter(user=user), pk=repertoire_id)


def moves(repertoire: Repertoire) -> QuerySet[RepertoireMove]:
    """All of the repertoire's moves, in the order they were added."""
    return repertoire.moves.order_by("pk")


def lines(repertoire: Repertoire) -> QuerySet[RepertoireLine]:
    """The repertoire's lines in their order, each with its number of moves."""
    return repertoire.lines.annotate(move_count=Count("moves")).order_by("position", "pk")


def line(*, user: User, repertoire_id: int, line_id: int) -> RepertoireLine:
    """One line of one of the user's repertoires; 404 for anyone else's."""
    return get_object_or_404(
        RepertoireLine.objects.filter(
            repertoire__user=user, repertoire_id=repertoire_id
        ).select_related("repertoire"),
        pk=line_id,
    )


@dataclass(frozen=True)
class ConflictChoice:
    move_uci: str
    move_san: str
    lines: list[str]  # the lines that play it, in their order


@dataclass(frozen=True)
class Conflict:
    """A position where lines of the repertoire play different moves of the user's."""

    fen: str
    choices: list[ConflictChoice]


def conflicts(repertoire: Repertoire) -> list[Conflict]:
    """Positions where one line plays a move of the user's that another line doesn't, and the
    other line one the first doesn't. Alternatives within a line are no conflict (ADR 0020)."""
    users_turn = "w" if repertoire.color == "white" else "b"
    order = {pk: n for n, pk in enumerate(lines(repertoire).values_list("pk", flat=True))}
    by_position: defaultdict[int, list[RepertoireMove]] = defaultdict(list)
    for move in repertoire.moves.prefetch_related("lines").order_by("pk"):
        if move.from_fen.split()[1] == users_turn:
            by_position[move.from_zobrist].append(move)
    found = []
    for moves in by_position.values():
        played = {m.pk: {line.pk for line in m.lines.all()} for m in moves}
        if any(
            played[a.pk] - played[b.pk] and played[b.pk] - played[a.pk]
            for a in moves
            for b in moves
            if a.pk < b.pk
        ):
            choices = [
                ConflictChoice(
                    move_uci=m.move_uci,
                    move_san=m.move_san,
                    lines=[line.name for line in sorted(m.lines.all(), key=lambda x: order[x.pk])],
                )
                for m in moves
            ]
            found.append(Conflict(fen=moves[0].from_fen, choices=choices))
    return found


def move(*, user: User, repertoire_id: int, move_id: int) -> RepertoireMove:
    """One move of one of the user's repertoires; 404 for anyone else's."""
    return get_object_or_404(
        RepertoireMove.objects.filter(
            repertoire__user=user, repertoire_id=repertoire_id
        ).select_related("repertoire"),
        pk=move_id,
    )


# ---------------------------------------------------------------- gap report


@dataclass
class Gap:
    """A move in the user's games that left the repertoire where it still had moves."""

    fen: str  # the position, with the repertoire's own moves from it
    move_uci: str
    move_san: str
    by_user: bool  # the user's own move ("left the repertoire"), or the opponent's ("not covered")
    games: int
    game_ids: list[int]  # the most recent GAP_GAMES of them, newest first
    last_played: date | None


# For each of the user's games with the repertoire's colour, the first ply whose move isn't in
# the repertoire; then those whose position still had moves in the repertoire, grouped by
# position and move. A game that ends inside the repertoire has no move there (""), and one
# from another starting position leaves it at ply 0, where the repertoire has no moves.
_GAPS_SQL = """
WITH first_out AS (
    SELECT DISTINCT ON (p.game_id) p.game_id, p.zobrist, p.move_uci, p.move_san
    FROM games_gameposition p
    JOIN games_game g ON g.id = p.game_id
    WHERE p.user_id = %(user)s AND g.user_color = %(color)s AND p.ply <= %(reach)s
      -- NOT IN, not NOT EXISTS: it is always looked up in a hash table of the repertoire's
      -- moves. With NOT EXISTS, a repertoire just imported (no statistics yet: "1 row") was
      -- compared with every position one by one, 14 s instead of 0.2 s for 100,000 games.
      AND (p.zobrist, p.move_uci) NOT IN (
          SELECT from_zobrist, move_uci FROM repertoire_repertoiremove
          WHERE repertoire_id = %(repertoire)s
      )
    ORDER BY p.game_id, p.ply
)
SELECT f.zobrist, f.move_uci, min(f.move_san), count(*),
       (array_agg(f.game_id ORDER BY g.date DESC NULLS LAST, g.id DESC))[1:%(listed)s],
       max(g.date)
FROM first_out f
JOIN games_game g ON g.id = f.game_id
WHERE f.move_uci <> ''
  AND f.zobrist IN (
      SELECT from_zobrist FROM repertoire_repertoiremove WHERE repertoire_id = %(repertoire)s
  )
GROUP BY f.zobrist, f.move_uci
ORDER BY count(*) DESC, f.move_uci
"""


def gaps(repertoire: Repertoire) -> list[Gap]:
    """Where the user's games left the repertoire, most frequent first."""
    rows = list(repertoire.moves.values_list("from_zobrist", "from_fen", "to_zobrist"))
    if not rows:
        return []
    fens = {from_zobrist: fen for from_zobrist, fen, _ in rows}
    params: dict[str, int | str] = {
        "user": repertoire.user_id,
        "color": repertoire.color,
        "repertoire": repertoire.pk,
        "reach": _reach([(f, t) for f, _, t in rows]),
        "listed": GAP_GAMES,
    }
    with connection.cursor() as cursor:
        cursor.execute(_GAPS_SQL, params)
        found = cursor.fetchall()
    user_white = repertoire.color == "white"
    return [
        Gap(
            fen=fens[zobrist],
            move_uci=move_uci,
            move_san=move_san,
            by_user=(fens[zobrist].split()[1] == "w") == user_white,
            games=games,
            game_ids=game_ids,
            last_played=last_played,
        )
        for zobrist, move_uci, move_san, games, game_ids, last_played in found
    ]


def _reach(moves: list[tuple[int, int]]) -> int:
    """The deepest ply at which a game can play a move of the repertoire, following its moves
    (from, to) from the starting position. Moves that lead back to a position on the way there
    are left out: a game going round such a circle is followed only that far."""
    moves_from = defaultdict(list)
    for from_zobrist, to_zobrist in moves:
        moves_from[from_zobrist].append(to_zobrist)
    start = as_bigint(START_ZOBRIST)
    # Depth first, without recursion: how many plies the repertoire goes on from each position.
    longest: dict[int, int] = {}
    on_path = {start}
    stack = [(start, iter(moves_from[start]))]
    while stack:
        position, unvisited = stack[-1]
        for after in unvisited:
            if after not in on_path and after not in longest:
                on_path.add(after)
                stack.append((after, iter(moves_from[after])))
                break
        else:
            stack.pop()
            on_path.discard(position)
            longest[position] = max(
                (longest[after] + 1 for after in moves_from[position] if after in longest),
                default=0,
            )
    return longest[start] - 1


# ---------------------------------------------------------------- drill


@dataclass
class DrillStep:
    """A move of a drill: the user's own, to be asked for (with its card), or the opponent's,
    to be played for them."""

    move_id: int
    fen: str  # the position the move is played from
    move_uci: str
    move_san: str
    comment: str
    card_id: int | None  # None for the opponent's moves
    due: bool
    # The repertoire's other moves of the user's in this position: playing one isn't wrong,
    # the user is asked for this one instead (ADR 0016).
    other_moves: list[str] = field(default_factory=list)


@dataclass
class DueDrill:
    step: DrillStep | None  # the card due longest, None if none is due
    last_move_uci: str  # the move that led to its position ("" at the start), to show it
    due: int  # how many of the repertoire's cards are due now


def next_due(repertoire: Repertoire) -> DueDrill:
    """The repertoire's card due longest, in its position."""
    due = ReviewCard.objects.filter(
        repertoire_move__repertoire=repertoire, due_at__lte=timezone.now()
    ).select_related("repertoire_move")
    card = due.order_by("due_at", "pk").first()
    if card is None or card.repertoire_move is None:
        return DueDrill(step=None, last_move_uci="", due=0)
    move = card.repertoire_move
    before = repertoire.moves.filter(to_zobrist=move.from_zobrist).order_by("pk").first()
    graph = _Graph(repertoire)
    return DueDrill(
        step=graph.step(move),
        last_move_uci=before.move_uci if before is not None else "",
        due=due.count(),
    )


def drill_line(repertoire: Repertoire, *, through: RepertoireMove | None = None) -> list[DrillStep]:
    """A line from the starting position to the end of the repertoire: through the given move,
    or else through the card due longest. From there on it follows, at each position, the
    move whose card (or, for the opponent's moves, the next card) is due first."""
    graph = _Graph(repertoire)
    if through is None:
        through = graph.most_urgent()
    path = graph.path_to(through) if through is not None else []
    seen = {as_bigint(START_ZOBRIST), *(m.to_zobrist for m in path)}
    position = path[-1].to_zobrist if path else as_bigint(START_ZOBRIST)
    while graph.moves_from[position]:
        move = min(graph.moves_from[position], key=lambda m: (graph.urgency(m), m.pk))
        path.append(move)
        if move.to_zobrist in seen:
            break  # back to a position the line has passed: it would go round in circles
        seen.add(move.to_zobrist)
        position = move.to_zobrist
    return [graph.step(m) for m in path]


_NEVER = datetime.max.replace(tzinfo=UTC)


class _Graph:
    """A repertoire's moves, by the positions they join, with their cards."""

    def __init__(self, repertoire: Repertoire) -> None:
        self.moves_from: defaultdict[int, list[RepertoireMove]] = defaultdict(list)
        self.cards: dict[int, ReviewCard] = {}  # by move id
        for move in repertoire.moves.select_related("card").order_by("pk"):
            self.moves_from[move.from_zobrist].append(move)
            card = getattr(move, "card", None)
            if card is not None:
                self.cards[move.pk] = card
        self.now = timezone.now()

    def step(self, move: RepertoireMove) -> DrillStep:
        card = self.cards.get(move.pk)
        others = [
            m.move_uci
            for m in self.moves_from[move.from_zobrist]
            if m.pk != move.pk and m.pk in self.cards
        ]
        return DrillStep(
            move_id=move.pk,
            fen=move.from_fen,
            move_uci=move.move_uci,
            move_san=move.move_san,
            comment=move.comment,
            card_id=card.pk if card is not None else None,
            due=card is not None and card.due_at <= self.now,
            other_moves=others if card is not None else [],
        )

    def urgency(self, move: RepertoireMove) -> datetime:
        """When the move's card is due; for the opponent's moves, the first card after it."""
        if move.pk in self.cards:
            return self.cards[move.pk].due_at
        after = [
            self.cards[m.pk].due_at for m in self.moves_from[move.to_zobrist] if m.pk in self.cards
        ]
        return min(after, default=_NEVER)

    def most_urgent(self) -> RepertoireMove | None:
        moves = [m for ms in self.moves_from.values() for m in ms if m.pk in self.cards]
        return min(moves, key=lambda m: (self.cards[m.pk].due_at, m.pk), default=None)

    def path_to(self, target: RepertoireMove) -> list[RepertoireMove]:
        """The shortest line of moves from the starting position that ends with the move."""
        start = as_bigint(START_ZOBRIST)
        came_by: dict[int, RepertoireMove | None] = {start: None}
        todo = deque([start])
        while todo and target.from_zobrist not in came_by:
            position = todo.popleft()
            for move in self.moves_from[position]:
                if move.to_zobrist not in came_by:
                    came_by[move.to_zobrist] = move
                    todo.append(move.to_zobrist)
        path = [target]
        previous = came_by.get(target.from_zobrist)
        while previous is not None:
            path.append(previous)
            previous = came_by[previous.from_zobrist]
        return path[::-1]
