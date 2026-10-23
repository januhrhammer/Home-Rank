"""Reading PGN files, compressed or not, as a stream of lines.

Reference databases come as PGN files of several GB, usually compressed: .pgn.gz, .pgn.bz2,
.pgn.zst or .7z archives. They are read line by line as they are decompressed, never unpacked to
disk or loaded into memory. A stream counts the decompressed bytes it has handed out, so that
an import can note where it is and later resume there (skip_to).
"""

import bz2
import gzip
import io
import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

import py7zr
import py7zr.io
import zstandard

SUFFIXES = (".pgn", ".gz", ".bz2", ".zst", ".7z")
# How much decompressed data the .7z reader thread may be ahead of the reader, in chunks.
_QUEUE_CHUNKS = 64


class UnsupportedFormatError(ValueError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"{path.name}: not a PGN file ({', '.join(SUFFIXES)})")


class PgnStream:
    """The lines of a PGN file, decompressed, with how far the reading got."""

    def __init__(self, lines: Iterator[bytes], progress_of: "ProgressSource") -> None:
        self._lines = lines
        self._progress_of = progress_of
        self.offset = 0  # decompressed bytes handed out so far

    def __iter__(self) -> Iterator[bytes]:
        for line in self._lines:
            self.offset += len(line)
            yield line

    def skip_to(self, offset: int) -> None:
        """Read and drop lines until `offset` decompressed bytes are behind; an import notes
        offsets at game boundaries, so the next line starts a game."""
        for line in self._lines:
            self.offset += len(line)
            if self.offset >= offset:
                return

    @property
    def progress(self) -> float:
        """How much of the file has been read, from 0 to 1."""
        return self._progress_of(self.offset)


class ProgressSource:
    """Tells how far a file has been read: by the compressed file's position where it can be
    asked, otherwise by the decompressed bytes against the decompressed size."""

    def __init__(self, raw: BinaryIO | None, total: int) -> None:
        self._raw = raw
        self._total = max(total, 1)

    def __call__(self, offset: int) -> float:
        position = self._raw.tell() if self._raw is not None else offset
        return min(1.0, position / self._total)


@contextmanager
def open_pgn(path: Path) -> Iterator[PgnStream]:
    """Open a PGN file, decompressing it as it is read, by its suffix."""
    suffix = path.suffix.lower()
    if suffix not in SUFFIXES:
        raise UnsupportedFormatError(path)
    if suffix == ".7z":
        with _open_7z(path) as stream:
            yield stream
        return
    size = path.stat().st_size
    with path.open("rb") as raw:
        if suffix == ".pgn":
            yield PgnStream(iter(raw), ProgressSource(raw, size))
            return
        decompressed: io.BufferedIOBase
        if suffix == ".gz":
            decompressed = gzip.GzipFile(fileobj=raw)
        elif suffix == ".bz2":
            decompressed = bz2.BZ2File(raw)
        else:
            reader = zstandard.ZstdDecompressor().stream_reader(raw, read_across_frames=True)
            decompressed = io.BufferedReader(reader)
        with decompressed:
            yield PgnStream(iter(decompressed), ProgressSource(raw, size))


@contextmanager
def _open_7z(path: Path) -> Iterator[PgnStream]:
    """A .7z archive's PGN files, one after the other. py7zr hands decompressed data to a
    writer; a thread runs the extraction into a queue, which the stream reads lines from."""
    with py7zr.SevenZipFile(path) as archive:
        members = [m for m in archive.list() if not m.is_directory]
        total = sum(m.uncompressed or 0 for m in members)
    chunks: queue.Queue[bytes | BaseException | None] = queue.Queue(maxsize=_QUEUE_CHUNKS)
    stop = threading.Event()

    class _Writer(py7zr.io.Py7zIO):
        def write(self, s: bytes | bytearray) -> int:
            if stop.is_set():
                raise _StoppedError
            chunks.put(bytes(s))
            return len(s)

        def read(self, size: int | None = None) -> bytes:
            return b""

        def seek(self, offset: int, whence: int = 0) -> int:
            return 0

        def flush(self) -> None:
            pass

        def size(self) -> int:
            return 0

    class _Factory(py7zr.io.WriterFactory):
        def create(self, filename: str) -> py7zr.io.Py7zIO:
            return _Writer()

    def extract() -> None:
        try:
            with py7zr.SevenZipFile(path) as archive:
                archive.extractall(factory=_Factory())
        except _StoppedError:
            pass
        except BaseException as error:  # handed to the reader, which raises it
            chunks.put(error)
        finally:
            chunks.put(None)

    def lines() -> Iterator[bytes]:
        pending = b""
        while (chunk := chunks.get()) is not None:
            if isinstance(chunk, BaseException):
                raise chunk
            pending += chunk
            *complete, pending = pending.split(b"\n")
            for line in complete:
                yield line + b"\n"
        if pending:
            yield pending

    thread = threading.Thread(target=extract, name=f"7z {path.name}", daemon=True)
    thread.start()
    try:
        yield PgnStream(lines(), ProgressSource(None, total))
    finally:
        stop.set()
        while thread.is_alive():  # unblock the writer if it waits for room in the queue
            try:
                chunks.get_nowait()
            except queue.Empty:
                thread.join(timeout=0.1)


class _StoppedError(Exception):
    """Ends the extraction when the reader stops early."""


def split_games(lines: Iterator[bytes]) -> Iterator[tuple[int, bytes]]:
    """The games of a stream of PGN lines, each with the offset where it starts.

    A game starts with its first tag line ("[...") after move text, so files whose games don't
    begin with [Event work too. Text before the first tag is dropped. Offsets count bytes from
    the start of the iteration.
    """
    game: list[bytes] = []
    start = offset = 0
    in_movetext = False
    for line in lines:
        is_tag = line.startswith(b"[")
        if is_tag and in_movetext:
            yield start, b"".join(game)
            game, in_movetext = [], False
        if is_tag and not game:
            start = offset
        if game or is_tag:
            game.append(line)
            if not is_tag and line.strip():
                in_movetext = True
        offset += len(line)
    if game:
        yield start, b"".join(game)
