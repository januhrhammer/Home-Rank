import json
from pathlib import Path

import pytest

from homerank.engine.evaluation import (
    MoveClass,
    classify,
    game_accuracy,
    move_accuracy,
    win_percent,
)

EVEN = 50  # winning chances in an equal position
WON = 97  # about what a mate or a ten-pawn lead gives
LOST = 100 - WON
PERFECT = 100  # accuracy

# ---------------------------------------------------------------- winning chances


def test_an_equal_position_is_fifty_fifty() -> None:
    assert win_percent(0, None, white_to_move=True) == EVEN


def test_a_pawn_up_is_about_59_percent_as_on_lichess() -> None:
    assert win_percent(100, None, white_to_move=True) == pytest.approx(59.10, abs=0.01)
    assert win_percent(-100, None, white_to_move=True) == pytest.approx(40.90, abs=0.01)


def test_scores_beyond_ten_pawns_count_as_ten_pawns() -> None:
    ten_pawns = win_percent(1000, None, white_to_move=True)

    assert win_percent(2500, None, white_to_move=True) == ten_pawns
    assert ten_pawns == pytest.approx(97.54, abs=0.01)


def test_a_mate_counts_as_the_largest_score() -> None:
    assert win_percent(None, 3, white_to_move=True) == win_percent(1000, None, white_to_move=True)
    assert win_percent(None, -1, white_to_move=True) == win_percent(-1000, None, white_to_move=True)


def test_mate_zero_means_the_side_to_move_is_checkmated() -> None:
    assert win_percent(None, 0, white_to_move=False) > WON  # Black is mated: White won
    assert win_percent(None, 0, white_to_move=True) < LOST


def test_a_score_needs_cp_or_mate() -> None:
    with pytest.raises(ValueError, match="cp or mate"):
        win_percent(None, None, white_to_move=True)


# ---------------------------------------------------------------- mistakes


@pytest.mark.parametrize(
    ("loss", "expected"),
    [
        (9.9, MoveClass.GOOD),
        (10, MoveClass.INACCURACY),
        (20, MoveClass.MISTAKE),
        (30, MoveClass.BLUNDER),
        (-15, MoveClass.GOOD),  # the move made things better
    ],
)
def test_moves_are_classified_by_the_chances_they_lose(loss: float, expected: MoveClass) -> None:
    assert classify(60, 60 - loss, white_moved=True) == expected
    assert classify(40, 40 + loss, white_moved=False) == expected  # Black's chances fall


def test_thresholds_can_be_changed() -> None:
    strict = (5.0, 10.0, 15.0)

    assert classify(50, 44, white_moved=True, thresholds=strict) == MoveClass.INACCURACY
    assert classify(50, 34, white_moved=True, thresholds=strict) == MoveClass.BLUNDER


# ---------------------------------------------------------------- accuracy


def test_a_move_that_keeps_the_chances_is_fully_accurate() -> None:
    assert move_accuracy(60, 60) == PERFECT
    assert move_accuracy(60, 70) == PERFECT


def test_losing_chances_lowers_accuracy_like_on_lichess() -> None:
    assert move_accuracy(60, 50) == pytest.approx(64.58, abs=0.01)
    assert move_accuracy(100, 0) == 0  # never below 0


def test_a_game_without_moves_has_no_accuracy() -> None:
    assert game_accuracy([50.0]) is None


def test_a_game_of_perfect_moves_is_fully_accurate() -> None:
    assert game_accuracy([50.0] * 41) == (100, 100)


def test_a_blunder_lowers_only_its_players_accuracy() -> None:
    wins = [50.0] * 21
    # White's 6th move (the 11th half-move, ply 10 → 11) throws the game away.
    wins[11:] = [15.0] * 10

    result = game_accuracy(wins)

    assert result is not None
    white, black = result
    assert white < PERFECT - 10
    assert black == PERFECT


def test_the_side_to_move_first_can_be_black() -> None:
    wins = [50.0, 20.0, 20.0]  # the first move, Black's, is good for Black

    assert game_accuracy(wins, white_first=False) == (100, 100)
    result = game_accuracy(wins, white_first=True)  # as White's move it would be bad
    assert result is not None
    assert result[0] < PERFECT


def test_accuracy_matches_lichess_on_real_games() -> None:
    # Three analysed Lichess games: the evals after each move, and the accuracies Lichess
    # showed for them (rounded to whole percent). Recorded from Lichess's game export.
    games = json.loads((Path(__file__).parent / "fixtures" / "lichess_accuracy.json").read_text())
    for recorded in games:
        # Lichess counts the starting position as +0.15.
        wins = [win_percent(15, None, white_to_move=True)]
        for i, score in enumerate(recorded["evals"]):
            white_to_move = i % 2 == 1  # after White's move, Black is to move
            wins.append(
                win_percent(score.get("eval"), score.get("mate"), white_to_move=white_to_move)
            )

        result = game_accuracy(wins)

        assert result is not None
        white, black = result
        assert round(white) == recorded["white_accuracy"]
        assert round(black) == recorded["black_accuracy"]
