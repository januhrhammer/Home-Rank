"""Cross-origin isolation headers, which live analysis needs for its threads (ADR 0018)."""

from django.test import Client

from homerank.core.isolation import add_static_headers


def test_pages_are_cross_origin_isolated(client: Client) -> None:
    response = client.get("/healthz")

    assert response["Cross-Origin-Opener-Policy"] == "same-origin"  # Django's default
    assert response["Cross-Origin-Embedder-Policy"] == "require-corp"


def test_static_files_get_the_header_too() -> None:
    headers: dict[str, str] = {}

    add_static_headers(headers, "/app/frontend/dist/engine/stockfish.js", "/engine/stockfish.js")

    assert headers == {"Cross-Origin-Embedder-Policy": "require-corp"}
