from ninja import Router
from ninja.security import HttpBearer
from ninja_jwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from ..models.client_models import Client
from ..models.social_account_models import SocialAccount
from ..schemas.auth_schemas import ErrorResponseSchema
from ..schemas.social_account_schemas import (
    SocialAccountConnectSchema,
    SocialAccountResponseSchema,
    SocialAccountListResponseSchema,
    SocialAccountDetailResponseSchema,
)

User = get_user_model()

VALID_PLATFORMS = [choice[0] for choice in SocialAccount.PLATFORM_CHOICES]


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            access_token = AccessToken(token)
            return User.objects.get(id=access_token['user_id'])
        except Exception:
            return None


social_router = Router(tags=["Social Accounts"])


def _serialize(account: SocialAccount) -> dict:
    return {
        "id": account.id,
        "platform": account.platform,
        "account_name": account.account_name,
        "expires_at": account.expires_at,
        "is_token_expired": account.is_token_expired,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def _get_client(client_id: int, user) -> Client | None:
    try:
        from django.db.models import Q
        return Client.objects.get(
            Q(id=client_id) & (
                Q(owner=user) |
                Q(members__user=user, members__status='accepted')
            )
        )
    except Client.DoesNotExist:
        return None


@social_router.get(
    "/{client_id}/social-accounts",
    response={200: SocialAccountListResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="List connected social accounts for a client",
)
def list_social_accounts(request, client_id: int):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    client = _get_client(client_id, user)
    if not client:
        return 404, {"success": False, "message": f"No client found with ID {client_id}"}

    accounts = SocialAccount.objects.filter(client=client).order_by('platform')

    return 200, {
        "success": True,
        "message": "Social accounts retrieved successfully",
        "data": [_serialize(a) for a in accounts],
        "count": accounts.count(),
    }


@social_router.post(
    "/{client_id}/social-accounts/connect",
    response={201: SocialAccountDetailResponseSchema, 400: ErrorResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Connect a social account to a client",
)
def connect_social_account(request, client_id: int, payload: SocialAccountConnectSchema):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    client = _get_client(client_id, user)
    if not client:
        return 404, {"success": False, "message": f"No client found with ID {client_id}"}

    if payload.platform not in VALID_PLATFORMS:
        return 400, {"success": False, "message": f"Invalid platform. Must be one of: {', '.join(VALID_PLATFORMS)}"}

    account, created = SocialAccount.objects.update_or_create(
        client=client,
        platform=payload.platform,
        defaults={
            "account_name": payload.account_name,
            "access_token": payload.access_token,
            "refresh_token": payload.refresh_token,
            "expires_at": payload.expires_at,
        }
    )

    action = "connected" if created else "reconnected"
    return 201, {
        "success": True,
        "message": f"{account.get_platform_display()} account {action} successfully",
        "data": _serialize(account),
    }


@social_router.delete(
    "/{client_id}/social-accounts/{platform}",
    response={200: ErrorResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Disconnect a social account from a client",
)
def disconnect_social_account(request, client_id: int, platform: str):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    client = _get_client(client_id, user)
    if not client:
        return 404, {"success": False, "message": f"No client found with ID {client_id}"}

    try:
        account = SocialAccount.objects.get(client=client, platform=platform)
    except SocialAccount.DoesNotExist:
        return 404, {"success": False, "message": f"No {platform} account connected to this client"}

    platform_display = account.get_platform_display()
    account.delete()

    return 200, {"success": True, "message": f"{platform_display} account disconnected successfully"}
