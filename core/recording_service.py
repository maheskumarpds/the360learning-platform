import os
import logging
import time
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction

from core.models import RecordedSession, Subject
from core.zoom_service import get_meeting_recordings, get_past_meeting_recordings
from core.s3_service import create_presigned_url, delete_file_from_s3

# Set up logging
logger = logging.getLogger(__name__)

def save_zoom_recording_to_db(meeting_id, uploaded_by, subject_id=None, class_level=None, title=None, description=None):
    """
    Save a Zoom recording to the database with options for S3 or direct URL storage
    
    Args:
        meeting_id (str): Zoom meeting ID
        uploaded_by (User): User who is uploading the recording
        subject_id (int, optional): Subject ID
        class_level (str, optional): Class level
        title (str, optional): Recording title
        description (str, optional): Recording description
        
    Returns:
        tuple: (success: bool, message: str, recorded_session: RecordedSession)
    """
    try:
        # Check if Zoom API keys are configured
        from core.zoom_service import is_zoom_configured
        if not is_zoom_configured():
            return False, "Zoom API is not configured. Please configure Zoom API keys to import recordings.", None

        # Get meeting recording information from Zoom API
        recording_data = get_meeting_recordings(meeting_id)
        
        if not recording_data or 'recording_files' not in recording_data or not recording_data['recording_files']:
            return False, "No recordings found for this meeting ID", None
        
        # Use the first recording file (usually the main recording)
        recording_file = None
        for file in recording_data['recording_files']:
            # Look for an MP4 file if possible
            if file.get('file_type', '').lower() == 'mp4':
                recording_file = file
                break
        
        # If no MP4 file found, use the first file
        if not recording_file and recording_data['recording_files']:
            recording_file = recording_data['recording_files'][0]
        
        if not recording_file:
            return False, "No usable recording file found", None
        
        # Prepare data for RecordedSession
        title = title or recording_data.get('topic', f"Zoom Recording {meeting_id}")
        file_type = 'video'
        duration_minutes = recording_file.get('duration', 0) or recording_data.get('duration', 0)
        recording_start_time = recording_file.get('recording_start', None)
        
        # Parse the recording start time, defaulting to current date if not available
        try:
            if recording_start_time:
                from datetime import datetime
                recorded_date = datetime.strptime(recording_start_time.split('T')[0], '%Y-%m-%d').date()
            else:
                recorded_date = timezone.now().date()
        except Exception as e:
            logger.exception(f"Error parsing recording date: {e}")
            recorded_date = timezone.now().date()
        
        # Check if S3 is configured for storage
        from core.s3_service import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
        storage_type = 's3' if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY else 'url'
        
        # Get the appropriate URL for the recording
        recording_url = recording_file.get('play_url') or recording_file.get('download_url')
        if not recording_url:
            return False, "No playable URL found for this recording", None
        
        # Get or create a default subject if not provided
        if not subject_id:
            subject, created = Subject.objects.get_or_create(
                name="General",
                defaults={'description': 'General recordings without a specific subject'}
            )
            subject_id = subject.id
        
        # Create the recorded session
        recorded_session = RecordedSession.objects.create(
            title=title,
            description=description or "",
            subject_id=subject_id,
            class_level=class_level or "0",  # Default to "All Classes" if not specified
            file_type=file_type,
            uploaded_by=uploaded_by,
            recording_url=recording_url,
            duration_minutes=duration_minutes,
            recorded_date=recorded_date,
            storage_type='zoom',
            zoom_meeting_id=meeting_id
        )
        
        return True, "Successfully imported Zoom recording", recorded_session
        
    except Exception as e:
        logger.exception(f"Error saving Zoom recording: {str(e)}")
        return False, f"Error saving recording: {str(e)}", None

def get_recording_stream_url(recorded_session):
    """
    Get a temporary streaming URL for a recorded session
    
    Args:
        recorded_session (RecordedSession): The recorded session
        
    Returns:
        str: URL for streaming the recording
    """
    if recorded_session.storage_type == 's3' and recorded_session.s3_object_key:
        # Generate a presigned URL for S3 stored recordings (1 hour validity)
        presigned_url = create_presigned_url(recorded_session.s3_object_key, expiration=3600)
        # If S3 is not configured or fails, fall back to the direct URL
        if not presigned_url:
            logger.warning(f"Failed to generate presigned URL for {recorded_session.s3_object_key}, falling back to direct URL")
            return recorded_session.recording_url
        return presigned_url
    else:
        # Return the regular URL for non-S3 stored recordings
        return recorded_session.recording_url

def get_class_recordings(class_level):
    """
    Get all recordings for a specific class level
    
    Args:
        class_level (str): Class level
        
    Returns:
        QuerySet: RecordedSession objects
    """
    return RecordedSession.objects.filter(class_level=class_level).order_by('-recorded_date')

def get_subject_recordings(subject_id, class_level=None):
    """
    Get all recordings for a specific subject
    
    Args:
        subject_id (int): Subject ID
        class_level (str, optional): Class level to filter by
        
    Returns:
        QuerySet: RecordedSession objects
    """
    queryset = RecordedSession.objects.filter(subject_id=subject_id)
    
    if class_level:
        queryset = queryset.filter(class_level=class_level)
        
    return queryset.order_by('-recorded_date')

def increment_recording_view_count(recording_id):
    """
    Increment the view count for a recording
    
    Args:
        recording_id (int): Recording ID
        
    Returns:
        bool: Success or failure
    """
    try:
        recording = RecordedSession.objects.get(id=recording_id)
        recording.views += 1
        recording.save(update_fields=['views'])
        return True
    except RecordedSession.DoesNotExist:
        return False
    except Exception as e:
        logger.error(f"Error incrementing view count: {str(e)}")
        return False