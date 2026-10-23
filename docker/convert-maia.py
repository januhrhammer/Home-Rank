# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "torch==2.14.1",
#     "onnx==1.23.2",
#     "onnxruntime==1.31.0",
#     "numpy",
#     "chess==1.11.2",
#     "maia3 @ git+https://github.com/CSSLab/maia3@1e13597c42d4858b7cfd7cfdae01e297263364b2",
# ]
#
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Convert Maia-3 5M, the human-like chess model, from PyTorch to ONNX (ADR 0017).

Run by hand, rarely: when Maia gets a new model. uv puts PyTorch (about 1 GB) and Maia's own
code into a throwaway environment, so neither ends up in the project or the image:

    uv run docker/convert-maia.py OUT_DIR

It downloads the official checkpoint (pinned below), exports it to OUT_DIR/maia3-5m.onnx and
checks that onnxruntime gives the same move probabilities as PyTorch on a fixed set of
positions; it fails otherwise. It also writes OUT_DIR/maia3-5m-expected.json: the official
model's answers for those positions, which the backend's own encoder is tested against
(homerank/engine/tests/fixtures/). Publish the model as described in docker/get-maia.sh.
"""

import argparse
import copy
import hashlib
import json
import random
import sys
import urllib.request
from collections import deque
from pathlib import Path

import chess
import numpy as np
import onnxruntime
import torch
from maia3.dataset import get_historical_tokens, tokenize_board
from maia3.model_registry import MODEL_SPECS
from maia3.models import MAIA3Model
from maia3.utils import get_all_possible_moves, mirror_move

# The official checkpoint, at a fixed revision of its Hugging Face repository.
CHECKPOINT_URL = (
    "https://huggingface.co/UofTCSSLab/Maia3-5M/resolve/"
    "b6559de2398d7140b985f28fd2c19fb5e47ddabe/maia3-5m.pt"
)
CHECKPOINT_SHA256 = "ba14208b2992d85502f5fb501934abf6aaaeb355e9f3fdf90e326911f562524f"

# Positions to compare and record: random games from the start (fixed seed), so they include
# openings, middlegames, both sides to move, captures and promotions. Ratings across the range
# Home-Rank offers.
SEED = 2026
GAMES = 30
RATINGS = [(800, 800), (1500, 1500), (2400, 2400), (1200, 1900)]
# The largest difference allowed between PyTorch's and ONNX's move probabilities.
TOLERANCE = 1e-4


class PlainRMSNorm(torch.nn.Module):
    """torch.nn.RMSNorm written out as its formula: the ONNX exporter doesn't know it."""

    def __init__(self, norm: torch.nn.RMSNorm) -> None:
        super().__init__()
        self.weight = norm.weight
        self.eps = norm.eps if norm.eps is not None else torch.finfo(torch.float32).eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps) * self.weight


class Outputs(torch.nn.Module):
    """The model's three outputs (moves, win/draw/loss, thinking time) as a plain tuple."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, tokens, self_elo, oppo_elo):  # type: ignore[no-untyped-def]
        logits_move, logits_value, logits_ponder = self.model(
            tokens, self_elo, oppo_elo
        )[:3]
        return logits_move, logits_value, logits_ponder


def download_checkpoint(path: Path) -> None:
    with urllib.request.urlopen(CHECKPOINT_URL) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != CHECKPOINT_SHA256:
        sys.exit("The checkpoint's checksum doesn't match: not converting it.")
    path.write_bytes(data)


def load_model(checkpoint: Path, config: dict) -> MAIA3Model:
    model = MAIA3Model(argparse.Namespace(**config, device="cpu"))
    # weights_only: the file is only read as tensors, never run as code.
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    state = state.get("model_state_dict", state)
    # Older checkpoints called the attention bias "smolgen" (as Maia's own loader handles it).
    model.load_state_dict({k.replace("smolgen", "gab"): v for k, v in state.items()})
    return model.eval()


def export(model: MAIA3Model, history: int, path: Path) -> None:
    plain = copy.deepcopy(model)
    for module in list(plain.modules()):
        for name, child in list(module.named_children()):
            if isinstance(child, torch.nn.RMSNorm):
                setattr(module, name, PlainRMSNorm(child))
    example = (
        torch.zeros(1, 64, 12 * history + 1),
        torch.tensor([1500]),
        torch.tensor([1500]),
    )
    torch.onnx.export(
        Outputs(plain),
        example,
        path,
        input_names=["tokens", "self_elo", "oppo_elo"],
        output_names=["logits_move", "logits_value", "logits_ponder"],
        opset_version=17,
        dynamo=False,  # the newer exporter fails on the attention layers
    )


def positions() -> list[list[str]]:
    """Move lists from the starting position; each ends in a position to ask about."""
    rng = random.Random(SEED)
    result = []
    for _ in range(GAMES):
        board = chess.Board()
        moves: list[str] = []
        stops = {rng.randrange(1, 80), rng.randrange(1, 80)}
        while not board.is_game_over() and len(moves) < 80:
            if len(moves) in stops:
                result.append(list(moves))
            move = rng.choice(list(board.legal_moves))
            board.push(move)
            moves.append(move.uci())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=True)

    spec = next(spec for spec in MODEL_SPECS if spec.name == "maia3-5m")
    config = spec.config
    checkpoint = out / "maia3-5m.pt"
    download_checkpoint(checkpoint)
    model = load_model(checkpoint, config)
    onnx_path = out / "maia3-5m.onnx"
    export(model, config["history"], onnx_path)
    session = onnxruntime.InferenceSession(
        onnx_path, providers=["CPUExecutionProvider"]
    )

    all_moves = get_all_possible_moves()
    cases = []
    for moves in positions():
        board = chess.Board()
        history = deque([tokenize_board(board)], maxlen=config["history"])
        for move in moves:
            board.push_uci(move)
            history.append(tokenize_board(board))
        tokens = get_historical_tokens(
            history, argparse.Namespace(**config), 0.0, 0.0, 0.0, 0.0
        )
        tokens = tokens.unsqueeze(0)
        legal = {
            all_moves.index(
                m.uci() if board.turn == chess.WHITE else mirror_move(m.uci())
            ): m
            for m in board.legal_moves
        }
        indexes = sorted(legal)
        for self_elo, oppo_elo in RATINGS:
            elos = (torch.tensor([self_elo]), torch.tensor([oppo_elo]))
            with torch.no_grad():
                reference = model(tokens, *elos)[0][0].numpy()[indexes]
            exported = session.run(
                None,
                {
                    "tokens": tokens.numpy(),
                    "self_elo": elos[0].numpy(),
                    "oppo_elo": elos[1].numpy(),
                },
            )[0][0][indexes]
            ref_probs = softmax(reference)
            if np.abs(ref_probs - softmax(exported)).max() > TOLERANCE:
                sys.exit(
                    f"ONNX differs from PyTorch after {' '.join(moves)} at {self_elo}."
                )
            top = np.argsort(-ref_probs)[:5]
            cases.append(
                {
                    "moves": moves,
                    "self_elo": self_elo,
                    "oppo_elo": oppo_elo,
                    "top": [
                        [legal[indexes[i]].uci(), round(float(ref_probs[i]), 6)]
                        for i in top
                    ],
                }
            )

    (out / "maia3-5m-expected.json").write_text(json.dumps(cases, indent=1) + "\n")
    digest = hashlib.sha256(onnx_path.read_bytes()).hexdigest()
    print(f"{len(cases)} cases match. {onnx_path}: sha256 {digest}")


def softmax(logits: np.ndarray) -> np.ndarray:
    exp = np.exp(logits - logits.max())
    return exp / exp.sum()


if __name__ == "__main__":
    main()
