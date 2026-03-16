from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta, date
from ..models import User, OTPVerification, CreditUsage


class CreatorScribeAdmin(admin.AdminSite):
    site_header = "CreatorScribe Authentication Admin"
    site_title = "CreatorScribe Admin"
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

admin_site = CreatorScribeAdmin(name='admin')

@admin.register(User, site=admin_site)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin"""

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

    list_filter = (
        'subscription_type',
        'is_verified',
        'oauth_provider',
        'is_staff',
        'is_superuser',
        'is_active',
        'date_joined'
    )

    search_fields = ('email', 'username', 'full_name', 'phone_number')

    ordering = ('email',)

    readonly_fields = ('date_joined', 'last_login', 'username', 'subscription_start_date', 'subscription_end_date')

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
            'classes': ('collapse',),
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

    username_field = 'email'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        if 'team_members_count' in form.base_fields:
            form.base_fields['team_members_count'].help_text = (
                "Required for startup users. Leave empty for freelancers."
            )

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
        """Display remaining tokens for the current month"""
        if obj.is_premium():
            return "∞ Unlimited"
        remaining = obj.get_remaining_tokens()
        used = obj.get_tokens_used_this_month()
        limit = obj.get_monthly_token_limit()
        return f"{remaining:,}/{limit:,} (used: {used:,})"
    credits_remaining_display.short_description = 'Tokens This Month'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('otp_verifications')

    actions = ['mark_as_verified', 'mark_as_unverified', 'cleanup_user_otps', 'delete_unverified_users',
               'upgrade_to_premium_monthly', 'upgrade_to_premium_yearly', 'downgrade_to_free']

    def mark_as_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} user(s) marked as verified.')
    mark_as_verified.short_description = "Mark selected users as verified"

    def mark_as_unverified(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} user(s) marked as unverified.')
    mark_as_unverified.short_description = "Mark selected users as unverified"

    def cleanup_user_otps(self, request, queryset):
        total_deleted = 0
        for user in queryset:
            deleted_count = user.otp_verifications.all().count()
            user.otp_verifications.all().delete()
            total_deleted += deleted_count
        self.message_user(request, f'Cleaned up {total_deleted} OTP(s) for {queryset.count()} user(s).')
    cleanup_user_otps.short_description = "Clean up OTPs for selected users"

    def delete_unverified_users(self, request, queryset):
        unverified_users = queryset.filter(is_verified=False)
        count = unverified_users.count()
        if count > 0:
            for user in unverified_users:
                user.otp_verifications.all().delete()
            unverified_users.delete()
            self.message_user(request, f'Deleted {count} unverified user(s) and their OTPs.')
        else:
            self.message_user(request, 'No unverified users found in selection.')
    delete_unverified_users.short_description = "Delete unverified users (and their OTPs)"

    def upgrade_to_premium_monthly(self, request, queryset):
        for user in queryset:
            user.upgrade_to_premium('premium_monthly')
        self.message_user(request, f'{queryset.count()} user(s) upgraded to Premium Monthly.')
    upgrade_to_premium_monthly.short_description = "Upgrade to Premium Monthly (28 days)"

    def upgrade_to_premium_yearly(self, request, queryset):
        for user in queryset:
            user.upgrade_to_premium('premium_yearly')
        self.message_user(request, f'{queryset.count()} user(s) upgraded to Premium Yearly.')
    upgrade_to_premium_yearly.short_description = "Upgrade to Premium Yearly (365 days)"

    def downgrade_to_free(self, request, queryset):
        for user in queryset:
            user.downgrade_to_free()
        self.message_user(request, f'{queryset.count()} user(s) downgraded to Free plan.')
    downgrade_to_free.short_description = "Downgrade to Free plan"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

@admin.register(User)
class DefaultUserAdmin(UserAdmin):
    """Default admin registration for User"""
    pass

@admin.register(CreditUsage, site=admin_site)
class CreditUsageAdmin(admin.ModelAdmin):
    """Admin interface for Credit Usage tracking"""

    list_display = (
        'id',
        'user_email',
        'user_subscription',
        'description_preview',
        'used_at',
        'formatted_date'
    )

    list_filter = (
        'used_at',
        'user__subscription_type'
    )

    search_fields = (
        'user__email',
        'user__full_name',
        'description'
    )

    ordering = ('-used_at',)

    readonly_fields = ('id', 'user', 'description', 'used_at')

    fieldsets = (
        (_('Credit Usage Information'), {
            'fields': (
                'id',
                'user',
                'description',
                'used_at'
            )
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def user_subscription(self, obj):
        if obj.user.is_premium():
            return f"💎 {obj.user.get_subscription_type_display()}"
        return "⚪ Free"
    user_subscription.short_description = 'Subscription'
    user_subscription.admin_order_field = 'user__subscription_type'

    def description_preview(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return "—"
    description_preview.short_description = 'Description'

    def formatted_date(self, obj):
        return obj.used_at.strftime('%Y-%m-%d %H:%M')
    formatted_date.short_description = 'Date/Time'
    formatted_date.admin_order_field = 'used_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    actions = ['export_credit_usage']

    def export_credit_usage(self, request, queryset):
        count = queryset.count()
        self.message_user(request, f'Export functionality will export {count} credit usage record(s).')
    export_credit_usage.short_description = "Export credit usage data"

@admin.register(CreditUsage)
class DefaultCreditUsageAdmin(CreditUsageAdmin):
    """Default admin registration for CreditUsage"""
    pass
