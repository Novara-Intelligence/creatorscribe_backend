from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from ..models.social_account_models import SocialAccount
from .auth_admin import admin_site


@admin.register(SocialAccount, site=admin_site)
class SocialAccountAdmin(admin.ModelAdmin):
    """Admin interface for Social Accounts"""

    list_display = (
        'id',
        'client_name',
        'platform',
        'account_name',
        'token_status',
        'expires_at',
        'updated_at',
    )

    list_filter = (
        'platform',
        'updated_at',
    )

    search_fields = (
        'account_name',
        'client__client_name',
        'client__owner__email',
    )

    ordering = ('client', 'platform')

    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        (_('Account Information'), {
            'fields': ('id', 'client', 'platform', 'account_name')
        }),
        (_('OAuth Tokens'), {
            'fields': ('access_token', 'refresh_token', 'expires_at'),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def client_name(self, obj):
        return obj.client.client_name
    client_name.short_description = 'Client'
    client_name.admin_order_field = 'client__client_name'

    def token_status(self, obj):
        if obj.is_token_expired:
            return '🔴 Expired'
        if obj.expires_at:
            days_left = (obj.expires_at - timezone.now()).days
            return f'🟢 Valid ({days_left}d)'
        return '🟡 No expiry'
    token_status.short_description = 'Token Status'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client', 'client__owner')

    def has_add_permission(self, request):
        return False


@admin.register(SocialAccount)
class DefaultSocialAccountAdmin(SocialAccountAdmin):
    """Default admin registration for SocialAccount"""
    pass
