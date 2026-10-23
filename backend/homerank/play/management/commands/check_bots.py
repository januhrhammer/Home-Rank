"""`manage.py check_bots`: let both bots move once, to see that they work here.

Self-hosters can run it after installing or updating (docker compose exec web python manage.py
check_bots); CI runs it in the image for amd64 and arm64. No database needed.
"""

import time
from typing import Any

import chess
from django.conf import settings
from django.core.management.base import BaseCommand

from homerank.engine.bots import STOCKFISH_MIN_ELO, Bot, MaiaBot, StockfishBot
from homerank.engine.maia import load


class Command(BaseCommand):
    help = "Let Maia and Stockfish each play a move, and show how long they took."

    def handle(self, *args: Any, **options: Any) -> None:
        bots: list[tuple[str, Bot]] = [
            ("Maia 1500", MaiaBot(load(settings.MAIA_PATH), elo=1500, opponent_elo=1500)),
            (
                f"Stockfish {STOCKFISH_MIN_ELO}",
                StockfishBot(settings.STOCKFISH_PATH, elo=STOCKFISH_MIN_ELO),
            ),
        ]
        board = chess.Board()
        board.push_san("e4")  # each bot answers 1. e4
        for name, bot in bots:
            started = time.monotonic()
            move = bot.move(board)
            took = (time.monotonic() - started) * 1000
            self.stdout.write(f"{name}: 1. e4 {board.san(move)} ({took:.0f} ms)")
        self.stdout.write(self.style.SUCCESS("Both bots work."))
