import bz2
import gzip
import threading
from pathlib import Path

import py7zr
import pytest
import zstandard

from homerank.chesslib.archives import UnsupportedFormatError, open_pgn, split_games

GAME_1 = b'[Event "One"]\n[Result "1-0"]\n\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n\n'
GAME_2 = b'[Event "Two"]\n[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1\n\n'
PGN = GAME_1 + GAME_2


def write(path: Path, data: bytes) -> Path:
    suffix = path.suffix
    if suffix == ".gz":
        path.write_bytes(gzip.compress(data))
    elif suffix == ".bz2":
        path.write_bytes(bz2.compress(data))
    elif suffix == ".zst":
        path.write_bytes(zstandard.ZstdCompressor().compress(data))
    elif suffix == ".7z":
        with py7zr.SevenZipFile(path, "w") as archive:
            archive.writestr(data, "games.pgn")
    else:
        path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    "name", ["games.pgn", "games.pgn.gz", "games.pgn.bz2", "games.pgn.zst", "games.7z"]
)
def test_reads_every_format_line_by_line(tmp_path: Path, name: str) -> None:
    path = write(tmp_path / name, PGN)

    with open_pgn(path) as stream:
        lines = list(stream)
        assert stream.progress == 1.0

    assert b"".join(lines) == PGN
    assert all(line.endswith(b"\n") for line in lines)


def test_a_7z_archive_may_hold_several_files(tmp_path: Path) -> None:
    path = tmp_path / "periods.7z"
    with py7zr.SevenZipFile(path, "w") as archive:
        archive.writestr(GAME_1, "1990.pgn")
        archive.writestr(GAME_2, "2000.pgn")

    with open_pgn(path) as stream:
        data = b"".join(stream)

    assert GAME_1 in data
    assert GAME_2 in data


def test_stopping_early_ends_the_7z_reader(tmp_path: Path) -> None:
    path = write(tmp_path / "big.7z", PGN * 2000)

    with open_pgn(path) as stream:
        next(iter(stream))

    assert not [t for t in threading.enumerate() if t.name == "7z big.7z"]


def test_progress_follows_the_file(tmp_path: Path) -> None:
    # Uncompressed: repeated games compress so well that gzip would read the file at once.
    path = write(tmp_path / "big.pgn", PGN * 5000)

    with open_pgn(path) as stream:
        lines = iter(stream)
        for _ in range(1000):
            next(lines)
        halfway = stream.progress

    assert 0 < halfway < 1


@pytest.mark.parametrize("name", ["games.pgn", "games.pgn.zst", "games.7z"])
def test_reading_resumes_at_an_offset(tmp_path: Path, name: str) -> None:
    path = write(tmp_path / name, PGN)

    with open_pgn(path) as stream:
        stream.skip_to(len(GAME_1))
        rest = b"".join(stream)
        assert stream.offset == len(PGN)

    assert rest == GAME_2


def test_other_files_are_refused(tmp_path: Path) -> None:
    path = write(tmp_path / "games.zip", PGN)

    with pytest.raises(UnsupportedFormatError, match=r"games\.zip: not a PGN file"), open_pgn(path):
        pass


# ---------------------------------------------------------------- splitting into games


def test_splits_at_each_games_first_tag_with_offsets() -> None:
    games = list(split_games(iter(PGN.splitlines(keepends=True))))

    assert games == [(0, GAME_1), (len(GAME_1), GAME_2)]


def test_games_need_not_start_with_event() -> None:
    pgn = b'[White "A"]\n\n1. e4 *\n[White "B"]\n[Black "C"]\n1. d4 *\n'

    games = [text for _, text in split_games(iter(pgn.splitlines(keepends=True)))]

    assert games == [b'[White "A"]\n\n1. e4 *\n', b'[White "B"]\n[Black "C"]\n1. d4 *\n']


def test_text_before_the_first_game_is_dropped() -> None:
    pgn = b"; exported by some program\n\n" + GAME_2

    assert list(split_games(iter(pgn.splitlines(keepends=True)))) == [(28, GAME_2)]
