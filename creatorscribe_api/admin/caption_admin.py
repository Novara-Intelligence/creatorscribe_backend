from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from ..models.caption_models import (
    CaptionSession, CaptionJob,
    AudioOutput, TranscriptionOutput, TranscriptionSegment, CaptionOutput,
)
from .auth_admin import admin_site


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class CaptionJobInline(admin.TabularInline):
    model = CaptionJob
    extra = 0
    fields = ('id', 'turn_index', 'media_type', 'status', 'prompt', 'created_at')
    readonly_fields = ('id', 'turn_index', 'media_type', 'status', 'created_at')
    show_change_link = True


class TranscriptionSegmentInline(admin.TabularInline):
    model = TranscriptionSegment
    extra = 0
    fields = ('index', 'text', 'start_second', 'end_second')
    readonly_fields = ('index', 'text', 'start_second', 'end_second')
    ordering = ('index',)


# ---------------------------------------------------------------------------
# CaptionSession
# ---------------------------------------------------------------------------

@admin.register(CaptionSession, site=admin_site)
class CaptionSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'client', 'user_email', 'job_count', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('title', 'client__client_name', 'user__email')
    ordering = ('-updated_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines = [CaptionJobInline]

    fieldsets = (
        (_('Session'), {
            'fields': ('id', 'client', 'user', 'title'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def job_count(self, obj):
        return obj.jobs.count()
    job_count.short_description = 'Jobs'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client', 'user')


@admin.register(CaptionSession)
class DefaultCaptionSessionAdmin(CaptionSessionAdmin):
    pass


# ---------------------------------------------------------------------------
# CaptionJob
# ---------------------------------------------------------------------------

@admin.register(CaptionJob, site=admin_site)
class CaptionJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'turn_index', 'session', 'client', 'user_email',
        'media_type', 'status', 'created_at',
    )
    list_filter = ('status', 'media_type', 'created_at')
    search_fields = ('session__title', 'client__client_name', 'user__email', 'prompt')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'media_type', 'turn_index', 'created_at', 'updated_at')

    fieldsets = (
        (_('Job'), {
            'fields': ('id', 'session', 'client', 'user', 'turn_index'),
        }),
        (_('Input'), {
            'fields': ('uploaded_file', 'prompt', 'media_type'),
        }),
        (_('Status'), {
            'fields': ('status', 'error_message'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('session', 'client', 'user', 'uploaded_file')


@admin.register(CaptionJob)
class DefaultCaptionJobAdmin(CaptionJobAdmin):
    pass


# ---------------------------------------------------------------------------
# AudioOutput
# ---------------------------------------------------------------------------

@admin.register(AudioOutput, site=admin_site)
class AudioOutputAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'duration', 'language', 'created_at')
    search_fields = ('job__session__title', 'language')
    readonly_fields = ('id', 'created_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('job__session')


@admin.register(AudioOutput)
class DefaultAudioOutputAdmin(AudioOutputAdmin):
    pass


# ---------------------------------------------------------------------------
# TranscriptionOutput
# ---------------------------------------------------------------------------

@admin.register(TranscriptionOutput, site=admin_site)
class TranscriptionOutputAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'language', 'text_preview', 'created_at')
    search_fields = ('job__session__title', 'full_text', 'language')
    readonly_fields = ('id', 'created_at')
    inlines = [TranscriptionSegmentInline]

    def text_preview(self, obj):
        return obj.full_text[:80] + '…' if len(obj.full_text) > 80 else obj.full_text
    text_preview.short_description = 'Text'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('job__session')


@admin.register(TranscriptionOutput)
class DefaultTranscriptionOutputAdmin(TranscriptionOutputAdmin):
    pass


# ---------------------------------------------------------------------------
# CaptionOutput
# ---------------------------------------------------------------------------

@admin.register(CaptionOutput, site=admin_site)
class CaptionOutputAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'title', 'tag_count', 'created_at')
    search_fields = ('title', 'description', 'job__session__title')
    readonly_fields = ('id', 'created_at')

    fieldsets = (
        (_('Caption'), {
            'fields': ('id', 'job', 'title', 'description', 'tags'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def tag_count(self, obj):
        return len(obj.tags)
    tag_count.short_description = 'Tags'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('job__session')


@admin.register(CaptionOutput)
class DefaultCaptionOutputAdmin(CaptionOutputAdmin):
    pass
