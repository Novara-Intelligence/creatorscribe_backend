from ninja import Schema
from typing import Optional, List
from datetime import datetime


class ClientCreateRequestSchema(Schema):
    client_name: Optional[str] = None
    brand_logo: Optional[str] = None  # Base64 encoded image or file path


class ClientResponseSchema(Schema):
    id: int
    client_name: Optional[str] = None
    brand_logo: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ClientCreateResponseSchema(Schema):
    success: bool
    message: str
    data: ClientResponseSchema


class ClientListResponseSchema(Schema):
    success: bool
    message: str
    data: List[ClientResponseSchema]
