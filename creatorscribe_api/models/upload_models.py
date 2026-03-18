import uuid
import os
from django.db import models
from .auth_models import User
from .client_models import Client


def upload_file_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    unique_name = uuid.uuid4().hex[:12]
    return f'uploads/{unique_name}{ext}'


class UploadedFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploads')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploads')
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to=upload_file_path)
    file_type = models.CharField(max_length=100)
    size = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name
