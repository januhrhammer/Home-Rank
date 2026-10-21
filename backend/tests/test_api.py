"""The API is mounted at /api/v1/ and documents itself."""

import re
from http import HTTPStatus

from django.test import Client


def test_openapi_schema_is_served(client: Client) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["info"]["title"] == "Home-Rank API"
    assert response.json()["info"]["version"] == "1"


def test_docs_page_loads_nothing_from_the_internet(client: Client) -> None:
    # Home-Rank must work offline, so the docs page may only load files from our own server.
    response = client.get("/api/v1/docs")
    html = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "/static/ninja/swagger-ui-bundle.js" in html
    assert not re.search(r"https?://", html)
