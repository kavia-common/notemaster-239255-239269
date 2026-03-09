from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.db import get_db_session
from src.api.repo_utils import (
    fetch_note_or_404,
    fetch_tags_for_note_ids,
    get_or_create_tag_ids,
    replace_note_tags,
)
from src.api.schemas import NoteCreate, NoteListResponse, NoteOut, NoteUpdate, TagOut
from src.api.tables import note_tags, notes, tags

router = APIRouter(prefix="/notes", tags=["Notes"])


def _note_out_from_row(row: dict, tags_list: list[dict]) -> NoteOut:
    return NoteOut(
        id=int(row["id"]),
        title=row["title"],
        content=row["content"],
        is_archived=bool(row["is_archived"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        tags=[TagOut(**t) for t in tags_list],
    )


@router.get(
    "",
    response_model=NoteListResponse,
    summary="List notes (optionally filtered by tag and/or full-text search)",
    description="Returns notes ordered by updated_at desc. Supports filtering by tag name/id and a simple search query over title/content.",
    operation_id="list_notes",
)
async def list_notes(
    q: Optional[str] = Query(None, description="Search query (matches title/content via ILIKE)."),
    tag_id: Optional[int] = Query(None, description="Filter notes having this tag id."),
    tag_name: Optional[str] = Query(None, description="Filter notes having this tag name (case-insensitive)."),
    include_archived: bool = Query(False, description="Include archived notes."),
    limit: int = Query(50, ge=1, le=200, description="Max notes to return."),
    offset: int = Query(0, ge=0, description="Offset for pagination."),
    session: AsyncSession = Depends(get_db_session),
) -> NoteListResponse:
    """
    PUBLIC_INTERFACE
    List notes with optional search + tag filtering.
    """
    where_clauses = []
    if not include_archived:
        where_clauses.append(notes.c.is_archived.is_(False))

    if q:
        pattern = f"%{q}%"
        where_clauses.append(or_(notes.c.title.ilike(pattern), notes.c.content.ilike(pattern)))

    base_from = notes

    if tag_id is not None or tag_name is not None:
        base_from = notes.join(note_tags, note_tags.c.note_id == notes.c.id).join(tags, tags.c.id == note_tags.c.tag_id)
        if tag_id is not None:
            where_clauses.append(tags.c.id == tag_id)
        if tag_name is not None:
            where_clauses.append(func.lower(tags.c.name) == func.lower(tag_name.strip()))

    where_expr = and_(*where_clauses) if where_clauses else None

    total_stmt = select(func.count(func.distinct(notes.c.id))).select_from(base_from)
    if where_expr is not None:
        total_stmt = total_stmt.where(where_expr)

    total_res = await session.execute(total_stmt)
    total = int(total_res.scalar_one())

    list_stmt = select(func.distinct(notes.c.id), notes).select_from(base_from)
    if where_expr is not None:
        list_stmt = list_stmt.where(where_expr)
    list_stmt = list_stmt.order_by(notes.c.updated_at.desc()).limit(limit).offset(offset)

    res = await session.execute(list_stmt)
    rows = [dict(r) for r in res.mappings().all()]
    note_ids = [int(r["id"]) for r in rows]
    tags_map = await fetch_tags_for_note_ids(session, note_ids)

    items = [_note_out_from_row(r, tags_map.get(int(r["id"]), [])) for r in rows]
    return NoteListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{note_id}",
    response_model=NoteOut,
    summary="Get a note by id",
    operation_id="get_note",
)
async def get_note(note_id: int, session: AsyncSession = Depends(get_db_session)) -> NoteOut:
    """
    PUBLIC_INTERFACE
    Fetch a single note including its tags.
    """
    row = await fetch_note_or_404(session, note_id)
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")
    tags_map = await fetch_tags_for_note_ids(session, [note_id])
    return _note_out_from_row(row, tags_map.get(note_id, []))


@router.post(
    "",
    response_model=NoteOut,
    summary="Create a new note",
    operation_id="create_note",
)
async def create_note(payload: NoteCreate, session: AsyncSession = Depends(get_db_session)) -> NoteOut:
    """
    PUBLIC_INTERFACE
    Create a note and attach tags (created if missing).
    """
    async with session.begin():
        created = await session.execute(
            insert(notes)
            .values(title=payload.title, content=payload.content, is_archived=payload.is_archived)
            .returning(notes)
        )
        row = dict(created.mappings().one())

        tag_ids = await get_or_create_tag_ids(session, payload.tag_names)
        await replace_note_tags(session, int(row["id"]), tag_ids)

    # Reload tags
    tags_map = await fetch_tags_for_note_ids(session, [int(row["id"])])
    return _note_out_from_row(row, tags_map.get(int(row["id"]), []))


@router.put(
    "/{note_id}",
    response_model=NoteOut,
    summary="Update a note",
    description="Updates note fields; if tag_names is provided it will replace the note's tags with that set.",
    operation_id="update_note",
)
async def update_note(note_id: int, payload: NoteUpdate, session: AsyncSession = Depends(get_db_session)) -> NoteOut:
    """
    PUBLIC_INTERFACE
    Update note content/title/archive flag and optionally replace tags.
    """
    async with session.begin():
        existing = await fetch_note_or_404(session, note_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found")

        update_values = {}
        if payload.title is not None:
            update_values["title"] = payload.title
        if payload.content is not None:
            update_values["content"] = payload.content
        if payload.is_archived is not None:
            update_values["is_archived"] = payload.is_archived

        if update_values:
            updated = await session.execute(
                update(notes).where(notes.c.id == note_id).values(**update_values).returning(notes)
            )
            row = dict(updated.mappings().one())
        else:
            row = existing

        if payload.tag_names is not None:
            tag_ids = await get_or_create_tag_ids(session, payload.tag_names)
            await replace_note_tags(session, note_id, tag_ids)

    tags_map = await fetch_tags_for_note_ids(session, [note_id])
    return _note_out_from_row(row, tags_map.get(note_id, []))


@router.delete(
    "/{note_id}",
    summary="Delete a note",
    operation_id="delete_note",
)
async def delete_note(note_id: int, session: AsyncSession = Depends(get_db_session)) -> dict:
    """
    PUBLIC_INTERFACE
    Delete a note. Cascades to note_tags via FK ON DELETE CASCADE.
    """
    async with session.begin():
        res = await session.execute(delete(notes).where(notes.c.id == note_id))
        if res.rowcount == 0:
            raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}
