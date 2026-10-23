"""The API's types keep their own names in the OpenAPI schema (and so in the frontend's types).

django-ninja names an enum's schema after its class, and two classes of the same name share one
schema silently: the bot games' Status once replaced the analysis's, and the frontend's types
said analyses were "playing" or "finished". Enums of one name with the same values (the import,
analysis and sync runs' Status) are harmless.
"""

import enum
import typing
from collections import defaultdict

from ninja import Schema

import config.api  # noqa: F401 (imports every router, and so every schema)


def _schemas(cls: type[Schema]) -> set[type[Schema]]:
    found = set()
    for sub in cls.__subclasses__():
        found |= {sub, *_schemas(sub)}
    return found


def _enums(annotation: object) -> set[type[enum.Enum]]:
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return {annotation}
    return {found for arg in typing.get_args(annotation) for found in _enums(arg)}


def test_enums_of_one_name_in_the_api_have_the_same_values() -> None:
    values_by_name: defaultdict[str, set[tuple[object, ...]]] = defaultdict(set)
    for schema in _schemas(Schema):
        for field in schema.model_fields.values():
            for found in _enums(field.annotation):
                values = tuple(member.value for member in found)
                values_by_name[found.__name__].add(values)

    clashes = {name: values for name, values in values_by_name.items() if len(values) > 1}
    assert clashes == {}
