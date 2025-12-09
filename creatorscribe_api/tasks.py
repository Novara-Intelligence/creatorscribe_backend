"""
Celery tasks for background processing
"""
import os
import logging
from celery import shared_task
from django.utils import timezone
from creatorscribe_api.models import Job
from creatorscribe_api.services.transcribe_service import TranscribeService
from creatorscribe_api.services.audio_service import AudioService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_content_generation_task(self, job_id: str):
    """
    Background task to process content generation from uploaded files
    
    Args:
        job_id: UUID of the job to process
        
    Progress stages:
        0% - Task started
        10% - Job loaded
        20% - Video conversion started (if video)
        40% - Transcription/analysis started
        70% - Content generation started
        90% - Finalizing
        100% - Completed
    """
    try:
        # Get the job
        try:
            job = Job.objects.get(job_id=job_id)
        except Job.DoesNotExist:
            logger.error(f"Job {job_id} not found")
            return {"error": f"Job {job_id} not found"}
        
        # Start processing
        job.start_processing()
        logger.info(f"Starting background processing for job {job_id}")
        
        # Progress: 10% - Job loaded
        job.update_progress(10)
        
        file_type = job.file_type
        file_path = job.file_path
        
        # Check if file exists
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            job.mark_failed(error_msg)
            return {"error": error_msg}
        
        # Process based on file type
        if file_type == 'image':
            # Progress: 20% - Starting image analysis
            job.update_progress(20)
            logger.info(f"Processing image: {file_path}")
            
            # Progress: 40% - Analyzing image
            job.update_progress(40)
            
            result = TranscribeService.generate_social_media_content_from_image(
                image_file_path=file_path,
                caption_length=job.caption_length,
                description_length=job.description_length,
                hashtag_count=job.hashtag_count,
                style=job.style,
                custom_prompt=job.custom_prompt
            )
            
            # Progress: 90% - Finalizing
            job.update_progress(90)
            
            if "error" in result:
                job.mark_failed(result["error"])
                return {"error": result["error"]}
            
            job.mark_completed(result)
            logger.info(f"Image processing completed for job {job_id}")
            
        elif file_type == 'video':
            # Progress: 20% - Converting video to audio
            job.update_progress(20)
            logger.info(f"Converting video to audio: {file_path}")
            
            success, audio_path_or_error = AudioService.video_to_audio(file_path)
            
            if not success:
                error_msg = f"Video to audio conversion failed: {audio_path_or_error}"
                logger.error(error_msg)
                job.mark_failed(error_msg)
                return {"error": error_msg}
            
            # Save converted audio path
            job.converted_audio_path = audio_path_or_error
            job.save(update_fields=['converted_audio_path'])
            
            logger.info(f"Video converted to audio: {audio_path_or_error}")
            
            # Progress: 40% - Starting transcription
            job.update_progress(40)
            logger.info(f"Transcribing audio: {audio_path_or_error}")
            
            # Progress: 70% - Generating content
            job.update_progress(70)
            
            result = TranscribeService.generate_social_media_content(
                audio_file_path=audio_path_or_error,
                caption_length=job.caption_length,
                description_length=job.description_length,
                hashtag_count=job.hashtag_count,
                style=job.style,
                custom_prompt=job.custom_prompt
            )
            
            # Progress: 90% - Finalizing
            job.update_progress(90)
            
            if "error" in result:
                job.mark_failed(result["error"])
                return {"error": result["error"]}
            
            job.mark_completed(result)
            logger.info(f"Video processing completed for job {job_id}")
            
        elif file_type == 'audio':
            # Progress: 20% - Starting transcription
            job.update_progress(20)
            logger.info(f"Transcribing audio: {file_path}")
            
            # Progress: 40% - Transcription in progress
            job.update_progress(40)
            
            # Progress: 70% - Generating content
            job.update_progress(70)
            
            result = TranscribeService.generate_social_media_content(
                audio_file_path=file_path,
                caption_length=job.caption_length,
                description_length=job.description_length,
                hashtag_count=job.hashtag_count,
                style=job.style,
                custom_prompt=job.custom_prompt
            )
            
            # Progress: 90% - Finalizing
            job.update_progress(90)
            
            if "error" in result:
                job.mark_failed(result["error"])
                return {"error": result["error"]}
            
            job.mark_completed(result)
            logger.info(f"Audio processing completed for job {job_id}")
        
        return {
            "status": "success",
            "job_id": str(job_id),
            "message": "Content generation completed successfully"
        }
        
    except Exception as e:
        error_msg = f"Task failed: {str(e)}"
        logger.error(f"Job {job_id} failed with error: {error_msg}", exc_info=True)
        
        try:
            job = Job.objects.get(job_id=job_id)
            job.mark_failed(error_msg)
        except Exception as update_error:
            logger.error(f"Failed to update job status: {update_error}")
        
        # Retry the task if it hasn't exceeded max retries
        raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds
