from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import EmailValidator
from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.utils import timezone
from datetime import timedelta, date
import random
import string


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        
        # Auto-generate username from email (part before @)
        username = email.split('@')[0]
        
        # Ensure username uniqueness by adding numbers if needed
        original_username = username
        counter = 1
        while self.model.objects.filter(username=username).exists():
            username = f"{original_username}{counter}"
            counter += 1
        
        extra_fields['username'] = username
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        from django.db import transaction
        
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)  # Superusers are always verified
        
        # Set default values for required fields if not provided
        extra_fields.setdefault('full_name', 'Admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        with transaction.atomic():
            user = self.create_user(email, password, **extra_fields)
            
            # Import Client model here to avoid circular imports
            from .client_models import Client
            
            # Create "Self as Client" for superuser
            Client.objects.create(
                user=user,
                client_name=user.full_name,
                contact_person=user.full_name,
                contact_email=user.email,
                contact_phone=user.phone_number if user.phone_number else '',
                industry_type='other'
            )
        
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model with email as the primary authentication field
    """
    
    SUBSCRIPTION_CHOICES = [
        ('free', 'Free'),
        ('premium_monthly', 'Premium Monthly'),
        ('premium_yearly', 'Premium Yearly'),
    ]
    
    # Basic Information
    full_name = models.CharField(max_length=60, blank=False)
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        help_text='Email address used for login'
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text='Phone number (optional)'
    )
    username = models.CharField(
        max_length=150,
        unique=True,
        help_text='Auto-generated from email address'
    )
    
    # Profile Information
    profile_pic = models.ImageField(
        upload_to='profile_pics/',
        null=True,
        blank=True,
        help_text='User profile picture'
    )
    
    # OAuth Information
    oauth_provider = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='OAuth provider (e.g., google, facebook, github)'
    )
    oauth_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text='Unique ID from OAuth provider'
    )
    oauth_access_token = models.TextField(
        blank=True,
        null=True,
        help_text='OAuth access token (encrypted in production)'
    )
    
    # Subscription & Credits
    subscription_type = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_CHOICES,
        default='free',
        help_text='User subscription plan'
    )
    subscription_start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the current subscription started'
    )
    subscription_end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the subscription expires (for premium users)'
    )
    
    # Django required fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False, help_text='Email verification status')
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Only email and password required for superuser creation
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.full_name} ({self.email})"
    
    def get_full_name(self):
        """Return the full name for the user."""
        return f"{self.full_name}".strip()
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.full_name
    
    def save(self, *args, **kwargs):
        # Auto-generate username from email if not provided
        if not self.username and self.email:
            base_username = self.email.split('@')[0]
            username = base_username
            counter = 1
            
            # Ensure username uniqueness
            while User.objects.filter(username=username).exclude(pk=self.pk).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            self.username = username
        
        # Set subscription_start_date if it's a new user
        if not self.pk and not self.subscription_start_date:
            self.subscription_start_date = timezone.now()
        
        # Automatically set subscription_end_date when subscription_type changes
        if self.pk:  # Only for existing users (not new users)
            try:
                old_user = User.objects.get(pk=self.pk)
                # Check if subscription type has changed
                if old_user.subscription_type != self.subscription_type:
                    if self.subscription_type == 'premium_monthly':
                        self.subscription_start_date = timezone.now()
                        self.subscription_end_date = timezone.now() + timedelta(days=28)
                    elif self.subscription_type == 'premium_yearly':
                        self.subscription_start_date = timezone.now()
                        self.subscription_end_date = timezone.now() + timedelta(days=365)
                    elif self.subscription_type == 'free':
                        # When downgrading to free, clear the end date
                        self.subscription_end_date = None
            except User.DoesNotExist:
                pass
        else:
            # For new users, set expiration date based on initial subscription type
            if self.subscription_type == 'premium_monthly':
                self.subscription_end_date = timezone.now() + timedelta(days=28)
            elif self.subscription_type == 'premium_yearly':
                self.subscription_end_date = timezone.now() + timedelta(days=365)
        
        super().save(*args, **kwargs)
    
    def is_premium(self):
        """Check if user has an active premium subscription"""
        if self.subscription_type in ['premium_monthly', 'premium_yearly']:
            # Check if subscription is still valid
            if self.subscription_end_date:
                is_valid = timezone.now() < self.subscription_end_date
                
                # Auto-expire if subscription has ended
                if not is_valid:
                    self.auto_expire_subscription()
                    return False
                
                return True
            # If no end date, assume it's active (lifetime premium)
            return True
        return False
    
    def auto_expire_subscription(self):
        """Automatically expire the subscription and downgrade to free"""
        self.subscription_type = 'free'
        # Keep the end date for historical records
        self.save(update_fields=['subscription_type'])
    
    def get_daily_credit_limit(self):
        """Get the daily credit limit based on subscription type"""
        if self.is_premium():
            return None  # Unlimited for premium users
        return 3  # Free users get 3 credits per day
    
    def get_credits_used_today(self):
        """Get the number of credits used today"""
        today = date.today()
        return CreditUsage.objects.filter(
            user=self,
            used_at__date=today
        ).count()
    
    def get_remaining_credits(self):
        """Get remaining credits for today"""
        if self.is_premium():
            return None  # Unlimited
        
        limit = self.get_daily_credit_limit()
        used = self.get_credits_used_today()
        return max(0, limit - used)
    
    def can_use_credit(self):
        """Check if user can use a credit"""
        if self.is_premium():
            return True  # Premium users have unlimited credits
        
        remaining = self.get_remaining_credits()
        return remaining > 0
    
    def use_credit(self, action_type='general', description=''):
        """
        Consume one credit for an action
        
        Args:
            action_type: Type of action (e.g., 'transcription', 'audio_conversion')
            description: Optional description of the action
        
        Returns:
            Tuple[bool, str]: (Success status, message)
        """
        if not self.can_use_credit():
            return False, "Daily credit limit reached. Please upgrade to premium for unlimited access."
        
        # Create credit usage record
        CreditUsage.objects.create(
            user=self,
            action_type=action_type,
            description=description
        )
        
        if self.is_premium():
            return True, "Credit used (unlimited available)"
        else:
            remaining = self.get_remaining_credits()
            return True, f"Credit used. {remaining} credits remaining today."
    
    def upgrade_to_premium(self, subscription_type='premium_monthly'):
        """
        Upgrade user to premium subscription
        
        Args:
            subscription_type: Type of premium subscription ('premium_monthly' or 'premium_yearly')
        """
        if subscription_type not in ['premium_monthly', 'premium_yearly']:
            raise ValueError("Invalid subscription type. Must be 'premium_monthly' or 'premium_yearly'")
        
        self.subscription_type = subscription_type
        self.subscription_start_date = timezone.now()
        
        # Set expiration based on subscription type
        if subscription_type == 'premium_monthly':
            self.subscription_end_date = timezone.now() + timedelta(days=28)
        elif subscription_type == 'premium_yearly':
            self.subscription_end_date = timezone.now() + timedelta(days=365)
        
        self.save(update_fields=['subscription_type', 'subscription_start_date', 'subscription_end_date'])
    
    def downgrade_to_free(self):
        """Downgrade user to free subscription"""
        self.subscription_type = 'free'
        self.subscription_end_date = None
        self.save(update_fields=['subscription_type', 'subscription_end_date'])


class OTPVerification(models.Model):
    """
    Model to store OTP verification codes for users
    """
    OTP_TYPE_CHOICES = [
        ('registration', 'Registration'),
        ('signin', 'Sign In'),
        ('password_reset', 'Password Reset'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_verifications')
    otp_code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'OTP Verification'
        verbose_name_plural = 'OTP Verifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.otp_type} - {self.otp_code}"
    
    @classmethod
    def cleanup_expired_otps(cls):
        """Delete all expired OTPs"""
        expired_otps = cls.objects.filter(expires_at__lt=timezone.now())
        count = expired_otps.count()
        expired_otps.delete()
        return count
    
    @classmethod
    def generate_otp(cls, user, otp_type='registration', expiry_minutes=15):
        """Generate a new OTP for the user"""
        from datetime import timedelta
        
        # Clean up expired OTPs for this user
        cls.objects.filter(
            user=user,
            expires_at__lt=timezone.now()
        ).delete()
        
        # Deactivate existing OTPs for this user and type
        cls.objects.filter(
            user=user, 
            otp_type=otp_type, 
            is_active=True
        ).update(is_active=False)
        
        # Generate 6-digit OTP
        otp_code = ''.join(random.choices(string.digits, k=6))
        
        # Set expiry time
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        
        # Create new OTP
        otp = cls.objects.create(
            user=user,
            otp_code=otp_code,
            otp_type=otp_type,
            expires_at=expires_at
        )
        
        return otp
    
    def is_valid(self):
        """Check if OTP is valid and not expired"""
        return (
            self.is_active and 
            not self.is_used and 
            timezone.now() < self.expires_at
        )
    
    def verify(self):
        """Mark OTP as used and delete it"""
        if self.is_valid():
            self.is_used = True
            self.save(update_fields=['is_used'])
            # Delete the OTP after successful verification
            self.delete()
            return True
        return False
    
    @classmethod
    def verify_otp(cls, user, otp_code, otp_type):
        """Verify OTP code for a user"""
        # Clean up expired OTPs before verification
        cls.cleanup_expired_otps()
        
        try:
            otp = cls.objects.get(
                user=user,
                otp_code=otp_code,
                otp_type=otp_type,
                is_active=True,
                is_used=False
            )
            
            if otp.is_valid():
                otp.verify()
                return True, "OTP verified successfully"
            else:
                return False, "OTP has expired"
                
        except cls.DoesNotExist:
            return False, "Invalid OTP code"


class CreditUsage(models.Model):
    """
    Model to track credit usage for users
    """
    ACTION_TYPE_CHOICES = [
        ('transcription', 'Transcription'),
        ('audio_conversion', 'Audio Conversion'),
        ('video_processing', 'Video Processing'),
        ('general', 'General'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='credit_usage',
        help_text='User who used the credit'
    )
    action_type = models.CharField(
        max_length=50,
        choices=ACTION_TYPE_CHOICES,
        default='general',
        help_text='Type of action that consumed the credit'
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text='Optional description of the action'
    )
    used_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the credit was used'
    )
    
    class Meta:
        verbose_name = 'Credit Usage'
        verbose_name_plural = 'Credit Usages'
        ordering = ['-used_at']
        indexes = [
            models.Index(fields=['user', '-used_at']),
            models.Index(fields=['user', 'action_type']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.action_type} - {self.used_at.strftime('%Y-%m-%d %H:%M')}"