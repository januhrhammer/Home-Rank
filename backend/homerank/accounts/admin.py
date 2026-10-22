from typing import TYPE_CHECKING

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.postgres.forms import SimpleArrayField

from homerank.accounts.models import User

# Django's admin and form classes are generic for mypy, but can't be subscripted at runtime.
if TYPE_CHECKING:
    BaseUserAdmin = UserAdmin[User]
    BaseUserChangeForm = UserChangeForm[User]
else:
    BaseUserAdmin = UserAdmin
    BaseUserChangeForm = UserChangeForm


class HomeRankUserChangeForm(BaseUserChangeForm):
    # One name per line: Django's default separates list entries with commas, which names such as
    # "Carlsen, Magnus" contain.
    player_names = SimpleArrayField(
        forms.CharField(max_length=100),
        delimiter="\n",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="The names this user plays under, one per line, as they appear in games.",
    )


@admin.register(User)
class HomeRankUserAdmin(BaseUserAdmin):
    form = HomeRankUserChangeForm
    fieldsets = (*(UserAdmin.fieldsets or ()), ("Chess", {"fields": ("player_names",)}))
