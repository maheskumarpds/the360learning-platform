from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.urls import reverse
from django.db.models import Q
from django.core.paginator import Paginator
import json
import logging

from core.models import RecordedSession, VideoConference, Subject, UserProfile
from core.recording_service import (
    save_zoom_recording_to_db, 
    get_recording_stream_url,
    increment_recording_view_count,
    get_class_recordings,
    get_subject_recordings
)
from core.zoom_service import get_meeting_recordings, is_zoom_configured
from core.forms import RecordedSessionForm
from core.s3_service import delete_file_from_s3

# Set up logging
logger = logging.getLogger(__name__)

@login_required
def recordings_list(request):
    """List recorded sessions with filtering"""
    user = request.user
    user_profile = get_object_or_404(UserProfile, user=user)
    
    # Get filter parameters
    subject_id = request.GET.get('subject')
    class_level = request.GET.get('class_level')
    search_query = request.GET.get('search', '')
    
    # Start with all recordings
    recordings = RecordedSession.objects.all()
    
    # Apply role-based restrictions
    if user_profile.role == 'student':
        # Students can only see recordings for their class level
        recordings = recordings.filter(class_level=user_profile.class_level)
    elif user_profile.role == 'teacher':
        # Teachers can see recordings they uploaded OR recordings for classes they teach
        teacher_classes = UserProfile.objects.filter(user=user).values_list('class_level', flat=True)
        recordings = recordings.filter(
            Q(uploaded_by=user) | Q(class_level__in=teacher_classes)
        )
    # Admins can see all recordings (no filtering needed)
    
    # Apply search filters
    if search_query:
        recordings = recordings.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Apply subject filter
    if subject_id:
        recordings = recordings.filter(subject_id=subject_id)
    
    # Apply class level filter (admin and teachers only)
    if class_level and user_profile.role != 'student':
        recordings = recordings.filter(class_level=class_level)
    
    # Apply sorting based on user selection
    sort_by = request.GET.get('sort', 'recent')
    if sort_by == 'popular':
        recordings = recordings.order_by('-views', '-recorded_date')
    elif sort_by == 'title':
        recordings = recordings.order_by('title')
    else:  # Default to most recent
        recordings = recordings.order_by('-recorded_date', '-upload_date')
    
    # Paginate results
    paginator = Paginator(recordings, 12)  # 12 recordings per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get subjects for filter
    if user_profile.role == 'student':
        subjects = Subject.objects.filter(
            class_assignments__class_level=user_profile.class_level
        ).distinct()
    elif user_profile.role == 'teacher':
        class_levels = UserProfile.objects.filter(user=user).values_list('class_level', flat=True)
        subjects = Subject.objects.filter(
            class_assignments__class_level__in=class_levels
        ).distinct()
    else:
        subjects = Subject.objects.all()
    
    # Get class levels for filter (not needed for students)
    class_levels = []
    if user_profile.role != 'student':
        if user_profile.role == 'teacher':
            class_levels = [(cl, dict(UserProfile.CLASS_CHOICES)[cl]) 
                          for cl in UserProfile.objects.filter(user=user).values_list('class_level', flat=True)]
        else:
            class_levels = UserProfile.CLASS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'subjects': subjects,
        'class_levels': class_levels,
        'selected_subject': subject_id,
        'selected_class': class_level,
        'search_query': search_query,
        'user_role': user_profile.role,
    }
    
    return render(request, 'recordings/list.html', context)

@login_required
def recording_detail(request, recording_id):
    """View details of a recorded session"""
    user = request.user
    user_profile = get_object_or_404(UserProfile, user=user)
    
    # Get recording and check permissions
    recording = get_object_or_404(RecordedSession, id=recording_id)
    
    # Students can only access recordings for their class level
    if user_profile.role == 'student' and recording.class_level != user_profile.class_level:
        messages.error(request, "You don't have permission to view this recording.")
        return redirect('recordings_list')
    
    # Teachers can only access recordings they uploaded or for classes they teach
    if user_profile.role == 'teacher':
        teacher_classes = UserProfile.objects.filter(user=user).values_list('class_level', flat=True)
        if recording.uploaded_by != user and recording.class_level not in teacher_classes:
            messages.error(request, "You don't have permission to view this recording.")
            return redirect('recordings_list')
    
    # Get streaming URL (S3 presigned URL or direct URL)
    streaming_url = get_recording_stream_url(recording)
    
    # Increment view count (only on GET request to avoid double counting)
    if request.method == 'GET':
        increment_recording_view_count(recording_id)
    
    # Get related recordings from the same subject
    related_recordings = RecordedSession.objects.filter(
        subject=recording.subject,
        class_level=recording.class_level
    ).exclude(id=recording_id).order_by('-recorded_date')[:4]
    
    context = {
        'recording': recording,
        'streaming_url': streaming_url,
        'related_recordings': related_recordings,
        'user_role': user_profile.role,
    }
    
    return render(request, 'recordings/detail.html', context)

@login_required
def upload_recording(request):
    """Upload a new recording"""
    user = request.user
    user_profile = get_object_or_404(UserProfile, user=user)
    
    # Only teachers and admins can upload recordings
    if user_profile.role == 'student':
        messages.error(request, "Students cannot upload recordings.")
        return redirect('recordings_list')
    
    if request.method == 'POST':
        form = RecordedSessionForm(request.POST)
        
        if form.is_valid():
            recording = form.save(commit=False)
            recording.uploaded_by = user
            
            # Teachers can only upload for their assigned classes
            if user_profile.role == 'teacher':
                teacher_classes = UserProfile.objects.filter(user=user).values_list('class_level', flat=True)
                if recording.class_level not in teacher_classes:
                    messages.error(request, "You can only upload recordings for classes you teach.")
                    return redirect('recordings_list')
            
            recording.save()
            messages.success(request, "Recording uploaded successfully.")
            return redirect('recording_detail', recording_id=recording.id)
    else:
        form = RecordedSessionForm()
    
    # Get subjects for dropdown
    if user_profile.role == 'teacher':
        class_levels = UserProfile.objects.filter(user=user).values_list('class_level', flat=True)
        subjects = Subject.objects.filter(
            class_assignments__class_level__in=class_levels
        ).distinct()
    else:
        subjects = Subject.objects.all()
    
    # Get class levels for dropdown
    if user_profile.role == 'teacher':
        class_levels = [(cl, dict(UserProfile.CLASS_CHOICES)[cl]) 
                      for cl in UserProfile.objects.filter(user=user).values_list('class_level', flat=True)]
    else:
        class_levels = UserProfile.CLASS_CHOICES
    
    context = {
        'form': form,
        'subjects': subjects,
        'class_levels': class_levels,
    }
    
    return render(request, 'recordings/upload.html', context)

@login_required
def edit_recording(request, recording_id):
    """Edit an existing recording"""
    user = request.user
    user_profile = get_object_or_404(UserProfile, user=user)
    
    # Get recording and check permissions
    recording = get_object_or_404(RecordedSession, id=recording_id)
    
    # Only the uploader or admin can edit
    if user_profile.role != 'admin' and recording.uploaded_by != user:
        messages.error(request, "You don't have permission to edit this recording.")
        return redirect('recording_detail', recording_id=recording.id)
    
    if request.method == 'POST':
        form = RecordedSessionForm(request.POST, instance=recording)
        
        if form.is_valid():
            # Teachers can only upload for their assigned classes
            if user_profile.role == 'teacher':
                teacher_classes = UserProfile.objects.filter(user=user).values_list('class_level', flat=True)
                if form.cleaned_data['class_level'] not in teacher_classes:
                    messages.error(request, "You can only upload recordings for classes you teach.")
                    context = {'form': form, 'recording': recording}
                    return render(request, 'recordings/edit.html', context)
            
            form.save()
            messages.success(request, "Recording updated successfully.")
            return redirect('recording_detail', recording_id=recording.id)
    else:
        form = RecordedSessionForm(instance=recording)
    
    context = {
        'form': form,
        'recording': recording,
    }
    
    return render(request, 'recordings/edit.html', context)

@login_required
def delete_recording(request, recording_id):
    """Delete a recording"""
    user = request.user
    user_profile = get_object_or_404(UserProfile, user=user)
    
    # Get recording and check permissions
    recording = get_object_or_404(RecordedSession, id=recording_id)
    
    # Only the uploader or admin can delete
    if user_profile.role != 'admin' and recording.uploaded_by != user:
        messages.error(request, "You don't have permission to delete this recording.")
        return redirect('recording_detail', recording_id=recording.id)
    
    if request.method == 'POST':
        # If recording is stored in S3, delete from S3 too
        if recording.storage_type == 's3' and recording.s3_object_key:
            result = delete_file_from_s3(recording.s3_object_key)
            if not result['success']:
                logger.warning(f"Failed to delete S3 object: {result.get('error', 'Unknown error')}")
        
        # Delete the recording from the database
        recording.delete()
        
        messages.success(request, "Recording deleted successfully.")
        return redirect('recordings_list')
    
    context = {
        'recording': recording,
    }
    
    return render(request, 'recordings/delete.html', context)

@login_required
def import_zoom_recording(request):
    """Import recording from Zoom cloud"""
    user = request.user
    user_profile = get_object_or_404(UserProfile, user=user)
    
    # Only teachers and admins can import recordings
    if user_profile.role == 'student':
        messages.error(request, "Students cannot import recordings.")
        return redirect('recordings_list')
    
    # Check if Zoom is configured
    if not is_zoom_configured():
        messages.warning(request, "Zoom API is not configured. Please contact the administrator.")
        return redirect('recordings_list')
    
    # Get meeting ID from query parameter
    meeting_id = request.GET.get('meeting_id')
    recording_info = None
    
    # If meeting ID was provided, fetch recording info
    if meeting_id:
        try:
            recording_info = get_meeting_recordings(meeting_id)
            if not recording_info or 'recording_files' not in recording_info or not recording_info['recording_files']:
                recording_info = None
        except Exception as e:
            logger.exception(f"Error fetching Zoom recording: {str(e)}")
            messages.error(request, f"Error fetching recording: {str(e)}")
    
    # Handle form submission to save the recording
    if request.method == 'POST':
        meeting_id = request.POST.get('meeting_id')
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        subject_id = request.POST.get('subject')
        class_level = request.POST.get('class_level')
        
        # Validate required fields
        if not all([meeting_id, title, subject_id, class_level]):
            messages.error(request, "Please fill in all required fields.")
            return redirect('import_zoom_recording')
        
        # Teachers can only upload for their assigned classes
        if user_profile.role == 'teacher':
            teacher_classes = UserProfile.objects.filter(user=user).values_list('class_level', flat=True)
            if class_level not in teacher_classes:
                messages.error(request, "You can only import recordings for classes you teach.")
                return redirect('import_zoom_recording')
        
        # Save the recording
        success, message, recording = save_zoom_recording_to_db(
            meeting_id=meeting_id,
            uploaded_by=user,
            subject_id=subject_id,
            class_level=class_level,
            title=title,
            description=description
        )
        
        if success:
            messages.success(request, "Zoom recording imported successfully.")
            return redirect('recording_detail', recording_id=recording.id)
        else:
            messages.error(request, message)
    
    # Get subjects for dropdown
    if user_profile.role == 'teacher':
        class_levels = UserProfile.objects.filter(user=user).values_list('class_level', flat=True)
        subjects = Subject.objects.filter(
            class_assignments__class_level__in=class_levels
        ).distinct()
    else:
        subjects = Subject.objects.all()
    
    # Get class levels for dropdown
    if user_profile.role == 'teacher':
        class_levels = [(cl, dict(UserProfile.CLASS_CHOICES)[cl]) 
                      for cl in UserProfile.objects.filter(user=user).values_list('class_level', flat=True)]
    else:
        class_levels = UserProfile.CLASS_CHOICES
    
    context = {
        'meeting_id': meeting_id,
        'recording_info': recording_info,
        'subjects': subjects,
        'class_levels': class_levels,
    }
    
    return render(request, 'recordings/import_zoom.html', context)