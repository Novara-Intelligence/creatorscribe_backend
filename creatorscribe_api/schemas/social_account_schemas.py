from ninja import Schema
from typing import Optional, List
from datetime import datetime


class SocialAccountConnectSchema(Schema):
    platform: str
    account_name: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None


class SocialAccountResponseSchema(Schema):
    id: int
    platform: str
    account_name: str
    expires_at: Optional[datetime] = None
    is_token_expired: bool
    created_at: datetime
    updated_at: datetime


class SocialAccountListResponseSchema(Schema):
    success: bool
    message: str
    data: List[SocialAccountResponseSchema]
    count: int


class SocialAccountDetailResponseSchema(Schema):
    success: bool
    message: str
    data: SocialAccountResponseSchema
