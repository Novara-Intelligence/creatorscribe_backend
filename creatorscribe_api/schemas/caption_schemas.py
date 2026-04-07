from ninja import Schema
from datetime import datetime
from uuid import UUID
from typing import Optional
from creatorscribe_api.utils.pagination import PaginationMeta


class SubmitJobIn(Schema):
    session_id: UUID
    file_id: Optional[int] = None
    prompt: str = ""


class CreateSessionIn(Schema):
    client_id: int
    title: str = "New Session"


class RenameSessionIn(Schema):
    title: str


class LastCaptionOut(Schema):
    title: str


class SessionOut(Schema):
    id: UUID
    client_id: int
    title: str
    thumbnail: Optional[str]
    job_count: int
    last_caption: Optional[LastCaptionOut]
    created_at: datetime
    updated_at: datetime


class SessionResponseSchema(Schema):
    success: bool
    message: str
    data: SessionOut


class SessionListResponseSchema(Schema):
    success: bool
    message: str
    data: list[SessionOut]
    meta: PaginationMeta
