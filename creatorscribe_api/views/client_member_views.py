from ninja import Router
from ninja_jwt.tokens import AccessToken
from typing import Optional
from django.contrib.auth import get_user_model
from django.db.models import Q
from ..models.client_models import Client, ClientMember
from ..schemas.auth_schemas import ErrorResponseSchema
from ..schemas.client_member_schemas import (
    InviteMemberSchema,
    UpdateMemberRoleSchema,
    MemberResponseSchema,
    MemberListResponseSchema,
    MemberDetailResponseSchema,
    InviteListResponseSchema,
)
from ..authentication import AuthBearer

User = get_user_model()


member_router = Router(tags=["Client Members"])

CAN_INVITE = {'owner', 'admin'}


def _get_owned_client(client_id: int, user):
    try:
        return Client.objects.get(id=client_id, owner=user)
    except Client.DoesNotExist:
        return None


def _get_managed_client(client_id: int, user):
    """Owner or admin can manage members."""
    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        return None, None
    role = client.get_user_role(user)
    if role not in CAN_INVITE:
        return None, None
    return client, role


def _serialize_member(m: ClientMember, request) -> dict:
    profile_pic = None
    if m.user.profile_pic:
        profile_pic = request.build_absolute_uri(m.user.profile_pic.url)
    return {
        "id": m.id,
        "user_id": m.user_id,
        "email": m.user.email,
        "full_name": m.user.full_name,
        "profile_pic": profile_pic,
        "role": m.role,
        "status": m.status,
        "invited_by_email": m.invited_by.email if m.invited_by else None,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
    }


@member_router.get(
    "/{client_id}/members",
    response={200: MemberListResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="List all members of a client",
)
def list_members(request, client_id: int, search: Optional[str] = None):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        return 404, {"success": False, "message": f"No client found with ID {client_id}"}

    if not client.is_member(user):
        return 404, {"success": False, "message": f"No client found with ID {client_id}"}

    members = client.members.select_related('user', 'invited_by').order_by('created_at')

    if search:
        members = members.filter(
            Q(user__email__icontains=search) | Q(user__full_name__icontains=search)
        )

    return 200, {
        "success": True,
        "message": "Members retrieved successfully",
        "data": [_serialize_member(m, request) for m in members],
        "count": members.count(),
    }


@member_router.post(
    "/{client_id}/members/invite",
    response={201: ErrorResponseSchema, 400: ErrorResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Invite one or more users to a client by email",
)
def invite_member(request, client_id: int, payload: InviteMemberSchema):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    client, _ = _get_managed_client(client_id, user)
    if not client:
        return 404, {"success": False, "message": f"No client found with ID {client_id} or insufficient permissions"}

    if not payload.emails:
        return 400, {"success": False, "message": "At least one email is required"}

    invited = []
    for email in payload.emails:
        email = email.strip().lower()
        try:
            invitee = User.objects.get(email=email)
        except User.DoesNotExist:
            continue

        if invitee == client.owner:
            continue

        member, created = ClientMember.objects.get_or_create(
            client=client,
            user=invitee,
            defaults={"role": payload.role, "status": "pending", "invited_by": user},
        )

        if not created and member.status != 'accepted':
            member.role = payload.role
            member.status = "pending"
            member.invited_by = user
            member.save(update_fields=['role', 'status', 'invited_by', 'updated_at'])

        if member.status != 'accepted':
            invited.append(_serialize_member(member, request))

    return 201, {"success": True, "message": f"{len(invited)} invite(s) sent"}


@member_router.post(
    "/{client_id}/members/accept",
    response={200: ErrorResponseSchema, 400: ErrorResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Accept a pending invite to a client",
)
def accept_invite(request, client_id: int):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    try:
        member = ClientMember.objects.select_related('client', 'invited_by').get(
            client_id=client_id,
            user=user,
            status='pending'
        )
    except ClientMember.DoesNotExist:
        return 404, {"success": False, "message": "No pending invite found for this client"}

    member.status = 'accepted'
    member.save(update_fields=['status', 'updated_at'])

    return 200, {"success": True, "message": f"You have joined '{member.client.client_name}' as {member.role}"}


@member_router.get(
    "/my-invites",
    response={200: InviteListResponseSchema, 401: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Get all pending invites for the authenticated user",
)
def get_my_invites(request):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    invites = ClientMember.objects.filter(
        user=user, status='pending'
    ).select_related('client', 'invited_by').order_by('-created_at')

    data = [
        {
            "id": inv.id,
            "client_id": inv.client_id,
            "client_name": inv.client.client_name,
            "client_logo": request.build_absolute_uri(inv.client.brand_logo.url) if inv.client.brand_logo else None,
            "invited_by_email": inv.invited_by.email if inv.invited_by else None,
            "role": inv.role,
            "created_at": inv.created_at,
        }
        for inv in invites
    ]

    return 200, {
        "success": True,
        "message": "Invites retrieved successfully",
        "data": data,
        "count": len(data),
    }


@member_router.post(
    "/{client_id}/members/reject",
    response={200: ErrorResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Reject a pending invite",
)
def reject_invite(request, client_id: int):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    try:
        member = ClientMember.objects.get(client_id=client_id, user=user, status='pending')
    except ClientMember.DoesNotExist:
        return 404, {"success": False, "message": "No pending invite found for this client"}

    member.status = 'rejected'
    member.save(update_fields=['status', 'updated_at'])

    return 200, {"success": True, "message": "Invite rejected"}


@member_router.patch(
    "/{client_id}/members/{member_id}/role",
    response={200: MemberDetailResponseSchema, 400: ErrorResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Update a member's role",
)
def update_member_role(request, client_id: int, member_id: int, payload: UpdateMemberRoleSchema):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    client, _ = _get_managed_client(client_id, user)
    if not client:
        return 404, {"success": False, "message": f"No client found with ID {client_id} or insufficient permissions"}

    try:
        member = ClientMember.objects.select_related('user', 'invited_by').get(id=member_id, client=client)
    except ClientMember.DoesNotExist:
        return 404, {"success": False, "message": "Member not found"}

    member.role = payload.role
    member.save(update_fields=['role', 'updated_at'])

    return 200, {
        "success": True,
        "message": f"Role updated to '{payload.role}'",
        "data": _serialize_member(member, request),
    }


@member_router.delete(
    "/{client_id}/members/{member_id}",
    response={200: ErrorResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Remove a member from a client",
)
def remove_member(request, client_id: int, member_id: int):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    client, _ = _get_managed_client(client_id, user)
    if not client:
        return 404, {"success": False, "message": f"No client found with ID {client_id} or insufficient permissions"}

    try:
        member = ClientMember.objects.select_related('user').get(id=member_id, client=client)
    except ClientMember.DoesNotExist:
        return 404, {"success": False, "message": "Member not found"}

    email = member.user.email
    member.delete()

    return 200, {"success": True, "message": f"{email} has been removed from this client"}


@member_router.delete(
    "/{client_id}/members/leave",
    response={200: ErrorResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Leave a client you are a member of",
)
def leave_client(request, client_id: int):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    try:
        member = ClientMember.objects.get(client_id=client_id, user=user)
    except ClientMember.DoesNotExist:
        return 404, {"success": False, "message": "You are not a member of this client"}

    member.delete()
    return 200, {"success": True, "message": "You have left the client"}
