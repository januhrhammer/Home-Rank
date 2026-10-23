# 12. Which Stockfish, and how it gets into the image

Date: 2026-10-23

## Status

Accepted

## Context

Engine analysis runs Stockfish in the worker container. The image is built for amd64 and arm64
(ADR 0007), and Stockfish is GPL-3.0: whoever distributes the program must offer its source
(ADR 0002). Stockfish's speed depends a lot on being built for the CPU's instruction set (AVX2,
AVX-512, NEON …), while one image has to run on many CPUs.

Three ways were considered:

- Debian's `stockfish` package: one `apt-get install`, but often a version or two behind, and
  built for the oldest CPUs of each architecture, so slower.
- Building Stockfish from source in the Dockerfile: the arm64 image is built under emulation in
  the release workflow, where compiling Stockfish takes very long.
- The official release's **"universal"** Linux build: since Stockfish 19 there is one per
  architecture, which contains several builds and picks the fastest one for the CPU it starts
  on. Its archive also contains the full source code and the licence.

## Decision

- The image contains the official universal build of the current Stockfish release (19 when
  this was written), for amd64 or arm64, at `/usr/local/bin/stockfish`.
- `docker/get-stockfish.sh` downloads it and checks it against a checksum pinned in the script.
  The Docker image, CI and local development (`just stockfish`) all use this script, so they all
  run the same version. Renovate proposes new versions; the checksums are updated by hand from
  the release page, and the build fails until they are.
- The release's source code and licence are copied into the image, to
  `/usr/share/doc/stockfish`, which meets the GPL's source requirement for the image itself.
- The backend finds the program through the `STOCKFISH_PATH` setting (default `stockfish`, on
  the PATH in the image).

## Consequences

- The image is about 100 MB larger: the universal program carries several builds and its
  neural networks.
- Tests that run Stockfish are marked `engine`; CI downloads it like developers do.
- Developers on macOS install Stockfish themselves and set `STOCKFISH_PATH`, since the download
  is a Linux program.
