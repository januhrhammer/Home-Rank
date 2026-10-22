from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.db import models


class User(AbstractUser):
    """A Home-Rank user, who logs in with a username. Email is optional.

    It extends Django's built-in user, because replacing the user model after the first migration
    is notoriously hard, while adding fields to our own is easy.
    """

    # The names the user plays under, e.g. "Uhrhammer, Jan" and "januhrhammer". Imports compare
    # them with each game's players to find the user's side (homerank.chesslib.players).
    player_names = ArrayField(models.CharField(max_length=100), default=list, blank=True)
