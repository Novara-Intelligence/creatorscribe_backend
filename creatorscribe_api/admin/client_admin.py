from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from ..models.client_models import Client, ClientMember
from .auth_admin import admin_site


class ClientMemberInline(admin.TabularInline):
    model = ClientMember
    extra = 0
    fields = ('user', 'role', 'status', 'invited_by')
    readonly_fields = ('invited_by', 'status')


@admin.register(ClientMember, site=admin_site)
class ClientMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'user_email', 'role', 'status', 'invited_by_email', 'created_at')
    list_filter = ('status', 'role', 'created_at')
    search_fields = ('user__email', 'user__full_name', 'client__client_name')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'invited_by', 'created_at', 'updated_at')

    fieldsets = (
        (_('Membership'), {
            'fields': ('id', 'client', 'user', 'role', 'status')
        }),
        (_('Invite Info'), {
            'fields': ('invited_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Member Email'
    user_email.admin_order_field = 'user__email'

    def invited_by_email(self, obj):
        return obj.invited_by.email if obj.invited_by else '—'
    invited_by_email.short_description = 'Invited By'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client', 'user', 'invited_by')


@admin.register(ClientMember)
class DefaultClientMemberAdmin(ClientMemberAdmin):
    pass


@admin.register(Client, site=admin_site)
class ClientAdmin(admin.ModelAdmin):
    """Admin interface for Client model"""

    list_display = (
        'id',
        'client_name',
        'user_email',
        'created_at',
        'updated_at'
    )

    list_filter = (
        'created_at',
        'updated_at'
    )

    search_fields = (
        'client_name',
        'owner__email',
        'owner__full_name'
    )

    ordering = ('-created_at',)

    readonly_fields = ('id', 'created_at', 'updated_at')

    inlines = [ClientMemberInline]

    fieldsets = (
        (_('Client Information'), {
            'fields': (
                'id',
                'owner',
                'client_name',
                'brand_logo',
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

    add_fieldsets = (
        (_('Client Information'), {
            'classes': ('wide',),
            'fields': (
                'owner',
                'client_name',
                'brand_logo',
            ),
        }),
    )

    def user_email(self, obj):
        return obj.owner.email
    user_email.short_description = 'Owner Email'
    user_email.admin_order_field = 'owner__email'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner')

    actions = ['export_client_data']

    def export_client_data(self, request, queryset):
        count = queryset.count()
        self.message_user(request, f'Export functionality will export {count} client(s).')
    export_client_data.short_description = "Export client data"


@admin.register(Client)
class DefaultClientAdmin(ClientAdmin):
    """Default admin registration for Client"""
    pass
