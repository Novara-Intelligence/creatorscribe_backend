from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from ..models.client_models import Client, ClientMember
from .auth_admin import admin_site


class ClientMemberInline(admin.TabularInline):
    model = ClientMember
    extra = 0
    fields = ('user', 'role', 'status', 'invited_by')
    readonly_fields = ('invited_by',)


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
