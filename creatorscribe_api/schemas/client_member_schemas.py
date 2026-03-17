from ninja import Schema
from typing import Optional, List
from datetime import datetime


class InviteMemberSchema(Schema):
    emails: List[str]
    role: str = "viewer"  # admin | editor | viewer


class UpdateMemberRoleSchema(Schema):
    role: str  # admin | editor | viewer


class MemberResponseSchema(Schema):
    id: int
    user_id: int
    email: str
    full_name: Optional[str] = None
    profile_pic: Optional[str] = None
    role: str
    status: str
    invited_by_email: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MemberDetailResponseSchema(Schema):
    success: bool
    message: str
    data: MemberResponseSchema


class MemberListResponseSchema(Schema):
    success: bool
    message: str
    data: List[MemberResponseSchema]
    count: int


class InviteResponseSchema(Schema):
    id: int
    client_id: int
    client_name: Optional[str] = None
    client_logo: Optional[str] = None
    invited_by_email: Optional[str] = None
    role: str
    created_at: datetime


class InviteListResponseSchema(Schema):
    success: bool
    message: str
    data: List[InviteResponseSchema]
    count: int
