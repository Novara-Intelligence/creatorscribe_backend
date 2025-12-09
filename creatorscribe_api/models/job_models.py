"""
Job model for tracking content generation tasks
"""
from django.db import models
from django.utils import timezone
from .auth_models import User
from .client_models import Client
import uuid


class Job(models.Model):
    """
    Model to track content generation jobs (audio, video, image processing)
    """
    
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),  # File uploaded, not processing yet
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    FILE_TYPE_CHOICES = [
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('image', 'Image'),
    ]
    
    # Job identification
    job_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text='Unique identifier for the job'
    )
    
    # Client and user information
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='jobs',
        help_text='Client/brand this job is for'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_jobs',
        help_text='User who created the job'
    )
    file_type = models.CharField(
        max_length=10,
        choices=FILE_TYPE_CHOICES,
        help_text='Type of file being processed'
    )
    original_filename = models.CharField(
        max_length=255,
        help_text='Original name of the uploaded file'
    )
    file_path = models.CharField(
        max_length=500,
        help_text='Path to the uploaded file'
    )
    
    # Processing information
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Current status of the job'
    )
    progress = models.IntegerField(
        default=0,
        help_text='Processing progress (0-100)'
    )
    
    # For video files - converted audio path
    converted_audio_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Path to converted audio file (for video processing)'
    )
    
    # Generation parameters
    caption_length = models.CharField(
        max_length=10,
        default='medium',
        help_text='Caption length: short, medium, or long'
    )
    description_length = models.CharField(
        max_length=10,
        default='medium',
        help_text='Description length: short, medium, or long'
    )
    hashtag_count = models.IntegerField(
        default=15,
        help_text='Number of hashtags to generate'
    )
    style = models.CharField(
        max_length=20,
        default='casual',
        help_text='Writing style for content generation (professional, casual, educational, etc.)'
    )
    custom_prompt = models.TextField(
        blank=True,
        null=True,
        help_text='Custom style prompt (used when style=custom)'
    )
    
    # Results
    result_data = models.JSONField(
        blank=True,
        null=True,
        help_text='Generated content (caption, description, hashtags, etc.)'
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text='Error message if job failed'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the job was created'
    )
    started_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When the job processing started'
    )
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When the job was completed or failed'
    )
    
    class Meta:
        verbose_name = 'Job'
        verbose_name_plural = 'Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['job_id']),
        ]
    
    def __str__(self):
        return f"{self.job_id} - {self.user.email} - {self.file_type} - {self.status}"
    
    def start_processing(self):
        """Mark job as started"""
        self.status = 'processing'
        self.started_at = timezone.now()
        self.progress = 0
        self.save(update_fields=['status', 'started_at', 'progress'])
    
    def update_progress(self, progress: int):
        """Update job progress (0-100)"""
        self.progress = max(0, min(100, progress))
        self.save(update_fields=['progress'])
    
    def mark_completed(self, result_data):
        """Mark job as completed with results"""
        self.status = 'completed'
        self.result_data = result_data
        self.completed_at = timezone.now()
        self.progress = 100
        self.save(update_fields=['status', 'result_data', 'completed_at', 'progress'])
    
    def mark_failed(self, error_message):
        """Mark job as failed with error message"""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])
    
    def get_processing_time(self):
        """Get the total processing time in seconds"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None
    
    def get_duration_display(self):
        """Get human-readable processing duration"""
        seconds = self.get_processing_time()
        if seconds is None:
            return "N/A"
        
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
