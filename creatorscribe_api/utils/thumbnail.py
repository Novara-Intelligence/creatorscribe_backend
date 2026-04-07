import io
import subprocess
import tempfile
import os
from django.core.files.base import ContentFile


def generate_video_thumbnail(video_path: str) -> ContentFile | None:
    """
    Extract the first frame of a video using ffmpeg and return it as a
    ContentFile (JPEG) ready to be saved to an ImageField.
    Returns None if ffmpeg is unavailable or extraction fails.
    """
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                tmp_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )

        if result.returncode != 0 or not os.path.exists(tmp_path):
            return None

        with open(tmp_path, "rb") as f:
            return ContentFile(f.read())

    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
