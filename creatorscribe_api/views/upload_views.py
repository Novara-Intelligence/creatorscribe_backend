from typing import Optional
from ninja import Router, File, Form
from ninja.files import UploadedFile
from ..models.upload_models import UploadedFile as UploadedFileModel
from ..models.client_models import Client
from ..schemas.upload_schemas import UploadedFileResponseSchema, UploadedFileListResponseSchema
from ..authentication import AuthBearer
from ..utils.pagination import paginate

upload_router = Router(tags=["Uploads"])

ALLOWED_TYPES = (
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'video/mp4',
    'video/quicktime',
    'application/pdf',
)


def _serialize(upload, request) -> dict:
    return {
        "id": upload.id,
        "original_name": upload.original_name,
        "file_url": request.build_absolute_uri(upload.file.url),
        "file_type": upload.file_type,
        "size": upload.size,
        "created_at": upload.created_at,
    }


@upload_router.post(
    "/",
    response={201: UploadedFileResponseSchema, 400: dict, 401: dict},
    auth=AuthBearer(),
    summary="Upload a file",
)
def upload_file(
    request,
    original_name: Form[str],
    file: File[UploadedFile],
    client_id: Form[int],
):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    if file.content_type not in ALLOWED_TYPES:
        return 400, {"success": False, "message": f"File type '{file.content_type}' not allowed"}

    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        return 400, {"success": False, "message": f"No client found with ID {client_id}"}

    upload = UploadedFileModel.objects.create(
        user=user,
        client=client,
        original_name=original_name,
        file=file,
        file_type=file.content_type,
        size=file.size,
    )

    return 201, {
        "success": True,
        "message": "File uploaded successfully",
        "data": _serialize(upload, request),
    }


@upload_router.get(
    "/",
    response={200: UploadedFileListResponseSchema, 401: dict, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="List/search uploaded files",
)
def list_uploads(
    request,
    client_id: int,
    name: Optional[str] = None,
    page: int = 1,
    limit: int = 15,
):
    user = request.auth
    if not user:
        return 401, {"success": False, "message": "Authentication required"}

    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        return 404, {"success": False, "message": f"No client found with ID {client_id}"}

    if not client.is_member(user):
        return 403, {"success": False, "message": "You are not a member of this client"}

    qs = UploadedFileModel.objects.filter(client=client).order_by('-created_at')

    if name:
        qs = qs.filter(original_name__icontains=name)

    result = paginate(qs, page=page, limit=limit)

    return 200, {
        "success": True,
        "message": "Files retrieved successfully",
        "data": [_serialize(u, request) for u in result["data"]],
        "pagination": result["meta"],
    }
