from django.db import models
from .auth_models import User


class Client(models.Model):
    """
    Client model to store information about clients/brands
    """
    # Primary Key
    id = models.AutoField(primary_key=True)

    # Foreign Key to User
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='clients',
        help_text='User who owns this client account'
    )

    client_name = models.CharField(
        max_length=255,
        help_text='Name of the client/brand',
        blank=True,
        null=True
    )

    brand_logo = models.ImageField(
        upload_to='client_logos/',
        null=True,
        blank=True,
        help_text='Client brand logo'
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when client was created'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Timestamp when client was last updated'
    )

    class Meta:
        db_table = 'clients'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'client_name']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.client_name} ({self.user.email})"
