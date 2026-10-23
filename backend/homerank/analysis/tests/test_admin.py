from http import HTTPStatus

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("model", ["analysisrun", "analysissettings"])
def test_staff_can_see_analyses_and_settings_but_not_add_them(
    admin_client: Client, model: str
) -> None:
    assert admin_client.get(reverse(f"admin:analysis_{model}_changelist")).status_code == (
        HTTPStatus.OK
    )
    add_page = admin_client.get(reverse(f"admin:analysis_{model}_add"))
    assert add_page.status_code == HTTPStatus.FORBIDDEN
