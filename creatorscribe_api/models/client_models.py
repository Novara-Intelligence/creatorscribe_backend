from django.db import models
from .auth_models import User


class Client(models.Model):
    """
    Client model. The owner created/controls the client.
    Other users can be invited as members via ClientMember.
    """
    id = models.AutoField(primary_key=True)

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_clients',
        help_text='User who created and owns this client'
    )

    client_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='Name of the client/brand'
    )

    brand_logo = models.ImageField(
        upload_to='client_logos/',
        null=True,
        blank=True,
        help_text='Client brand logo'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clients'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'client_name']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.client_name} ({self.owner.email})"

    def get_members(self):
        """Return all accepted members excluding the owner."""
        return self.members.filter(status='accepted').select_related('user')

    def is_member(self, user):
        """Check if a user has accepted membership (owner counts too)."""
        if self.owner_id == user.id:
            return True
        return self.members.filter(user=user, status='accepted').exists()

    def get_user_role(self, user):
        """Return the role of a user. Owner is always 'owner'."""
        if self.owner_id == user.id:
            return 'owner'
        member = self.members.filter(user=user, status='accepted').first()
        return member.role if member else None


class ClientMember(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('editor', 'Editor'),
        ('viewer', 'Viewer'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='members',
        help_text='Client this membership belongs to'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='client_memberships',
        help_text='Invited user'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='viewer',
        help_text='Permission level for this member'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Whether the invite has been accepted'
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_invites',
        help_text='User who sent the invite'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_members'
        verbose_name = 'Client Member'
        verbose_name_plural = 'Client Members'
        unique_together = [('client', 'user')]
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.user.email} → {self.client.client_name} ({self.role}, {self.status})"
