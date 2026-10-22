"""Pagination for every list in the API: ?limit=&offset=, answered with {items, total}.

Use it on a list endpoint with django-ninja's decorator: @paginate(LimitOffset).
"""

from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest
from ninja import Field, Schema
from ninja.pagination import PaginationBase

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class LimitOffset(PaginationBase):
    class Input(Schema):
        limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
        offset: int = Field(0, ge=0)

    class Output(Schema):
        items: list[Any]
        total: int  # all matching items, not just this page

    def paginate_queryset(
        self,
        queryset: QuerySet[Any],
        pagination: Input,
        request: HttpRequest,
        **params: Any,
    ) -> dict[str, Any]:
        start = pagination.offset
        return {"items": queryset[start : start + pagination.limit], "total": queryset.count()}
