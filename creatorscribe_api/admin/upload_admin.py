from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from ..models.upload_models import UploadedFile
from .auth_admin import admin_site


@admin.register(UploadedFile, site=admin_site)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'original_name', 'file_type', 'size_display', 'user_email', 'client', 'created_at')
    list_filter = ('file_type', 'created_at', 'client')
    search_fields = ('original_name', 'user__email', 'client__client_name')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'file_type', 'size', 'created_at')
    exclude = ()  # file_type and size auto-filled from uploaded file

    fieldsets = (
        (_('File Info'), {
            'fields': ('id', 'original_name', 'file', 'file_type', 'size')
        }),
        (_('Ownership'), {
            'fields': ('user', 'client')
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Uploaded By'
    user_email.admin_order_field = 'user__email'

    def size_display(self, obj):
        if obj.size < 1024:
            return f'{obj.size} B'
        elif obj.size < 1024 ** 2:
            return f'{obj.size / 1024:.1f} KB'
        elif obj.size < 1024 ** 3:
            return f'{obj.size / 1024 ** 2:.1f} MB'
        return f'{obj.size / 1024 ** 3:.1f} GB'
    size_display.short_description = 'Size'
    size_display.admin_order_field = 'size'

    def save_model(self, request, obj, form, change):
        uploaded = form.files.get('file')
        if uploaded:
            obj.file_type = uploaded.content_type or 'application/octet-stream'
            obj.size = uploaded.size
        elif not obj.pk:
            obj.file_type = obj.file_type or 'application/octet-stream'
            obj.size = obj.size or 0
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'client')


@admin.register(UploadedFile)
class DefaultUploadedFileAdmin(UploadedFileAdmin):
    pass
