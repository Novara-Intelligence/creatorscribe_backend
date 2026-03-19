# Caption Studio — Backend API Documentation

End-to-end pipeline for AI-generated captions from an already-uploaded **video or image** (`UploadedFile`) — grouped into persistent chat sessions.

- **Video** → extract audio → transcribe → generate captions
- **Image** → generate captions directly (no audio/transcription step)

Files are not uploaded through this API. The frontend passes the `id` of an existing `UploadedFile` record.

---

## Table of Contents

- [Overview](#overview)
- [Django Models](#django-models)
- [API Endpoints](#api-endpoints)
  - [Sessions (Conversations)](#sessions-conversations)
    - [1. Create New Session](#1-create-new-session)
    - [2. List Sessions — History](#2-list-sessions--history)
    - [3. Get Session Detail](#3-get-session-detail)
    - [4. Rename Session](#4-rename-session)
    - [5. Delete Session](#5-delete-session)
  - [Jobs (Turns inside a Session)](#jobs-turns-inside-a-session)
    - [6. Submit Job](#6-submit-job)
    - [7. Stream Job Progress (SSE)](#7-stream-job-progress-sse)
    - [8. Get Job — Polling Fallback](#8-get-job--polling-fallback)
    - [9. Follow-up Prompt](#9-follow-up-prompt)
- [SSE Event Reference](#sse-event-reference)
- [Django SSE View Sketch](#django-sse-view-sketch)
- [Frontend Integration](#frontend-integration)
  - [New Chat](#new-chat)
  - [Load History](#load-history)
  - [Continue Session](#continue-session)
  - [Real-time Job Stream](#real-time-job-stream)
- [Design Decisions](#design-decisions)

---

## Overview

```
User
 │
 ├─► POST /sessions/                        ← start a new chat
 │         │
 │         ▼
 │   CaptionSession (id, title, ...)
 │         │
 │         ├─► POST /sessions/{id}/jobs/    ← upload video OR image + prompt
 │         │         │
 │         │      media_type = "video"          media_type = "image"
 │         │         │                               │
 │         │   [1] Extract audio                     │
 │         │        ──► SSE: audio_ready             │
 │         │   [2] Transcribe audio                  │
 │         │        ──► SSE: transcription_ready      │
 │         │   [3] Generate captions  ◄──────────────┘
 │         │        ──► SSE: caption_ready
 │         │        ──► SSE: done
 │         │
 │         └─► POST /sessions/{id}/jobs/{job_id}/refine/   ← follow-up prompt
 │
 └─► GET /sessions/                         ← load history sidebar
```

Each session holds many **jobs** (turns). Each job holds an optional audio output, optional transcription, and one caption output.
Images skip straight to caption generation — no audio or transcription is produced.

---

## Django Models

```python
# models.py

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from uploads.models import UploadedFile   # your existing model

User = get_user_model()


class CaptionSession(models.Model):
    """
    A conversation / chat session.
    Groups multiple CaptionJob turns under one history entry.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="caption_sessions")
    title      = models.CharField(max_length=255, blank=True)  # auto-set from first job's video name
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)            # bumped on every new job

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or str(self.id)


class CaptionJob(models.Model):
    """
    One turn in a session — references an existing UploadedFile.
    - video jobs:  extract audio → transcribe → generate captions
    - image jobs:  generate captions directly (no audio/transcription)
    - refine jobs: no media — reuse existing audio/transcription, regenerate captions only

    media_type is derived automatically from uploaded_file.file_type on save.
    """

    class Status(models.TextChoices):
        PENDING      = "pending",      "Pending"
        EXTRACTING   = "extracting",   "Extracting Audio"   # video only
        TRANSCRIBING = "transcribing", "Transcribing"       # video only
        CAPTIONING   = "captioning",   "Generating Captions"
        DONE         = "done",         "Done"
        FAILED       = "failed",       "Failed"

    class MediaType(models.TextChoices):
        VIDEO  = "video",  "Video"
        IMAGE  = "image",  "Image"
        NONE   = "none",   "None"   # refine/follow-up jobs

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session       = models.ForeignKey(CaptionSession, on_delete=models.CASCADE, related_name="jobs")
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name="caption_jobs")
    uploaded_file = models.ForeignKey(
        UploadedFile,
        on_delete=models.SET_NULL,
        null=True, blank=True,          # null for refine jobs
        related_name="caption_jobs",
    )
    prompt        = models.TextField(blank=True)
    media_type    = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.NONE)
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    turn_index    = models.PositiveIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["turn_index"]

    def save(self, *args, **kwargs):
        # Auto-derive media_type from the linked UploadedFile's file_type
        if self.uploaded_file:
            ft = self.uploaded_file.file_type or ""
            if ft.startswith("video/"):
                self.media_type = self.MediaType.VIDEO
            elif ft.startswith("image/"):
                self.media_type = self.MediaType.IMAGE
        super().save(*args, **kwargs)

    @property
    def is_video(self):
        return self.media_type == self.MediaType.VIDEO

    @property
    def is_image(self):
        return self.media_type == self.MediaType.IMAGE


class AudioOutput(models.Model):
    """Extracted audio track from the video."""

    job        = models.OneToOneField(CaptionJob, on_delete=models.CASCADE, related_name="audio")
    file       = models.FileField(upload_to="audio/")
    duration   = models.FloatField(null=True)
    language   = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TranscriptionOutput(models.Model):
    """Full transcription result."""

    job        = models.OneToOneField(CaptionJob, on_delete=models.CASCADE, related_name="transcription")
    full_text  = models.TextField()
    language   = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)


class TranscriptionSegment(models.Model):
    """Word-level timestamped segments."""

    transcription = models.ForeignKey(
        TranscriptionOutput, on_delete=models.CASCADE, related_name="segments"
    )
    text         = models.CharField(max_length=200)
    start_second = models.FloatField()
    end_second   = models.FloatField()
    index        = models.PositiveIntegerField()

    class Meta:
        ordering = ["index"]


class CaptionOutput(models.Model):
    """Generated title, description and tags."""

    job         = models.OneToOneField(CaptionJob, on_delete=models.CASCADE, related_name="caption")
    title       = models.CharField(max_length=255)
    description = models.TextField()
    tags        = models.JSONField(default=list)  # ["#GoldenHour", "#CinematicVibes", ...]
    created_at  = models.DateTimeField(auto_now_add=True)
```

---

## API Endpoints

### Sessions (Conversations)

---

#### 1. Create New Session

```
POST /api/caption-studio/sessions/
Content-Type: application/json
Authorization: Bearer <token>
```

**Request** *(optional)*

```json
{ "title": "My travel reel" }
```

If `title` is omitted, the backend auto-sets it from the first job's video filename once submitted.

**Response `201`**

```json
{
  "id": "a1b2c3d4-...",
  "title": "",
  "created_at": "2026-03-19T10:00:00Z",
  "updated_at": "2026-03-19T10:00:00Z",
  "job_count": 0
}
```

---

#### 2. List Sessions — History

```
GET /api/caption-studio/sessions/
Authorization: Bearer <token>
```

**Query params**

| Param    | Type    | Default | Description                     |
|----------|---------|---------|---------------------------------|
| `page`   | integer | 1       | Page number                     |
| `limit`  | integer | 20      | Sessions per page               |
| `search` | string  | —       | Filter by title                 |

**Response `200`**

```json
{
  "count": 42,
  "next": "/api/caption-studio/sessions/?page=2",
  "previous": null,
  "results": [
    {
      "id": "a1b2c3d4-...",
      "title": "Golden hour reel",
      "thumbnail": "/media/thumbnails/a1b2c3d4.jpg",
      "job_count": 3,
      "last_caption": {
        "title": "Golden Hour — When Light Meets Shadow"
      },
      "created_at": "2026-03-19T10:00:00Z",
      "updated_at": "2026-03-19T10:05:00Z"
    }
  ]
}
```

> `thumbnail` is auto-generated from the first frame of the first job's video.

---

#### 3. Get Session Detail

Returns the full session with all turns (jobs) in order.

```
GET /api/caption-studio/sessions/{session_id}/
Authorization: Bearer <token>
```

**Response `200`**

```json
{
  "id": "a1b2c3d4-...",
  "title": "Golden hour reel",
  "created_at": "2026-03-19T10:00:00Z",
  "updated_at": "2026-03-19T10:05:00Z",
  "jobs": [
    {
      "id": "3f8a2c1d-...",
      "turn_index": 0,
      "media_type": "video",
      "prompt": "Make it engaging for Instagram",
      "status": "done",
      "uploaded_file": {
        "id": "f1e2d3c4-...",
        "original_name": "golden-hour.mp4",
        "file_type": "video/mp4",
        "size": 10485760,
        "url": "/media/uploads/golden-hour.mp4"
      },
      "audio": {
        "url": "/media/audio/3f8a2c1d.mp3",
        "duration": 47.3,
        "language": "en"
      },
      "transcription": {
        "full_text": "Capturing the moment when light meets shadow...",
        "language": "en",
        "segments": [
          { "index": 0, "text": "Capturing", "start_second": 0.0, "end_second": 0.6 }
        ]
      },
      "caption": {
        "title": "Golden Hour — When Light Meets Shadow",
        "description": "A cinematic moment captured at dusk...",
        "tags": ["#GoldenHour", "#CinematicVibes"]
      },
      "created_at": "2026-03-19T10:00:00Z"
    },
    {
      "id": "7b6a5c4d-...",
      "turn_index": 1,
      "media_type": "image",
      "prompt": "Make it fun for TikTok",
      "status": "done",
      "uploaded_file": {
        "id": "a2b3c4d5-...",
        "original_name": "sunset.jpg",
        "file_type": "image/jpeg",
        "size": 204800,
        "url": "/media/uploads/sunset.jpg"
      },
      "audio": null,
      "transcription": null,
      "caption": {
        "title": "Chasing Sunsets",
        "description": "Every sunset is a reminder to pause and appreciate the little things.",
        "tags": ["#Sunset", "#TikTok", "#GoldenHour"]
      },
      "created_at": "2026-03-19T10:02:00Z"
    },
    {
      "id": "9c8d7e6f-...",
      "turn_index": 2,
      "media_type": "none",
      "prompt": "Make the description shorter",
      "status": "done",
      "uploaded_file": null,
      "audio": null,
      "transcription": null,
      "caption": {
        "title": "Golden Hour",
        "description": "Chasing light at dusk.",
        "tags": ["#GoldenHour", "#Sunset", "#CinematicVibes"]
      },
      "created_at": "2026-03-19T10:03:00Z"
    }
  ]
}
```

---

#### 4. Rename Session

```
PATCH /api/caption-studio/sessions/{session_id}/
Content-Type: application/json
Authorization: Bearer <token>
```

**Request**

```json
{ "title": "Beach reel — June" }
```

**Response `200`**

```json
{
  "id": "a1b2c3d4-...",
  "title": "Beach reel — June",
  "updated_at": "2026-03-19T10:10:00Z"
}
```

---

#### 5. Delete Session

Deletes the session and all associated jobs, audio files, and outputs.

```
DELETE /api/caption-studio/sessions/{session_id}/
Authorization: Bearer <token>
```

**Response `204 No Content`**

---

### Jobs (Turns inside a Session)

---

#### 6. Submit Job

Start a new turn by referencing an already-uploaded file from `UploadedFile`.

```
POST /api/caption-studio/sessions/{session_id}/jobs/
Content-Type: application/json
Authorization: Bearer <token>
```

**Request fields**

| Field              | Type   | Required | Description                                              |
|--------------------|--------|----------|----------------------------------------------------------|
| `uploaded_file_id` | uuid   | Yes      | ID of an existing `UploadedFile` owned by the user       |
| `prompt`           | string | No       | Additional instructions for captions                     |

> The backend reads `uploaded_file.file_type` to determine the pipeline:
> - `video/*` → full pipeline (audio extraction + transcription + captions)
> - `image/*` → captions only

**Response `201`**

```json
{
  "id": "3f8a2c1d-...",
  "session_id": "a1b2c3d4-...",
  "turn_index": 0,
  "media_type": "image",
  "status": "pending",
  "prompt": "Make it engaging for Instagram",
  "uploaded_file": {
    "id": "f1e2d3c4-...",
    "original_name": "sunset.jpg",
    "file_type": "image/jpeg",
    "size": 204800,
    "url": "/media/uploads/sunset.jpg"
  },
  "created_at": "2026-03-19T10:00:00Z"
}
```

---

#### 7. Stream Job Progress (SSE)

```
GET /api/caption-studio/sessions/{session_id}/jobs/{job_id}/stream/
Authorization: Bearer <token>
Accept: text/event-stream
```

See [SSE Event Reference](#sse-event-reference) for full payload shapes.

---

#### 8. Get Job — Polling Fallback

```
GET /api/caption-studio/sessions/{session_id}/jobs/{job_id}/
Authorization: Bearer <token>
```

**Response `200`** — same shape as the job objects inside [Get Session Detail](#3-get-session-detail).

**`status` values**

| Value          | Applies to     | Meaning                               |
|----------------|----------------|---------------------------------------|
| `pending`      | video + image  | Job queued, not yet started           |
| `extracting`   | video only     | Converting video to audio             |
| `transcribing` | video only     | Transcribing audio                    |
| `captioning`   | video + image  | Generating title, description, tags   |
| `done`         | video + image  | All stages complete                   |
| `failed`       | video + image  | Pipeline failed — see `error_message` |

**`media_type` values**

| Value   | Meaning                                       |
|---------|-----------------------------------------------|
| `video` | Video upload — full pipeline runs             |
| `image` | Image upload — captions generated directly    |
| `none`  | Follow-up / refine job — no media attached    |

---

#### 9. Follow-up Prompt

Text-only refinement. Reuses the audio and transcription from the session's first job.

```
POST /api/caption-studio/sessions/{session_id}/jobs/{job_id}/refine/
Content-Type: application/json
Authorization: Bearer <token>
```

**Request**

```json
{ "prompt": "Make the description shorter and add more hashtags" }
```

**Response `201`** — new job object (same shape as [Submit Job](#6-submit-job) response), `turn_index` incremented.

Streams a `caption_ready` + `done` SSE on its own stream URL once processing completes.

---

## SSE Event Reference

All events follow this envelope:

```
data: {"type": "<event_type>", "data": { ... }}\n\n
```

**Events by media type**

| Event                  | Video | Image |
|------------------------|-------|-------|
| `audio_ready`          | ✓     | —     |
| `transcription_ready`  | ✓     | —     |
| `caption_ready`        | ✓     | ✓     |
| `done`                 | ✓     | ✓     |
| `error`                | ✓     | ✓     |

### `audio_ready`

```json
{
  "type": "audio_ready",
  "data": {
    "url": "/media/audio/3f8a2c1d.mp3",
    "duration": 47.3,
    "language": "en"
  }
}
```

### `transcription_ready`

```json
{
  "type": "transcription_ready",
  "data": {
    "full_text": "Capturing the moment when light meets shadow...",
    "language": "en",
    "segments": [
      { "index": 0, "text": "Capturing", "start_second": 0.0, "end_second": 0.6 },
      { "index": 1, "text": "the",       "start_second": 0.6, "end_second": 0.8 }
    ]
  }
}
```

### `caption_ready`

```json
{
  "type": "caption_ready",
  "data": {
    "title": "Golden Hour — When Light Meets Shadow",
    "description": "A cinematic moment captured at dusk...",
    "tags": ["#GoldenHour", "#CinematicVibes", "#NaturePhotography"]
  }
}
```

### `done`

```json
{
  "type": "done",
  "data": {
    "job_id": "3f8a2c1d-...",
    "session_id": "a1b2c3d4-..."
  }
}
```

### `error`

```json
{
  "type": "error",
  "data": { "message": "Audio extraction failed: unsupported codec" }
}
```

---

## Django SSE View Sketch

```python
# views.py
import json
from django.http import StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from .models import CaptionSession, CaptionJob
from .pubsub import subscribe_to_job


@login_required
def job_stream(request, session_id, job_id):
    def event_stream():
        try:
            job = CaptionJob.objects.get(
                id=job_id,
                session__id=session_id,
                user=request.user,
            )
        except CaptionJob.DoesNotExist:
            yield 'data: {"type":"error","data":{"message":"Job not found"}}\n\n'
            return

        for event_type, payload in subscribe_to_job(job_id):
            data = json.dumps({"type": event_type, "data": payload})
            yield f"data: {data}\n\n"
            if event_type in ("done", "error"):
                break

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
```

---

## Frontend Integration

### New Chat

```ts
// User clicks "New Chat" in the sidebar
async function startNewSession() {
  const res = await fetch("/api/caption-studio/sessions/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const session = await res.json();
  router.push(`/app/caption-studio?session=${session.id}`);
}
```

---

### Load History

```ts
// Sidebar on mount
async function loadHistory(page = 1) {
  const res = await fetch(`/api/caption-studio/sessions/?page=${page}`);
  const { results, count, next } = await res.json();
  // render results as history list items
}
```

---

### Continue Session

```ts
// User clicks a history item
async function openSession(sessionId: string) {
  const res = await fetch(`/api/caption-studio/sessions/${sessionId}/`);
  const session = await res.json();
  // hydrate messages state from session.jobs
  const messages = session.jobs.flatMap((job) => jobToMessages(job));
  setMessages(messages);
}

function jobToMessages(job) {
  const msgs = [];
  if (job.uploaded_file || job.prompt) {
    msgs.push({
      role: "user",
      mediaUrl: job.uploaded_file?.url ?? null,
      mediaType: job.media_type,   // "video" | "image" | "none"
      text: job.prompt,
    });
  }
  msgs.push({
    role: "assistant",
    isStreaming: false,
    isDone: job.status === "done",
    audio: job.audio,
    transcription: job.transcription,
    caption: job.caption,
  });
  return msgs;
}
```

---

### Real-time Job Stream

```ts
async function submitJob(sessionId: string, uploadedFileId: string, prompt: string) {
  // 1. Submit the job — reference existing UploadedFile
  const res0 = await fetch(`/api/caption-studio/sessions/${sessionId}/jobs/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uploaded_file_id: uploadedFileId, prompt }),
  });
  const { id: jobId, media_type } = await res0.json();

  // 2. Open SSE stream
  const es = new EventSource(
    `/api/caption-studio/sessions/${sessionId}/jobs/${jobId}/stream/`
  );

  es.onmessage = (e) => {
    const { type, data } = JSON.parse(e.data);

    // video-only events (media_type === "video")
    if (type === "audio_ready") {
      patch({ showAudio: true, audioUrl: data.url, reasoningText: REASONING_STEPS[1] });
    }
    if (type === "transcription_ready") {
      patch({ showTranscription: true, segments: data.segments, reasoningText: REASONING_STEPS[2] });
    }

    // both video and image
    if (type === "caption_ready") {
      patch({ showCaptions: true, caption: data, isStreaming: false, reasoningText: REASONING_STEPS[3] });
    }
    if (type === "error") {
      patch({ isStreaming: false, error: data.message });
    }
    if (type === "done" || type === "error") {
      es.close();
      setIsThinking(false);
    }
  };

  es.onerror = () => {
    es.close();
    setIsThinking(false);
  };
}
```

> For image jobs the frontend will never receive `audio_ready` or `transcription_ready`. The
> reasoning UI can be simplified to show only a single "Generating captions…" step.

---

## Design Decisions

| Decision | Reason |
|----------|--------|
| **`CaptionSession` wraps many `CaptionJob`s** | One session = one history entry in the sidebar. Multiple turns (first upload + follow-up prompts) all belong to the same session. |
| **`turn_index` on job** | Preserves the order of turns when rebuilding conversation history on the frontend. |
| **`video` nullable on job** | Follow-up (refine) jobs have no video — they reuse the first turn's audio and transcription. |
| **SSE over WebSocket** | Pipeline is unidirectional (server → client). SSE is simpler, works over HTTP/1.1, and reconnects automatically. |
| **Each stage saves before emitting** | Polling fallback and history reload always reflect real persisted state. Safe to reconnect mid-stream. |
| **`updated_at` on session auto-bumped** | Keeps the history sidebar sorted by most recently active session, not just creation date. |
| **`thumbnail` from first video frame** | Gives the history list a visual preview without storing extra user uploads. Generate with FFmpeg on job completion. |
| **`tags` as `JSONField`** | No separate Tag model needed unless you want cross-session tag analytics or autocomplete. |
| **UUID primary keys everywhere** | Safe to expose in URLs without leaking sequential IDs. |
| **FK to `UploadedFile` instead of raw file fields** | Files are already stored and accessible. No duplicate storage. Job creation is a lightweight JSON request — no multipart upload needed at this stage. |
| **`media_type` auto-derived from `file_type`** | `save()` reads `uploaded_file.file_type` (`video/*` vs `image/*`) so the caller never needs to specify it manually. |
| **`media_type` field on job** | Single field drives which pipeline stages run. Frontend uses it to know which SSE events to expect and which cards (audio/transcription) to render. |
| **`image` jobs skip audio/transcription** | No `AudioOutput` or `TranscriptionOutput` rows are created — `audio` and `transcription` fields in the response are `null`. Caption generation receives the image directly. |
| **Same `CaptionOutput` model for both** | Title, description, and tags are produced regardless of input type — no need for a separate image caption model. |
