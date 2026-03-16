from django.db import models
from .client_models import Client


class SocialAccount(models.Model):
    """
    Stores connected social media accounts for a client.
    Each client can have one account per platform.
    """
    PLATFORM_CHOICES = [
        ('youtube', 'YouTube'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook (Meta)'),
        ('linkedin', 'LinkedIn'),
        ('twitter', 'Twitter / X'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='social_accounts',
        help_text='Client this social account belongs to'
    )
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        help_text='Social media platform'
    )
    account_name = models.CharField(
        max_length=255,
        help_text='Display name or handle of the account'
    )
    access_token = models.TextField(
        help_text='OAuth access token'
    )
    refresh_token = models.TextField(
        blank=True,
        null=True,
        help_text='OAuth refresh token'
    )
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When the access token expires'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'social_accounts'
        verbose_name = 'Social Account'
        verbose_name_plural = 'Social Accounts'
        unique_together = [('client', 'platform')]
        indexes = [
            models.Index(fields=['client', 'platform']),
        ]

    def __str__(self):
        return f"{self.client.client_name} — {self.get_platform_display()} (@{self.account_name})"

    @property
    def is_token_expired(self):
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() >= self.expires_at
