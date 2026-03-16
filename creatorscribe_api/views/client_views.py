from ninja import Router
from ninja.security import HttpBearer
from ninja_jwt.tokens import AccessToken
from django.contrib.auth import get_user_model
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
            user_id = access_token['user_id']
            return User.objects.get(id=user_id)
        except Exception:
            return None


client_router = Router(tags=["Clients"])

@client_router.get(
    "/my-clients",
    response={200: ClientListResponseSchema, 401: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Get list of clients for logged-in user",
    description="Returns all clients associated with the authenticated user"
)
def get_user_clients(request):
    user = request.auth

    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    clients = Client.objects.filter(user=user).order_by('-created_at')

    client_data = [
        {
            "id": c.id,
            "client_name": c.client_name,
            "brand_logo": c.brand_logo.url if c.brand_logo else None,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in clients
    ]

    return 200, {
        "success": True,
        "message": "Clients retrieved successfully",
        "data": client_data,
    }


@client_router.get(
    "/my-clients/{client_id}",
    response={200: ClientResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Get specific client details",
    description="Returns details of a specific client by ID for the authenticated user"
)
def get_client_detail(request, client_id: int):
    user = request.auth

    if not user:
        return 401, {"success": False, "message": "Invalid or missing authentication token"}

    try:
        client = Client.objects.get(id=client_id, user=user)
    except Client.DoesNotExist:
        return 404, {"success": False, "message": f"No client found with ID {client_id} for this user"}

    return 200, {
        "id": client.id,
        "client_name": client.client_name,
        "brand_logo": client.brand_logo.url if client.brand_logo else None,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
    }


@client_router.post(
    "/add-client",
    response={201: ClientCreateResponseSchema, 400: ErrorResponseSchema, 401: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Add a new client",
    description="Create a new client for the authenticated user"
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
            user=user,
            client_name=payload.client_name,
            brand_logo=brand_logo_file,
        )

        return 201, {
            "success": True,
            "message": f"Client '{client.client_name}' created successfully",
        }

    except Exception as e:
        return 400, {"success": False, "message": f"Failed to create client: {str(e)}"}
