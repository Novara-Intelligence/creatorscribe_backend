from django.db import models
from django.conf import settings
from .auth_models import User


class Client(models.Model):
    """
    Client model to store information about clients/brands
    """
    INDUSTRY_CHOICES = [
        ('technology', 'Technology'),
        ('healthcare', 'Healthcare'),
        ('finance', 'Finance'),
        ('retail', 'Retail'),
        ('education', 'Education'),
        ('hospitality', 'Hospitality'),
        ('real_estate', 'Real Estate'),
        ('entertainment', 'Entertainment'),
        ('food_beverage', 'Food & Beverage'),
        ('fashion', 'Fashion'),
        ('automotive', 'Automotive'),
        ('manufacturing', 'Manufacturing'),
        ('consulting', 'Consulting'),
        ('marketing', 'Marketing'),
        ('other', 'Other'),
    ]

    # Primary Key
    id = models.AutoField(primary_key=True)
    
    # Foreign Key to User
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='clients',
        help_text='User who owns this client account'
    )
    
    # Basic Client Information
    client_name = models.CharField(
        max_length=255,
        help_text='Name of the client/brand'
    )
    
    brand_logo = models.ImageField(
        upload_to='client_logos/',
        null=True,
        blank=True,
        help_text='Client brand logo'
    )
    
    industry_type = models.CharField(
        max_length=50,
        choices=INDUSTRY_CHOICES,
        default='other',
        help_text='Industry type of the client'
    )
    
    # Contact Information
    contact_person = models.CharField(
        max_length=255,
        help_text='Primary contact person name'
    )
    
    contact_email = models.EmailField(
        help_text='Contact email address'
    )
    
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text='Contact phone number'
    )
    
    # Social Media Accounts (Profile URLs)
    facebook_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Facebook profile/page URL'
    )
    
    instagram_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Instagram profile URL'
    )
    
    youtube_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='YouTube channel URL'
    )
    
    linkedin_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='LinkedIn profile/company page URL'
    )
    
    twitter_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Twitter/X profile URL'
    )
    
    tiktok_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='TikTok profile URL'
    )
    
    # Preferences
    preferred_post_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Preferred time for posting content (HH:MM format)'
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
            models.Index(fields=['industry_type']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.client_name} - {self.contact_person}"
    
    def get_social_accounts(self):
        """Return a dictionary of all social media accounts"""
        return {
            'facebook': self.facebook_url,
            'instagram': self.instagram_url,
            'youtube': self.youtube_url,
            'linkedin': self.linkedin_url,
            'twitter': self.twitter_url,
            'tiktok': self.tiktok_url,
        }
    
    def get_active_social_accounts(self):
        """Return a list of active social media platforms"""
        social_accounts = self.get_social_accounts()
        return [platform for platform, url in social_accounts.items() if url]
    
    def has_social_account(self, platform):
        """Check if client has a specific social media account"""
        social_accounts = self.get_social_accounts()
        return bool(social_accounts.get(platform))
