from collections.abc import Iterator

import pytest

from homerank.chesslib.pgn import PgnError, PgnGame, read_pgn

SCHOLARS_MATE = """\
[Event "Casual game"]
[White "Anna"]
[Black "Ben"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""

ANNOTATED = """\
[Event "Lesson"]
[White "Carla"]
[Black "Dan"]
[Result "*"]

1. d4 {A comment that runs
[over a line that starts with a bracket]} 1... d5 (1... Nf6 2. c4 $1) 2. c4 *
"""


def lines(text: str, encoding: str = "utf-8") -> list[bytes]:
    """A PGN text split into lines as bytes, as reading a file in binary mode returns them."""
    return text.encode(encoding).splitlines(keepends=True)


def read(text: str) -> list[PgnGame | PgnError]:
    return list(read_pgn(lines(text)))


def test_reads_each_game_with_its_text_and_line() -> None:
    first, second = read(SCHOLARS_MATE + "\n" + ANNOTATED)

    assert isinstance(first, PgnGame)
    assert first.line == 1
    assert first.pgn == SCHOLARS_MATE
    assert first.game.headers["White"] == "Anna"
    assert first.game.end().board().is_checkmate()

    assert isinstance(second, PgnGame)
    assert second.line == SCHOLARS_MATE.count("\n") + 2
    assert second.pgn == ANNOTATED


def test_keeps_comments_and_variations() -> None:
    (result,) = read(ANNOTATED)

    assert isinstance(result, PgnGame)
    first_move = result.game.next()
    assert first_move is not None
    assert first_move.comment == "A comment that runs\n[over a line that starts with a bracket]"
    reply = first_move.variations
    assert [node.san() for node in reply] == ["d5", "Nf6"]


def test_skips_blank_lines_between_games() -> None:
    before, between = "\n\n", "\n\n\n"

    first, second = read(before + SCHOLARS_MATE + between + SCHOLARS_MATE)

    assert first.line == len(before) + 1
    assert second.line == first.line + SCHOLARS_MATE.count("\n") + len(between)
    assert first.pgn == second.pgn == SCHOLARS_MATE


def test_reports_an_illegal_move_and_reads_on() -> None:
    broken = SCHOLARS_MATE.replace("Qxf7#", "Qxf8")

    error, game = read(broken + "\n" + ANNOTATED)

    assert isinstance(error, PgnError)
    assert error.line == 1
    assert error.reason.startswith("illegal san: 'Qxf8'")
    assert error.pgn == broken
    assert isinstance(game, PgnGame)


@pytest.mark.parametrize(
    ("movetext", "unknown"),
    [
        ("4. Qxf9 1-0", "Qxf9"),  # a square that doesn't exist
        ("4. Qxf7# xyz 1-0", "xyz"),
        ("4. Qxf7# 1-O", "1-O"),
    ],
)
def test_reports_text_that_python_chess_would_skip(movetext: str, unknown: str) -> None:
    """Without this check, the game would be stored without the skipped move."""
    (error,) = read(SCHOLARS_MATE.replace("4. Qxf7# 1-0", movetext))

    assert isinstance(error, PgnError)
    assert error.reason == f"not a move: {unknown!r}"


def test_accepts_common_notation() -> None:
    movetext = """\
1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 d6 8.c3 O-O 9.h3 Nb8
10.d4 Nbd7 11.c4 c6 12.cxb5 axb5 13.Nc3 Bb7 14.Bg5 b4 15.Nb1 h6 16.Bh4 c5 17.dxe5 Nxe4
18.Bxe7 Qxe7 19.exd6 Qf6 20.Nbd2 Nxd6 21.Nc4 Nxc4 22.Bxc4 Nb6 23.Ne5 Rae8 24.Bxf7+ Rxf7
25.Nxf7 Rxe1+ 26.Qxe1 Kxf7 27.Qe3 Qg5 28.Qxg5 hxg5 29.b3 Ke6 30.a3 Kd6 31.axb4 cxb4 32.Ra5 Nd5
33.f3 Bc8 34.Kf2 Bf5 35.Ra7 g6 36.Ra6+ Kc5 37.Ke1 Nf4 38.g3 Nxh3 39.Kd2 Kb5 40.Rd6 Kc5
41.Ra6 Nf2 42.g4 Bd3 43.Re6 1/2-1/2
"""
    extras = """\
1. e4 $1 e5!? 2. f4 exf4 3. g4 fxg3 e.p. ; a comment to the end of the line
% an escaped line
4. Nf3 (4. hxg3) 4... gxh2 5. Rxh2 *
"""
    for text in (movetext, extras):
        (result,) = read('[Event "?"]\n\n' + text)
        assert isinstance(result, PgnGame), result


def test_reports_unsupported_variants() -> None:
    atomic = SCHOLARS_MATE.replace('[Result "1-0"]', '[Result "1-0"]\n[Variant "Atomic"]')

    (error,) = read(atomic)

    assert isinstance(error, PgnError)
    assert error.reason == "unsupported variant: Atomic"


def test_reads_chess960() -> None:
    chess960 = """\
[Variant "Chess960"]
[FEN "bqnrkrnb/pppppppp/8/8/8/8/PPPPPPPP/BQNRKRNB w KQkq - 0 1"]
[SetUp "1"]

1. e4 e5 *
"""
    (result,) = read(chess960)

    assert isinstance(result, PgnGame)


@pytest.mark.parametrize(
    ("encoding", "name"),
    [("utf-8", "Lukáš Černý"), ("cp1252", "Jürgen Müller")],
)
def test_decodes_utf8_and_windows_1252(encoding: str, name: str) -> None:
    text = SCHOLARS_MATE.replace("Anna", name)

    (result,) = read_pgn(lines(text, encoding))

    assert isinstance(result, PgnGame)
    assert result.game.headers["White"] == name
    assert result.pgn == text


def test_ignores_a_byte_order_mark() -> None:
    (result,) = read_pgn(lines("﻿" + SCHOLARS_MATE))

    assert isinstance(result, PgnGame)
    assert result.pgn == SCHOLARS_MATE
    assert result.game.headers["Event"] == "Casual game"


def test_reads_a_last_game_without_a_final_newline() -> None:
    (result,) = read(SCHOLARS_MATE.rstrip("\n"))

    assert isinstance(result, PgnGame)
    assert result.pgn == SCHOLARS_MATE


def test_an_empty_file_has_no_games() -> None:
    assert read("") == []
    assert read("\n\n  \n") == []


def test_reads_lazily() -> None:
    """Only the lines up to the first game are read before it is handed out."""
    consumed: list[bytes] = []

    def file_lines() -> Iterator[bytes]:
        for line in lines(SCHOLARS_MATE + "\n" + ANNOTATED):
            consumed.append(line)
            yield line

    games = read_pgn(file_lines())
    next(games)

    assert len(consumed) == SCHOLARS_MATE.count("\n") + 1


def test_doesnt_log_broken_games(caplog: pytest.LogCaptureFixture) -> None:
    """read_pgn reports broken games itself; python-chess would also log each one as an error."""
    read(SCHOLARS_MATE.replace("Qxf7#", "Qxf8"))

    assert caplog.records == []
