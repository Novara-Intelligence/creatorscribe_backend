from ninja import Router
from ..models.caption_models import CaptionSession, CaptionOutput
from ..models.client_models import Client
from ..schemas.caption_schemas import CreateSessionIn, RenameSessionIn, SessionResponseSchema, SessionListResponseSchema
from ..authentication import AuthBearer
from ..utils.pagination import paginate

caption_session_router = Router(tags=["Caption Studio — Sessions"])


def _serialize_session(session, request) -> dict:
    # Thumbnail: auto-generated from first frame of first video job
    thumbnail = None
    if session.thumbnail:
        thumbnail = request.build_absolute_uri(session.thumbnail.url)

    # Last caption: most recent job that has a CaptionOutput
    last_caption = None
    latest_captioned_job = (
        session.jobs
        .filter(caption__isnull=False)
        .select_related("caption")
        .order_by("-created_at")
        .first()
    )
    if latest_captioned_job:
        last_caption = {"title": latest_captioned_job.caption.title}

    return {
        "id": session.id,
        "client_id": session.client_id,
        "title": session.title,
        "thumbnail": thumbnail,
        "job_count": session.jobs.count(),
        "last_caption": last_caption,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@caption_session_router.get(
    "/",
    response={200: SessionListResponseSchema, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="List all Caption Studio sessions for a client",
)
def list_sessions(request, client_id: int, search: str = "", page: int = 1, limit: int = 15):
    user = request.auth

    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        return 404, {"success": False, "message": "Client not found"}

    if not client.is_member(user):
        return 403, {"success": False, "message": "You are not a member of this client"}

    sessions = CaptionSession.objects.filter(client=client).order_by("-created_at")
    if search:
        sessions = sessions.filter(title__icontains=search)
    result = paginate(sessions, page=page, limit=limit)

    return 200, {
        "success": True,
        "message": "Sessions retrieved successfully",
        "data": [_serialize_session(s, request) for s in result["data"]],
        "meta": result["meta"],
    }


@caption_session_router.post(
    "/",
    response={201: SessionResponseSchema, 400: dict, 401: dict, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="Create a new Caption Studio session",
)
def create_session(request, payload: CreateSessionIn):
    user = request.auth

    try:
        client = Client.objects.get(id=payload.client_id)
    except Client.DoesNotExist:
        return 404, {"success": False, "message": "Client not found"}

    if not client.is_member(user):
        return 403, {"success": False, "message": "You are not a member of this client"}

    session = CaptionSession.objects.create(
        client=client,
        user=user,
        title=payload.title,
    )

    return 201, {
        "success": True,
        "message": "Session created successfully",
        "data": _serialize_session(session, request),
    }


@caption_session_router.patch(
    "/{session_id}/",
    response={200: SessionResponseSchema, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="Rename a Caption Studio session (also updates latest caption title if present)",
)
def rename_session(request, session_id, payload: RenameSessionIn):
    user = request.auth

    try:
        session = CaptionSession.objects.get(id=session_id)
    except CaptionSession.DoesNotExist:
        return 404, {"success": False, "message": "Session not found"}

    if not session.client.is_member(user):
        return 403, {"success": False, "message": "You are not a member of this client"}

    session.title = payload.title
    session.save(update_fields=["title", "updated_at"])

    latest_captioned_job = (
        session.jobs
        .filter(caption__isnull=False)
        .select_related("caption")
        .order_by("-created_at")
        .first()
    )
    if latest_captioned_job:
        latest_captioned_job.caption.title = payload.title
        latest_captioned_job.caption.save(update_fields=["title"])

    return 200, {
        "success": True,
        "message": "Session renamed successfully",
        "data": _serialize_session(session, request),
    }


@caption_session_router.delete(
    "/{session_id}/",
    response={200: dict, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="Delete a Caption Studio session",
)
def delete_session(request, session_id):
    user = request.auth

    try:
        session = CaptionSession.objects.get(id=session_id)
    except CaptionSession.DoesNotExist:
        return 404, {"success": False, "message": "Session not found"}

    if not session.client.is_member(user):
        return 403, {"success": False, "message": "You are not a member of this client"}

    session.delete()

    return 200, {"success": True, "message": "Session deleted successfully"}
