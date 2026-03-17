import json
from typing import Optional, List
from ninja import Router, File, Form
from ninja.files import UploadedFile
from ninja import Router
from django.contrib.auth import get_user_model
from django.db.models import Q
from ..models.client_models import Client, ClientMember
from ..schemas import (
    ErrorResponseSchema,
    ClientResponseSchema,
    ClientListResponseSchema,
    ClientCreateResponseSchema,
)
from ..authentication import AuthBearer

User = get_user_model()


client_router = Router(tags=["Clients"])


def _serialize(client: Client, user, request) -> dict:
    social_accounts = [
        sa.platform
        for sa in client.social_accounts.all()
    ]
    
    return {
        "id": client.id,
        "client_name": client.client_name,
        "brand_logo": request.build_absolute_uri(client.brand_logo.url) if client.brand_logo else None,
        "role": client.get_user_role(user),
        "social_accounts": social_accounts,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
    }


def _get_accessible_client(client_id: int, user):
    """Return client if user is owner or accepted member."""
    try:
        return Client.objects.get(
            Q(id=client_id) & (
                Q(owner=user) |
                Q(members__user=user, members__status='accepted')
            )
        )
    except Client.DoesNotExist:
        return None


@client_router.get(
    "/my-clients",
    response={200: ClientListResponseSchema, 401: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Get all clients the user owns or is a member of",
)
def get_user_clients(request):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    clients = Client.objects.filter(
        Q(owner=user) | Q(members__user=user, members__status='accepted')
    ).distinct().order_by('-created_at')

    return 200, {
        "success": True,
        "message": "Clients retrieved successfully",
        "data": [_serialize(c, user, request) for c in clients],
        "count": clients.count(),
    }


@client_router.get(
    "/my-clients/{client_id}",
    response={200: ClientResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Get specific client details",
)
def get_client_detail(request, client_id: int):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Invalid or missing authentication token"}

    client = _get_accessible_client(client_id, user)
    if not client:
        return 404, {"success": False, "message": f"No client found with ID {client_id}"}

    return 200, _serialize(client, user, request)


@client_router.post(
    "/add-client",
    response={201: ClientCreateResponseSchema, 400: ErrorResponseSchema, 401: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Create a new client (multipart/form-data)",
)
def add_client(
    request,
    client_name: Form[Optional[str]] = None,
    brand_logo: File[Optional[UploadedFile]] = None,
    invite_emails: Form[Optional[str]] = None,  # JSON string: '["a@b.com","c@d.com"]'
):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    try:
        # Validate brand logo type if provided
        if brand_logo:
            allowed_types = ('image/jpeg', 'image/png', 'image/gif', 'image/webp')
            if brand_logo.content_type not in allowed_types:
                return 400, {"success": False, "message": "Invalid image type. Allowed: jpeg, png, gif, webp"}

        client = Client.objects.create(
            owner=user,
            client_name=client_name,
            brand_logo=brand_logo,
        )

        # Process invites if provided (expects JSON array string)
        emails: List[str] = []
        if invite_emails:
            try:
                emails = json.loads(invite_emails)
            except (json.JSONDecodeError, TypeError):
                # Fallback: treat as single comma-separated string
                emails = [e.strip() for e in invite_emails.split(',') if e.strip()]

        if emails:
            User_ = user.__class__
            for email in emails:
                email = email.strip().lower()
                if email == user.email:
                    continue
                try:
                    invitee = User_.objects.get(email=email)
                    ClientMember.objects.get_or_create(
                        client=client,
                        user=invitee,
                        defaults={"role": "viewer", "status": "pending", "invited_by": user},
                    )
                except User_.DoesNotExist:
                    pass

        return 201, {
            "success": True,
            "message": f"Client '{client.client_name}' created successfully",
            "data": _serialize(client, user, request),
        }

    except Exception as e:
        return 400, {"success": False, "message": f"Failed to create client: {str(e)}"}
