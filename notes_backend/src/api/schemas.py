from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TagBase(BaseModel):
    name: str = Field(..., description="Tag name (case-insensitive unique).", min_length=1)


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: str = Field(..., description="New tag name (case-insensitive unique).", min_length=1)


class TagOut(TagBase):
    id: int = Field(..., description="Tag ID.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")
    note_count: Optional[int] = Field(None, description="Number of notes that have this tag (when requested).")


class NoteBase(BaseModel):
    title: str = Field("", description="Note title.")
    content: str = Field("", description="Note content (markdown/plaintext).")
    is_archived: bool = Field(False, description="Whether the note is archived.")


class NoteCreate(NoteBase):
    tag_names: List[str] = Field(default_factory=list, description="Tags to attach by name (created if missing).")


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Updated title.")
    content: Optional[str] = Field(None, description="Updated content.")
    is_archived: Optional[bool] = Field(None, description="Updated archive status.")
    tag_names: Optional[List[str]] = Field(None, description="If provided, replaces note tags with these names.")


class NoteOut(NoteBase):
    id: int = Field(..., description="Note ID.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")
    tags: List[TagOut] = Field(default_factory=list, description="Tags attached to the note.")


class NoteListResponse(BaseModel):
    items: List[NoteOut] = Field(..., description="Page of notes.")
    total: int = Field(..., description="Total matching notes (before pagination).")
    limit: int = Field(..., description="Limit used.")
    offset: int = Field(..., description="Offset used.")


class TagListResponse(BaseModel):
    items: List[TagOut] = Field(..., description="List of tags.")
    total: int = Field(..., description="Total tags.")
