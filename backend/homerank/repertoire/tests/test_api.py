"""The repertoire API: repertoires, moves, PGN import, seeding, gaps and drills."""

import io
from http import HTTPStatus
from typing import Any

import chess
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from homerank.accounts.models import User
from homerank.chesslib.pgn import PgnGame, read_pgn
from homerank.games.services import new_game, store_games
from homerank.repertoire.models import Repertoire, RepertoireMove
from homerank.repertoire.services import create_repertoire, import_pgn

pytestmark = pytest.mark.django_db

AS_JSON = "application/json"
URL = "/api/v1/repertoires"


@pytest.fixture
def alice() -> User:
    return User.objects.create_user(username="alice", player_names=["alice64"])


@pytest.fixture
def alice_client(client: Client, alice: User) -> Client:
    client.force_login(alice)
    return client


@pytest.fixture
def white(alice: User) -> Repertoire:
    repertoire = create_repertoire(user=alice, name="Queen's Gambit", color="white")
    import_pgn(repertoire, lines=io.BytesIO(b"1. d4 d5 2. c4 e6 (2... c6 3. Nf3) 3. Nc3 *"))
    return repertoire


def post(client: Client, url: str, data: dict[str, Any]) -> Any:
    return client.post(url, data, content_type=AS_JSON)


def test_create_list_rename_and_delete(alice_client: Client) -> None:
    created = post(alice_client, URL, {"name": "Sicilian", "color": "black"})
    repertoire_id = created.json()["id"]
    renamed = alice_client.patch(
        f"{URL}/{repertoire_id}", {"name": "Najdorf"}, content_type=AS_JSON
    )
    listed = alice_client.get(URL).json()
    deleted = alice_client.delete(f"{URL}/{repertoire_id}")

    assert created.status_code == HTTPStatus.CREATED
    assert created.json() == {
        "id": repertoire_id,
        "name": "Sicilian",
        "color": "black",
        "move_count": 0,
        "due": 0,
    }
    assert renamed.json()["name"] == "Najdorf"
    assert [r["name"] for r in listed] == ["Najdorf"]
    assert deleted.status_code == HTTPStatus.NO_CONTENT
    assert not Repertoire.objects.exists()


def test_a_name_taken_is_a_conflict(alice_client: Client, white: Repertoire) -> None:
    response = post(alice_client, URL, {"name": "Queen's Gambit", "color": "black"})

    assert response.status_code == HTTPStatus.CONFLICT


def test_the_list_counts_moves_and_due_cards(alice_client: Client, white: Repertoire) -> None:
    (listed,) = alice_client.get(URL).json()

    assert (listed["move_count"], listed["due"]) == (7, 4)


def test_moves_join_positions_by_their_hashes(alice_client: Client, white: Repertoire) -> None:
    moves = alice_client.get(f"{URL}/{white.pk}/moves").json()

    d4, d5 = moves[:2]
    assert (d4["move_san"], d4["from_fen"]) == ("d4", chess.STARTING_FEN)
    assert d5["from_position"] == d4["to_position"]
    assert isinstance(d4["to_position"], str)  # 64-bit numbers don't fit JavaScript's
    assert d4["card_id"] is not None
    assert d5["card_id"] is None


def test_add_comment_and_remove_a_move(alice_client: Client, white: Repertoire) -> None:
    board = chess.Board()
    board.push_san("d4")
    added = post(alice_client, f"{URL}/{white.pk}/moves", {"fen": board.fen(), "move_uci": "g8f6"})
    move_id = added.json()["id"]
    commented = alice_client.patch(
        f"{URL}/{white.pk}/moves/{move_id}", {"comment": "Indian"}, content_type=AS_JSON
    )
    removed = alice_client.delete(f"{URL}/{white.pk}/moves/{move_id}")

    assert added.status_code == HTTPStatus.CREATED
    assert added.json()["move_san"] == "Nf6"
    assert commented.json()["comment"] == "Indian"
    assert removed.json() == {"removed": 1}


def test_an_illegal_move_is_refused(alice_client: Client, white: Repertoire) -> None:
    response = post(
        alice_client, f"{URL}/{white.pk}/moves", {"fen": chess.STARTING_FEN, "move_uci": "e2e5"}
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["detail"] == "This move isn't legal in this position."


def test_import_pgn(alice_client: Client, white: Repertoire) -> None:
    upload = SimpleUploadedFile("course.pgn", b"1. d4 Nf6 2. c4 *\n")

    response = alice_client.post(f"{URL}/{white.pk}/import", {"file": upload})

    assert response.json() == {"moves_added": 2, "games_read": 1, "games_skipped": 0}


def test_seed_and_gaps(alice_client: Client, alice: User, white: Repertoire) -> None:
    text = '[White "alice64"]\n[Black "bob_b"]\n[Result "*"]\n\n1. d4 d5 2. c4 dxc4 *'
    (item,) = read_pgn(io.BytesIO(text.encode()))
    assert isinstance(item, PgnGame)
    store_games(alice, [new_game(alice, item)])

    gaps = alice_client.get(f"{URL}/{white.pk}/gaps").json()
    seeded = post(alice_client, f"{URL}/{white.pk}/seed", {"depth": 4, "min_games": 1})

    assert [(g["move_san"], g["by_user"], g["games"]) for g in gaps] == [("dxc4", False, 1)]
    assert seeded.json() == {"moves_added": 1}
    assert RepertoireMove.objects.filter(repertoire=white, move_san="dxc4").exists()


def test_seed_depth_is_limited(alice_client: Client, white: Repertoire) -> None:
    response = post(alice_client, f"{URL}/{white.pk}/seed", {"depth": 31})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_drill_a_card_and_review_it(alice_client: Client, white: Repertoire) -> None:
    drill = alice_client.get(f"{URL}/{white.pk}/drill/next").json()
    card_id = drill["step"]["card_id"]
    reviewed = post(
        alice_client,
        "/api/v1/training/reviews",
        {"card_id": card_id, "correct": True, "elapsed_ms": 800},
    )
    after = alice_client.get(f"{URL}/{white.pk}/drill/next").json()

    assert (drill["step"]["move_san"], drill["last_move_uci"], drill["due"]) == ("d4", "", 4)
    assert reviewed.status_code == HTTPStatus.CREATED
    assert reviewed.json()["rating"] == 3  # noqa: PLR2004  Good
    assert (after["step"]["move_san"], after["due"]) == ("c4", 3)


def test_drill_a_line_through_a_move(alice_client: Client, white: Repertoire) -> None:
    c6 = RepertoireMove.objects.get(repertoire=white, move_san="c6")

    line = alice_client.get(f"{URL}/{white.pk}/drill/line", {"through": c6.pk}).json()

    assert [s["move_san"] for s in line] == ["d4", "d5", "c4", "c6", "Nf3"]
    assert line[1]["card_id"] is None


def test_someone_elses_repertoire_is_not_found(white: Repertoire, client: Client) -> None:
    bob = User.objects.create_user(username="bob")
    client.force_login(bob)
    move = white.moves.first()
    assert move is not None
    base = f"{URL}/{white.pk}"

    responses = [
        client.get(base),
        client.patch(base, {"name": "mine"}, content_type=AS_JSON),
        client.delete(base),
        client.get(f"{base}/moves"),
        post(client, f"{base}/moves", {"fen": chess.STARTING_FEN, "move_uci": "e2e4"}),
        client.patch(f"{base}/moves/{move.pk}", {"comment": "mine"}, content_type=AS_JSON),
        client.delete(f"{base}/moves/{move.pk}"),
        client.post(f"{base}/import", {"file": SimpleUploadedFile("a.pgn", b"1. e4 *")}),
        post(client, f"{base}/seed", {}),
        client.get(f"{base}/gaps"),
        client.get(f"{base}/drill/next"),
        client.get(f"{base}/drill/line"),
    ]

    assert {r.status_code for r in responses} == {HTTPStatus.NOT_FOUND}
    assert client.get(URL).json() == []
    assert white.moves.count() == 7  # noqa: PLR2004


def test_a_move_of_another_repertoire_is_not_found(
    alice_client: Client, alice: User, white: Repertoire
) -> None:
    other = create_repertoire(user=alice, name="London", color="white")
    move = white.moves.first()
    assert move is not None

    response = alice_client.get(f"{URL}/{other.pk}/drill/line", {"through": move.pk})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_logged_out_is_unauthorized(client: Client) -> None:
    assert client.get(URL).status_code == HTTPStatus.UNAUTHORIZED
