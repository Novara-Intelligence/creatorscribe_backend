import os
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models.caption_models import CaptionJob
from .utils.thumbnail import generate_video_thumbnail


@receiver(post_save, sender=CaptionJob)
def set_session_thumbnail(sender, instance, created, **kwargs):
    """
    When a video CaptionJob is saved, generate a thumbnail for its session
    if the session doesn't have one yet.
    """
    if not created:
        return
    if not instance.is_video:
        return

    session = instance.session
    if session.thumbnail:
        return

    uploaded_file = instance.uploaded_file
    if not uploaded_file or not uploaded_file.file:
        return

    try:
        video_path = uploaded_file.file.path
    except (ValueError, NotImplementedError):
        return

    thumbnail_data = generate_video_thumbnail(video_path)
    if thumbnail_data is None:
        return

    filename = f"{session.id}.jpg"
    session.thumbnail.save(filename, thumbnail_data, save=True)
