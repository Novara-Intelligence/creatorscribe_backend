import uuid
from django.db import models
from .auth_models import User
from .client_models import Client
from .upload_models import UploadedFile


class CaptionSession(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client     = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='caption_sessions')
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='caption_sessions')
    title      = models.CharField(max_length=255, blank=True)
    thumbnail  = models.ImageField(upload_to='thumbnails/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'caption_sessions'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['client', '-updated_at']),
            models.Index(fields=['user', '-updated_at']),
        ]

    def __str__(self):
        return self.title or str(self.id)


class CaptionJob(models.Model):

    class Status(models.TextChoices):
        PENDING      = 'pending',      'Pending'
        EXTRACTING   = 'extracting',   'Extracting Audio'
        TRANSCRIBING = 'transcribing', 'Transcribing'
        CAPTIONING   = 'captioning',   'Generating Captions'
        DONE         = 'done',         'Done'
        FAILED       = 'failed',       'Failed'

    class MediaType(models.TextChoices):
        VIDEO = 'video', 'Video'
        IMAGE = 'image', 'Image'
        NONE  = 'none',  'None'

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session       = models.ForeignKey(CaptionSession, on_delete=models.CASCADE, related_name='jobs')
    client        = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='caption_jobs')
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='caption_jobs')
    uploaded_file = models.ForeignKey(
        UploadedFile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='caption_jobs',
    )
    prompt        = models.TextField(blank=True)
    media_type    = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.NONE)
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    turn_index    = models.PositiveIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'caption_jobs'
        ordering = ['turn_index']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['session', 'turn_index']),
        ]

    def save(self, *args, **kwargs):
        if self.uploaded_file_id and self.uploaded_file:
            ft = self.uploaded_file.file_type or ''
            if ft.startswith('video/'):
                self.media_type = self.MediaType.VIDEO
            elif ft.startswith('image/'):
                self.media_type = self.MediaType.IMAGE
        super().save(*args, **kwargs)

    @property
    def is_video(self):
        return self.media_type == self.MediaType.VIDEO

    @property
    def is_image(self):
        return self.media_type == self.MediaType.IMAGE

    def __str__(self):
        return f'Job {self.turn_index} — {self.session_id}'


class AudioOutput(models.Model):
    job        = models.OneToOneField(CaptionJob, on_delete=models.CASCADE, related_name='audio')
    file       = models.FileField(upload_to='audio/')
    duration   = models.FloatField(null=True)
    language   = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'caption_audio_outputs'


class TranscriptionOutput(models.Model):
    job        = models.OneToOneField(CaptionJob, on_delete=models.CASCADE, related_name='transcription')
    full_text  = models.TextField()
    language   = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'caption_transcription_outputs'


class TranscriptionSegment(models.Model):
    transcription = models.ForeignKey(
        TranscriptionOutput, on_delete=models.CASCADE, related_name='segments'
    )
    text         = models.CharField(max_length=200)
    start_second = models.FloatField()
    end_second   = models.FloatField()
    index        = models.PositiveIntegerField()

    class Meta:
        db_table = 'caption_transcription_segments'
        ordering = ['index']


class CaptionOutput(models.Model):
    job         = models.OneToOneField(CaptionJob, on_delete=models.CASCADE, related_name='caption')
    title       = models.CharField(max_length=255)
    description = models.TextField()
    tags        = models.JSONField(default=list)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'caption_outputs'
