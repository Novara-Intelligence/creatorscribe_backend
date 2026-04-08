# CreatorScribe Backend

Django REST API backend for CreatorScribe — a Caption Studio platform that processes videos and images into captions, transcriptions, and social media content via a real-time streaming pipeline.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.2 + Django Ninja |
| Auth | JWT (django-ninja-jwt) |
| Task Queue | Celery 5.4 |
| Broker / Cache | Redis |
| Media Processing | ffmpeg (audio extraction) |
| Database | SQLite (dev) |
| API Docs | Auto-generated at `/api/v1/docs` |

---

## Project Structure

```
creatorscribe_backend/
├── creatorscribe/              # Django project config
│   ├── settings.py
│   ├── urls.py                 # Router registration + SSE URL
│   └── celery.py               # Celery app config
├── creatorscribe_api/
│   ├── models/
│   │   ├── auth_models.py
│   │   ├── client_models.py
│   │   ├── upload_models.py
│   │   └── caption_models.py   # CaptionSession, CaptionJob, AudioOutput,
│   │                           #   TranscriptionOutput, TranscriptionSegment,
│   │                           #   CaptionOutput
│   ├── views/
│   │   ├── auth_views.py
│   │   ├── client_views.py
│   │   ├── upload_views.py
│   │   ├── caption_session_views.py   # Session CRUD + load session/jobs
│   │   └── caption_job_views.py       # Submit job + SSE stream
│   ├── tasks/
│   │   └── caption_tasks.py    # Celery pipeline: extract → transcribe → caption
│   ├── schemas/
│   │   └── caption_schemas.py
│   └── utils/
│       ├── extract_audio.py    # ffmpeg audio extraction
│       ├── thumbnail.py        # ffmpeg thumbnail generation
│       └── pagination.py
├── requirements.txt
├── CAPTION_JOBS_API.md         # Jobs API reference
└── CAPTION_STUDIO_API.md       # Studio API reference
```

---

## Prerequisites

- Python 3.12+
- Redis
- ffmpeg + ffprobe

```bash
# macOS
brew install redis ffmpeg

# Ubuntu
sudo apt install redis-server ffmpeg
```

---

## Setup

```bash
# 1. Create and activate virtualenv
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env   # fill in SECRET_KEY, DB settings, etc.

# 4. Run migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser
```

---

## Running Locally

Requires **3 terminals**:

```bash
# Terminal 1 — Redis
redis-server

# Terminal 2 — Django
python manage.py runserver

# Terminal 3 — Celery worker
celery -A creatorscribe worker -l info
```

Verify everything is up:
```bash
redis-cli ping          # → PONG
curl http://localhost:8000/api/v1/docs   # → Swagger UI
```

---

## API Overview

Base URL: `http://localhost:8000/api/v1/`  
Auth: `Authorization: Bearer <token>`  
Docs: `GET /api/v1/docs`

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register/` | Register new user |
| POST | `/auth/login/` | Login, get JWT token |
| POST | `/auth/refresh/` | Refresh token |

### Uploads
| Method | Endpoint | Description |
|---|---|---|
| POST | `/uploads/` | Upload a video or image file |

### Caption Studio — Sessions
| Method | Endpoint | Description |
|---|---|---|
| GET | `/caption-studio/sessions/?client_id=&search=` | List sessions |
| POST | `/caption-studio/sessions/` | Create session |
| GET | `/caption-studio/sessions/{id}/` | Get single session |
| PATCH | `/caption-studio/sessions/{id}/` | Rename session |
| DELETE | `/caption-studio/sessions/{id}/` | Delete session |
| GET | `/caption-studio/sessions/{id}/jobs/` | Load all jobs for a session |

### Caption Studio — Jobs
| Method | Endpoint | Description |
|---|---|---|
| POST | `/caption-studio/jobs/` | Submit a new job |
| GET | `/caption-studio/jobs/{id}/stream/` | SSE stream — real-time pipeline events |

---

## Caption Pipeline

When a job is submitted the Celery task runs these stages, publishing an SSE event immediately after each:

```
Video input:
  extracting   → audio_ready         (real MP3 extracted via ffmpeg)
  transcribing → transcription_ready (full_text + SRT + word segments)
  captioning   → caption_ready       (title + description + tags)  ← final event

Image input:
  captioning   → caption_ready  ← final event
```

Connect to the SSE stream right after submitting:
```bash
# Submit job
curl -X POST http://localhost:8000/api/v1/caption-studio/jobs/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "...", "file_id": 1}'

# Open stream (no auth required)
curl -N http://localhost:8000/api/v1/caption-studio/jobs/<job_id>/stream/
```

If you connect after the job has already finished, all events are replayed from the database instantly.

See [CAPTION_JOBS_API.md](CAPTION_JOBS_API.md) for full event schema reference.

---

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for local dev |
| `ALLOWED_HOSTS` | Comma-separated hosts |
| `CELERY_BROKER_URL` | Redis URL (default: `redis://localhost:6379/0`) |
| `MEDIA_ROOT` | Path for uploaded/generated files |

---

## Troubleshooting

**Redis connection refused**
```bash
brew services start redis   # macOS
sudo systemctl start redis  # Linux
```

**Celery task not found**
```bash
# Restart worker after any task file changes
pkill -f "celery worker"
celery -A creatorscribe worker -l info
# Look for the task in [tasks] on startup
```

**ffmpeg not found**
```bash
brew install ffmpeg    # macOS
sudo apt install ffmpeg  # Ubuntu
which ffmpeg           # verify path
```
