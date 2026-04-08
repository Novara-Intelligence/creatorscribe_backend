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


class AudioOut(Schema):
    audio_url: Optional[str]
    duration: Optional[float]
    language: str


class SegmentOut(Schema):
    text: str
    startSecond: float
    endSecond: float


class TranscriptionOut(Schema):
    full_text: str
    srt: str
    segments: list[SegmentOut]


class CaptionOut(Schema):
    title: str
    description: str
    tags: list[str]


class UploadedFileOut(Schema):
    id: int
    original_name: str
    file_url: str
    file_type: str
    size: int


class JobOut(Schema):
    id: UUID
    turn_index: int
    status: str
    media_type: str
    prompt: str
    created_at: datetime
    uploaded_file: Optional[UploadedFileOut]
    audio: Optional[AudioOut]
    transcription: Optional[TranscriptionOut]
    caption: Optional[CaptionOut]


class JobListResponseSchema(Schema):
    success: bool
    message: str
    data: list[JobOut]
