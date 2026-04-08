import json
import time
import redis
from celery import shared_task
from django.conf import settings

from ..utils.extract_audio import extract_audio_from_video
from ..models.caption_models import (
    CaptionJob,
    AudioOutput,
    TranscriptionOutput,
    TranscriptionSegment,
    CaptionOutput,
)

redis_client = redis.from_url(settings.CELERY_BROKER_URL)

# ---------------------------------------------------------------------------
# MVP static mock data
# ---------------------------------------------------------------------------

MOCK_SEGMENTS = [
    {"text": "Capturing", "startSecond": 0.0,  "endSecond": 0.6},
    {"text": "the",       "startSecond": 0.6,  "endSecond": 0.8},
    {"text": "moment",    "startSecond": 0.8,  "endSecond": 1.3},
    {"text": "when",      "startSecond": 1.3,  "endSecond": 1.6},
    {"text": "light",     "startSecond": 1.6,  "endSecond": 2.0},
    {"text": "meets",     "startSecond": 2.0,  "endSecond": 2.4},
    {"text": "shadow,",   "startSecond": 2.4,  "endSecond": 3.0},
    {"text": "the",       "startSecond": 3.0,  "endSecond": 3.2},
    {"text": "world",     "startSecond": 3.2,  "endSecond": 3.6},
    {"text": "holds",     "startSecond": 3.6,  "endSecond": 4.0},
    {"text": "its",       "startSecond": 4.0,  "endSecond": 4.2},
    {"text": "breath.",   "startSecond": 4.2,  "endSecond": 5.0},
]

MOCK_FULL_TEXT = "Capturing the moment when light meets shadow, the world holds its breath."

MOCK_CAPTION = {
    "title": "Golden Hour — When Light Meets Shadow",
    "description": (
        "A cinematic moment captured at dusk, where the interplay of light and shadow "
        "tells a story beyond words. Perfect for travel, lifestyle, and nature content."
    ),
    "tags": [
        "#GoldenHour",
        "#CinematicVibes",
        "#NaturePhotography",
        "#SunsetMoment",
        "#VisualStorytelling",
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _publish(job_id: str, type_: str, data: dict = None):
    payload = {"type": type_}
    if data is not None:
        payload["data"] = data
    redis_client.publish(f"caption_job:{job_id}", json.dumps(payload))


def _segments_to_srt(segments: list[dict]) -> str:
    """Convert word-level segments to SRT format (grouped into ~5-word lines)."""
    lines = []
    chunk, chunk_start, chunk_end = [], None, None
    index = 1

    for seg in segments:
        if chunk_start is None:
            chunk_start = seg["startSecond"]
        chunk.append(seg["text"])
        chunk_end = seg["endSecond"]

        if len(chunk) >= 5:
            lines.append(_srt_block(index, chunk_start, chunk_end, " ".join(chunk)))
            index += 1
            chunk, chunk_start, chunk_end = [], None, None

    if chunk:
        lines.append(_srt_block(index, chunk_start, chunk_end, " ".join(chunk)))

    return "\n\n".join(lines)


def _srt_block(index: int, start: float, end: float, text: str) -> str:
    return f"{index}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{text}"


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _pipeline_video(job: CaptionJob, job_id: str):
    """Video path: extract audio → transcribe → caption."""

    # Stage 1 — Extract audio
    job.status = CaptionJob.Status.EXTRACTING
    job.save(update_fields=["status", "updated_at"])

    video_path = job.uploaded_file.file.path
    result = extract_audio_from_video(video_path)
    if result is None:
        raise RuntimeError("ffmpeg failed to extract audio from video")

    audio_content, duration, filename = result

    audio_output = AudioOutput(job=job, duration=duration, language="en")
    audio_output.file.save(filename, audio_content, save=True)

    _publish(job_id, "audio_ready", {
        "audio_url": audio_output.file.url,
        "duration": audio_output.duration,
        "language": audio_output.language,
    })

    time.sleep(40)

    # Stage 2 — Transcribe
    job.status = CaptionJob.Status.TRANSCRIBING
    job.save(update_fields=["status", "updated_at"])

    transcription = TranscriptionOutput.objects.create(
        job=job,
        full_text=MOCK_FULL_TEXT,
        language="en",
    )

    TranscriptionSegment.objects.bulk_create([
        TranscriptionSegment(
            transcription=transcription,
            text=seg["text"],
            start_second=seg["startSecond"],
            end_second=seg["endSecond"],
            index=i,
        )
        for i, seg in enumerate(MOCK_SEGMENTS)
    ])

    _publish(job_id, "transcription_ready", {
        "full_text": MOCK_FULL_TEXT,
        "srt": _segments_to_srt(MOCK_SEGMENTS),
        "segments": MOCK_SEGMENTS,
    })

    time.sleep(50)

    # Stage 3 — Caption
    _generate_caption(job, job_id)


def _pipeline_image(job: CaptionJob, job_id: str):
    """Image path: skip audio/transcription, go straight to caption."""

    job.status = CaptionJob.Status.CAPTIONING
    job.save(update_fields=["status", "updated_at"])

    _generate_caption(job, job_id)


def _generate_caption(job: CaptionJob, job_id: str):
    """Shared final stage — saves CaptionOutput and publishes caption_ready."""

    job.status = CaptionJob.Status.CAPTIONING
    job.save(update_fields=["status", "updated_at"])

    CaptionOutput.objects.create(
        job=job,
        title=MOCK_CAPTION["title"],
        description=MOCK_CAPTION["description"],
        tags=MOCK_CAPTION["tags"],
    )

    _publish(job_id, "caption_ready", MOCK_CAPTION)

    time.sleep(30)


# ---------------------------------------------------------------------------
# Pipeline task
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0)
def run_caption_pipeline(self, job_id: str):
    try:
        job = CaptionJob.objects.select_related("uploaded_file", "session").get(id=job_id)
    except CaptionJob.DoesNotExist:
        return

    try:
        if job.is_video:
            _pipeline_video(job, job_id)
        else:
            # image or no media — skip audio/transcription, go straight to captions
            _pipeline_image(job, job_id)

        job.status = CaptionJob.Status.DONE
        job.save(update_fields=["status", "updated_at"])

    except Exception as exc:
        job.status = CaptionJob.Status.FAILED
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])
        _publish(job_id, "error", {"message": str(exc)})
        raise
