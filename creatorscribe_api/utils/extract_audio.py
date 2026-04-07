import json
import os
import subprocess
import tempfile
import uuid

from django.core.files.base import ContentFile


def extract_audio_from_video(video_path: str) -> tuple[ContentFile, float, str] | None:
    """
    Extract audio from a video file using ffmpeg.

    Returns:
        (ContentFile, duration_seconds, filename) on success
        None if ffmpeg fails or file has no audio stream
    """
    tmp_path = None
    try:
        suffix = f"{uuid.uuid4().hex}.mp3"
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(tmp_fd)

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",                   # no video
                "-acodec", "libmp3lame",
                "-q:a", "4",             # variable bitrate ~165kbps
                tmp_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=300,
        )

        if result.returncode != 0 or not os.path.exists(tmp_path):
            return None

        duration = _probe_duration(video_path)

        with open(tmp_path, "rb") as f:
            return ContentFile(f.read()), duration, suffix

    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _probe_duration(video_path: str) -> float:
    """Use ffprobe to get the duration of a media file in seconds."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info.get("format", {}).get("duration", 0))
    except Exception:
        pass
    return 0.0
