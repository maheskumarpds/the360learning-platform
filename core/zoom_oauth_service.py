"""
Zoom OAuth Service for the the360learning platform
Provides OAuth2.0 authentication for Zoom API instead of JWT
"""

import os
import requests
import json
from datetime import datetime, timedelta

from django.conf import settings
from django.urls import reverse

# Base URLs
ZOOM_API_BASE_URL = 'https://api.zoom.us/v2'
ZOOM_OAUTH_URL = 'https://zoom.us/oauth'


def is_oauth_configured():
    """
    Check if Zoom OAuth is configured with valid credentials
    
    Returns:
        bool: True if Zoom OAuth is configured, False otherwise
    """
    client_id = os.environ.get('ZOOM_CLIENT_ID')
    client_secret = os.environ.get('ZOOM_CLIENT_SECRET')
    
    return bool(client_id and client_secret)


def get_oauth_authorization_url(request, state=None):
    """
    Generate the OAuth authorization URL for Zoom
    
    Args:
        request: Django request object for generating the redirect_uri
        state: Optional state parameter for CSRF protection
        
    Returns:
        str: Authorization URL
    """
    client_id = os.environ.get('ZOOM_CLIENT_ID')
    
    if not client_id:
        raise ValueError("Zoom OAuth client ID is not configured")
    
    # Get the absolute URI for the callback endpoint
    redirect_uri = request.build_absolute_uri(reverse('zoom_oauth_callback'))
    
    # Define the required OAuth scopes
    # user:read - Read your user info and settings
    # meeting:write - Create and update meetings
    # meeting:read - View your meetings
    scopes = [
        'user:read:admin',
        'user:read',
        'meeting:write:admin',
        'meeting:write',
        'meeting:read:admin',
        'meeting:read'
    ]
    
    # Build the authorization URL
    auth_url = f"{ZOOM_OAUTH_URL}/authorize"
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': ' '.join(scopes)
    }
    
    # Add state parameter if provided (for CSRF protection)
    if state:
        params['state'] = state
    
    # Convert params dict to URL query string
    query_string = '&'.join([f"{key}={params[key]}" for key in params])
    
    return f"{auth_url}?{query_string}"


def get_oauth_token(code, redirect_uri=None):
    """
    Exchange authorization code for an OAuth token
    
    Args:
        code: Authorization code
        redirect_uri: Redirect URI (must match the one used for authorization)
        
    Returns:
        dict: OAuth token response including access_token, refresh_token, expires_in, etc.
    """
    client_id = os.environ.get('ZOOM_CLIENT_ID')
    client_secret = os.environ.get('ZOOM_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        raise ValueError("Zoom OAuth credentials are not configured")
    
    token_url = f"{ZOOM_OAUTH_URL}/token"
    
    # Prepare the request data
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri
    }
    
    # Basic auth with client ID and secret
    auth = (client_id, client_secret)
    
    response = None
    try:
        response = requests.post(token_url, data=data, auth=auth)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        return response.json()
    except requests.exceptions.RequestException as e:
        # Log the error and return error details
        print(f"Error getting OAuth token: {str(e)}")
        
        # Try to extract error message from response
        error_details = {'error': str(e)}
        if response is not None:
            try:
                error_details = response.json()
            except:
                pass
        
        return error_details


def refresh_oauth_token(refresh_token):
    """
    Refresh an expired OAuth token
    
    Args:
        refresh_token: Refresh token
        
    Returns:
        dict: OAuth token response including new access_token, refresh_token, expires_in, etc.
    """
    client_id = os.environ.get('ZOOM_CLIENT_ID')
    client_secret = os.environ.get('ZOOM_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        raise ValueError("Zoom OAuth credentials are not configured")
    
    token_url = f"{ZOOM_OAUTH_URL}/token"
    
    # Prepare the request data
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    
    # Basic auth with client ID and secret
    auth = (client_id, client_secret)
    
    try:
        response = requests.post(token_url, data=data, auth=auth)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        return response.json()
    except requests.exceptions.RequestException as e:
        # Log the error and return None
        print(f"Error refreshing OAuth token: {str(e)}")
        return None


def get_oauth_headers(access_token):
    """
    Get headers for Zoom API requests using OAuth
    
    Args:
        access_token: OAuth access token
        
    Returns:
        dict: Headers with OAuth access token
    """
    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }


def create_meeting_oauth(access_token, topic, start_time, duration, description='', password=None):
    """
    Create a Zoom meeting using OAuth
    
    Args:
        access_token: OAuth access token
        topic: Meeting topic/title
        start_time: Meeting start time (datetime)
        duration: Meeting duration in minutes
        description: Meeting description (optional)
        password: Meeting password (optional)
        
    Returns:
        dict: Meeting information including join URL
    """
    if not access_token:
        return {'success': False, 'error': 'No access token provided'}
    
    # Format the start time in Zoom's required format (ISO 8601)
    formatted_start_time = start_time.strftime('%Y-%m-%dT%H:%M:%S')
    
    # Prepare the request data
    data = {
        'topic': topic,
        'type': 2,  # Scheduled meeting
        'start_time': formatted_start_time,
        'duration': duration,
        'timezone': 'UTC',
        'schedule_for': '',  # Schedule for another user if needed
        'settings': {
            'host_video': True,
            'participant_video': True,
            'join_before_host': False,
            'mute_upon_entry': True,
            'watermark': False,
            'use_pmi': False,
            'approval_type': 0,
            'registration_type': 1,
            'audio': 'both',
            'auto_recording': 'none'
        }
    }
    
    # Add optional parameters if provided
    if description:
        data['agenda'] = description
        
    if password:
        data['password'] = password
    
    # Set the API endpoint
    url = f"{ZOOM_API_BASE_URL}/users/me/meetings"
    
    # Set request headers
    headers = get_oauth_headers(access_token)
    
    response = None
    try:
        # Make the API request
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        
        # Parse response data
        result = response.json()
        
        # Return success with meeting details
        return {
            'success': True,
            'meeting_id': result.get('id'),
            'join_url': result.get('join_url'),
            'start_url': result.get('start_url'),
            'password': result.get('password', '')
        }
    except requests.exceptions.RequestException as e:
        # Handle error and return failure with details
        error_msg = "Failed to create Zoom meeting"
        if response is not None:
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
        
        return {
            'success': False,
            'error': error_msg
        }


def get_meeting_oauth(access_token, meeting_id):
    """
    Get Zoom meeting details using OAuth
    
    Args:
        access_token: OAuth access token
        meeting_id: Zoom meeting ID
        
    Returns:
        dict: Meeting information
    """
    if not access_token:
        return {'success': False, 'error': 'No access token provided'}
    
    # Set the API endpoint
    url = f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}"
    
    # Set request headers
    headers = get_oauth_headers(access_token)
    
    response = None
    try:
        # Make the API request
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse response data
        result = response.json()
        
        # Return success with meeting details
        return {
            'success': True,
            'meeting': result
        }
    except requests.exceptions.RequestException as e:
        # Handle error and return failure with details
        error_msg = "Failed to get Zoom meeting"
        if response is not None:
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
        
        return {
            'success': False,
            'error': error_msg
        }


def update_meeting_oauth(access_token, meeting_id, topic=None, start_time=None, duration=None, description=None, password=None):
    """
    Update an existing Zoom meeting using OAuth
    
    Args:
        access_token: OAuth access token
        meeting_id: Zoom meeting ID
        topic: Meeting topic/title (optional)
        start_time: Meeting start time (datetime, optional)
        duration: Meeting duration in minutes (optional)
        description: Meeting description (optional)
        password: Meeting password (optional)
        
    Returns:
        dict: Result of update operation
    """
    if not access_token:
        return {'success': False, 'error': 'No access token provided'}
    
    # Prepare the request data
    data = {}
    
    # Add optional parameters if provided
    if topic:
        data['topic'] = topic
        
    if start_time:
        # Format the start time in Zoom's required format (ISO 8601)
        data['start_time'] = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        
    if duration:
        data['duration'] = duration
        
    if description:
        data['agenda'] = description
        
    if password:
        data['password'] = password
    
    # If no updates specified, return early
    if not data:
        return {'success': True, 'message': 'No updates specified'}
    
    # Set the API endpoint
    url = f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}"
    
    # Set request headers
    headers = get_oauth_headers(access_token)
    
    response = None
    try:
        # Make the API request
        response = requests.patch(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        
        # Return success
        return {
            'success': True,
            'message': 'Meeting updated successfully'
        }
    except requests.exceptions.RequestException as e:
        # Handle error and return failure with details
        error_msg = "Failed to update Zoom meeting"
        if response is not None:
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
        
        return {
            'success': False,
            'error': error_msg
        }


def delete_meeting_oauth(access_token, meeting_id):
    """
    Delete a Zoom meeting using OAuth
    
    Args:
        access_token: OAuth access token
        meeting_id: Zoom meeting ID
        
    Returns:
        dict: Result of delete operation
    """
    if not access_token:
        return {'success': False, 'error': 'No access token provided'}
    
    # Set the API endpoint
    url = f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}"
    
    # Set request headers
    headers = get_oauth_headers(access_token)
    
    response = None
    try:
        # Make the API request
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        
        # Return success
        return {
            'success': True,
            'message': 'Meeting deleted successfully'
        }
    except requests.exceptions.RequestException as e:
        # Handle error and return failure with details
        error_msg = "Failed to delete Zoom meeting"
        if response is not None:
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
        
        return {
            'success': False,
            'error': error_msg
        }


def get_user_meetings_oauth(access_token, user_id='me'):
    """
    Get a list of meetings for a user using OAuth
    
    Args:
        access_token: OAuth access token
        user_id: Zoom user ID (default: 'me' for authenticated user)
        
    Returns:
        dict: List of user's meetings
    """
    if not access_token:
        return {'success': False, 'error': 'No access token provided'}
    
    # Set the API endpoint
    url = f"{ZOOM_API_BASE_URL}/users/{user_id}/meetings"
    
    # Set request headers
    headers = get_oauth_headers(access_token)
    
    response = None
    try:
        # Make the API request
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse response data
        result = response.json()
        
        # Return success with meetings list
        return {
            'success': True,
            'meetings': result.get('meetings', [])
        }
    except requests.exceptions.RequestException as e:
        # Handle error and return failure with details
        error_msg = "Failed to get Zoom meetings"
        if response is not None:
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
        
        return {
            'success': False,
            'error': error_msg
        }


def get_server_to_server_token():
    """
    Get Zoom access token using Server-to-Server OAuth with account credentials
    
    This uses the Account ID, Client ID, and Client Secret to obtain an access token
    without user interaction, suitable for server applications.
    
    Returns:
        str: Access token or None if failed
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Get credentials with detailed logging
    account_id = os.environ.get('ZOOM_ACCOUNT_ID')
    client_id = os.environ.get('ZOOM_CLIENT_ID')
    client_secret = os.environ.get('ZOOM_CLIENT_SECRET')
    
    # Log credential status (without exposing actual values)
    logger.info(f"ZOOM_ACCOUNT_ID is {'set' if account_id else 'NOT SET'}")
    logger.info(f"ZOOM_CLIENT_ID is {'set' if client_id else 'NOT SET'}")
    logger.info(f"ZOOM_CLIENT_SECRET is {'set' if client_secret else 'NOT SET'}")
    
    if not account_id or not client_id or not client_secret:
        logger.error("Zoom server-to-server OAuth credentials are not configured correctly")
        return None
    
    token_url = f"{ZOOM_OAUTH_URL}/token"
    logger.info(f"Attempting to get server-to-server token from {token_url}")
    
    # Prepare the request parameters
    params = {
        "grant_type": "account_credentials",
        "account_id": account_id
    }
    
    # Basic auth with client ID and secret
    auth = (client_id, client_secret)
    
    try:
        response = requests.post(token_url, params=params, auth=auth)
        logger.info(f"Zoom token API response status: {response.status_code}")
        
        # Check for error response
        if response.status_code != 200:
            logger.error(f"Zoom token API error: Status {response.status_code}")
            try:
                error_data = response.json()
                logger.error(f"Error details: {error_data}")
            except:
                logger.error(f"Error response: {response.text}")
            return None
        
        # Extract access token from response
        token_data = response.json()
        
        if 'access_token' in token_data:
            logger.info("Successfully obtained Zoom server-to-server token")
            return token_data.get("access_token")
        else:
            logger.error(f"Token response missing access_token: {token_data}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting server-to-server token: {str(e)}")
        return None


def create_meeting_server_to_server(email, topic, start_time=None, duration=60, description=''):
    """
    Create a Zoom meeting using Server-to-Server OAuth
    
    Args:
        email: Email of the Zoom user to schedule the meeting for
        topic: Meeting topic/title
        start_time: Meeting start time (datetime, optional - defaults to 1 hour from now)
        duration: Meeting duration in minutes (default: 60)
        description: Meeting description (optional)
        
    Returns:
        dict: Meeting information including join_url, or error message
    """
    # Get access token
    access_token = get_server_to_server_token()
    
    if not access_token:
        return {'success': False, 'error': 'Failed to obtain access token'}
    
    # Default start time to 1 hour from now if not provided
    if start_time is None:
        start_time = datetime.now() + timedelta(hours=1)
    
    # Format the start time in Zoom's required format (ISO 8601)
    formatted_start_time = start_time.strftime('%Y-%m-%dT%H:%M:%S')
    
    # Meeting details
    meeting_data = {
        "topic": topic,
        "type": 2,  # Scheduled meeting
        "start_time": formatted_start_time,
        "duration": duration,
        "timezone": "UTC",
        "settings": {
            "join_before_host": True,
            "host_video": True,
            "participant_video": True,
            "mute_upon_entry": True,
            "auto_recording": "none"
        }
    }
    
    # Add description if provided
    if description:
        meeting_data["agenda"] = description
    
    # Set headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Create meeting
    url = f"{ZOOM_API_BASE_URL}/users/{email}/meetings"
    
    response = None
    try:
        response = requests.post(url, headers=headers, json=meeting_data)
        response.raise_for_status()
        
        # Extract meeting details
        result = response.json()
        
        return {
            'success': True,
            'meeting_id': result.get('id'),
            'join_url': result.get('join_url'),
            'start_url': result.get('start_url'),
            'password': result.get('password', '')
        }
    except requests.exceptions.RequestException as e:
        # Handle error
        error_msg = "Failed to create Zoom meeting"
        if response is not None:
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = f"{error_msg}: {error_data['message']}"
            except:
                error_msg = f"{error_msg}: {str(e)}"
        
        return {
            'success': False,
            'error': error_msg
        }


def get_meeting_recordings_oauth(access_token, meeting_id):
    """
    Get recordings from a past meeting using OAuth
    
    Args:
        access_token: OAuth access token
        meeting_id: Past meeting ID
        
    Returns:
        dict: Meeting recordings information
    """
    if not access_token:
        return {'success': False, 'error': 'No access token provided'}
    
    # Set the API endpoint
    url = f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}/recordings"
    
    # Set request headers
    headers = get_oauth_headers(access_token)
    
    response = None
    try:
        # Make the API request
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse response data
        result = response.json()
        
        # Return success with recordings details
        return {
            'success': True,
            'recordings': result
        }
    except requests.exceptions.RequestException as e:
        # Handle error and return failure with details
        error_msg = "Failed to get meeting recordings"
        if response is not None:
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
        
        return {
            'success': False,
            'error': error_msg
        }