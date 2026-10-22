from typing import Annotated

from ninja import Field, Schema
from pydantic import StringConstraints


class LoginIn(Schema):
    username: str
    password: str


class UserOut(Schema):
    """What the API reveals about a user. Fields are listed explicitly, so a field added to the
    User model later never ends up in responses by accident."""

    id: int
    username: str
    email: str
    is_staff: bool


# As long as the model's field allows; spaces at the ends don't count.
PlayerName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class SettingsOut(Schema):
    """The logged-in user's settings."""

    player_names: list[str] = Field(
        description="The names the user plays under, to find their side in each game"
    )


class SettingsPatch(Schema):
    """Changes to the settings; what is left out stays as it is."""

    player_names: list[PlayerName] | None = Field(None, max_length=20)
