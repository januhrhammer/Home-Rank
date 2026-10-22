import pytest

from homerank.chesslib.players import Side, normalise_name, user_side


@pytest.mark.parametrize(
    "name",
    ["Carlsen, Magnus", "carlsen,magnus", "CARLSEN,  Magnus", " Carlsen ,Magnus "],
)
def test_spelling_variants_are_equal(name: str) -> None:
    assert normalise_name(name) == "carlsen,magnus"


def test_different_names_stay_different() -> None:
    assert normalise_name("Carlsen, M.") != normalise_name("Carlsen, Magnus")
    assert normalise_name("Magnus Carlsen") != normalise_name("Carlsen, Magnus")


def test_unicode_variants_are_equal() -> None:
    composed, decomposed = "M\u00fcller, J\u00fcrgen", "Mu\u0308ller, Ju\u0308rgen"  # ü, or u + ¨

    assert normalise_name(composed) == normalise_name(decomposed)


NAMES = ["Uhrhammer, Jan", "januhrhammer"]


def test_finds_the_users_side() -> None:
    assert user_side("uhrhammer,jan", "Carlsen, Magnus", NAMES) == Side.WHITE
    assert user_side("Hikaru", "JanUhrhammer", NAMES) == Side.BLACK


def test_no_side_when_the_user_didnt_play() -> None:
    assert user_side("Hikaru", "Carlsen, Magnus", NAMES) is None
    assert user_side("Hikaru", "Carlsen, Magnus", []) is None


def test_no_side_in_a_game_against_oneself() -> None:
    assert user_side("januhrhammer", "Uhrhammer, Jan", NAMES) is None


def test_empty_names_match_nothing() -> None:
    assert user_side("", "Carlsen, Magnus", ["", "  "]) is None
