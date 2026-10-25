"""Index the games of databases imported before in the game list's order, newest first.

Without it, each page of a database's games sorted all of them: seconds for millions of games.
New imports get it from repository.build_index. Building it takes a minute or two for ten
million games; the website starts once it is done.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def newest_first(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    database_model = apps.get_model("reference", "ReferenceDatabase")
    for pk in database_model.objects.values_list("pk", flat=True):
        schema_editor.execute(
            f"CREATE INDEX IF NOT EXISTS reference_game_{int(pk)}_newest"
            f" ON reference_game_{int(pk)} (date DESC NULLS LAST, id DESC)"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("reference", "0002_partitioned_tables"),
    ]

    # Going back leaves the indexes; they do no harm.
    operations = [migrations.RunPython(newest_first, migrations.RunPython.noop)]
