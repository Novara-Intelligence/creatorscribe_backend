from ninja import Router
from ..models.caption_models import CaptionSession, CaptionOutput
from ..models.client_models import Client
from ..schemas.caption_schemas import CreateSessionIn, RenameSessionIn, SessionResponseSchema, SessionListResponseSchema, JobListResponseSchema
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


@caption_session_router.get(
    "/{session_id}/",
    response={200: SessionResponseSchema, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="Get a single Caption Studio session",
)
def get_session(request, session_id):
    user = request.auth

    try:
        session = CaptionSession.objects.get(id=session_id)
    except CaptionSession.DoesNotExist:
        return 404, {"success": False, "message": "Session not found"}

    if not session.client.is_member(user):
        return 403, {"success": False, "message": "You are not a member of this client"}

    return 200, {
        "success": True,
        "message": "Session retrieved successfully",
        "data": _serialize_session(session, request),
    }


@caption_session_router.get(
    "/{session_id}/jobs/",
    response={200: JobListResponseSchema, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="Get all jobs for a session with full output data",
)
def get_session_jobs(request, session_id):
    from ..tasks.caption_tasks import _segments_to_srt

    user = request.auth

    try:
        session = CaptionSession.objects.get(id=session_id)
    except CaptionSession.DoesNotExist:
        return 404, {"success": False, "message": "Session not found"}

    if not session.client.is_member(user):
        return 403, {"success": False, "message": "You are not a member of this client"}

    jobs = (
        session.jobs
        .select_related("audio", "transcription", "caption", "uploaded_file")
        .prefetch_related("transcription__segments")
        .order_by("turn_index")
    )

    data = []
    for job in jobs:
        uploaded_file = None
        if job.uploaded_file_id:
            f = job.uploaded_file
            uploaded_file = {
                "id": f.id,
                "original_name": f.original_name,
                "file_url": request.build_absolute_uri(f.file.url),
                "file_type": f.file_type,
                "size": f.size,
            }

        audio = None
        if hasattr(job, "audio"):
            audio = {
                "audio_url": request.build_absolute_uri(job.audio.file.url) if job.audio.file else None,
                "duration": job.audio.duration,
                "language": job.audio.language,
            }

        transcription = None
        if hasattr(job, "transcription"):
            segments = [
                {"text": s.text, "startSecond": s.start_second, "endSecond": s.end_second}
                for s in job.transcription.segments.all()
            ]
            transcription = {
                "full_text": job.transcription.full_text,
                "srt": _segments_to_srt(segments),
                "segments": segments,
            }

        caption = None
        if hasattr(job, "caption"):
            caption = {
                "title": job.caption.title,
                "description": job.caption.description,
                "tags": job.caption.tags,
            }

        data.append({
            "id": job.id,
            "turn_index": job.turn_index,
            "status": job.status,
            "media_type": job.media_type,
            "prompt": job.prompt,
            "created_at": job.created_at,
            "uploaded_file": uploaded_file,
            "audio": audio,
            "transcription": transcription,
            "caption": caption,
        })

    return 200, {
        "success": True,
        "message": "Jobs retrieved successfully",
        "data": data,
    }
