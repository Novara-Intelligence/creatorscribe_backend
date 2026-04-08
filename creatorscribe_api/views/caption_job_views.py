import json
import redis
from django.conf import settings
from django.http import StreamingHttpResponse
from ninja import Router

from ..authentication import AuthBearer
from ..models.caption_models import CaptionJob, CaptionSession
from ..models.upload_models import UploadedFile
from ..schemas.caption_schemas import SubmitJobIn

caption_job_router = Router(tags=["Caption Studio — Jobs"])

redis_client = redis.from_url(settings.CELERY_BROKER_URL)


# ---------------------------------------------------------------------------
# POST / — Submit a job
# ---------------------------------------------------------------------------

@caption_job_router.post(
    "/",
    response={201: dict, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="Submit a new caption job for a session",
)
def submit_job(request, payload: SubmitJobIn):
    from ..tasks.caption_tasks import run_caption_pipeline

    user = request.auth

    try:
        session = CaptionSession.objects.select_related("client").get(id=payload.session_id)
    except CaptionSession.DoesNotExist:
        return 404, {"success": False, "message": "Session not found"}

    if not session.client.is_member(user):
        return 403, {"success": False, "message": "You are not a member of this client"}

    uploaded_file = None
    if payload.file_id:
        # New file explicitly provided — use it
        try:
            uploaded_file = UploadedFile.objects.get(id=payload.file_id, client=session.client)
        except UploadedFile.DoesNotExist:
            return 404, {"success": False, "message": "Uploaded file not found"}
    else:
        # No file provided — inherit from the most recent job in this session
        prev_job = session.jobs.filter(uploaded_file__isnull=False).order_by("-turn_index").first()
        if prev_job:
            uploaded_file = prev_job.uploaded_file

    turn_index = session.jobs.count()

    job = CaptionJob.objects.create(
        session=session,
        client=session.client,
        user=user,
        uploaded_file=uploaded_file,
        prompt=payload.prompt,
        turn_index=turn_index,
        status=CaptionJob.Status.PENDING,
    )

    run_caption_pipeline.delay(str(job.id))

    return 201, {
        "success": True,
        "message": "Job submitted",
        "data": {
            "job_id": str(job.id),
            "status": job.status,
            "turn_index": job.turn_index,
        },
    }


# ---------------------------------------------------------------------------
# GET /{job_id}/stream/ — SSE stream (plain Django view, registered in urls.py)
# ---------------------------------------------------------------------------

def stream_job(request, job_id):
    """
    Server-Sent Events endpoint.

    On connect it first replays any stages already saved in the DB (so late
    clients don't miss events), then subscribes to Redis pubsub for live
    events if the job is still running.
    """
    def _sse(type_, data=None):
        payload = {"type": type_}
        if data is not None:
            payload["data"] = data
        return f"data: {json.dumps(payload)}\n\n"

    def event_generator():
        try:
            job = CaptionJob.objects.select_related(
                "audio", "transcription", "caption"
            ).prefetch_related("transcription__segments").get(id=job_id)
        except CaptionJob.DoesNotExist:
            yield _sse("error", {"message": "Job not found"})
            return

        # --- Replay already-completed stages from DB ---
        replayed_final = False

        if hasattr(job, "audio"):
            yield _sse("audio_ready", {
                "audio_url": request.build_absolute_uri(job.audio.file.url),
                "duration": job.audio.duration,
                "language": job.audio.language,
            })

        if hasattr(job, "transcription"):
            segments = [
                {"text": s.text, "startSecond": s.start_second, "endSecond": s.end_second}
                for s in job.transcription.segments.all()
            ]
            from ..tasks.caption_tasks import _segments_to_srt
            yield _sse("transcription_ready", {
                "full_text": job.transcription.full_text,
                "srt": _segments_to_srt(segments),
                "segments": segments,
            })

        if hasattr(job, "caption"):
            yield _sse("caption_ready", {
                "title": job.caption.title,
                "description": job.caption.description,
                "tags": job.caption.tags,
            })

        if job.status == CaptionJob.Status.DONE:
            replayed_final = True
        elif job.status == CaptionJob.Status.FAILED:
            yield _sse("error", {"message": job.error_message})
            replayed_final = True

        if replayed_final:
            return

        # --- Job still running — subscribe to Redis for live events ---
        pubsub = redis_client.pubsub()
        channel = f"caption_job:{job_id}"
        pubsub.subscribe(channel)

        try:
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                raw = message["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode()

                yield f"data: {raw}\n\n"

                try:
                    if json.loads(raw).get("type") in ("caption_ready", "error"):
                        break
                except (json.JSONDecodeError, AttributeError):
                    break
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    response = StreamingHttpResponse(event_generator(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
