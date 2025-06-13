from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
import json
from datetime import datetime, timedelta


class UserProfile(models.Model):
    """Extended user profile with additional educational information"""
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Administrator'),
    )
    
    CLASS_CHOICES = (
        ('1', 'Class 1'),
        ('2', 'Class 2'),
        ('3', 'Class 3'),
        ('4', 'Class 4'),
        ('5', 'Class 5'),
        ('6', 'Class 6'),
        ('7', 'Class 7'),
        ('8', 'Class 8'),
        ('9', 'Class 9'),
        ('10', 'Class 10'),
        ('11', 'Class 11'),
        ('12', 'Class 12'),
        ('eng_com', 'English Communication'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    class_level = models.CharField(max_length=10, choices=CLASS_CHOICES, null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    profile_picture = models.CharField(max_length=255, blank=True, help_text="URL to profile picture")
    date_joined = models.DateTimeField(auto_now_add=True)
    
    # Payment tracking fields
    payment_status = models.CharField(max_length=20, choices=(
        ('pending', 'Payment Pending'),
        ('paid', 'Payment Completed'),
        ('exempt', 'Payment Exempt'),
        ('failed', 'Payment Failed'),
    ), default='pending')
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_id = models.CharField(max_length=100, blank=True, null=True, help_text="Payment gateway transaction ID")
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    def get_absolute_url(self):
        return reverse('profile_view', args=[self.user.username])


class Subject(models.Model):
    """Subject or course offered in the educational platform"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='book', help_text="Font Awesome icon name")
    
    def __str__(self):
        return self.name
        
    def get_classes(self):
        """Returns a list of class levels this subject is assigned to"""
        return ClassSubject.objects.filter(subject=self).values_list('class_level', flat=True)


class ClassSubject(models.Model):
    """Association between class levels and subjects"""
    class_level = models.CharField(max_length=10, choices=UserProfile.CLASS_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='class_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['class_level', 'subject']
        verbose_name = "Class Subject Assignment"
        verbose_name_plural = "Class Subject Assignments"
    
    def __str__(self):
        return f"{self.get_class_level_display()} - {self.subject.name}"


class StudyMaterial(models.Model):
    """Educational resources organized by subject and class level"""
    FILE_TYPE_CHOICES = (
        ('pdf', 'PDF'),
        ('doc', 'DOCX'),
        ('ppt', 'PPTX'),
        ('img', 'Image'),
        ('vid', 'Video'),
        ('aud', 'Audio'),
        ('other', 'Other'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='materials')
    class_level = models.CharField(max_length=10, choices=UserProfile.CLASS_CHOICES)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    # Store uploaded file directly in the database instead of URL
    file = models.FileField(upload_to='study_materials/', blank=True, null=True, help_text="Upload study material file")
    # Keep file_url for backward compatibility, but make it optional
    file_url = models.CharField(max_length=255, blank=True, null=True, help_text="URL to external material (optional)")
    file_size = models.PositiveIntegerField(default=0, help_text="Size of file in bytes")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_materials')
    upload_date = models.DateTimeField(auto_now_add=True)
    views = models.PositiveIntegerField(default=0)
    downloads = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.title} ({self.get_file_type_display()})"
    
    def get_absolute_url(self):
        return reverse('material_detail', args=[self.id])
        
    def save(self, *args, **kwargs):
        # Calculate file size if a file is uploaded
        if self.file and not self.file_size and hasattr(self.file, 'size'):
            self.file_size = self.file.size
        super().save(*args, **kwargs)
        
    def get_file_size_display(self):
        """Return human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024 or unit == 'GB':
                return f"{size:.1f} {unit}"
            size /= 1024


class VideoConference(models.Model):
    """Scheduled video conference sessions"""
    PLATFORM_CHOICES = (
        ('zoom', 'Zoom'),
        ('meet', 'Google Meet'),
        ('teams', 'Microsoft Teams'),
    )
    
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    RECORDING_STATUS_CHOICES = (
        ('none', 'No Recording'),
        ('waiting', 'Waiting for Recording'),
        ('processing', 'Processing Recording'),
        ('available', 'Recording Available'),
        ('failed', 'Recording Failed'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='conferences')
    class_level = models.CharField(max_length=10, choices=UserProfile.CLASS_CHOICES)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='zoom')
    meeting_id = models.CharField(max_length=100, blank=True)
    meeting_password = models.CharField(max_length=20, blank=True)
    meeting_link = models.URLField(blank=True)
    scheduled_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scheduled_conferences')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_recurring = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Add specific participants beyond the class level
    participants = models.ManyToManyField(User, through='VideoConferenceParticipant', 
                                        related_name='invited_conferences', blank=True)
    
    # Zoom specific fields
    zoom_start_url = models.URLField(blank=True, help_text="URL for host to start the meeting (Zoom only)")
    zoom_host_id = models.CharField(max_length=100, blank=True, help_text="Host ID for the meeting (Zoom only)")
    zoom_cloud_recording_url = models.URLField(blank=True, help_text="URL to cloud recording (Zoom only)")
    enable_sdk = models.BooleanField(default=True, help_text="Enable Zoom SDK for in-browser meetings")
    used_oauth = models.BooleanField(default=False, help_text="Indicates if this meeting was created using OAuth authentication")
    
    # Recording fields for S3 integration
    recording_status = models.CharField(max_length=20, choices=RECORDING_STATUS_CHOICES, default='none')
    recording_url = models.URLField(blank=True, null=True, help_text="S3 URL for the recording")
    recording_s3_key = models.CharField(max_length=255, blank=True, null=True, help_text="S3 object key for the recording")
    recording_processed_at = models.DateTimeField(blank=True, null=True)
    auto_record = models.BooleanField(default=False, help_text="Automatically record this meeting")
    
    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def get_absolute_url(self):
        return reverse('video_detail', args=[self.id])
    
    @property
    def is_active(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time
    
    @property
    def duration_minutes(self):
        """Calculate meeting duration in minutes"""
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)
    
    def update_status(self):
        """Update meeting status based on current time"""
        now = timezone.now()
        
        if self.status == 'cancelled':
            return
            
        if now < self.start_time:
            self.status = 'scheduled'
        elif self.start_time <= now <= self.end_time:
            self.status = 'active'
        else:
            self.status = 'completed'
        
        self.save(update_fields=['status'])
    
    def create_zoom_meeting(self, use_sdk=None):
        """Create a Zoom meeting using the Zoom API or SDK"""
        if self.platform != 'zoom':
            return False
        
        # If use_sdk is not specified, use the model's enable_sdk field
        if use_sdk is None:
            use_sdk = self.enable_sdk
            
        if use_sdk:
            from core.zoom_service import sdk_create_meeting as create_meeting
        else:
            from core.zoom_service import create_meeting
        
        # Add any special settings for educational meetings
        settings = {
            'host_video': True,
            'participant_video': True,
            'join_before_host': False,
            'mute_upon_entry': True,
            'waiting_room': True,
            'meeting_authentication': False,
            'auto_recording': 'cloud' if self.class_level in ['11', '12'] else 'none'  # Record for higher classes
        }
        
        result = create_meeting(
            topic=self.title,
            start_time=self.start_time,
            duration=self.duration_minutes,
            description=self.description,
            password=self.meeting_password if self.meeting_password else None,
            settings=settings if use_sdk else None
        )
        
        if result.get('success'):
            self.meeting_id = result.get('meeting_id', '')
            self.meeting_link = result.get('join_url', '')
            self.zoom_start_url = result.get('start_url', '')
            self.meeting_password = result.get('password', '')
            self.save(update_fields=['meeting_id', 'meeting_link', 'zoom_start_url', 'meeting_password'])
            return True
        
        return False
    
    def create_zoom_meeting_oauth(self, access_token=None, use_current_user=True):
        """
        Create a Zoom meeting using OAuth authentication
        
        Args:
            access_token (str, optional): OAuth access token. If not provided and use_current_user is True,
                                         will try to use scheduled_by user's token.
            use_current_user (bool): Whether to use the current user's token if access_token not provided.
        
        Returns:
            bool: Success status
        """
        if self.platform != 'zoom':
            return False
            
        # Import the OAuth service
        from core.zoom_oauth_service import create_meeting_oauth, refresh_oauth_token, is_oauth_configured
        from core.models import ZoomOAuthToken
        
        if not is_oauth_configured():
            # Fall back to JWT if OAuth is not configured
            return self.create_zoom_meeting()
            
        # If no access token provided, try to get from user
        if not access_token and use_current_user:
            try:
                # Try to get the current user from the request
                from threading import current_thread
                request = getattr(current_thread(), 'request', None)
                
                # Determine which user to use for OAuth token
                user = None
                if request and hasattr(request, 'user') and request.user.is_authenticated:
                    user = request.user
                else:
                    user = self.scheduled_by
                
                if not user:
                    return self.create_zoom_meeting()
                    
                # Get the token for the user
                try:
                    token = ZoomOAuthToken.objects.filter(user=user).latest('created_at')
                    print(f"Found OAuth token for user {user.username}, expired: {token.is_expired}")
                    
                    # Check if token is expired and needs refresh
                    if token.is_expired:
                        print(f"Refreshing expired token for user {user.username}")
                        token_data = refresh_oauth_token(token.refresh_token)
                        if token_data and not 'error' in token_data:
                            token.save_token_response(token_data)
                            print(f"Token refreshed successfully for user {user.username}")
                        else:
                            print(f"Token refresh failed for user {user.username}")
                            # If refresh failed, try fallback to JWT
                            return self.create_zoom_meeting()
                            
                    access_token = token.access_token
                except ZoomOAuthToken.DoesNotExist:
                    # No token for user, fall back to JWT
                    print(f"No OAuth token found for user {user.username}")
                    return self.create_zoom_meeting()
            except ZoomOAuthToken.DoesNotExist:
                # No token for user, fall back to JWT
                print(f"No OAuth token found for user in outer try block")
                return self.create_zoom_meeting()
            except Exception as e:
                # Log the error for debugging
                print(f"OAuth token retrieval error: {str(e)}")
                # Fall back to JWT as a last resort
                return self.create_zoom_meeting()
        
        if not access_token:
            return self.create_zoom_meeting()
            
        # Add special settings for educational meetings
        settings = {
            'host_video': True,
            'participant_video': True,
            'join_before_host': False,
            'mute_upon_entry': True,
            'waiting_room': True,
            'meeting_authentication': False,
            'auto_recording': 'cloud' if self.class_level in ['11', '12'] else 'none'  # Record for higher classes
        }
            
        # Create the meeting using OAuth
        try:
            result = create_meeting_oauth(
                access_token=access_token,
                topic=self.title,
                start_time=self.start_time,
                duration=self.duration_minutes,
                description=self.description,
                password=self.meeting_password if self.meeting_password else None
            )
            
            # Handle the result
            if result.get('success'):
                self.meeting_id = result.get('id', '')
                self.meeting_link = result.get('join_url', '')
                self.zoom_start_url = result.get('start_url', '')
                self.meeting_password = result.get('password', '')
                self.used_oauth = True  # Mark that this meeting was created with OAuth
                self.save(update_fields=['meeting_id', 'meeting_link', 'zoom_start_url', 'meeting_password', 'used_oauth'])
                return True
        except Exception as e:
            # Log the error for debugging
            print(f"OAuth meeting creation error: {str(e)}")
            
        # If we get here, OAuth failed - log the error and fall back to JWT
        print(f"OAuth meeting creation failed for user {self.scheduled_by.username} - falling back to JWT")
        return self.create_zoom_meeting()
        
    def update_zoom_meeting(self):
        """Update an existing Zoom meeting"""
        if self.platform != 'zoom' or not self.meeting_id:
            return False
            
        # Check if this meeting was created with OAuth and try to update with OAuth first
        if hasattr(self, 'used_oauth') and self.used_oauth:
            try:
                # Try updating with OAuth first
                return self.update_zoom_meeting_oauth(use_current_user=False)
            except Exception as e:
                # If OAuth update fails, fall back to JWT
                print(f"OAuth meeting update error: {str(e)}")
                return self._update_zoom_meeting_jwt()
        
        # Default to JWT update method
        return self._update_zoom_meeting_jwt()
    
    def update_zoom_meeting_oauth(self, access_token=None, use_current_user=True):
        """
        Update a Zoom meeting using OAuth authentication
        
        Args:
            access_token (str, optional): OAuth access token. If not provided and use_current_user is True,
                                         will try to use scheduled_by user's token.
            use_current_user (bool): Whether to use the current user's token if access_token not provided.
        
        Returns:
            bool: Success status
        """
        if self.platform != 'zoom' or not self.meeting_id:
            return False
            
        # Import the OAuth service
        from core.zoom_oauth_service import update_meeting_oauth, refresh_oauth_token, is_oauth_configured
        from core.models import ZoomOAuthToken
        
        if not is_oauth_configured():
            # Fall back to JWT if OAuth is not configured
            return self._update_zoom_meeting_jwt()
            
        # If no access token provided, try to get from user
        if not access_token and use_current_user:
            try:
                # Try to get the current user from the request
                from threading import current_thread
                request = getattr(current_thread(), 'request', None)
                
                # Determine which user to use for OAuth token
                user = None
                if request and hasattr(request, 'user') and request.user.is_authenticated:
                    user = request.user
                elif not use_current_user and self.scheduled_by:
                    user = self.scheduled_by
                
                if not user:
                    return self._update_zoom_meeting_jwt()
                    
                token = ZoomOAuthToken.objects.filter(user=user).latest('created_at')
                
                # Check if token is expired and needs refresh
                if token.is_expired:
                    token_data = refresh_oauth_token(token.refresh_token)
                    if token_data and not 'error' in token_data:
                        token.save_token_response(token_data)
                    else:
                        return self._update_zoom_meeting_jwt()
                        
                access_token = token.access_token
            except ZoomOAuthToken.DoesNotExist:
                # No token for user, fall back to JWT
                return self._update_zoom_meeting_jwt()
            except Exception as e:
                # Log the error for debugging
                print(f"OAuth token retrieval error: {str(e)}")
                return self._update_zoom_meeting_jwt()
        
        if not access_token:
            return self._update_zoom_meeting_jwt()
            
        # Update meeting with OAuth
        try:
            result = update_meeting_oauth(
                access_token=access_token,
                meeting_id=self.meeting_id,
                topic=self.title,
                start_time=self.start_time,
                duration=self.duration_minutes,
                description=self.description,
                password=self.meeting_password if self.meeting_password else None
            )
            
            if result.get('success'):
                return True
        except Exception as e:
            print(f"OAuth meeting update error: {str(e)}")
            
        # If OAuth update failed, try JWT
        return self._update_zoom_meeting_jwt()
    
    def _update_zoom_meeting_jwt(self):
        """Legacy method to update Zoom meeting using JWT"""
        from core.zoom_service import update_meeting
        
        result = update_meeting(
            meeting_id=self.meeting_id,
            topic=self.title,
            start_time=self.start_time,
            duration=self.duration_minutes,
            description=self.description,
            password=self.meeting_password if self.meeting_password else None
        )
        
        return result.get('success', False)
    
    def delete_zoom_meeting(self):
        """Delete a Zoom meeting"""
        if self.platform != 'zoom' or not self.meeting_id:
            return False
            
        # Check if this meeting was created with OAuth and try to delete with OAuth first
        if hasattr(self, 'used_oauth') and self.used_oauth:
            try:
                from core.zoom_oauth_service import delete_meeting_oauth, refresh_oauth_token, is_oauth_configured
                from core.models import ZoomOAuthToken
                
                if not is_oauth_configured():
                    return self._delete_zoom_meeting_jwt()
                    
                # Get the token for the meeting creator
                token = ZoomOAuthToken.objects.filter(user=self.scheduled_by).latest('created_at')
                
                # Check if token is expired and needs refresh
                if token.is_expired:
                    token_data = refresh_oauth_token(token.refresh_token)
                    if token_data and not 'error' in token_data:
                        token.save_token_response(token_data)
                    else:
                        # If refresh failed, fall back to JWT
                        return self._delete_zoom_meeting_jwt()
                
                # Delete meeting using OAuth
                result = delete_meeting_oauth(
                    access_token=token.access_token,
                    meeting_id=self.meeting_id
                )
                
                if result.get('success'):
                    return True
                    
            except (ZoomOAuthToken.DoesNotExist, Exception) as e:
                # Log the error and fall back to JWT
                print(f"OAuth meeting delete error: {str(e)}")
                return self._delete_zoom_meeting_jwt()
        
        # Fall back to JWT delete method
        return self._delete_zoom_meeting_jwt()
        
    def _delete_zoom_meeting_jwt(self):
        """Legacy method to delete Zoom meeting using JWT"""
        from core.zoom_service import delete_meeting
        
        result = delete_meeting(meeting_id=self.meeting_id)
        return result.get('success', False)
        
class RecordedSession(models.Model):
    """Recorded video sessions for later viewing"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='recordings')
    class_level = models.CharField(max_length=10, choices=UserProfile.CLASS_CHOICES)
    recording_url = models.URLField()
    thumbnail_url = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_recordings')
    duration_minutes = models.PositiveIntegerField(default=0)
    recorded_date = models.DateField()
    upload_date = models.DateTimeField(auto_now_add=True)
    views = models.PositiveIntegerField(default=0)
    
    # S3 storage information
    s3_object_key = models.CharField(max_length=255, blank=True, help_text="S3 object key for the recording file")
    storage_type = models.CharField(max_length=20, default='url', choices=(
        ('url', 'External URL'),
        ('s3', 'Amazon S3 Storage'),
        ('zoom', 'Zoom Cloud Recording')
    ))
    is_processed = models.BooleanField(default=True, help_text="Indicates if the video has been processed and is ready to view")
    file_size_mb = models.FloatField(null=True, blank=True, help_text="File size in megabytes")
    
    def __str__(self):
        return f"{self.title} - {self.recorded_date}"
    
    def get_absolute_url(self):
        return reverse('recording_detail', args=[self.id])
        
    def get_secure_url(self):
        """Generate a secure URL for viewing the recording"""
        from core.s3_service import create_presigned_url
        
        if self.storage_type == 's3' and self.s3_object_key:
            # Generate a presigned URL for S3 stored recordings
            return create_presigned_url(self.s3_object_key)
        else:
            # Return the regular URL for non-S3 stored recordings
            return self.recording_url


class Assignment(models.Model):
    """Assignments created by teachers for students"""
    DIFFICULTY_CHOICES = (
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    class_level = models.CharField(max_length=10, choices=UserProfile.CLASS_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_assignments')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    instructions = models.TextField()
    attachment_url = models.CharField(max_length=255, blank=True, help_text="URL to attached file")
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    total_points = models.PositiveIntegerField(default=100)
    
    def __str__(self):
        return f"{self.title} - Due: {self.due_date.strftime('%Y-%m-%d')}"
    
    def get_absolute_url(self):
        return reverse('assignment_detail', args=[self.id])
    
    @property
    def is_past_due(self):
        return timezone.now() > self.due_date


class AssignmentSubmission(models.Model):
    """Student submissions for assignments"""
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignment_submissions')
    submission_text = models.TextField(blank=True)
    attachment_url = models.CharField(max_length=255, blank=True, help_text="URL to submission file")
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_graded = models.BooleanField(default=False)
    points_earned = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_submissions')
    
    def __str__(self):
        return f"Submission by {self.student.username} for {self.assignment.title}"
    
    def get_absolute_url(self):
        return reverse('submission_detail', args=[self.id])
    
    @property
    def is_late(self):
        return self.submitted_at > self.assignment.due_date


class AITutorSession(models.Model):
    """AI tutor interaction sessions"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_sessions')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='ai_sessions', null=True, blank=True)
    title = models.CharField(max_length=100, blank=True, help_text="Custom session title")
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False, help_text="Pin important sessions")
    
    def __str__(self):
        if self.title:
            return f"{self.title} - {self.student.username}"
        return f"AI Session: {self.student.username} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"
        
    def get_first_question(self):
        """Return the first question in the session for context"""
        first_message = self.messages.filter(message_type='question').order_by('timestamp').first()
        if first_message:
            # Truncate long messages to reasonable preview length
            content = first_message.content[:50]
            return f"{content}..." if len(first_message.content) > 50 else content
        return "No questions yet"


class AITutorMessage(models.Model):
    """Individual messages in an AI tutor session"""
    MESSAGE_TYPE_CHOICES = (
        ('question', 'Student Question'),
        ('answer', 'AI Answer'),
        ('summary', 'Summary'),
        ('example', 'Example'),
        ('question_gen', 'Generated Question'),
        ('thread_question', 'Thread Question'),
        ('thread_answer', 'Thread Answer'),
    )
    
    session = models.ForeignKey(AITutorSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    parent_message = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='thread_replies')
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    def has_thread_replies(self):
        """Check if this message has any replies in a thread"""
        return self.thread_replies.exists()
    
    def __str__(self):
        return f"{self.get_message_type_display()}: {self.content[:50]}..."

    class Meta:
        ordering = ['timestamp']


class Quiz(models.Model):
    """Quiz or assessment for students"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='quizzes')
    class_level = models.CharField(max_length=10, choices=UserProfile.CLASS_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_quizzes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    time_limit = models.PositiveIntegerField(default=0, help_text="Time limit in minutes (0 for no limit)")
    passing_score = models.PositiveIntegerField(default=70, help_text="Passing score percentage")
    is_active = models.BooleanField(default=False)
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('quiz_detail', args=[self.id])
    
    @property
    def num_questions(self):
        return self.questions.count()
    
    @property
    def avg_score(self):
        attempts = self.attempts.filter(completed=True)
        if not attempts.exists():
            return 0
        return attempts.aggregate(models.Avg('score'))['score__avg']
    
    @property
    def completion_count(self):
        return self.attempts.filter(completed=True).count()


class QuizQuestion(models.Model):
    """Individual question in a quiz"""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_number = models.PositiveIntegerField()
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255, blank=True)
    option_c = models.CharField(max_length=255, blank=True)
    option_d = models.CharField(max_length=255, blank=True)
    correct_option = models.CharField(max_length=1, choices=[
        ('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D')
    ])
    explanation = models.TextField(blank=True, help_text="Explanation of the correct answer")
    
    def __str__(self):
        return f"Q{self.question_number}: {self.question_text[:50]}..."
    
    class Meta:
        ordering = ['question_number']
        unique_together = ['quiz', 'question_number']


class QuizAttempt(models.Model):
    """Record of a student's attempt at a quiz"""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    score = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        status = "Completed" if self.completed else "In Progress"
        return f"{self.student.username}'s attempt of {self.quiz.title} ({status})"
    
    @property
    def time_taken(self):
        if not self.completed or not self.completed_at:
            return None
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() / 60)
    
    @property
    def passed(self):
        if not self.completed or self.score is None:
            return False
        return self.score >= self.quiz.passing_score


class QuizResponse(models.Model):
    """Individual response to a quiz question"""
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1)
    
    def __str__(self):
        return f"Response to Q{self.question.question_number} by {self.attempt.student.username}"
    
    @property
    def is_correct(self):
        return self.selected_option == self.question.correct_option


class UserSettings(models.Model):
    """User settings and preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    
    # Notification settings
    email_assignments = models.BooleanField(default=True, help_text="Receive email notifications for new assignments")
    email_meetings = models.BooleanField(default=True, help_text="Receive email notifications for scheduled meetings")
    email_weekly_summary = models.BooleanField(default=True, help_text="Receive weekly learning summary emails")
    
    # Display settings
    dark_mode = models.BooleanField(default=False, help_text="Use dark mode theme")
    font_size = models.CharField(max_length=10, default='medium', choices=[
        ('small', 'Small'), 
        ('medium', 'Medium'), 
        ('large', 'Large')
    ])
    
    # Learning preferences
    preferred_learning_style = models.CharField(max_length=20, default='visual', choices=[
        ('visual', 'Visual Learning'),
        ('auditory', 'Auditory Learning'),
        ('reading', 'Reading/Writing'),
        ('kinesthetic', 'Kinesthetic Learning')
    ])
    
    # For teachers/admins only
    default_class_level = models.CharField(max_length=10, blank=True, choices=UserProfile.CLASS_CHOICES, 
                                        help_text="Default class level when creating content (teachers/admins only)")
    
    # AI Tutor settings
    ai_responses_length = models.CharField(max_length=10, default='medium', choices=[
        ('brief', 'Brief'),
        ('medium', 'Medium'),
        ('detailed', 'Detailed')
    ])
    
    date_modified = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Settings for {self.user.username}"
        
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get existing settings or create defaults for user"""
        settings, created = cls.objects.get_or_create(user=user)
        return settings


class ZoomOAuthToken(models.Model):
    """OAuth tokens for Zoom API access"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='zoom_tokens')
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_type = models.CharField(max_length=10, default='bearer')
    expires_at = models.DateTimeField()
    scope = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Zoom OAuth Token"
        verbose_name_plural = "Zoom OAuth Tokens"
    
    def __str__(self):
        return f"Zoom OAuth Token for {self.user.username}"
    
    @property
    def is_expired(self):
        """Check if the token has expired"""
        now = timezone.now()
        return now >= self.expires_at
    
    @property
    def expires_in(self):
        """Calculate seconds until token expiration"""
        if self.is_expired:
            return 0
        delta = self.expires_at - timezone.now()
        return int(delta.total_seconds())
    
    def save_token_response(self, token_data):
        """Save token data from OAuth response"""
        self.access_token = token_data.get('access_token')
        self.refresh_token = token_data.get('refresh_token')
        self.token_type = token_data.get('token_type', 'bearer')
        
        # Calculate expiration time
        expires_in = token_data.get('expires_in', 3600)  # Default to 1 hour
        self.expires_at = timezone.now() + timedelta(seconds=expires_in)
        
        self.scope = token_data.get('scope', '')
        self.save()
        
    def to_dict(self):
        """Convert token to dictionary for API use"""
        return {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': self.token_type,
            'expires_in': self.expires_in,
            'scope': self.scope,
        }


class VideoConferenceParticipant(models.Model):
    """Individual participants invited to a video conference"""
    PARTICIPANT_TYPES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('guest', 'Guest'),
    )
    
    conference = models.ForeignKey(VideoConference, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    participant_type = models.CharField(max_length=10, choices=PARTICIPANT_TYPES, default='student')
    invited_at = models.DateTimeField(auto_now_add=True)
    attended = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('conference', 'user')
        ordering = ['invited_at']
        
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.conference.title}"
