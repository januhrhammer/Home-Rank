from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """A Home-Rank user, who logs in with a username. Email is optional.

    For now this is identical to Django's built-in user. It exists because replacing the user
    model after the first migration is notoriously hard, while adding fields to our own is easy.
    """
