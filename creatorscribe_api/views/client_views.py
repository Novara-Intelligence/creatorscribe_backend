from ninja import Router
from ninja.security import HttpBearer
from ninja_jwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from django.db.models import Q
from ..models.client_models import Client
from ..schemas import (
    ErrorResponseSchema,
    ClientResponseSchema,
    ClientListResponseSchema,
    ClientCreateRequestSchema,
    ClientCreateResponseSchema,
)

User = get_user_model()


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            access_token = AccessToken(token)
            return User.objects.get(id=access_token['user_id'])
        except Exception:
            return None


client_router = Router(tags=["Clients"])


def _serialize(client: Client, user) -> dict:
    return {
        "id": client.id,
        "client_name": client.client_name,
        "brand_logo": client.brand_logo.url if client.brand_logo else None,
        "role": client.get_user_role(user),
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
        "data": [_serialize(c, user) for c in clients],
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

    return 200, _serialize(client, user)


@client_router.post(
    "/add-client",
    response={201: ClientCreateResponseSchema, 400: ErrorResponseSchema, 401: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Create a new client",
)
def add_client(request, payload: ClientCreateRequestSchema):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    try:
        brand_logo_file = None
        if payload.brand_logo:
            try:
                import base64
                import os
                from django.core.files.base import ContentFile

                if payload.brand_logo.startswith('data:image/'):
                    header, data = payload.brand_logo.split(',', 1)
                    file_ext = header.split('/')[1].split(';')[0]
                    image_data = base64.b64decode(data)
                    brand_logo_file = ContentFile(image_data, name=f"brand_logo_{user.id}.{file_ext}")
                elif payload.brand_logo.startswith('/') and os.path.exists(payload.brand_logo):
                    with open(payload.brand_logo, 'rb') as f:
                        file_ext = payload.brand_logo.split('.')[-1]
                        brand_logo_file = ContentFile(f.read(), name=f"brand_logo_{user.id}.{file_ext}")
            except Exception as e:
                return 400, {"success": False, "message": f"Invalid brand_logo: {str(e)}"}

        client = Client.objects.create(
            owner=user,
            client_name=payload.client_name,
            brand_logo=brand_logo_file,
        )

        return 201, {
            "success": True,
            "message": f"Client '{client.client_name}' created successfully",
            "data": _serialize(client, user),
        }

    except Exception as e:
        return 400, {"success": False, "message": f"Failed to create client: {str(e)}"}
