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
    ClientCreateResponseSchema
)

User = get_user_model()

# JWT Authentication
class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)
            return user
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
    """
    Get all clients for the authenticated user
    
    Returns:
        - List of clients with their details
        - Total count of clients
    """
    user = request.auth
    
    if not user:
        return 401, {
            "success": False,
            "message": "Authentication required",
        }
    
    # Get all clients for the user
    clients = Client.objects.filter(user=user).order_by('-created_at')
    
    # Serialize clients
    client_data = [
        {
            "id": client.id,
            "client_name": client.client_name,
            "contact_person": client.contact_person,
            "contact_email": client.contact_email,
            "contact_phone": client.contact_phone,
            "industry_type": client.industry_type,
            "brand_logo": client.brand_logo.url if client.brand_logo else None,
            "facebook_url": client.facebook_url,
            "instagram_url": client.instagram_url,
            "youtube_url": client.youtube_url,
            "linkedin_url": client.linkedin_url,
            "twitter_url": client.twitter_url,
            "tiktok_url": client.tiktok_url,
            "preferred_post_time": client.preferred_post_time.strftime('%H:%M') if client.preferred_post_time else None,
            "created_at": client.created_at,
            "updated_at": client.updated_at,
        }
        for client in clients
    ]
    
    return 200, {
        "success": True,
        "message": "Clients retrieved successfully",
        "data": client_data,
        "count": len(client_data)
    }


@client_router.get(
    "/my-clients/{client_id}",
    response={200: ClientResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Get specific client details",
    description="Returns details of a specific client by ID for the authenticated user"
)
def get_client_detail(request, client_id: int):
    """
    Get details of a specific client
    
    Args:
        client_id: The ID of the client to retrieve
    
    Returns:
        - Client details if found and belongs to user
        - 404 if not found or doesn't belong to user
    """
    user = request.auth
    
    if not user:
        return 401, {
            "success": False,
            "message": "Invalid or missing authentication token",
        }
    
    # Get client and verify ownership
    try:
        client = Client.objects.get(id=client_id, user=user)
    except Client.DoesNotExist:
        return 404, {
            "success": False,
            "message": f"No client found with ID {client_id} for this user",
        }
    
    return 200, {
        "id": client.id,
        "client_name": client.client_name,
        "contact_person": client.contact_person,
        "contact_email": client.contact_email,
        "contact_phone": client.contact_phone,
        "industry_type": client.industry_type,
        "brand_logo": client.brand_logo.url if client.brand_logo else None,
        "facebook_url": client.facebook_url,
        "instagram_url": client.instagram_url,
        "youtube_url": client.youtube_url,
        "linkedin_url": client.linkedin_url,
        "twitter_url": client.twitter_url,
        "tiktok_url": client.tiktok_url,
        "preferred_post_time": client.preferred_post_time.strftime('%H:%M') if client.preferred_post_time else None,
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
    """
    Add a new client for the authenticated user
    
    Args:
        payload: Client data including required and optional fields
    
    Returns:
        - 201: Client created successfully with client details
        - 400: Validation error or client creation failed
        - 401: Authentication required
    """
    from datetime import datetime
    
    user = request.auth
    
    if not user:
        return 401, {
            "success": False,
            "message": "Authentication required",
        }
    
    try:
        # Validate industry type
        valid_industries = [choice[0] for choice in Client.INDUSTRY_CHOICES]
        if payload.industry_type not in valid_industries:
            return 400, {
                "success": False,
                "message": f"Invalid industry type. Must be one of: {', '.join(valid_industries)}",
            }
        
        # Parse preferred_post_time if provided
        preferred_time = None
        if payload.preferred_post_time:
            try:
                # Validate time format (HH:MM)
                time_parts = payload.preferred_post_time.split(':')
                if len(time_parts) != 2:
                    raise ValueError("Invalid time format")
                
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                
                if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                    raise ValueError("Invalid time values")
                
                preferred_time = datetime.strptime(payload.preferred_post_time, '%H:%M').time()
            except ValueError:
                return 400, {
                    "success": False,
                    "message": "Invalid preferred_post_time format. Use HH:MM (24-hour format).",
                }
        
        # Handle brand_logo if provided
        brand_logo_file = None
        if payload.brand_logo:
            try:
                import base64
                import tempfile
                import os
                from django.core.files.base import ContentFile
                
                # Check if it's a base64 encoded image
                if payload.brand_logo.startswith('data:image/'):
                    # Extract the base64 data
                    header, data = payload.brand_logo.split(',', 1)
                    # Get the file extension from the header
                    file_ext = header.split('/')[1].split(';')[0]
                    # Decode base64
                    image_data = base64.b64decode(data)
                    # Create a ContentFile
                    brand_logo_file = ContentFile(image_data, name=f"brand_logo_{user.id}_{payload.client_name[:20]}.{file_ext}")
                elif payload.brand_logo.startswith('/'):
                    # Handle file path (if uploading via file path)
                    if os.path.exists(payload.brand_logo):
                        with open(payload.brand_logo, 'rb') as f:
                            file_ext = payload.brand_logo.split('.')[-1]
                            brand_logo_file = ContentFile(f.read(), name=f"brand_logo_{user.id}_{payload.client_name[:20]}.{file_ext}")
            except Exception as e:
                return 400, {
                    "success": False,
                    "message": f"Invalid brand_logo format: {str(e)}",
                }

        # Create the client
        client = Client.objects.create(
            user=user,
            client_name=payload.client_name,
            contact_person=payload.contact_person,
            contact_email=payload.contact_email,
            contact_phone=payload.contact_phone,
            industry_type=payload.industry_type,
            brand_logo=brand_logo_file,
            facebook_url=payload.facebook_url,
            instagram_url=payload.instagram_url,
            youtube_url=payload.youtube_url,
            linkedin_url=payload.linkedin_url,
            twitter_url=payload.twitter_url,
            tiktok_url=payload.tiktok_url,
            preferred_post_time=preferred_time,
        )
        
        # Prepare response data
        client_data = {
            "id": client.id,
            "client_name": client.client_name,
            "contact_person": client.contact_person,
            "contact_email": client.contact_email,
            "contact_phone": client.contact_phone,
            "industry_type": client.industry_type,
            "brand_logo": client.brand_logo.url if client.brand_logo else None,
            "facebook_url": client.facebook_url,
            "instagram_url": client.instagram_url,
            "youtube_url": client.youtube_url,
            "linkedin_url": client.linkedin_url,
            "twitter_url": client.twitter_url,
            "tiktok_url": client.tiktok_url,
            "preferred_post_time": client.preferred_post_time.strftime('%H:%M') if client.preferred_post_time else None,
            "created_at": client.created_at,
            "updated_at": client.updated_at,
        }
        
        return 201, {
            "success": True,
            "message": f"Client '{client.client_name}' created successfully",
            "data": client_data
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Failed to create client: {str(e)}",
        }
