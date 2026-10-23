import io
import re

import pytest
from django.core.management import call_command

pytestmark = [pytest.mark.maia, pytest.mark.engine]


def test_both_bots_answer_e4() -> None:
    out = io.StringIO()

    call_command("check_bots", stdout=out)

    lines = out.getvalue().splitlines()
    assert re.fullmatch(r"Maia 1500: 1\. e4 \S+ \(\d+ ms\)", lines[0])
    assert re.fullmatch(r"Stockfish 1320: 1\. e4 \S+ \(\d+ ms\)", lines[1])
    assert lines[2] == "Both bots work."
