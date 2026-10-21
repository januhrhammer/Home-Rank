from ninja import Schema


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
