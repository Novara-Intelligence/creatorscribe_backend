import json
import random
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
# MVP random mock data pools
# ---------------------------------------------------------------------------

_TRANSCRIPTION_POOL = [
    [
        ("Capturing", 0.0, 0.6), ("the", 0.6, 0.8), ("moment", 0.8, 1.3),
        ("when", 1.3, 1.6), ("light", 1.6, 2.0), ("meets", 2.0, 2.4),
        ("shadow,", 2.4, 3.0), ("the", 3.0, 3.2), ("world", 3.2, 3.6),
        ("holds", 3.6, 4.0), ("its", 4.0, 4.2), ("breath.", 4.2, 5.0),
    ],
    [
        ("The", 0.0, 0.3), ("city", 0.3, 0.7), ("never", 0.7, 1.1),
        ("sleeps,", 1.1, 1.6), ("lights", 1.6, 2.0), ("flicker", 2.0, 2.5),
        ("through", 2.5, 2.8), ("the", 2.8, 3.0), ("rain.", 3.0, 3.8),
    ],
    [
        ("Every", 0.0, 0.4), ("step", 0.4, 0.7), ("forward", 0.7, 1.2),
        ("is", 1.2, 1.4), ("a", 1.4, 1.5), ("story", 1.5, 1.9),
        ("waiting", 1.9, 2.4), ("to", 2.4, 2.6), ("be", 2.6, 2.8),
        ("told.", 2.8, 3.5),
    ],
    [
        ("Beyond", 0.0, 0.5), ("the", 0.5, 0.7), ("horizon", 0.7, 1.3),
        ("lies", 1.3, 1.6), ("a", 1.6, 1.7), ("world", 1.7, 2.1),
        ("unseen", 2.1, 2.7), ("by", 2.7, 2.9), ("most.", 2.9, 3.6),
    ],
    [
        ("In", 0.0, 0.2), ("the", 0.2, 0.4), ("stillness", 0.4, 1.0),
        ("of", 1.0, 1.2), ("dawn,", 1.2, 1.8), ("nature", 1.8, 2.3),
        ("speaks", 2.3, 2.8), ("its", 2.8, 3.0), ("truth.", 3.0, 3.9),
    ],
]

_CAPTION_POOL = [
    {
        "title": "Golden Hour — When Light Meets Shadow",
        "description": "A cinematic moment captured at dusk, where the interplay of light and shadow tells a story beyond words. Perfect for travel, lifestyle, and nature content.",
        "tags": ["#GoldenHour", "#CinematicVibes", "#NaturePhotography", "#SunsetMoment", "#VisualStorytelling"],
    },
    {
        "title": "City Lights After the Rain",
        "description": "Urban energy captured in its purest form — rain-soaked streets reflecting neon signs and the pulse of a city that never stops. Ideal for street photography and lifestyle reels.",
        "tags": ["#CityVibes", "#StreetPhotography", "#NightLife", "#UrbanArt", "#RainyDay"],
    },
    {
        "title": "One Step Forward",
        "description": "A motivational snapshot of progress and momentum. Whether you're building a brand or chasing a dream, every step counts. Great for personal growth and entrepreneurship content.",
        "tags": ["#Motivation", "#Growth", "#Mindset", "#ContentCreator", "#Entrepreneur"],
    },
    {
        "title": "Beyond the Horizon",
        "description": "Wide open landscapes that remind us how vast and beautiful the world truly is. Perfect for travel vlogs, adventure reels, and wanderlust-driven storytelling.",
        "tags": ["#Travel", "#Adventure", "#Wanderlust", "#Explore", "#LandscapePhotography"],
    },
    {
        "title": "The Stillness of Dawn",
        "description": "Early morning light, quiet streets, and the gentle hush before the world wakes up. A serene visual for wellness, mindfulness, and lifestyle creators.",
        "tags": ["#MorningVibes", "#Wellness", "#Mindfulness", "#Lifestyle", "#PeacefulMoments"],
    },
]


def _random_mock() -> tuple[list[dict], str, dict]:
    """Pick a random transcription + matching caption from the pool."""
    index = random.randint(0, len(_TRANSCRIPTION_POOL) - 1)
    raw_segments = _TRANSCRIPTION_POOL[index]
    segments = [
        {"text": t, "startSecond": s, "endSecond": e}
        for t, s, e in raw_segments
    ]
    full_text = " ".join(t for t, _, _ in raw_segments)
    caption = _CAPTION_POOL[index]
    return segments, full_text, caption

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

    time.sleep(5)

    # Stage 2 — Transcribe
    job.status = CaptionJob.Status.TRANSCRIBING
    job.save(update_fields=["status", "updated_at"])

    segments, full_text, caption = _random_mock()

    transcription = TranscriptionOutput.objects.create(
        job=job,
        full_text=full_text,
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
        for i, seg in enumerate(segments)
    ])

    _publish(job_id, "transcription_ready", {
        "full_text": full_text,
        "srt": _segments_to_srt(segments),
        "segments": segments,
    })

    time.sleep(5)

    # Stage 3 — Caption
    _generate_caption(job, job_id, caption)


def _pipeline_image(job: CaptionJob, job_id: str):
    """Image path: skip audio/transcription, go straight to caption."""

    job.status = CaptionJob.Status.CAPTIONING
    job.save(update_fields=["status", "updated_at"])

    _, _, caption = _random_mock()
    _generate_caption(job, job_id, caption)


def _generate_caption(job: CaptionJob, job_id: str, caption: dict):
    """Shared final stage — saves CaptionOutput and publishes caption_ready."""

    job.status = CaptionJob.Status.CAPTIONING
    job.save(update_fields=["status", "updated_at"])

    CaptionOutput.objects.create(
        job=job,
        title=caption["title"],
        description=caption["description"],
        tags=caption["tags"],
    )

    _publish(job_id, "caption_ready", caption)

    time.sleep(3)


# ---------------------------------------------------------------------------
# Pipeline task
# ---------------------------------------------------------------------------

@shared_task
def run_caption_pipeline(job_id: str):
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
