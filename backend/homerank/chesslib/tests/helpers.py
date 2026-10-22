import io

import chess.pgn

SCHOLARS_MATE = """\
[Event "Casual game"]
[Site "Hamburg"]
[Date "2024.03.05"]
[White "Anna"]
[Black "Ben"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""


def parse(pgn: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn))
    assert game is not None
    return game
