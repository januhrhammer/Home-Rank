"""Reading a user's repertoires. Every query is filtered by the user."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.db import connection
from django.db.models import Count, QuerySet
from django.shortcuts import get_object_or_404

from homerank.accounts.models import User
from homerank.chesslib.positions import as_bigint
from homerank.chesslib.repertoire import START_ZOBRIST
from homerank.repertoire.models import Repertoire, RepertoireMove

# Games listed per gap at most; the count covers all of them.
GAP_GAMES = 20
# Plies a repertoire can reach at most, for the gap report's search.
MAX_REACH = 200


def repertoires(*, user: User) -> QuerySet[Repertoire]:
    """The user's repertoires by name, each with its number of moves."""
    return (
        Repertoire.objects.filter(user=user)
        .annotate(move_count=Count("moves"))
        .order_by("name", "pk")
    )


def repertoire(*, user: User, repertoire_id: int) -> Repertoire:
    """One of the user's repertoires; 404 for anyone else's."""
    return get_object_or_404(Repertoire.objects.filter(user=user), pk=repertoire_id)


def moves(repertoire: Repertoire) -> QuerySet[RepertoireMove]:
    """All of the repertoire's moves, in the order they were added."""
    return repertoire.moves.order_by("pk")


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
    SELECT p.game_id, min(p.ply) AS ply
    FROM games_gameposition p
    JOIN games_game g ON g.id = p.game_id
    WHERE p.user_id = %(user)s AND g.user_color = %(color)s AND p.ply <= %(reach)s
      AND NOT EXISTS (
          SELECT 1 FROM repertoire_repertoiremove m
          WHERE m.repertoire_id = %(repertoire)s
            AND m.from_zobrist = p.zobrist AND m.move_uci = p.move_uci
      )
    GROUP BY p.game_id
)
SELECT p.zobrist, p.move_uci, min(p.move_san), count(*),
       (array_agg(p.game_id ORDER BY g.date DESC NULLS LAST, g.id DESC))[1:%(listed)s],
       max(g.date)
FROM first_out f
JOIN games_gameposition p ON p.game_id = f.game_id AND p.ply = f.ply
JOIN games_game g ON g.id = f.game_id
WHERE p.move_uci <> ''
  AND p.zobrist IN (
      SELECT from_zobrist FROM repertoire_repertoiremove WHERE repertoire_id = %(repertoire)s
  )
GROUP BY p.zobrist, p.move_uci
ORDER BY count(*) DESC, p.move_uci
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
    """The deepest ply at which a move of the repertoire can be played, following its moves
    (from, to) from the starting position; at most MAX_REACH."""
    moves_from = defaultdict(list)
    for from_zobrist, to_zobrist in moves:
        moves_from[from_zobrist].append(to_zobrist)
    deepest = 0
    level = {as_bigint(START_ZOBRIST)}
    for ply in range(MAX_REACH):
        level = {after for position in level for after in moves_from[position]}
        if not level:
            break
        deepest = ply
    return deepest
