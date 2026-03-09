from __future__ import annotations

from typing import Dict, List, Sequence

from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.tables import note_tags, notes, tags


def _normalize_tag_name(name: str) -> str:
    return name.strip()


async def get_or_create_tag_ids(session: AsyncSession, tag_names: Sequence[str]) -> List[int]:
    """
    Ensure tags exist (case-insensitive unique) and return tag IDs in the same order as input.
    Empty/whitespace-only names are ignored.
    """
    normalized = [_normalize_tag_name(n) for n in tag_names]
    normalized = [n for n in normalized if n]
    if not normalized:
        return []

    tag_ids: List[int] = []
    for name in normalized:
        # Try find existing
        existing = await session.execute(select(tags.c.id).where(func.lower(tags.c.name) == func.lower(name)))
        tag_id = existing.scalar_one_or_none()
        if tag_id is not None:
            tag_ids.append(int(tag_id))
            continue

        # Create; handle race via unique index by catching IntegrityError then re-select
        try:
            created = await session.execute(insert(tags).values(name=name).returning(tags.c.id))
            tag_id = created.scalar_one()
            tag_ids.append(int(tag_id))
        except IntegrityError:
            await session.rollback()
            existing2 = await session.execute(select(tags.c.id).where(func.lower(tags.c.name) == func.lower(name)))
            tag_id2 = existing2.scalar_one()
            tag_ids.append(int(tag_id2))

    return tag_ids


async def replace_note_tags(session: AsyncSession, note_id: int, tag_ids: Sequence[int]) -> None:
    """Replace all tags for a note with the provided tag IDs."""
    await session.execute(delete(note_tags).where(note_tags.c.note_id == note_id))
    if not tag_ids:
        return
    rows = [{"note_id": note_id, "tag_id": int(tid)} for tid in tag_ids]
    # ON CONFLICT DO NOTHING since (note_id, tag_id) is PK
    await session.execute(insert(note_tags).values(rows).on_conflict_do_nothing())


async def fetch_tags_for_note_ids(session: AsyncSession, note_ids: Sequence[int]) -> Dict[int, List[dict]]:
    """Return mapping note_id -> list[tag_row_dict]."""
    if not note_ids:
        return {}
    res = await session.execute(
        select(
            note_tags.c.note_id,
            tags.c.id,
            tags.c.name,
            tags.c.created_at,
            tags.c.updated_at,
        )
        .select_from(note_tags.join(tags, tags.c.id == note_tags.c.tag_id))
        .where(note_tags.c.note_id.in_(list(note_ids)))
        .order_by(tags.c.name.asc())
    )
    mapping: Dict[int, List[dict]] = {}
    for row in res.mappings().all():
        nid = int(row["note_id"])
        mapping.setdefault(nid, []).append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return mapping


async def fetch_note_or_404(session: AsyncSession, note_id: int) -> dict | None:
    """Fetch a single note row as dict (without tags)."""
    res = await session.execute(select(notes).where(notes.c.id == note_id))
    row = res.mappings().first()
    return dict(row) if row else None
