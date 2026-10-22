"""Player names: recognising one name written in different ways, and finding the user's side."""

import re
import unicodedata
from collections.abc import Iterable
from enum import StrEnum


class Side(StrEnum):
    WHITE = "white"
    BLACK = "black"


def normalise_name(name: str) -> str:
    """The name in a form in which spelling variants are equal.

    "Carlsen, Magnus", "carlsen,magnus" and "CARLSEN,  Magnus" all become "carlsen,magnus".
    Names that really differ stay different: "Carlsen, M." is not "Carlsen, Magnus".
    """
    name = unicodedata.normalize("NFKC", name).casefold()
    name = re.sub(r"\s*,\s*", ",", name)
    return " ".join(name.split())


def user_side(white: str, black: str, user_names: Iterable[str]) -> Side | None:
    """Which side the user played, given the names they play under; None if not exactly one."""
    names = {normalise_name(name) for name in user_names} - {""}
    plays_white = normalise_name(white) in names
    plays_black = normalise_name(black) in names
    if plays_white == plays_black:
        return None  # neither, or both, as in a game against oneself
    return Side.WHITE if plays_white else Side.BLACK
