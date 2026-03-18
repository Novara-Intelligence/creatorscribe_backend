from ninja import Schema
from datetime import datetime
from typing import List


class UploadedFileOut(Schema):
    id: int
    original_name: str
    file_url: str
    file_type: str
    size: int
    created_at: datetime


class UploadedFileResponseSchema(Schema):
    success: bool
    message: str
    data: UploadedFileOut


class PaginationMetaSchema(Schema):
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_previous: bool


class UploadedFileListResponseSchema(Schema):
    success: bool
    message: str
    data: List[UploadedFileOut]
    pagination: PaginationMetaSchema
