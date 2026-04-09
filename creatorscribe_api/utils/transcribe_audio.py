from openai import OpenAI
from django.conf import settings


def transcribe_audio(audio_path: str) -> dict | None:
    """
    Transcribe an audio file using OpenAI Whisper (whisper-1).

    Returns:
        {
            "full_text": str,
            "language": str,
            "segments": [{"text": str, "startSecond": float, "endSecond": float}, ...]
        }
        or None if transcription fails.
    """
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word"],
            )

        segments = [
            {
                "text": w.word,
                "startSecond": round(w.start, 3),
                "endSecond": round(w.end, 3),
            }
            for w in (response.words or [])
        ]

        return {
            "full_text": response.text.strip(),
            "language": response.language or "en",
            "segments": segments,
        }

    except Exception:
        return None
