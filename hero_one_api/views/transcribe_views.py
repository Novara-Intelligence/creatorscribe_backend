"""
Transcribe views for handling file uploads and content generation
"""
import os
import logging
from pathlib import Path
from ninja import Router, File, Query
from ninja.files import UploadedFile
from ninja.security import HttpBearer
from rest_framework_simplejwt.tokens import AccessToken
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from typing import Optional

from hero_one_api.models import Job, Client
from hero_one_api.services.transcribe_service import TranscribeService
from hero_one_api.services.audio_service import AudioService
from hero_one_api.schemas import ErrorResponseSchema
from hero_one_api.tasks import process_content_generation_task

logger = logging.getLogger(__name__)

User = get_user_model()

# JWT Authentication
class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)
            return user
        except Exception:
            return None

transcribe_router = Router(tags=["Transcribe"])


@transcribe_router.get("/styles", response={200: dict})
def get_available_styles(request):
    """
    Get available writing styles for content generation
    
    Returns a list of available styles with descriptions
    """
    from hero_one_api.services.transcribe_service import TranscribeService
    
    return 200, {
        "styles": TranscribeService.get_available_styles(),
        "message": "Available writing styles for content generation"
    }


# Supported file extensions
AUDIO_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac']
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']


def get_file_type(filename: str) -> Optional[str]:
    """Determine file type based on extension"""
    ext = Path(filename).suffix.lower()
    
    if ext in AUDIO_EXTENSIONS:
        return 'audio'
    elif ext in VIDEO_EXTENSIONS:
        return 'video'
    elif ext in IMAGE_EXTENSIONS:
        return 'image'
    return None


def save_uploaded_file(file: UploadedFile, user_id: int, client_name: str) -> str:
    """Save uploaded file to media directory"""
    # Sanitize client name for use in file path
    import re
    safe_client_name = re.sub(r'[^\w\s-]', '', client_name)
    safe_client_name = re.sub(r'[-\s]+', '_', safe_client_name)
    safe_client_name = safe_client_name.strip('_').lower()
    
    # Create upload directory structure: media/uploads/{user_id}/{client_name}/
    upload_dir = Path(settings.MEDIA_ROOT) / 'uploads' / str(user_id) / safe_client_name
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename with timestamp
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{file.name}"
    file_path = upload_dir / filename
    
    # Save file
    with open(file_path, 'wb') as f:
        for chunk in file.chunks():
            f.write(chunk)
    
    return str(file_path)


@transcribe_router.post("/upload-file", response={200: dict, 400: ErrorResponseSchema, 401: ErrorResponseSchema}, auth=AuthBearer())
def upload_file_only(
    request,
    client_id: int,
    file: UploadedFile = File(...)
):
    """
    Step 1: Upload a file only (no processing yet)
    
    - **client_id**: ID of the client/brand this content is for (required)
    - **file**: Audio (mp3, wav, etc.), Video (mp4, mov, etc.), or Image (jpg, png, etc.)
    
    Returns file information. User can then adjust configuration and call /generate to start processing.
    """
    try:
        # Check authentication
        if not request.auth:
            return 401, {
                "success": False,
                "message": "Authentication required",
            }
        
        user = request.auth
        
        # Check if client exists and belongs to user
        try:
            client = Client.objects.get(id=client_id, user=user)
        except Client.DoesNotExist:
            return 400, {
                "success": False,
                "message": f"Client with ID {client_id} not found or does not belong to you",
            }
        
        # Validate file type
        file_type = get_file_type(file.name)
        if not file_type:
            return 400, {
                "success": False,
                "message": f"Unsupported file type. Supported formats: "
                         f"Audio ({', '.join(AUDIO_EXTENSIONS)}), "
                         f"Video ({', '.join(VIDEO_EXTENSIONS)}), "
                         f"Image ({', '.join(IMAGE_EXTENSIONS)})"
            }
        
        # Save uploaded file
        file_path = save_uploaded_file(file, user.id, client.client_name)
        logger.info(f"File uploaded: {file_path} by user {user.email} for client {client.client_name}")
        
        # Create job in 'uploaded' state (not processing yet)
        job = Job.objects.create(
            client=client,
            user=user,
            file_type=file_type,
            original_filename=file.name,
            file_path=file_path,
            status='uploaded',  # New status: uploaded but not processing
            caption_length='medium',  # Defaults, can be changed when calling /generate
            description_length='medium',
            hashtag_count=15,
            style='casual',  # Default style
            custom_prompt=None,
        )
        
        logger.info(f"File uploaded, job created: {job.job_id} for user {user.email}")
        
        return 200, {
            "message": "File uploaded successfully. Call /generate with job_id to start processing.",
            "job_id": str(job.job_id),
            "client_id": client.id,
            "client_name": client.client_name,
            "file_type": file_type,
            "original_filename": file.name,
            "status": "uploaded",
            "note": "File is uploaded. You can now configure settings and call POST /api/transcribe/generate to start processing."
        }
    
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return 400, {"success": False, "message": f"Upload failed: {str(e)}"}


@transcribe_router.post("/generate", response={200: dict, 400: ErrorResponseSchema, 401: ErrorResponseSchema}, auth=AuthBearer())
def generate_content_from_upload(
    request,
    job_id: str,
    caption_length: str = Query('medium'),
    description_length: str = Query('medium'),
    hashtag_count: int = Query(15),
    style: str = Query('casual'),
    custom_prompt: Optional[str] = Query(None, min_length=0)
):
    """
    Step 2: Start content generation for an uploaded file
    
    - **job_id**: UUID of the job from /upload-file endpoint (required)
    - **caption_length**: 'short', 'medium', or 'long' (default: medium)
    - **description_length**: 'short', 'medium', or 'long' (default: medium)
    - **hashtag_count**: Number of hashtags (5-30, default: 15)
    - **style**: Writing style - 'professional', 'casual', 'educational', 'entertaining', 'inspirational', 'technical', 'storytelling', 'minimalist', 'viral', or 'luxury' (default: casual)
    - **custom_prompt**: Additional custom instructions (optional, works with any style)
    
    Returns job information with task_id to track progress
    """
    try:
        # Check authentication
        if not request.auth:
            return 401, {
                "success": False,
                "message": "Authentication required",
            }
        
        user = request.auth
        
        # Get job
        try:
            job = Job.objects.get(job_id=job_id, user=user)
        except Job.DoesNotExist:
            return 400, {
                "success": False,
                "message": f"Job with ID {job_id} not found or does not belong to you",
            }
        
        # Check if job is in correct state
        if job.status not in ['uploaded', 'failed']:
            return 400, {
                "success": False,
                "message": f"Job is already {job.status}. Can only generate from uploaded or failed jobs.",
            }
        
        # Check if user can use credit
        if not user.can_use_credit():
            return 400, {"success": False, "message": "Daily credit limit reached. Please upgrade to premium for unlimited access."}
        
        # Validate parameters
        if caption_length not in ['short', 'medium', 'long']:
            return 400, {"success": False, "message": "caption_length must be 'short', 'medium', or 'long'"}
        
        if description_length not in ['short', 'medium', 'long']:
            return 400, {"success": False, "message": "description_length must be 'short', 'medium', or 'long'"}
        
        # Import TranscribeService to access style templates
        from hero_one_api.services.transcribe_service import TranscribeService
        valid_styles = list(TranscribeService.STYLE_TEMPLATES.keys())
        if style not in valid_styles:
            return 400, {"success": False, "message": f"style must be one of: {', '.join(valid_styles)}"}
        
        hashtag_count = max(5, min(30, hashtag_count))
        
        # Handle empty custom_prompt (convert empty string to None)
        if custom_prompt is not None and custom_prompt.strip() == '':
            custom_prompt = None
        
        # Use credit
        success, message = user.use_credit(
            action_type='content_generation',
            description=f"Generate content from {job.file_type}: {job.original_filename}"
        )
        
        if not success:
            return 400, {"success": False, "message": message}
        
        # Update job configuration
        job.caption_length = caption_length
        job.description_length = description_length
        job.hashtag_count = hashtag_count
        job.style = style
        job.custom_prompt = custom_prompt
        job.status = 'pending'
        job.save(update_fields=['caption_length', 'description_length', 'hashtag_count', 'style', 'custom_prompt', 'status'])
        
        logger.info(f"Starting content generation for job: {job.job_id}")
        
        # Queue the task for background processing
        task = process_content_generation_task.delay(str(job.job_id))
        logger.info(f"Background task queued for job {job.job_id}, task_id: {task.id}")
        
        return 200, {
            "message": "Content generation started. Processing in background.",
            "job_id": str(job.job_id),
            "task_id": task.id,
            "client_id": job.client.id,
            "client_name": job.client.client_name,
            "file_type": job.file_type,
            "status": "pending",
            "credits_used": message,
            "note": "Use GET /api/transcribe/job/{job_id} to check progress and get results"
        }
    
    except Exception as e:
        logger.error(f"Generate content failed: {str(e)}")
        return 400, {"success": False, "message": f"Generate content failed: {str(e)}"}


@transcribe_router.post("/upload", response={200: dict, 400: ErrorResponseSchema, 401: ErrorResponseSchema}, auth=AuthBearer())
def upload_and_generate_content(
    request,
    client_id: int,
    file: UploadedFile = File(...),
    caption_length: str = 'medium',
    description_length: str = 'medium',
    hashtag_count: int = 15
):
    """
    Upload a file and immediately start content generation (single step - legacy endpoint)
    
    - **client_id**: ID of the client/brand this content is for (required)
    - **file**: Audio (mp3, wav, etc.), Video (mp4, mov, etc.), or Image (jpg, png, etc.)
    - **caption_length**: 'short', 'medium', or 'long' (default: medium)
    - **description_length**: 'short', 'medium', or 'long' (default: medium)
    - **hashtag_count**: Number of hashtags (5-30, default: 15)
    
    Returns job information with job_id to track progress
    
    Note: For better UX, use /upload-file followed by /generate for two-step process
    """
    try:
        # Check authentication
        if not request.auth:
            return 401, {
                "success": False,
                "message": "Authentication required",
            }
        
        user = request.auth
        
        # Check if client exists and belongs to user
        try:
            client = Client.objects.get(id=client_id, user=user)
        except Client.DoesNotExist:
            return 400, {
                "success": False,
                "message": f"Client with ID {client_id} not found or does not belong to you",
            }
        
        # Check if user can use credit
        if not user.can_use_credit():
            return 400, {"success": False, "message": "Daily credit limit reached. Please upgrade to premium for unlimited access."}
        
        # Validate file type
        file_type = get_file_type(file.name)
        if not file_type:
            return 400, {
                "success": False,
                "message": f"Unsupported file type. Supported formats: "
                         f"Audio ({', '.join(AUDIO_EXTENSIONS)}), "
                         f"Video ({', '.join(VIDEO_EXTENSIONS)}), "
                         f"Image ({', '.join(IMAGE_EXTENSIONS)})"
            }
        
        # Validate parameters
        if caption_length not in ['short', 'medium', 'long']:
            return 400, {"success": False, "message": "caption_length must be 'short', 'medium', or 'long'"}
        
        if description_length not in ['short', 'medium', 'long']:
            return 400, {"success": False, "message": "description_length must be 'short', 'medium', or 'long'"}
        
        hashtag_count = max(5, min(30, hashtag_count))
        
        # Save uploaded file
        file_path = save_uploaded_file(file, user.id, client.client_name)
        logger.info(f"File uploaded: {file_path} by user {user.email} for client {client.client_name}")
        
        # Use credit
        success, message = user.use_credit(
            action_type='content_generation',
            description=f"Generate content from {file_type}: {file.name}"
        )
        
        if not success:
            # Delete uploaded file if credit usage failed
            if os.path.exists(file_path):
                os.remove(file_path)
            return 400, {"success": False, "message": message}
        
        # Create job
        job = Job.objects.create(
            client=client,
            user=user,
            file_type=file_type,
            original_filename=file.name,
            file_path=file_path,
            caption_length=caption_length,
            description_length=description_length,
            hashtag_count=hashtag_count,
            status='pending'
        )
        
        logger.info(f"Job created: {job.job_id} for user {user.email}")
        
        # Queue the task for background processing
        task = process_content_generation_task.delay(str(job.job_id))
        logger.info(f"Background task queued for job {job.job_id}, task_id: {task.id}")
        
        return 200, {
            "message": "File uploaded successfully. Processing in background.",
            "job_id": str(job.job_id),
            "task_id": task.id,
            "client_id": client.id,
            "client_name": client.client_name,
            "file_type": file_type,
            "status": "pending",
            "credits_used": message,
        }
    
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return 400, {"success": False, "message": f"Upload failed: {str(e)}"}

@transcribe_router.get("/job/{job_id}", response={200: dict, 400: ErrorResponseSchema, 404: ErrorResponseSchema, 401: ErrorResponseSchema}, auth=AuthBearer())
def get_job_status(request, job_id: str):
    """
    Get the status and results of a job
    
    - **job_id**: UUID of the job
    
    Returns job status, results (if completed), and processing information
    """
    try:
        # Check authentication
        if not request.auth:
            return 401, {"success": False, "message": "Authentication required"}
        
        user = request.auth
        
        # Get job
        try:
            job = Job.objects.get(job_id=job_id, user=user)
        except Job.DoesNotExist:
            return 404, {"success": False, "message": "Job not found"}
        
        response = {
            "job_id": str(job.job_id),
            "client_id": job.client.id,
            "client_name": job.client.client_name,
            "file_type": job.file_type,
            "original_filename": job.original_filename,
            "status": job.status,
            "progress": job.progress,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "processing_time": job.get_duration_display(),
        }
        
        if job.status == 'completed':
            response["result"] = job.result_data
        elif job.status == 'failed':
            response["error"] = job.error_message
        
        return 200, response
        
    except Exception as e:
        logger.error(f"Get job status failed: {str(e)}")
        return 400, {"success": False, "message": f"Failed to get job status: {str(e)}"}


@transcribe_router.get("/jobs", response={200: dict, 400: ErrorResponseSchema, 401: ErrorResponseSchema}, auth=AuthBearer())
def list_user_jobs(request, limit: int = Query(10), offset: int = Query(0), client_id: int = Query(None)):
    """
    List all jobs for the authenticated user
    
    - **limit**: Number of jobs to return (default: 10, max: 100)
    - **offset**: Number of jobs to skip (default: 0)
    - **client_id**: Filter by specific client ID (optional)
    
    Returns paginated list of user's jobs
    """
    try:
        # Check authentication
        if not request.auth:
            return 401, {"success": False, "message": "Authentication required"}
        
        user = request.auth
        
        # Validate and limit pagination
        limit = min(max(1, limit), 100)
        offset = max(0, offset)
        
        # Get jobs - filter by client if provided
        jobs_query = Job.objects.filter(user=user)
        
        if client_id:
            # Verify client belongs to user
            try:
                client = Client.objects.get(id=client_id, user=user)
                jobs_query = jobs_query.filter(client=client)
            except Client.DoesNotExist:
                return 400, {"success": False, "message": f"Client with ID {client_id} not found or does not belong to you"}
        
        jobs = jobs_query.select_related('client')[offset:offset + limit]
        total_count = jobs_query.count()
        
        jobs_list = []
        for job in jobs:
            job_data = {
                "job_id": str(job.job_id),
                "client_id": job.client.id,
                "client_name": job.client.client_name,
                "file_type": job.file_type,
                "original_filename": job.original_filename,
                "status": job.status,
                "progress": job.progress,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "processing_time": job.get_duration_display(),
            }
            
            # Add video URL if file type is video
            if job.file_type == 'video' and job.file_path:
                # Convert file path to media URL
                # file_path is absolute, we need to make it relative to MEDIA_ROOT
                relative_path = job.file_path.replace(str(settings.MEDIA_ROOT), '').lstrip('/')
                video_url = f"{settings.MEDIA_URL}{relative_path}"
                job_data["source_url"] = video_url
            
            if job.file_type == 'image' and job.file_path:
                # Convert file path to media URL
                relative_path = job.file_path.replace(str(settings.MEDIA_ROOT), '').lstrip('/')
                image_url = f"{settings.MEDIA_URL}{relative_path}"
                job_data["source_url"] = image_url
            
            jobs_list.append(job_data)
        
        return 200, {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "jobs": jobs_list
        }
        
    except Exception as e:
        logger.error(f"List jobs failed: {str(e)}")
        return 400, {"success": False, "message": f"Failed to list jobs: {str(e)}"}
