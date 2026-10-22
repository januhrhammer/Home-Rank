# 7. Docker images for amd64 and arm64

Date: 2026-10-22

## Status

Accepted

## Context

Many homeservers are ARM machines: a Raspberry Pi 4 or 5, or a small ARM board, running a
64-bit operating system. Others are ordinary x86-64 mini PCs and servers. Home-Rank's image is
built from Debian-based Python and Node.js images, which exist for both architectures, and all
its Python dependencies ship prebuilt wheels for both.

## Decision

Build and publish every image for **linux/amd64 and linux/arm64**, from the first release on.

- CI builds both on every pull request, each on a native GitHub runner, and starts and scans
  both.
- Releases build both in one job, arm64 under emulation, and publish them as one multi-platform
  image: `docker pull` picks the right one.

32-bit ARM (armv7, e.g. a Raspberry Pi with a 32-bit system) is not supported.

## Consequences

- Raspberry Pi owners can install Home-Rank the same way as everyone else.
- Every new dependency must be available for both architectures. This matters most for the
  engine: Stockfish (M3) needs an arm64 build in the image.
- A release takes longer, because arm64 is emulated; CI builds stay fast on native runners.
- Performance on a Pi is a real target: imports and analysis must stay usable there, not only on
  x86 machines.
