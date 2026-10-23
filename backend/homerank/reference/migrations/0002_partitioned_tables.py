"""The tables of reference databases' data, partitioned by database (ADR 0015).

Each database gets one partition of each, created and dropped with it by
homerank.reference.repository; deleting a database drops its partitions instead of deleting
millions of rows. Indexes besides the primary keys are built per partition after an import.

No foreign keys to reference_referencedatabase: the partitions come and go with their database,
and a foreign key would stop Django from emptying that table (TRUNCATE) in tests.
"""

from django.db import migrations

CREATE = """
CREATE TABLE reference_game (
    database_id integer NOT NULL,
    id integer NOT NULL,
    white text NOT NULL,
    black text NOT NULL,
    white_elo smallint,
    black_elo smallint,
    result varchar(7) NOT NULL,
    date date,
    date_pgn varchar(10) NOT NULL,
    event text NOT NULL,
    site text NOT NULL,
    eco varchar(3) NOT NULL,
    opening text NOT NULL,
    ply_count smallint NOT NULL,
    start_fen text NOT NULL,
    moves bytea NOT NULL,
    dedup_hash bytea NOT NULL,
    PRIMARY KEY (database_id, id)
) PARTITION BY LIST (database_id);

CREATE TABLE reference_explorer (
    database_id integer NOT NULL,
    zobrist bigint NOT NULL,
    move smallint NOT NULL,
    white integer NOT NULL,
    draws integer NOT NULL,
    black integer NOT NULL,
    rating_sum bigint NOT NULL,
    rating_count integer NOT NULL,
    last_year smallint,
    PRIMARY KEY (database_id, zobrist, move)
) PARTITION BY LIST (database_id);

-- The position index: entries of 13 bytes (hash, game, ply), sorted, in buckets by the hash's
-- top bits.
CREATE TABLE reference_bucket (
    database_id integer NOT NULL,
    bucket integer NOT NULL,
    entries bytea NOT NULL,
    PRIMARY KEY (database_id, bucket)
) PARTITION BY LIST (database_id);
"""

DROP = """
DROP TABLE reference_bucket;
DROP TABLE reference_explorer;
DROP TABLE reference_game;
"""


class Migration(migrations.Migration):
    dependencies = [("reference", "0001_initial")]

    operations = [migrations.RunSQL(CREATE, DROP)]
