from ninja import Schema
from typing import Optional, List
from datetime import datetime


class InviteMemberSchema(Schema):
    email: str
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
