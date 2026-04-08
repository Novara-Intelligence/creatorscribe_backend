# Caption Studio — Jobs API

Base URL: `/api/v1/caption-studio/jobs/`  
Auth: Bearer token required on all endpoints except `/stream/`

---

## 1. Submit Job

**POST** `/api/v1/caption-studio/jobs/`

Starts the caption pipeline for a session. Returns immediately with a `job_id` — use it to open the SSE stream.

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | UUID | Yes | The session this job belongs to |
| `file_id` | int | No | ID of an already-uploaded file |
| `prompt` | string | No | Optional follow-up instruction |

### Response `201`

```json
{
  "success": true,
  "message": "Job submitted",
  "data": {
    "job_id": "9ac7f665-217c-4ee3-b698-44fc436ac78b",
    "status": "pending",
    "turn_index": 0
  }
}
```

---

## 2. SSE Stream

**GET** `/api/v1/caption-studio/jobs/{job_id}/stream/`

Connect immediately after submitting. Streams events as each pipeline stage completes.  
If you connect **after** the job is already done, all events are replayed instantly from the database.

### Headers

```
Accept: text/event-stream
```

---

## Video Pipeline

Events arrive in this order:

### `audio_ready`
Audio extracted from the video file.

```json
data: {
  "type": "audio_ready",
  "data": {
    "audio_url": "http://example.com/media/audio/abc123.mp3",
    "duration": 12.4,
    "language": "en"
  }
}
```

### `transcription_ready`
Audio transcribed — includes 3 formats at once.

```json
data: {
  "type": "transcription_ready",
  "data": {
    "full_text": "Capturing the moment when light meets shadow, the world holds its breath.",
    "srt": "1\n00:00:00,000 --> 00:00:03,000\nCapturing the moment when light meets\n\n2\n00:00:03,000 --> 00:00:05,000\nshadow, the world holds its breath.",
    "segments": [
      { "text": "Capturing", "startSecond": 0.0, "endSecond": 0.6 },
      { "text": "the",       "startSecond": 0.6, "endSecond": 0.8 },
      { "text": "moment",    "startSecond": 0.8, "endSecond": 1.3 },
      { "text": "when",      "startSecond": 1.3, "endSecond": 1.6 },
      { "text": "light",     "startSecond": 1.6, "endSecond": 2.0 },
      { "text": "meets",     "startSecond": 2.0, "endSecond": 2.4 },
      { "text": "shadow,",   "startSecond": 2.4, "endSecond": 3.0 },
      { "text": "the",       "startSecond": 3.0, "endSecond": 3.2 },
      { "text": "world",     "startSecond": 3.2, "endSecond": 3.6 },
      { "text": "holds",     "startSecond": 3.6, "endSecond": 4.0 },
      { "text": "its",       "startSecond": 4.0, "endSecond": 4.2 },
      { "text": "breath.",   "startSecond": 4.2, "endSecond": 5.0 }
    ]
  }
}
```

### `caption_ready`
Title, description and tags generated from the transcription. **This is the final event — the connection closes after this.**

```json
data: {
  "type": "caption_ready",
  "data": {
    "title": "Golden Hour — When Light Meets Shadow",
    "description": "A cinematic moment captured at dusk, where the interplay of light and shadow tells a story beyond words. Perfect for travel, lifestyle, and nature content.",
    "tags": ["#GoldenHour", "#CinematicVibes", "#NaturePhotography", "#SunsetMoment", "#VisualStorytelling"]
  }
}
```

---

## Image Pipeline

Images skip audio extraction and transcription — `caption_ready` is the only event emitted.

### `caption_ready`
**Final event — the connection closes after this.**

```json
data: {
  "type": "caption_ready",
  "data": {
    "title": "Golden Hour — When Light Meets Shadow",
    "description": "A cinematic moment captured at dusk, where the interplay of light and shadow tells a story beyond words. Perfect for travel, lifestyle, and nature content.",
    "tags": ["#GoldenHour", "#CinematicVibes", "#NaturePhotography", "#SunsetMoment", "#VisualStorytelling"]
  }
}
```

---

## Error Event

Sent if any stage fails. Pipeline stops immediately.

```json
data: {
  "type": "error",
  "data": { "message": "ffmpeg failed to extract audio from video" }
}
```

---

## Event Summary

| Event | Video | Image |
|---|---|---|
| `audio_ready` | ✅ | ❌ |
| `transcription_ready` | ✅ | ❌ |
| `caption_ready` _(final)_ | ✅ | ✅ |
| `error` | ✅ | ✅ |

---

## Job Status Reference

| Status | Description |
|---|---|
| `pending` | Job created, waiting for worker |
| `extracting` | Extracting audio from video |
| `transcribing` | Transcribing audio to text |
| `captioning` | Generating title, description, tags |
| `done` | Pipeline completed successfully |
| `failed` | Pipeline failed — see `error` event |

---

## curl Example

```bash
# 1. Submit a job
curl -X POST http://localhost:8000/api/v1/caption-studio/jobs/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", "file_id": 1}'

# 2. Open the SSE stream
curl -N http://localhost:8000/api/v1/caption-studio/jobs/<job_id>/stream/
```
