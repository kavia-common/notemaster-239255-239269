from sqlalchemy import BIGINT, BOOLEAN, Column, DateTime, MetaData, Table, Text, func

# Use a single metadata instance for all tables.
metadata = MetaData()

notes = Table(
    "notes",
    metadata,
    Column("id", BIGINT, primary_key=True),
    Column("title", Text, nullable=False, server_default=""),
    Column("content", Text, nullable=False, server_default=""),
    Column("is_archived", BOOLEAN, nullable=False, server_default="false"),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)

tags = Table(
    "tags",
    metadata,
    Column("id", BIGINT, primary_key=True),
    Column("name", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)

note_tags = Table(
    "note_tags",
    metadata,
    Column("note_id", BIGINT, primary_key=True),
    Column("tag_id", BIGINT, primary_key=True),
)
