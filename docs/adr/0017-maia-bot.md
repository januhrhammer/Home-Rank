# 17. Maia as a human-like opponent, and how it runs

Date: 2026-10-23

## Status

Accepted (maintainer, 2026-10-23)

## Context

M8 lets users play positions out against a bot. The maintainer wants one that plays like a
person of a chosen rating, not like an engine with its strength turned down, and chose to run
it on the server. [Maia](https://github.com/CSSLab/maia3) is such a model: trained on Lichess
games (Jan 2023 – Jul 2025) to predict the move a player of a given rating makes. Maia-3 is the
current version; its 5M-parameter model is the one meant for CPUs. Code and weights are
AGPL-3.0, like Home-Rank (ADR 0002).

The official way to run it is a Python UCI engine on PyTorch. PyTorch alone is about 1 GB, more
than the whole image today. A spike (2026-10-23) tried the alternative: the same model as ONNX,
run by onnxruntime.

- **Export:** the official checkpoint (`UofTCSSLab/Maia3-5M`, `maia3-5m.pt`) exports to ONNX
  with PyTorch's classic exporter at opset 17 once `torch.nn.RMSNorm` is written out as its
  formula; a batch of one position (the newer exporter fails on the attention layers).
- **Same moves:** on 300 positions from real games (with their last 8 positions as history,
  as the model expects) at ratings 800–2300, a board encoder written with NumPy and
  python-chess only gives bit-identical input to Maia's own, and the ONNX model picks the same
  top move as PyTorch every time; move probabilities differ by at most 6·10⁻⁶.
- **Cost:** 21 MB model, onnxruntime about 22–24 MB per wheel (amd64 and arm64 exist), about
  55 MB more memory per process holding the model, 3.5 ms per move on one CPU thread (amd64
  desktop; arm64 not measured yet).
- **Strength:** with sampling (temperature 1, Maia's default, which reproduces how players of
  that rating choose, mistakes included), the rating input works in the right direction but is
  compressed: Maia 1100 scored 33 % against Maia 1500, 1500 scored 28 % against 1900, 1900
  scored 35 % against 2300, and 1100 scored 13 % against 1900 (40 games each), i.e. 400
  nominal points play like about 110–170 real ones. Against Stockfish limited to the same
  number (`UCI_Elo`, which is on an engine scale), sampled Maia scored 5–20 %; always playing
  the top move, Maia 1500 scored 55 % against Stockfish 1500.

Three ways to get the ONNX model into the image were considered:

- **Convert in the Docker build**, from the official checkpoint: nothing to host, but every
  build downloads PyTorch (~1 GB), and the arm64 release image is built under emulation.
- **A community conversion** ([bqrio/maia3-onnx](https://huggingface.co/bqrio/maia3-onnx)):
  its 5M model takes a single position (64×12), not the official model's 8-position history
  (64×97), so it isn't the same model, or not used the same way.
- **Convert once, publish it ourselves**: a script in this repository converts the official
  checkpoint and checks the result against PyTorch; its output is attached to a GitHub release
  of this repository and downloaded with a pinned checksum, like Stockfish (ADR 0012).

## Decision

- Opponents are **Maia-3 5M** for human-like play, and **Stockfish with `UCI_LimitStrength`**
  (1320 and up) for stronger opponents.
- Maia runs as **ONNX with onnxruntime** in the website's process: a bot move is part of the
  request that sends the user's move (milliseconds). No PyTorch in the image.
- The board encoding and move decoding are our own (NumPy, python-chess), a port of Maia's,
  in `engine` (no Django). Input: the last 8 positions of the game, as the model was trained.
- Maia **samples** its moves (temperature 1): that is what makes it human-like. The rating
  offered is Maia's own, a Lichess rating, from 800 to 2400; the UI says that it plays like a
  Lichess player of about that rating, not like an engine rating.
- The model comes from the **"convert once, publish it ourselves"** way: `docker/convert-maia.py`
  (run in a throwaway environment with PyTorch) writes `maia3-5m.onnx` and fails unless it
  matches PyTorch on a fixed set of positions; it is attached to a release of this repository;
  `docker/get-maia.sh` downloads it with a pinned SHA-256 for the image, CI and `just maia`.
  The image keeps Maia's licence and a pointer to its source in `/usr/share/doc/maia3`.

## Consequences

- The image grows by about 70 MB (onnxruntime and its dependencies, and the model).
- Each website process that has served a bot move holds the model: about 55 MB more memory per
  web worker (two by default).
- A new Maia model means running the script again and publishing a new file; Renovate can't
  propose it.
- Users should not read Maia's rating as a promise: it is the rating of the players it imitates.
  How its play compares with Stockfish's limited strength is shown by the numbers above.
