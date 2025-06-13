import os
import json
import time
import jwt
import requests
import tempfile
import logging
from datetime import datetime, timedelta
from django.conf import settings
from zoomus import ZoomClient
from core.s3_service import upload_file_to_s3, create_presigned_url

# Set up logging
logger = logging.getLogger(__name__)

# Zoom API credentials
ZOOM_API_KEY = os.environ.get('ZOOM_API_KEY')
ZOOM_API_SECRET = os.environ.get('ZOOM_API_SECRET')
ZOOM_API_BASE_URL = 'https://api.zoom.us/v2'

def is_zoom_configured():
    """
    Check if Zoom API is configured with valid credentials
    
    Returns:
        bool: True if Zoom API is configured, False otherwise
    """
    return bool(ZOOM_API_KEY and ZOOM_API_SECRET)

# Initialize Zoom SDK client
# Note: Newer versions of zoomus may require account_id parameter
try:
    zoom_client = ZoomClient(ZOOM_API_KEY, ZOOM_API_SECRET) if is_zoom_configured() else None
except TypeError:
    # For newer zoomus versions, provide a dummy account_id
    # In JWT auth mode, account_id may not be strictly needed for all operations
    zoom_client = ZoomClient(ZOOM_API_KEY, ZOOM_API_SECRET, 'me') if is_zoom_configured() else None

def generate_jwt_token():
    """
    Generate a JWT token for Zoom API authentication
    
    Returns:
        str: JWT token
    """
    # Set token expiration time (1 hour)
    token_exp = datetime.utcnow() + timedelta(hours=1)
    
    # Create payload
    payload = {
        'iss': ZOOM_API_KEY,
        'exp': int(token_exp.timestamp())
    }
    
    # Generate JWT token
    token = jwt.encode(payload, ZOOM_API_SECRET, algorithm='HS256')
    
    # If the token is returned as bytes, decode it to a string
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    
    return token

def get_headers():
    """
    Get headers for Zoom API requests
    
    Returns:
        dict: Headers with JWT token
    """
    return {
        'Authorization': f'Bearer {generate_jwt_token()}',
        'Content-Type': 'application/json'
    }

def create_meeting(topic, start_time, duration, description='', password=None):
    """
    Create a Zoom meeting
    
    Args:
        topic (str): Meeting topic/title
        start_time (datetime): Meeting start time
        duration (int): Meeting duration in minutes
        description (str, optional): Meeting description
        password (str, optional): Meeting password
        
    Returns:
        dict: Meeting information including join URL
    """
    url = f"{ZOOM_API_BASE_URL}/users/me/meetings"
    
    # Format start time for Zoom API
    formatted_time = start_time.strftime('%Y-%m-%dT%H:%M:%S')
    
    # Prepare meeting data
    meeting_data = {
        'topic': topic,
        'type': 2,  # Scheduled meeting
        'start_time': formatted_time,
        'duration': duration,
        'timezone': 'UTC',
        'agenda': description,
        'settings': {
            'host_video': True,
            'participant_video': True,
            'join_before_host': False,
            'mute_upon_entry': True,
            'waiting_room': True,
            'meeting_authentication': False
        }
    }
    
    # Add password if provided
    if password:
        meeting_data['password'] = password
    
    try:
        response = requests.post(url, headers=get_headers(), json=meeting_data)
        
        # Check if the request was successful
        if response.status_code == 201:
            meeting_info = response.json()
            return {
                'success': True,
                'meeting_id': meeting_info.get('id'),
                'join_url': meeting_info.get('join_url'),
                'start_url': meeting_info.get('start_url'),
                'password': meeting_info.get('password', ''),
                'duration': meeting_info.get('duration'),
                'start_time': meeting_info.get('start_time')
            }
        else:
            return {
                'success': False,
                'error': f"Error creating meeting: {response.status_code} - {response.text}"
            }
    except Exception as e:
        return {
            'success': False,
            'error': f"Exception creating meeting: {str(e)}"
        }

def get_meeting(meeting_id):
    """
    Get Zoom meeting details
    
    Args:
        meeting_id (str): Zoom meeting ID
        
    Returns:
        dict: Meeting information
    """
    url = f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}"
    
    try:
        response = requests.get(url, headers=get_headers())
        
        if response.status_code == 200:
            return {
                'success': True,
                'meeting_info': response.json()
            }
        else:
            return {
                'success': False,
                'error': f"Error getting meeting: {response.status_code} - {response.text}"
            }
    except Exception as e:
        return {
            'success': False,
            'error': f"Exception getting meeting: {str(e)}"
        }

def update_meeting(meeting_id, topic=None, start_time=None, duration=None, description=None, password=None):
    """
    Update an existing Zoom meeting
    
    Args:
        meeting_id (str): Zoom meeting ID
        topic (str, optional): Meeting topic/title
        start_time (datetime, optional): Meeting start time
        duration (int, optional): Meeting duration in minutes
        description (str, optional): Meeting description
        password (str, optional): Meeting password
        
    Returns:
        dict: Result of update operation
    """
    url = f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}"
    
    # Prepare meeting data with only the fields to update
    meeting_data = {}
    
    if topic:
        meeting_data['topic'] = topic
    
    if start_time:
        # Format start time for Zoom API
        meeting_data['start_time'] = start_time.strftime('%Y-%m-%dT%H:%M:%S')
    
    if duration:
        meeting_data['duration'] = duration
    
    if description:
        meeting_data['agenda'] = description
    
    if password:
        meeting_data['password'] = password
    
    try:
        response = requests.patch(url, headers=get_headers(), json=meeting_data)
        
        if response.status_code == 204:  # No content returned on success
            return {
                'success': True,
                'message': 'Meeting updated successfully'
            }
        else:
            return {
                'success': False,
                'error': f"Error updating meeting: {response.status_code} - {response.text}"
            }
    except Exception as e:
        return {
            'success': False,
            'error': f"Exception updating meeting: {str(e)}"
        }

def delete_meeting(meeting_id):
    """
    Delete a Zoom meeting
    
    Args:
        meeting_id (str): Zoom meeting ID
        
    Returns:
        dict: Result of delete operation
    """
    url = f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}"
    
    try:
        response = requests.delete(url, headers=get_headers())
        
        if response.status_code == 204:  # No content returned on success
            return {
                'success': True,
                'message': 'Meeting deleted successfully'
            }
        else:
            return {
                'success': False,
                'error': f"Error deleting meeting: {response.status_code} - {response.text}"
            }
    except Exception as e:
        return {
            'success': False,
            'error': f"Exception deleting meeting: {str(e)}"
        }

def get_past_meeting_recordings(meeting_id):
    """
    Get recordings from a past meeting
    
    Args:
        meeting_id (str): Past meeting ID
        
    Returns:
        dict: Meeting recordings information
    """
    url = f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}/recordings"
    
    try:
        response = requests.get(url, headers=get_headers())
        
        if response.status_code == 200:
            return {
                'success': True,
                'recording_info': response.json()
            }
        else:
            return {
                'success': False,
                'error': f"Error getting recordings: {response.status_code} - {response.text}"
            }
    except Exception as e:
        return {
            'success': False,
            'error': f"Exception getting recordings: {str(e)}"
        }

def get_meeting_recordings(meeting_id):
    """
    Get recording files for a specific meeting
    
    Args:
        meeting_id (str): The meeting ID
        
    Returns:
        dict or None: Recording information or None if error/no recordings
    """
    if not is_zoom_configured():
        logger.warning("Zoom API is not configured")
        return None
        
    try:
        result = get_past_meeting_recordings(meeting_id)
        
        if result.get('success'):
            return result.get('recording_info')
        else:
            logger.error(f"Error fetching recordings: {result.get('error')}")
            return None
    except Exception as e:
        logger.exception(f"Exception getting meeting recordings: {str(e)}")
        return None


# SDK-based functions for enhanced functionality

def sdk_create_meeting(topic, start_time, duration, description='', password=None, settings=None):
    """
    Create a Zoom meeting using the Zoom SDK
    
    Args:
        topic (str): Meeting topic/title
        start_time (datetime): Meeting start time
        duration (int): Meeting duration in minutes
        description (str, optional): Meeting description
        password (str, optional): Meeting password
        settings (dict, optional): Additional meeting settings
        
    Returns:
        dict: Meeting information including join URL
    """
    # Format start time for Zoom API
    formatted_time = start_time.strftime('%Y-%m-%dT%H:%M:%S')
    
    # Default meeting settings
    default_settings = {
        'host_video': True,
        'participant_video': True,
        'join_before_host': False,
        'mute_upon_entry': True,
        'waiting_room': True,
        'auto_recording': 'none'
    }
    
    # Update with custom settings if provided
    if settings:
        default_settings.update(settings)
    
    # Prepare meeting parameters
    params = {
        'topic': topic,
        'type': 2,  # Scheduled meeting
        'start_time': formatted_time,
        'duration': duration,
        'timezone': 'UTC',
        'agenda': description,
        'settings': default_settings
    }
    
    # Add password if provided
    if password:
        params['password'] = password
    
    try:
        # Use the SDK client to create the meeting
        response = zoom_client.meeting.create(user_id='me', **params)
        
        # Check if the request was successful
        if response.get('status_code') == 201:
            meeting_info = response.get('json', {})
            return {
                'success': True,
                'meeting_id': meeting_info.get('id'),
                'join_url': meeting_info.get('join_url'),
                'start_url': meeting_info.get('start_url'),
                'password': meeting_info.get('password', ''),
                'duration': meeting_info.get('duration'),
                'start_time': meeting_info.get('start_time')
            }
        else:
            return {
                'success': False,
                'error': f"Error creating meeting: {response}"
            }
    except Exception as e:
        return {
            'success': False,
            'error': f"Exception creating meeting: {str(e)}"
        }

def get_user_meetings(user_id='me', meeting_type='scheduled'):
    """
    Get a list of meetings for a user
    
    Args:
        user_id (str): Zoom user ID (default: 'me' for authenticated user)
        meeting_type (str): Type of meetings to retrieve (scheduled, live, upcoming)
        
    Returns:
        dict: List of user's meetings
    """
    try:
        params = {'type': meeting_type}
        response = zoom_client.meeting.list(user_id=user_id, **params)
        
        if response.get('status_code') == 200:
            return {
                'success': True,
                'meetings': response.get('json', {}).get('meetings', [])
            }
        else:
            return {
                'success': False,
                'error': f"Error getting user meetings: {response}"
            }
    except Exception as e:
        return {
            'success': False,
            'error': f"Exception getting user meetings: {str(e)}"
        }

def generate_meeting_signature(meeting_number, role):
    """
    Generate a signature for joining a Zoom meeting via the web SDK
    
    Args:
        meeting_number (str): The Zoom meeting number
        role (int): Role in the meeting (0 for attendee, 1 for host)
        
    Returns:
        str: Signature string for the Zoom Web SDK
    """
    timestamp = int(time.time() * 1000) - 30000
    data = f"{ZOOM_API_KEY}{meeting_number}{timestamp}{role}"
    
    # Generate the signature
    signature = jwt.encode(
        {'hash': data},
        ZOOM_API_SECRET,
        algorithm='HS256'
    )
    
    # If the signature is returned as bytes, decode it to a string
    if isinstance(signature, bytes):
        signature = signature.decode('utf-8')
    
    return signature

def get_meeting_participants(meeting_id):
    """
    Get a list of participants for a meeting
    
    Args:
        meeting_id (str): The Zoom meeting ID
        
    Returns:
        dict: List of meeting participants
    """
    try:
        response = zoom_client.meeting.list_registration(id=meeting_id)
        
        if response.get('status_code') == 200:
            return {
                'success': True,
                'participants': response.get('json', {}).get('registrants', [])
            }
        else:
            return {
                'success': False,
                'error': f"Error getting meeting participants: {response}"
            }
    except Exception as e:
        return {
            'success': False,
            'error': f"Exception getting meeting participants: {str(e)}"
        }


def download_recording_to_s3(meeting_id, recording_file=None, conference_obj=None):
    """
    Download a recording from Zoom and upload it to S3
    
    Args:
        meeting_id (str): Past meeting ID
        recording_file (dict, optional): Specific recording file object to download.
                                        If None, all recording files will be processed.
        conference_obj (VideoConference, optional): Associated VideoConference object to update with recording info
        
    Returns:
        dict: Result with success status and uploaded file information
    """
    # First, get the recording information
    recording_result = get_past_meeting_recordings(meeting_id)
    
    if not recording_result.get('success'):
        if conference_obj:
            conference_obj.recording_status = 'failed'
            conference_obj.save()
        return {
            'success': False,
            'error': recording_result.get('error', 'Failed to get recording information')
        }
    
    recording_info = recording_result.get('recording_info', {})
    recording_files = recording_info.get('recording_files', [])
    
    if not recording_files:
        if conference_obj:
            conference_obj.recording_status = 'none'
            conference_obj.save()
        return {
            'success': False,
            'error': 'No recording files found for this meeting'
        }
    
    # If a specific recording file is provided, filter to only that one
    if recording_file:
        recording_files = [rf for rf in recording_files if rf.get('id') == recording_file.get('id')]
        
        if not recording_files:
            if conference_obj:
                conference_obj.recording_status = 'failed'
                conference_obj.save()
            return {
                'success': False,
                'error': 'Specified recording file not found'
            }
    
    # Results to return
    results = {
        'success': True,
        'uploads': []
    }
    
    # If we have a conference object, update its status to indicate recording processing
    if conference_obj:
        conference_obj.recording_status = 'processing'
        conference_obj.save()
    
    # Process each recording file
    for file in recording_files:
        file_type = file.get('file_type', '').lower()
        
        # We're only interested in MP4 files for video playback
        if file_type != 'mp4':
            continue
        
        download_url = file.get('download_url')
        if not download_url:
            logger.warning(f"No download URL for recording file: {file.get('id')}")
            continue
        
        # Add JWT token to the download URL for authentication
        download_url_with_token = f"{download_url}?access_token={generate_jwt_token()}"
        
        try:
            # Download the file to a temporary location
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_path = temp_file.name
                
                logger.info(f"Downloading recording to {temp_path}")
                
                # Stream the download to avoid memory issues with large files
                with requests.get(download_url_with_token, stream=True) as r:
                    r.raise_for_status()
                    for chunk in r.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
            
            # Get file size in MB for record keeping
            file_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
            
            # Generate a meaningful object name with meeting info
            meeting_topic = recording_info.get('topic', '').replace(' ', '_')
            recording_start = file.get('recording_start', '').replace(':', '-').replace(' ', '_')
            
            object_name = f"recordings/{meeting_id}/{meeting_topic}_{recording_start}_{file.get('id')}.mp4"
            
            # Upload the file to S3
            s3_result = upload_file_to_s3(
                file_path=temp_path,
                object_name=object_name,
                extra_args={
                    'ContentType': 'video/mp4',
                    'ACL': 'private'
                }
            )
            
            # Clean up the temporary file
            os.unlink(temp_path)
            
            if s3_result.get('success'):
                # Add result to the list of successful uploads
                upload_info = {
                    'meeting_id': meeting_id,
                    'recording_id': file.get('id'),
                    'recording_type': file.get('recording_type'),
                    's3_object_key': object_name,
                    'file_url': s3_result.get('file_url'),
                    'file_size_mb': file_size_mb,
                    'recording_start': file.get('recording_start'),
                    'recording_end': file.get('recording_end')
                }
                
                # Update the conference object with recording details if available
                if conference_obj:
                    from datetime import datetime, timezone
                    conference_obj.recording_status = 'available'
                    conference_obj.recording_url = s3_result.get('file_url')
                    conference_obj.recording_s3_key = object_name
                    conference_obj.recording_processed_at = datetime.now(timezone.utc)
                    conference_obj.save()
                    
                results['uploads'].append(upload_info)
            else:
                logger.error(f"S3 upload failed: {s3_result.get('error')}")
                error_info = {
                    'meeting_id': meeting_id,
                    'recording_id': file.get('id'),
                    'error': s3_result.get('error'),
                    'status': 'failed'
                }
                
                # Update conference object status on failure
                if conference_obj:
                    conference_obj.recording_status = 'failed'
                    conference_obj.save()
                    
                results['uploads'].append(error_info)
        
        except Exception as e:
            logger.exception(f"Error processing recording file {file.get('id')}: {str(e)}")
            error_info = {
                'meeting_id': meeting_id,
                'recording_id': file.get('id'),
                'error': str(e),
                'status': 'failed'
            }
            
            # Update conference object status on exception
            if conference_obj:
                conference_obj.recording_status = 'failed'
                conference_obj.save()
                
            results['uploads'].append(error_info)
    
    # Check if we had any successful uploads
    if not results['uploads']:
        if conference_obj:
            conference_obj.recording_status = 'none'
            conference_obj.save()
        results['success'] = False
        results['error'] = 'No recordings were processed'
    elif not any(upload.get('status') != 'failed' for upload in results['uploads']):
        # All uploads failed
        if conference_obj:
            conference_obj.recording_status = 'failed'
            conference_obj.save()
        results['success'] = False
        results['error'] = 'All recording uploads failed'
    
    return results

def setup_auto_recording_for_meeting(meeting_id, save_to_s3=True, conference_obj=None):
    """
    Configure auto-recording settings for a meeting
    
    Args:
        meeting_id (str): Meeting ID
        save_to_s3 (bool): Whether to automatically save recordings to S3
        conference_obj (VideoConference, optional): Associated VideoConference object to update
        
    Returns:
        dict: Result with success status
    """
    url = f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}/settings"
    
    settings_data = {
        'settings': {
            'auto_recording': 'cloud',  # Record automatically to the cloud
            'recording_disclaimer': True,  # Show recording disclaimer
            'recording_reminder': True,  # Remind participants that recording is on
        }
    }
    
    try:
        # Update meeting settings
        response = requests.patch(url, headers=get_headers(), json=settings_data)
        
        if response.status_code == 204:  # No content returned on success
            # Update the conference object if provided
            if conference_obj:
                conference_obj.auto_record = True
                conference_obj.recording_status = 'waiting'
                conference_obj.save()
                
            return {
                'success': True,
                'message': 'Auto-recording configured successfully',
                'save_to_s3': save_to_s3
            }
        else:
            # Update conference object with failed status if provided
            if conference_obj:
                conference_obj.auto_record = False
                conference_obj.save()
                
            return {
                'success': False,
                'error': f"Error configuring auto-recording: {response.status_code} - {response.text}"
            }
    except Exception as e:
        # Update conference object with failed status if provided
        if conference_obj:
            conference_obj.auto_record = False
            conference_obj.save()
            
        return {
            'success': False,
            'error': f"Exception configuring auto-recording: {str(e)}"
        }