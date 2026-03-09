from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.db import get_db_session
from src.api.schemas import TagCreate, TagListResponse, TagOut, TagUpdate
from src.api.tables import note_tags, tags

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get(
    "",
    response_model=TagListResponse,
    summary="List tags",
    description="Returns tags ordered by name with optional note_count.",
    operation_id="list_tags",
)
async def list_tags(
    include_counts: bool = Query(True, description="Include note_count in each tag."),
    session: AsyncSession = Depends(get_db_session),
) -> TagListResponse:
    """
    PUBLIC_INTERFACE
    List all tags. If include_counts=true, includes note counts (number of notes linked).
    """
    if include_counts:
        stmt = (
            select(
                tags.c.id,
                tags.c.name,
                tags.c.created_at,
                tags.c.updated_at,
                func.count(note_tags.c.note_id).label("note_count"),
            )
            .select_from(tags.outerjoin(note_tags, note_tags.c.tag_id == tags.c.id))
            .group_by(tags.c.id)
            .order_by(func.lower(tags.c.name).asc())
        )
    else:
        stmt = select(tags).order_by(func.lower(tags.c.name).asc())

    res = await session.execute(stmt)
    rows = [dict(r) for r in res.mappings().all()]

    items = [TagOut(**row) for row in rows]
    return TagListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=TagOut,
    summary="Create a tag",
    operation_id="create_tag",
)
async def create_tag(payload: TagCreate, session: AsyncSession = Depends(get_db_session)) -> TagOut:
    """
    PUBLIC_INTERFACE
    Create a tag. Name is case-insensitive unique (enforced by DB index).
    """
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Tag name cannot be empty")

    try:
        async with session.begin():
            created = await session.execute(insert(tags).values(name=name).returning(tags))
            row = dict(created.mappings().one())
            row["note_count"] = 0
            return TagOut(**row)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Tag name already exists")


@router.put(
    "/{tag_id}",
    response_model=TagOut,
    summary="Rename a tag",
    operation_id="update_tag",
)
async def update_tag(tag_id: int, payload: TagUpdate, session: AsyncSession = Depends(get_db_session)) -> TagOut:
    """
    PUBLIC_INTERFACE
    Rename a tag. Name is case-insensitive unique.
    """
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Tag name cannot be empty")

    try:
        async with session.begin():
            updated = await session.execute(
                update(tags).where(tags.c.id == tag_id).values(name=name).returning(tags)
            )
            row = updated.mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Tag not found")

        # include note_count
        count_res = await session.execute(select(func.count()).select_from(note_tags).where(note_tags.c.tag_id == tag_id))
        note_count = int(count_res.scalar_one())
        out = dict(row)
        out["note_count"] = note_count
        return TagOut(**out)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Tag name already exists")


@router.delete(
    "/{tag_id}",
    summary="Delete a tag",
    description="Deletes the tag and its note associations (note_tags rows) via ON DELETE CASCADE.",
    operation_id="delete_tag",
)
async def delete_tag(tag_id: int, session: AsyncSession = Depends(get_db_session)) -> dict:
    """
    PUBLIC_INTERFACE
    Delete a tag.
    """
    async with session.begin():
        res = await session.execute(delete(tags).where(tags.c.id == tag_id))
        if res.rowcount == 0:
            raise HTTPException(status_code=404, detail="Tag not found")
    return {"ok": True}
