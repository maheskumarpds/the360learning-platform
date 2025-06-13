from django.contrib import admin
from .models import (
    UserProfile, Subject, ClassSubject, StudyMaterial, VideoConference,
    RecordedSession, Assignment, AssignmentSubmission,
    AITutorSession, AITutorMessage
)

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'class_level', 'date_joined')
    list_filter = ('role', 'class_level')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')

class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'class_level', 'file_type', 'uploaded_by', 'upload_date')
    list_filter = ('subject', 'class_level', 'file_type')
    search_fields = ('title', 'description')

class VideoConferenceAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'class_level', 'platform', 'start_time', 'scheduled_by')
    list_filter = ('subject', 'class_level', 'platform', 'is_recurring')
    search_fields = ('title', 'description')

class RecordedSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'class_level', 'recorded_date', 'duration_minutes', 'views')
    list_filter = ('subject', 'class_level')
    search_fields = ('title', 'description')

class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'class_level', 'created_by', 'due_date', 'difficulty')
    list_filter = ('subject', 'class_level', 'difficulty')
    search_fields = ('title', 'description')

class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'submitted_at', 'is_graded', 'points_earned')
    list_filter = ('is_graded',)
    search_fields = ('assignment__title', 'student__username')

class AITutorMessageInline(admin.TabularInline):
    model = AITutorMessage
    extra = 0

class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'get_class_name', 'subject', 'assigned_by', 'assigned_at')
    list_filter = ('class_level', 'subject')
    search_fields = ('subject__name',)
    
    def get_class_name(self, obj):
        return obj.get_class_level_display()
    get_class_name.short_description = 'Class'

class AITutorSessionAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'started_at', 'last_activity', 'is_active')
    list_filter = ('is_active', 'subject')
    search_fields = ('student__username',)
    inlines = [AITutorMessageInline]

admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Subject)
admin.site.register(ClassSubject, ClassSubjectAdmin)
admin.site.register(StudyMaterial, StudyMaterialAdmin)
admin.site.register(VideoConference, VideoConferenceAdmin)
admin.site.register(RecordedSession, RecordedSessionAdmin)
admin.site.register(Assignment, AssignmentAdmin)
admin.site.register(AssignmentSubmission, AssignmentSubmissionAdmin)
admin.site.register(AITutorSession, AITutorSessionAdmin)
admin.site.register(AITutorMessage)
