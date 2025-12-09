from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta, date
from .models import User, OTPVerification, Client, CreditUsage, Job

# Register your models here.
class HeroOneAdmin(admin.AdminSite):
    site_header = "HeroOne Authentication Admin"
    site_title = "HeroOne Admin"
    index_title = "Authentication Management Dashboard"
    
    def index(self, request, extra_context=None):
        """Custom admin dashboard with statistics"""
        extra_context = extra_context or {}
        
        # User statistics
        total_users = User.objects.count()
        verified_users = User.objects.filter(is_verified=True).count()
        unverified_users = User.objects.filter(is_verified=False).count()
        
        # Subscription statistics
        free_users = User.objects.filter(subscription_type='free').count()
        premium_monthly_users = User.objects.filter(subscription_type='premium_monthly').count()
        premium_yearly_users = User.objects.filter(subscription_type='premium_yearly').count()
        
        # OTP statistics
        total_otps = OTPVerification.objects.count()
        active_otps = OTPVerification.objects.filter(is_active=True, is_used=False).count()
        expired_otps = OTPVerification.objects.filter(expires_at__lt=timezone.now()).count()
        
        # Credit statistics
        today = date.today()
        credits_used_today = CreditUsage.objects.filter(used_at__date=today).count()
        total_credits_used = CreditUsage.objects.count()
        
        # Recent registrations (last 24 hours)
        yesterday = timezone.now() - timedelta(days=1)
        recent_registrations = User.objects.filter(date_joined__gte=yesterday).count()
        
        # Users needing attention (unverified for more than 24 hours)
        old_unverified = User.objects.filter(
            is_verified=False,
            date_joined__lt=yesterday
        ).count()
        
        extra_context.update({
            'dashboard_stats': {
                'total_users': total_users,
                'verified_users': verified_users,
                'unverified_users': unverified_users,
                'verification_rate': round((verified_users / total_users * 100) if total_users > 0 else 0, 1),
                'free_users': free_users,
                'premium_monthly_users': premium_monthly_users,
                'premium_yearly_users': premium_yearly_users,
                'total_otps': total_otps,
                'active_otps': active_otps,
                'expired_otps': expired_otps,
                'credits_used_today': credits_used_today,
                'total_credits_used': total_credits_used,
                'recent_registrations': recent_registrations,
                'old_unverified': old_unverified,
            }
        })
        
        return super().index(request, extra_context)
    
admin_site = HeroOneAdmin(name='admin')


@admin.register(User, site=admin_site)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin"""
    
    # Fields to display in the user list
    list_display = (
        'email', 
        'username', 
        'full_name', 
        'phone_number',
        'subscription_type',
        'subscription_status_display',
        'credits_remaining_display',
        'oauth_provider',
        'is_verified',
        'verification_status_display',
        'is_active', 
        'is_staff', 
        'date_joined',
        'pending_otps_count'
    )
    
    # Fields to filter by
    list_filter = (
        'subscription_type',
        'is_verified',
        'oauth_provider',
        'is_staff', 
        'is_superuser', 
        'is_active', 
        'date_joined'
    )
    
    # Fields to search by
    search_fields = ('email', 'username', 'full_name', 'phone_number')
    
    # Default ordering
    ordering = ('email',)
    
    # Fields that should be read-only
    readonly_fields = ('date_joined', 'last_login', 'username', 'subscription_start_date', 'subscription_end_date')
    
    # Fieldsets for the user detail/edit page
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        (_('Personal info'), {
            'fields': (
                'full_name', 
                'phone_number',
                'username',
                'profile_pic'
            )
        }),
        (_('OAuth Information'), {
            'fields': (
                'oauth_provider',
                'oauth_id',
                'oauth_access_token'
            ),
            'classes': ('collapse',),  # Make it collapsible
        }),
        (_('Subscription & Credits'), {
            'fields': (
                'subscription_type',
                'subscription_start_date',
                'subscription_end_date'
            ),
        }),
        (_('Verification & Permissions'), {
            'fields': (
                'is_verified',
                'is_active', 
                'is_staff', 
                'is_superuser',
                'groups', 
                'user_permissions'
            ),
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'date_joined')
        }),
    )
    
    # Fieldsets for adding a new user
    add_fieldsets = (
        (_('Authentication'), {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
        (_('Personal Information'), {
            'classes': ('wide',),
            'fields': ('full_name', 'phone_number'),
        }),
    )
    
    # Use email as the username field
    username_field = 'email'
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Override to add custom validation and help text
        """
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for team_members_count field
        if 'team_members_count' in form.base_fields:
            form.base_fields['team_members_count'].help_text = (
                "Required for startup users. Leave empty for freelancers."
            )
        
        # Add help text for phone_number field
        if 'phone_number' in form.base_fields:
            form.base_fields['phone_number'].help_text = (
                "Optional phone number for contact purposes."
            )
        
        return form
    
    def verification_status_display(self, obj):
        """Display verification status with color coding"""
        if obj.is_verified:
            return "✅ Verified"
        else:
            return "❌ Unverified"
    verification_status_display.short_description = 'Status'
    verification_status_display.admin_order_field = 'is_verified'
    
    def pending_otps_count(self, obj):
        """Count of active OTPs for this user"""
        count = obj.otp_verifications.filter(is_active=True, is_used=False).count()
        if count > 0:
            return f"📧 {count}"
        return "—"
    pending_otps_count.short_description = 'Pending OTPs'
    
    def subscription_status_display(self, obj):
        """Display subscription status with expiry info"""
        if obj.is_premium():
            if obj.subscription_end_date:
                days_left = (obj.subscription_end_date - timezone.now()).days
                return f"✅ Active ({days_left} days left)"
            return "✅ Active (Lifetime)"
        return "⚪ Free"
    subscription_status_display.short_description = 'Subscription Status'
    subscription_status_display.admin_order_field = 'subscription_type'
    
    def credits_remaining_display(self, obj):
        """Display remaining credits for today"""
        if obj.is_premium():
            return "∞ Unlimited"
        remaining = obj.get_remaining_credits()
        used = obj.get_credits_used_today()
        limit = obj.get_daily_credit_limit()
        return f"{remaining}/{limit} (used: {used})"
    credits_remaining_display.short_description = 'Credits Today'
    
    def get_queryset(self, request):
        """Optimize queryset with prefetch_related for OTPs"""
        return super().get_queryset(request).prefetch_related('otp_verifications')
    
    # Admin Actions
    actions = ['mark_as_verified', 'mark_as_unverified', 'cleanup_user_otps', 'delete_unverified_users', 
               'upgrade_to_premium_monthly', 'upgrade_to_premium_yearly', 'downgrade_to_free']
    
    def mark_as_verified(self, request, queryset):
        """Mark selected users as verified"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} user(s) marked as verified.')
    mark_as_verified.short_description = "Mark selected users as verified"
    
    def mark_as_unverified(self, request, queryset):
        """Mark selected users as unverified"""
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} user(s) marked as unverified.')
    mark_as_unverified.short_description = "Mark selected users as unverified"
    
    def cleanup_user_otps(self, request, queryset):
        """Clean up all OTPs for selected users"""
        total_deleted = 0
        for user in queryset:
            deleted_count = user.otp_verifications.all().count()
            user.otp_verifications.all().delete()
            total_deleted += deleted_count
        self.message_user(request, f'Cleaned up {total_deleted} OTP(s) for {queryset.count()} user(s).')
    cleanup_user_otps.short_description = "Clean up OTPs for selected users"
    
    def delete_unverified_users(self, request, queryset):
        """Delete unverified users from selection"""
        unverified_users = queryset.filter(is_verified=False)
        count = unverified_users.count()
        
        if count > 0:
            # Clean up their OTPs first
            for user in unverified_users:
                user.otp_verifications.all().delete()
            unverified_users.delete()
            self.message_user(request, f'Deleted {count} unverified user(s) and their OTPs.')
        else:
            self.message_user(request, 'No unverified users found in selection.')
    delete_unverified_users.short_description = "Delete unverified users (and their OTPs)"
    
    def upgrade_to_premium_monthly(self, request, queryset):
        """Upgrade selected users to premium monthly"""
        for user in queryset:
            user.upgrade_to_premium('premium_monthly')
        self.message_user(request, f'{queryset.count()} user(s) upgraded to Premium Monthly.')
    upgrade_to_premium_monthly.short_description = "Upgrade to Premium Monthly (28 days)"
    
    def upgrade_to_premium_yearly(self, request, queryset):
        """Upgrade selected users to premium yearly"""
        for user in queryset:
            user.upgrade_to_premium('premium_yearly')
        self.message_user(request, f'{queryset.count()} user(s) upgraded to Premium Yearly.')
    upgrade_to_premium_yearly.short_description = "Upgrade to Premium Yearly (365 days)"
    
    def downgrade_to_free(self, request, queryset):
        """Downgrade selected users to free plan"""
        for user in queryset:
            user.downgrade_to_free()
        self.message_user(request, f'{queryset.count()} user(s) downgraded to Free plan.')
    downgrade_to_free.short_description = "Downgrade to Free plan"
    
    def save_model(self, request, obj, form, change):
        """
        Override to handle custom validation
        """
        super().save_model(request, obj, form, change)


# Also register with default admin for backward compatibility
@admin.register(User)
class DefaultUserAdmin(UserAdmin):
    """Default admin registration for User"""
    pass


@admin.register(Client, site=admin_site)
class ClientAdmin(admin.ModelAdmin):
    """Admin interface for Client model"""
    
    # Fields to display in the list
    list_display = (
        'id',
        'client_name',
        'user_email',
        'industry_type',
        'contact_person',
        'contact_email',
        'contact_phone',
        'social_accounts_count',
        'created_at',
        'updated_at'
    )
    
    # Fields to filter by
    list_filter = (
        'industry_type',
        'created_at',
        'updated_at'
    )
    
    # Fields to search by
    search_fields = (
        'client_name',
        'contact_person',
        'contact_email',
        'contact_phone',
        'user__email',
        'user__full_name'
    )
    
    # Default ordering (newest first)
    ordering = ('-created_at',)
    
    # Read-only fields
    readonly_fields = ('id', 'created_at', 'updated_at', 'social_accounts_summary')
    
    # Fieldsets for the client detail/edit page
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'id',
                'user',
                'client_name',
                'brand_logo',
                'industry_type'
            )
        }),
        (_('Contact Information'), {
            'fields': (
                'contact_person',
                'contact_email',
                'contact_phone'
            )
        }),
        (_('Social Media Accounts'), {
            'fields': (
                'facebook_url',
                'instagram_url',
                'youtube_url',
                'linkedin_url',
                'twitter_url',
                'tiktok_url',
                'social_accounts_summary'
            ),
            'classes': ('wide',),
        }),
        (_('Preferences'), {
            'fields': (
                'preferred_post_time',
            )
        }),
        (_('Timestamps'), {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',),
        }),
    )
    
    # Fieldsets for adding a new client
    add_fieldsets = (
        (_('Basic Information'), {
            'classes': ('wide',),
            'fields': (
                'user',
                'client_name',
                'brand_logo',
                'industry_type'
            ),
        }),
        (_('Contact Information'), {
            'classes': ('wide',),
            'fields': (
                'contact_person',
                'contact_email',
                'contact_phone'
            ),
        }),
    )
    
    def user_email(self, obj):
        """Display user email in the list"""
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
    
    def social_accounts_count(self, obj):
        """Display count of connected social accounts"""
        count = len(obj.get_active_social_accounts())
        if count > 0:
            platforms = ', '.join(obj.get_active_social_accounts())
            return f"🔗 {count} ({platforms})"
        return "—"
    social_accounts_count.short_description = 'Social Accounts'
    
    def social_accounts_summary(self, obj):
        """Display detailed social accounts summary"""
        active = obj.get_active_social_accounts()
        if not active:
            return "No social accounts connected"
        
        summary = []
        for platform in active:
            summary.append(f"✓ {platform.title()}")
        
        return ", ".join(summary)
    social_accounts_summary.short_description = 'Connected Platforms'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    # Admin Actions
    actions = ['export_client_data', 'clear_social_accounts']
    
    def export_client_data(self, request, queryset):
        """Export selected clients data (placeholder for future implementation)"""
        count = queryset.count()
        self.message_user(request, f'Export functionality will export {count} client(s).')
    export_client_data.short_description = "Export client data"
    
    def clear_social_accounts(self, request, queryset):
        """Clear all social media accounts for selected clients"""
        updated = queryset.update(
            facebook_url=None,
            instagram_url=None,
            youtube_url=None,
            linkedin_url=None,
            twitter_url=None,
            tiktok_url=None
        )
        self.message_user(request, f'Cleared social accounts for {updated} client(s).')
    clear_social_accounts.short_description = "Clear all social accounts"


@admin.register(Client)
class DefaultClientAdmin(ClientAdmin):
    """Default admin registration for Client"""
    pass


@admin.register(CreditUsage, site=admin_site)
class CreditUsageAdmin(admin.ModelAdmin):
    """Admin interface for Credit Usage tracking"""
    
    # Fields to display in the list
    list_display = (
        'id',
        'user_email',
        'user_subscription',
        'action_type',
        'description_preview',
        'used_at',
        'formatted_date'
    )
    
    # Fields to filter by
    list_filter = (
        'action_type',
        'used_at',
        'user__subscription_type'
    )
    
    # Fields to search by
    search_fields = (
        'user__email',
        'user__full_name',
        'action_type',
        'description'
    )
    
    # Default ordering (newest first)
    ordering = ('-used_at',)
    
    # Read-only fields (all fields are read-only for audit purposes)
    readonly_fields = ('id', 'user', 'action_type', 'description', 'used_at')
    
    # Fieldsets for the detail page
    fieldsets = (
        (_('Credit Usage Information'), {
            'fields': (
                'id',
                'user',
                'action_type',
                'description',
                'used_at'
            )
        }),
    )
    
    def user_email(self, obj):
        """Display user email"""
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
    
    def user_subscription(self, obj):
        """Display user subscription type"""
        if obj.user.is_premium():
            return f"💎 {obj.user.get_subscription_type_display()}"
        return "⚪ Free"
    user_subscription.short_description = 'Subscription'
    user_subscription.admin_order_field = 'user__subscription_type'
    
    def description_preview(self, obj):
        """Display preview of description"""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return "—"
    description_preview.short_description = 'Description'
    
    def formatted_date(self, obj):
        """Display formatted date"""
        return obj.used_at.strftime('%Y-%m-%d %H:%M')
    formatted_date.short_description = 'Date/Time'
    formatted_date.admin_order_field = 'used_at'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        """Disable manual adding of credit usage (should be automatic)"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing of credit usage (audit trail)"""
        return False
    
    # Admin Actions
    actions = ['export_credit_usage']
    
    def export_credit_usage(self, request, queryset):
        """Export selected credit usage data (placeholder for future implementation)"""
        count = queryset.count()
        self.message_user(request, f'Export functionality will export {count} credit usage record(s).')
    export_credit_usage.short_description = "Export credit usage data"


@admin.register(CreditUsage)
class DefaultCreditUsageAdmin(CreditUsageAdmin):
    """Default admin registration for CreditUsage"""
    pass


@admin.register(Job, site=admin_site)
class JobAdmin(admin.ModelAdmin):
    """Admin interface for Job model"""
    
    # Fields to display in the list
    list_display = (
        'job_id',
        'client_name_display',
        'user_email',
        'file_type',
        'original_filename',
        'style_display',
        'custom_prompt_display',
        'status_display',
        'progress_display',
        'created_at',
        'processing_time_display',
        'has_results'
    )
    
    # Fields to filter by
    list_filter = (
        'status',
        'file_type',
        'style',
        'created_at',
        'user__subscription_type'
    )
    
    # Fields to search by
    search_fields = (
        'job_id',
        'client__client_name',
        'user__email',
        'user__full_name',
        'original_filename',
        'error_message'
    )
    
    # Default ordering (newest first)
    ordering = ('-created_at',)
    
    # Read-only fields
    readonly_fields = (
        'job_id',
        'client',
        'user',
        'file_type',
        'original_filename',
        'file_path',
        'converted_audio_path',
        'status',
        'progress',
        'result_data',
        'error_message',
        'created_at',
        'started_at',
        'completed_at',
        'processing_time_display',
        'result_preview'
    )
    
    # Fieldsets for the detail page
    fieldsets = (
        (_('Job Information'), {
            'fields': (
                'job_id',
                'client',
                'user',
                'status',
                'progress',
                'file_type',
                'original_filename'
            )
        }),
        (_('File Paths'), {
            'fields': (
                'file_path',
                'converted_audio_path'
            ),
            'classes': ('collapse',)
        }),
        (_('Processing Parameters'), {
            'fields': (
                'caption_length',
                'description_length',
                'hashtag_count',
                'style',
                'custom_prompt'
            )
        }),
        (_('Results'), {
            'fields': (
                'result_preview',
                'result_data'
            ),
            'classes': ('collapse',)
        }),
        (_('Error Information'), {
            'fields': (
                'error_message',
            ),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': (
                'created_at',
                'started_at',
                'completed_at',
                'processing_time_display'
            )
        })
    )
    
    def client_name_display(self, obj):
        """Display client name"""
        return obj.client.client_name
    client_name_display.short_description = 'Client'
    client_name_display.admin_order_field = 'client__client_name'
    
    def user_email(self, obj):
        """Display user email"""
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def style_display(self, obj):
        """Display style with icon"""
        style_icons = {
            'professional': '💼',
            'casual': '😊',
            'educational': '📚',
            'entertaining': '🎉',
            'inspirational': '✨',
            'technical': '⚙️',
            'storytelling': '📖',
            'minimalist': '🔲',
            'viral': '🔥',
            'luxury': '💎'
        }
        icon = style_icons.get(obj.style, '📝')
        return f"{icon} {obj.style.title()}"
    style_display.short_description = 'Style'
    style_display.admin_order_field = 'style'
    
    def custom_prompt_display(self, obj):
        """Display custom prompt preview"""
        if obj.custom_prompt:
            preview = obj.custom_prompt[:30] + '...' if len(obj.custom_prompt) > 30 else obj.custom_prompt
            return f"📝 {preview}"
        return "—"
    custom_prompt_display.short_description = 'Custom Prompt'
    
    def status_display(self, obj):
        """Display status with color coding"""
        status_icons = {
            'uploaded': '📤',
            'pending': '⏳',
            'processing': '⚙️',
            'completed': '✅',
            'failed': '❌'
        }
        icon = status_icons.get(obj.status, '❓')
        return f"{icon} {obj.get_status_display()}"
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def progress_display(self, obj):
        """Display progress percentage"""
        if obj.status == 'uploaded':
            return "—"
        elif obj.status in ['pending', 'processing']:
            return f"{obj.progress}%"
        elif obj.status == 'completed':
            return "100%"
        return "—"
    progress_display.short_description = 'Progress'
    progress_display.admin_order_field = 'progress'
    
    def processing_time_display(self, obj):
        """Display processing time"""
        return obj.get_duration_display()
    processing_time_display.short_description = 'Processing Time'
    
    def has_results(self, obj):
        """Display whether job has results"""
        if obj.status == 'completed' and obj.result_data:
            return "✓ Yes"
        elif obj.status == 'failed':
            return "❌ Error"
        return "—"
    has_results.short_description = 'Results'
    
    def result_preview(self, obj):
        """Display preview of results"""
        if not obj.result_data:
            return "No results"
        
        try:
            import json
            result = obj.result_data
            preview = []
            
            if 'caption' in result:
                caption = result['caption'][:100]
                preview.append(f"Caption: {caption}...")
            
            if 'hashtags' in result:
                hashtags = result['hashtags'][:50]
                preview.append(f"Hashtags: {hashtags}...")
            
            return "\n".join(preview) if preview else "Results available"
        except:
            return "Results available (error parsing preview)"
    result_preview.short_description = 'Results Preview'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('client', 'user')
    
    def has_add_permission(self, request):
        """Disable manual adding of jobs"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing of jobs"""
        return False
    
    # Admin Actions
    actions = ['export_job_data', 'retry_failed_jobs']
    
    def export_job_data(self, request, queryset):
        """Export selected job data"""
        count = queryset.count()
        self.message_user(request, f'Export functionality will export {count} job(s).')
    export_job_data.short_description = "Export job data"
    
    def retry_failed_jobs(self, request, queryset):
        """Retry failed jobs (placeholder)"""
        failed_jobs = queryset.filter(status='failed')
        count = failed_jobs.count()
        self.message_user(request, f'Retry functionality will retry {count} failed job(s).')
    retry_failed_jobs.short_description = "Retry failed jobs"


@admin.register(Job)
class DefaultJobAdmin(JobAdmin):
    """Default admin registration for Job"""
    pass
