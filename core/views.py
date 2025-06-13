import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.urls import reverse
import logging
from django.contrib.auth.views import LoginView
from .email_service import send_user_login_notification

# Initialize logger
logger = logging.getLogger(__name__)

class CustomLoginView(LoginView):
    """Custom login view that sends an email notification on successful login"""
    template_name = 'registration/login.html'
    
    def form_valid(self, form):
        """Called when valid form data has been POSTed"""
        # Call the parent class's form_valid() method
        response = super().form_valid(form)
        
        # Send login notification email
        try:
            send_user_login_notification(self.request.user, self.request)
            logger.info(f"Login notification sent to {self.request.user.email}")
        except Exception as e:
            logger.error(f"Error sending login notification: {str(e)}")
        
        return response

from .models import (
    UserProfile, Subject, ClassSubject, StudyMaterial, VideoConference,
    RecordedSession, Assignment, AssignmentSubmission,
    AITutorSession, AITutorMessage, UserSettings
)
from .forms import (
    UserRegisterForm, UserProfileForm, ClassSubjectForm, StudyMaterialForm,
    VideoConferenceForm, RecordedSessionForm, AssignmentForm, UserAccessForm,
    AssignmentSubmissionForm, GradeSubmissionForm, AITutorSessionForm,
    UserSettingsForm, SubjectForm
)
from .stripe_service import create_checkout_session, verify_checkout_session, handle_stripe_webhook
from .ai_service import get_ai_response, generate_practice_questions
from .zoom_oauth_service import create_meeting_server_to_server, get_server_to_server_token
from datetime import datetime, timedelta


def home(request):
    """Pre-login home page with platform introduction"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    subjects = Subject.objects.all()[:6]  # Get first 6 subjects for showcase
    return render(request, 'home.html', {
        'subjects': subjects,
    })


@login_required
@user_passes_test(lambda u: u.profile.role in ['admin', 'teacher'])
def server_to_server_meeting(request):
    """
    Create a Zoom meeting using Server-to-Server OAuth (Account Credentials flow)
    This doesn't require user OAuth authentication, using server credentials instead
    """
    # Check if user has permission to schedule meetings
    if request.user.profile.role not in ['admin', 'teacher']:
        messages.error(request, "Only teachers and administrators can schedule meetings.")
        return redirect('dashboard')
    
    # Verify server-to-server credentials are available
    token = get_server_to_server_token()
    if not token:
        context = {
            'error': "Zoom server-to-server API credentials are not properly configured. "
                    "Please ensure ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, and ZOOM_CLIENT_SECRET are set.",
        }
        return render(request, 'video/server_to_server_meeting.html', context)
    
    # Process form submission
    if request.method == 'POST':
        # Get form data
        topic = request.POST.get('topic')
        email = request.POST.get('email')  # Get email from form input
        start_date = request.POST.get('start_date')
        start_time = request.POST.get('start_time')
        duration = request.POST.get('duration', 60)
        description = request.POST.get('description', '')
        
        # Get subject and class level
        subject_id = request.POST.get('subject')
        class_level = request.POST.get('class_level')
        
        # Validate all required fields
        if not all([topic, email, start_date, start_time, subject_id, class_level]):
            # Get required context for form
            from .models import Subject, User, UserProfile
            subjects = Subject.objects.all()
            class_levels = UserProfile.CLASS_CHOICES
            users = User.objects.filter(is_active=True)
            
            context = {
                'subjects': subjects,
                'class_levels': class_levels,
                'users': users,
                'error': "Please fill in all required fields including subject and class level."
            }
            messages.error(request, "Please fill in all required fields including subject and class level.")
            return render(request, 'video/server_to_server_meeting.html', context)
        
        try:
            # Convert duration to integer
            duration = int(duration)
            
            # Parse the start date and time
            start_datetime_str = f"{start_date} {start_time}"
            start_datetime = datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M')
            
            # Create the meeting
            result = create_meeting_server_to_server(
                email=email,
                topic=topic,
                start_time=start_datetime,
                duration=duration,
                description=description
            )
            
            if result['success']:
                # Prepare success context
                context = {
                    'success': True,
                    'meeting_id': result.get('meeting_id'),
                    'join_url': result.get('join_url'),
                    'start_url': result.get('start_url'),
                    'password': result.get('password', ''),
                    'topic': topic,
                    'start_time': start_datetime.strftime('%Y-%m-%dT%H:%M:%S')
                }
                
                # Save the meeting in our database
                try:
                    # Get subject from form
                    subject_id = request.POST.get('subject')
                    subject = None
                    if subject_id:
                        try:
                            from .models import Subject
                            subject = Subject.objects.get(id=subject_id)
                        except Exception as subj_error:
                            logger.error(f"Error fetching subject: {str(subj_error)}")
                    
                    # Get class level from form
                    class_level = request.POST.get('class_level')
                    
                    meeting = VideoConference(
                        title=topic,
                        description=description,
                        scheduled_by=request.user,
                        platform='zoom',
                        start_time=start_datetime,
                        end_time=start_datetime + timedelta(minutes=duration),
                        meeting_id=str(result.get('meeting_id')),
                        meeting_password=result.get('password', ''),
                        meeting_link=result.get('join_url'),
                        is_recurring=False,
                        enable_sdk=False,
                        subject=subject,
                        class_level=class_level,
                    )
                    meeting.save()
                    
                    # Add selected participants if any
                    selected_participants = request.POST.getlist('selected_participants')
                    if selected_participants:
                        from .models import VideoConferenceParticipant, User
                        for user_id in selected_participants:
                            try:
                                user = User.objects.get(id=user_id)
                                participant = VideoConferenceParticipant(
                                    conference=meeting,
                                    participant=user,
                                    is_host=False,
                                    has_joined=False
                                )
                                participant.save()
                            except Exception as part_error:
                                logger.error(f"Error adding participant {user_id}: {str(part_error)}")
                    
                    messages.success(request, "Zoom meeting created successfully and saved to the database.")
                    # Redirect to the meeting detail page instead of rendering the creation form again
                    return redirect('video_conference_detail', pk=meeting.id)
                except Exception as e:
                    logger.error(f"Error saving meeting to database: {str(e)}")
                    # We still consider this a success since the Zoom meeting was created
                    messages.warning(request, f"Zoom meeting created, but there was an error saving to database: {str(e)}")
                    return render(request, 'video/server_to_server_meeting.html', context)
            else:
                # Handle error
                error_message = result.get('error', 'Unknown error creating Zoom meeting')
                context = {'error': error_message}
                return render(request, 'video/server_to_server_meeting.html', context)
        
        except Exception as e:
            logger.exception(f"Error creating Zoom meeting: {str(e)}")
            context = {'error': f"Error creating Zoom meeting: {str(e)}"}
            return render(request, 'video/server_to_server_meeting.html', context)
    
    # GET request - just show the form
    # Get subjects for the dropdown
    from .models import Subject, User
    subjects = Subject.objects.all()
    
    # Get class levels for the dropdown
    from .models import UserProfile
    class_levels = UserProfile.CLASS_CHOICES
    
    # Get users for participant selection
    users = User.objects.filter(is_active=True)
    
    context = {
        'subjects': subjects,
        'class_levels': class_levels,
        'users': users
    }
    
    return render(request, 'video/server_to_server_meeting.html', context)


def register(request):
    """User registration with role selection and profile creation"""
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        
        # For debugging - log the form errors if not valid
        if not form.is_valid():
            logger.warning(f"Registration form errors: {form.errors}")
            for field, errors in form.errors.items():
                logger.warning(f"Field {field} errors: {errors}")
            return render(request, 'registration/register.html', {'form': form})
            
        # If form is valid, proceed with user creation
        try:
            # Save the user
            user = form.save()
            
            # Get profile data from form
            role = form.cleaned_data.get('role')
            class_level = form.cleaned_data.get('class_level')
            bio = form.cleaned_data.get('bio', '')
            phone_number = form.cleaned_data.get('phone_number', '')
            profile_picture = form.cleaned_data.get('profile_picture', '')
            
            # Create the UserProfile
            profile = UserProfile.objects.create(
                user=user,
                role=role,
                class_level=class_level,
                bio=bio,
                phone_number=phone_number,
                profile_picture=profile_picture
            )
            
            # Create UserSettings
            UserSettings.objects.create(
                user=user,
                default_class_level=class_level
            )
            
            # Send welcome email notification
            from .email_service import send_user_signup_notification
            try:
                email_sent = send_user_signup_notification(user, profile)
                if email_sent:
                    logger.info(f"Welcome email sent to {user.email}")
                    messages.success(request, f"Welcome email sent to {user.email}. Please check your inbox.")
                else:
                    logger.warning(f"Failed to send welcome email to {user.email}")
                    messages.warning(request, "We couldn't send your welcome email. Please check your email settings.")
            except Exception as e:
                logger.error(f"Error sending welcome email: {str(e)}")
                messages.warning(request, "There was a problem sending your welcome email.")
            
            # Temporarily disable payment requirement - set all accounts as exempt
            profile.payment_status = 'exempt'
            profile.save()
            
            # Log the user in
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            
            messages.success(request, f"Account created for {username}! You are now logged in.")
            return redirect('dashboard')
        
        except Exception as e:
            # Log the error for debugging
            logger.error(f"Error during user registration: {str(e)}")
            messages.error(request, f"Registration error: {str(e)}")
            return render(request, 'registration/register.html', {'form': form})
    else:
        form = UserRegisterForm()
    
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    """Role-based dashboard for users"""
    user = request.user
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Add debug message about the user's role
    messages.info(request, f"Debug: Your role is '{profile.role}' and your class level is '{profile.class_level}'")
    
    if created:
        messages.info(request, "We've created a default profile for you. Please update your information.")
        return redirect('profile_edit')
    
    # Common data for all roles
    upcoming_assignments = []
    recent_materials = []
    
    if profile.role == 'student':
        # Student-specific dashboard data
        class_level = profile.class_level
        upcoming_assignments = Assignment.objects.filter(
            class_level=class_level,
            due_date__gt=timezone.now()
        ).order_by('due_date')[:5]
        
        recent_materials = StudyMaterial.objects.filter(
            class_level=class_level
        ).order_by('-upload_date')[:5]
        
        # Get student's submitted assignments
        submitted_assignments = AssignmentSubmission.objects.filter(
            student=user
        ).select_related('assignment').order_by('-submitted_at')[:5]
        
        # Get upcoming classes
        upcoming_classes = VideoConference.objects.filter(
            class_level=class_level,
            start_time__gt=timezone.now()
        ).order_by('start_time')[:3]
        
        return render(request, 'dashboard.html', {
            'profile': profile,
            'upcoming_assignments': upcoming_assignments,
            'recent_materials': recent_materials,
            'submitted_assignments': submitted_assignments,
            'upcoming_classes': upcoming_classes,
        })
        
    elif profile.role == 'teacher':
        # Teacher-specific dashboard data
        created_assignments = Assignment.objects.filter(
            created_by=user
        ).order_by('-created_at')[:5]
        
        uploaded_materials = StudyMaterial.objects.filter(
            uploaded_by=user
        ).order_by('-upload_date')[:5]
        
        # Get pending submissions to grade
        pending_submissions = AssignmentSubmission.objects.filter(
            assignment__created_by=user,
            is_graded=False
        ).select_related('assignment', 'student').order_by('submitted_at')[:10]
        
        # Get upcoming classes scheduled by the teacher
        upcoming_classes = VideoConference.objects.filter(
            scheduled_by=user,
            start_time__gt=timezone.now()
        ).order_by('start_time')[:3]
        
        return render(request, 'dashboard.html', {
            'profile': profile,
            'created_assignments': created_assignments,
            'uploaded_materials': uploaded_materials,
            'pending_submissions': pending_submissions,
            'upcoming_classes': upcoming_classes,
        })
        
    elif profile.role == 'admin':
        # Admin-specific dashboard data
        recent_users = UserProfile.objects.all().order_by('-date_joined')[:10]
        recent_materials = StudyMaterial.objects.all().order_by('-upload_date')[:10]
        
        # Get recent video conferences
        recent_conferences = VideoConference.objects.all().order_by('-start_time')[:10]
        
        return render(request, 'dashboard.html', {
            'profile': profile,
            'recent_users': recent_users,
            'recent_materials': recent_materials,
            'recent_conferences': recent_conferences,
            'is_admin_dashboard': True,
        })
    
    return render(request, 'dashboard.html', {
        'profile': profile,
        'upcoming_assignments': upcoming_assignments,
        'recent_materials': recent_materials,
    })


@login_required
def profile_view(request, username):
    """View user profile"""
    try:
        user = User.objects.get(username=username)
        user_profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': 'student',
                'class_level': '1',
            }
        )
    except User.DoesNotExist:
        messages.error(request, f"User {username} does not exist.")
        return redirect('dashboard')
    return render(request, 'profile/view.html', {'profile': user_profile})


@login_required
def profile_edit(request):
    """Edit user profile"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('profile_view', username=request.user.username)
    else:
        form = UserProfileForm(instance=profile, user=request.user)
    
    return render(request, 'profile/edit.html', {'form': form, 'profile': profile})


@login_required
def materials_list(request):
    """List and search study materials with class-level filtering"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    query = request.GET.get('q', '')
    subject_id = request.GET.get('subject', '')
    class_level = request.GET.get('class_level', '')
    file_type = request.GET.get('file_type', '')
    
    # Apply class-level filtering for students
    if profile.role == 'student':
        # Students can only see materials for their class level
        materials = StudyMaterial.objects.filter(
            class_level=profile.class_level
        ).order_by('-upload_date')
    else:
        # Teachers and admins can see all materials, or filter by class
        materials = StudyMaterial.objects.all().order_by('-upload_date')
        
        # For teachers, show materials they uploaded and materials for their class level
        if profile.role == 'teacher':
            materials = materials.filter(
                Q(uploaded_by=request.user) | Q(class_level=profile.class_level)
            ).distinct()
    
    # Apply search and other filters
    if query:
        materials = materials.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    
    if subject_id:
        materials = materials.filter(subject_id=subject_id)
    
    # Only apply class_level filter for non-students (students are already filtered by their class)
    if class_level and profile.role != 'student':
        materials = materials.filter(class_level=class_level)
    
    if file_type:
        materials = materials.filter(file_type=file_type)
    
    # Get available subjects and class levels for filter dropdowns
    subjects = Subject.objects.all()
    class_levels = UserProfile.CLASS_CHOICES
    file_types = StudyMaterial.FILE_TYPE_CHOICES
    
    # Pagination
    paginator = Paginator(materials, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'materials/list.html', {
        'page_obj': page_obj,
        'subjects': subjects,
        'class_levels': class_levels,
        'file_types': file_types,
        'query': query,
        'selected_subject': subject_id,
        'selected_class_level': class_level if profile.role != 'student' else profile.class_level,
        'selected_file_type': file_type,
        'profile': profile,  # Pass profile to the template
    })


@login_required
def material_detail(request, pk):
    """View details of a specific study material with class-level access control"""
    material = get_object_or_404(StudyMaterial, pk=pk)
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Check if student has access to this material
    if profile.role == 'student' and profile.class_level != material.class_level:
        messages.error(request, "You don't have access to this material. It's for a different class level.")
        return redirect('materials_list')
    
    # Increment view count
    material.views += 1
    material.save()
    
    return render(request, 'materials/detail.html', {'material': material, 'profile': profile})


@login_required
def material_download(request, pk):
    """Track download of a study material with class-level access control"""
    material = get_object_or_404(StudyMaterial, pk=pk)
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Check if student has access to this material
    if profile.role == 'student' and profile.class_level != material.class_level:
        messages.error(request, "You don't have access to this material. It's for a different class level.")
        return redirect('materials_list')
    
    # Increment download count
    material.downloads += 1
    material.save()
    
    # If material has a file stored in the database, serve it
    if material.file and hasattr(material.file, 'url'):
        # Use the file's URL to redirect (Django handles file serving)
        return redirect(material.file.url)
        # Alternatively, if you need more control over download:
        # response = HttpResponse(content_type='application/octet-stream')
        # response['Content-Disposition'] = f'attachment; filename="{material.file.name.split("/")[-1]}"'
        # response['X-Accel-Redirect'] = material.file.url
        # return response
    # Otherwise redirect to the file URL (for backward compatibility)
    elif material.file_url:
        return redirect(material.file_url)
    else:
        messages.error(request, "No file available for download.")
        return redirect('material_detail', pk=material.pk)


@login_required
def material_upload(request):
    """Upload new study material - restricted to admin and teachers"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Check if user is admin or teacher
    if profile.role == 'student':
        messages.error(request, "Study material upload is restricted to teachers and administrators only.")
        return redirect('materials_list')
    
    if request.method == 'POST':
        # Pass both POST data and FILES to the form
        form = StudyMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.uploaded_by = request.user
            
            # For teachers, restrict uploads to their class level
            if profile.role == 'teacher' and material.class_level != profile.class_level:
                messages.error(request, "Teachers can only upload materials for their assigned class level.")
                return render(request, 'materials/upload.html', {'form': form, 'profile': profile})
            
            # Calculate file size if uploading a file
            if 'file' in request.FILES:
                uploaded_file = request.FILES['file']
                material.file_size = uploaded_file.size
                
            material.save()
            messages.success(request, "Study material uploaded successfully!")
            return redirect('material_detail', pk=material.pk)
    else:
        form = StudyMaterialForm()
        
        # Pre-select the teacher's class level
        if profile.role == 'teacher':
            form.fields['class_level'].initial = profile.class_level
    
    return render(request, 'materials/upload.html', {'form': form, 'profile': profile})


@login_required
def video_conferences_list(request):
    """List upcoming and past video conferences"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Filter conferences by class level for students
    now = timezone.now()
    
    if profile.role == 'student':
        upcoming_conferences = VideoConference.objects.filter(
            class_level=profile.class_level,
            start_time__gt=now
        ).order_by('start_time')
        
        past_conferences = VideoConference.objects.filter(
            class_level=profile.class_level,
            end_time__lt=now
        ).order_by('-start_time')
    else:
        # Teachers and admins can see all conferences
        upcoming_conferences = VideoConference.objects.filter(
            start_time__gt=now
        ).order_by('start_time')
        
        # For teachers, also show conferences they scheduled
        if profile.role == 'teacher':
            upcoming_conferences = upcoming_conferences.filter(
                Q(scheduled_by=request.user) | Q(class_level__in=['all', profile.class_level])
            ).distinct()
        
        past_conferences = VideoConference.objects.filter(
            end_time__lt=now
        ).order_by('-start_time')
        
        if profile.role == 'teacher':
            past_conferences = past_conferences.filter(scheduled_by=request.user)
    
    # Pagination
    upcoming_paginator = Paginator(upcoming_conferences, 5)
    upcoming_page = request.GET.get('upcoming_page')
    upcoming_page_obj = upcoming_paginator.get_page(upcoming_page)
    
    past_paginator = Paginator(past_conferences, 5)
    past_page = request.GET.get('past_page')
    past_page_obj = past_paginator.get_page(past_page)
    
    return render(request, 'video/list.html', {
        'upcoming_page_obj': upcoming_page_obj,
        'past_page_obj': past_page_obj,
        'profile': profile,
    })


@login_required
def video_conference_detail(request, pk):
    """View for displaying video conference details"""
    try:
        conference = get_object_or_404(VideoConference, pk=pk)
        # Get or create user profile to avoid 404 errors
        profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={
                'role': 'student',
                'class_level': '1',
            }
        )
        
        # Get participants if any
        from .models import VideoConferenceParticipant
        participants = VideoConferenceParticipant.objects.filter(conference=conference)
        
        context = {
            'conference': conference,
            'profile': profile,
            'participants': participants,
            'is_host': request.user == conference.scheduled_by or profile.role == 'admin',
        }
        
        return render(request, 'video/detail.html', context)
    except Exception as e:
        messages.error(request, f"Error accessing meeting details: {str(e)}")
        return redirect('video_conferences_list')


@login_required
def video_conference_create(request):
    """Create a new video conference with Zoom integration and email notifications"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Check if user is teacher or admin
    if profile.role not in ['teacher', 'admin']:
        messages.error(request, "You don't have permission to schedule conferences.")
        return redirect('video_conferences_list')
    
    if request.method == 'POST':
        form = VideoConferenceForm(request.POST)
        if form.is_valid():
            conference = form.save(commit=False)
            conference.scheduled_by = request.user
            conference.status = 'scheduled'
            conference.save()
            
            # Get selected participants if any
            selected_participants = form.cleaned_data.get('selected_participants', [])
            
            # Initialize potential participant list for notification
            participants_to_notify = []
            
            # Create Zoom meeting if platform is Zoom
            if conference.platform == 'zoom':
                # Check if SDK checkbox was selected
                use_sdk = request.POST.get('use_zoom_sdk') == 'on'
                conference.enable_sdk = use_sdk
                
                # Check if OAuth checkbox was selected
                use_oauth = request.POST.get('use_zoom_oauth') == 'on'
                conference.used_oauth = use_oauth
                conference.save(update_fields=['enable_sdk', 'used_oauth'])
                
                # Create the Zoom meeting based on OAuth preference
                if use_oauth:
                    # For OAuth, use the specific OAuth method
                    zoom_result = conference.create_zoom_meeting_oauth()
                else:
                    # For regular JWT, use the standard method
                    zoom_result = conference.create_zoom_meeting()
                
                if zoom_result:
                    sdk_message = "with SDK for in-browser meetings" if conference.enable_sdk else "with standard Zoom client"
                    oauth_message = " using your connected Zoom account" if use_oauth else ""
                    messages.success(request, f"Video conference scheduled successfully with Zoom integration{oauth_message} {sdk_message}!")
                    
                    # Send email notifications based on selection
                    try:
                        # Import here to avoid circular imports
                        from core.email_service import send_meeting_invitation
                        from core.models import VideoConferenceParticipant
                        
                        # Determine recipients based on whether specific participants were selected
                        if selected_participants:
                            # Add selected participants to the conference
                            for user in selected_participants:
                                # Determine participant type based on user's role
                                try:
                                    user_role = user.userprofile.role
                                    participant_type = 'teacher' if user_role == 'teacher' else 'student'
                                except:
                                    participant_type = 'student'  # Default
                                
                                # Create the participant relationship
                                VideoConferenceParticipant.objects.create(
                                    conference=conference,
                                    user=user,
                                    participant_type=participant_type
                                )
                            
                            # Send emails to selected participants
                            email_result = send_meeting_invitation(conference, selected_participants, is_targeted=True)
                            if email_result:
                                messages.success(request, f"Email invitations sent to {len(selected_participants)} participants.")
                            else:
                                messages.warning(request, "Conference scheduled, but there was an issue sending email invitations.")
                                
                        else:
                            # Get all students in this class level
                            class_level = conference.class_level
                            students = User.objects.filter(
                                userprofile__role='student',
                                userprofile__class_level=class_level
                            )
                            
                            # Add them as participants
                            for student in students:
                                VideoConferenceParticipant.objects.create(
                                    conference=conference,
                                    user=student,
                                    participant_type='student'
                                )
                            
                            # Send email to all students in class level
                            if students.exists():
                                email_result = send_meeting_invitation(conference, students)
                                if email_result:
                                    messages.success(request, f"Email invitations sent to {students.count()} students in {conference.get_class_level_display()}.")
                                else:
                                    messages.warning(request, "Conference scheduled, but there was an issue sending email invitations.")
                    except Exception as e:
                        messages.warning(request, f"Conference scheduled, but there was an issue managing participants: {str(e)}")
                else:
                    messages.warning(request, "Conference scheduled, but there was an issue with Zoom integration. You may need to set up the meeting manually.")
            else:
                messages.success(request, "Video conference scheduled successfully!")
                
            return redirect('video_conferences_list')
    else:
        form = VideoConferenceForm(initial={'platform': 'zoom'})  # Default to Zoom
    
    # Pass additional context for UI
    context = {
        'form': form, 
        'profile': profile,
        'is_zoom_available': bool(os.environ.get('ZOOM_API_KEY') and os.environ.get('ZOOM_API_SECRET')),
        'is_email_available': bool(os.environ.get('SENDGRID_API_KEY')),
    }
    
    return render(request, 'video/create.html', context)


@login_required
def video_conference_edit(request, pk):
    """Edit an existing video conference"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Check if user is teacher or admin
    if profile.role not in ['teacher', 'admin']:
        messages.error(request, "You don't have permission to edit conferences.")
        return redirect('video_conferences_list')
    
    # Get the conference or return 404
    conference = get_object_or_404(VideoConference, pk=pk)
    
    # Check if user is allowed to edit this conference
    if request.user != conference.scheduled_by and profile.role != 'admin':
        messages.error(request, "You can only edit conferences that you scheduled.")
        return redirect('video_conferences_list')
    
    if request.method == 'POST':
        form = VideoConferenceForm(request.POST, instance=conference)
        
        # Handle participant selection
        selected_participants = None
        if 'selected_participants' in request.POST:
            selected_participants = request.POST.getlist('selected_participants')
        
        if form.is_valid():
            updated_conference = form.save(commit=False)
            
            # Don't change the scheduled_by user
            updated_conference.scheduled_by = conference.scheduled_by
            
            # Save the conference
            # Track what fields were changed to include in the notification
            changed_fields = []
            for field in ['title', 'description', 'subject', 'class_level', 'start_time', 'end_time']:
                if getattr(conference, field) != getattr(updated_conference, field):
                    if field == 'start_time' or field == 'end_time':
                        old_value = getattr(conference, field).strftime("%B %d, %Y at %I:%M %p")
                        new_value = getattr(updated_conference, field).strftime("%B %d, %Y at %I:%M %p")
                        changed_fields.append(f"{field.replace('_', ' ').title()} changed from {old_value} to {new_value}")
                    elif field == 'subject':
                        old_subject = conference.subject.name if conference.subject else "None"
                        new_subject = updated_conference.subject.name if updated_conference.subject else "None"
                        changed_fields.append(f"Subject changed from {old_subject} to {new_subject}")
                    elif field == 'class_level':
                        old_level = conference.get_class_level_display()
                        new_level = updated_conference.get_class_level_display()
                        changed_fields.append(f"Class Level changed from {old_level} to {new_level}")
                    else:
                        changed_fields.append(f"{field.replace('_', ' ').title()} was updated")
            
            # Now save the updated conference
            updated_conference.save()
            
            messages.success(request, f"Conference '{updated_conference.title}' has been updated.")
            
            # Get all existing participants to notify them of the change
            from .models import VideoConferenceParticipant
            existing_participants = VideoConferenceParticipant.objects.filter(
                conference=updated_conference
            ).select_related('user')
            existing_users = [p.user for p in existing_participants if p.user.is_active and p.user.email]
            
            # Add new participants if selected
            if selected_participants:
                try:
                    selected_users = User.objects.filter(id__in=selected_participants)
                    if selected_users.exists():
                        # Import email services here to avoid circular imports
                        from core.email_service import send_meeting_invitation, send_meeting_update_notification
                        
                        # Get new users not already in the participants list
                        new_users = [user for user in selected_users if user not in existing_users]
                        
                        # If there are new users, send them an invitation
                        if new_users:
                            # Send targeted invitations to new participants
                            email_result = send_meeting_invitation(updated_conference, new_users, is_targeted=True)
                            if email_result:
                                messages.success(request, f"Email invitations sent to {len(new_users)} new participants.")
                            
                            # Add new users to existing users list for update notification
                            existing_users.extend(new_users)
                        
                        # Send update notification to all participants
                        if existing_users:
                            update_result = send_meeting_update_notification(
                                meeting=updated_conference,
                                recipients=existing_users,
                                update_type='Meeting Updated',
                                changes=changed_fields
                            )
                            
                            if update_result:
                                messages.success(request, f"Meeting update notification sent to {len(existing_users)} participants.")
                            else:
                                messages.warning(request, "Conference updated, but there was an issue sending update notifications.")
                except Exception as e:
                    messages.warning(request, f"Conference updated, but email notifications failed: {str(e)}")
            else:
                # If no specific participants selected, still notify existing participants of the changes
                try:
                    if existing_users:
                        # Import email service here to avoid circular imports
                        from core.email_service import send_meeting_update_notification
                        
                        # Send update notification to all existing participants
                        update_result = send_meeting_update_notification(
                            meeting=updated_conference,
                            recipients=existing_users,
                            update_type='Meeting Updated',
                            changes=changed_fields
                        )
                        
                        if update_result:
                            messages.success(request, f"Meeting update notification sent to {len(existing_users)} participants.")
                except Exception as e:
                    messages.warning(request, f"Conference updated, but email notifications failed: {str(e)}")
            
            return redirect('video_conferences_list')
    else:
        # For GET requests, create a form with the existing conference data
        form = VideoConferenceForm(instance=conference)
        
        # If there are specific fields that need special handling
        if conference.platform == 'zoom' and conference.used_oauth:
            form.fields['use_zoom_oauth'].initial = True
    
    # Get appropriate form context based on user's role
    context = {
        'form': form,
        'title': 'Edit Video Conference',
        'has_zoom_oauth_token': has_zoom_oauth_token(request.user),
        'edit_mode': True,
        'conference': conference
    }
    
    return render(request, 'video/create.html', context)

def video_conference_join(request, pk):
    """Join a video conference with class-level access control"""
    conference = get_object_or_404(VideoConference, pk=pk)
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Check if student has access to this conference
    if profile.role == 'student' and profile.class_level != conference.class_level:
        messages.error(request, "You don't have access to this conference. It's for a different class level.")
        return redirect('video_conferences_list')
    
    # Update conference status based on current time
    conference.update_status()
    
    # Check if the conference is active
    now = timezone.now()
    if conference.start_time > now:
        messages.error(request, "This conference hasn't started yet.")
        return redirect('video_conferences_list')
    
    if conference.end_time < now:
        messages.error(request, "This conference has already ended.")
        return redirect('video_conferences_list')
    
    # For Zoom meetings, redirect to the Zoom URL or show Zoom join details
    if conference.platform == 'zoom' and conference.meeting_link:
        # Generate meeting signature for SDK integration
        meeting_signature = None
        if conference.meeting_id:
            from core.zoom_service import generate_meeting_signature
            # Role: 1 for host, 0 for attendee
            role = 1 if request.user == conference.scheduled_by else 0
            meeting_signature = generate_meeting_signature(conference.meeting_id, role)
        
        # Prepare context with host status and signature for SDK
        context = {
            'conference': conference,
            'profile': profile,
            'is_host': request.user == conference.scheduled_by,
            'meeting_signature': meeting_signature,
        }
        return render(request, 'video/join_zoom.html', context)
    
    # For all platforms, including Zoom
    context = {
        'conference': conference,
        'profile': profile,
        'is_host': request.user == conference.scheduled_by or profile.role == 'admin',
    }
    return render(request, 'video/join.html', context)


@login_required
def video_conference_join_sdk(request, pk):
    """Join a Zoom conference using the web SDK interface"""
    conference = get_object_or_404(VideoConference, pk=pk)
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Check if student has access to this conference
    if profile.role == 'student' and profile.class_level != conference.class_level:
        messages.error(request, "You don't have access to this conference. It's for a different class level.")
        return redirect('video_conferences_list')
    
    # Check if this is a Zoom conference
    if conference.platform != 'zoom' or not conference.meeting_id:
        messages.error(request, "This feature is only available for Zoom meetings with a valid meeting ID.")
        return redirect('video_conference_join', pk=pk)
    
    # Update conference status based on current time
    conference.update_status()
    
    # Check if the conference is active
    now = timezone.now()
    if conference.start_time > now:
        messages.error(request, "This conference hasn't started yet.")
        return redirect('video_conferences_list')
    
    if conference.end_time < now:
        messages.error(request, "This conference has already ended.")
        return redirect('video_conferences_list')
        
    # Generate meeting signature for SDK integration
    from core.zoom_service import generate_meeting_signature
    # Role: 1 for host, 0 for attendee
    role = 1 if request.user == conference.scheduled_by or profile.role in ['admin', 'teacher'] else 0
    meeting_signature = generate_meeting_signature(conference.meeting_id, role)
    
    # Get Zoom API key
    zoom_api_key = os.environ.get('ZOOM_API_KEY', '')
    
    # Prepare context with host status and signature for SDK
    context = {
        'conference': conference,
        'profile': profile,
        'is_host': request.user == conference.scheduled_by or profile.role == 'admin',
        'meeting_signature': meeting_signature,
        'zoom_api_key': zoom_api_key,
    }
    
    return render(request, 'video/zoom_sdk.html', context)


@login_required
def get_zoom_signature(request, meeting_id):
    """API endpoint to get Zoom meeting signature for the SDK"""
    if not meeting_id:
        return JsonResponse({'success': False, 'error': 'Meeting ID is required'})
    
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    try:
        # Find the conference with this meeting ID
        conference = VideoConference.objects.get(meeting_id=meeting_id)
        
        # Check if student has access to this conference
        if profile.role == 'student' and profile.class_level != conference.class_level:
            return JsonResponse({
                'success': False, 
                'error': "You don't have access to this conference."
            })
        
        # Generate meeting signature for SDK integration
        from core.zoom_service import generate_meeting_signature
        # Role: 1 for host, 0 for attendee
        role = 1 if request.user == conference.scheduled_by or profile.role in ['admin', 'teacher'] else 0
        meeting_signature = generate_meeting_signature(meeting_id, role)
        
        return JsonResponse({
            'success': True,
            'signature': meeting_signature,
            'role': role,
            'username': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
            'api_key': os.environ.get('ZOOM_API_KEY', '')
        })
    except VideoConference.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Meeting not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def toggle_auto_record(request, pk):
    """Toggle auto-recording setting for a meeting"""
    # Check if user is allowed to process recordings (admin or teacher)
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role not in ['admin', 'teacher']:
        return JsonResponse({
            'success': False,
            'error': "You don't have permission to change meeting settings."
        })
    
    # Get the conference
    conference = get_object_or_404(VideoConference, id=pk)
    
    # Check if the user is authorized to modify this meeting
    if request.user != conference.scheduled_by and profile.role != 'admin':
        return JsonResponse({
            'success': False,
            'error': "You don't have permission to modify this meeting."
        })
    
    # Parse JSON data from request
    import json
    try:
        data = json.loads(request.body)
        enabled = data.get('enabled', False)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': "Invalid request format."
        })
    
    # Update the auto_record setting
    conference.auto_record = enabled
    conference.save(update_fields=['auto_record'])
    
    # If enabled, also set the recording status to 'waiting'
    if enabled and conference.recording_status == 'none':
        conference.recording_status = 'waiting'
        conference.save(update_fields=['recording_status'])
        
        # Setup auto-recording for the meeting if it's already scheduled
        if conference.status == 'scheduled' and conference.meeting_id:
            from core.zoom_service import setup_auto_recording_for_meeting
            setup_auto_recording_for_meeting(conference.meeting_id, save_to_s3=True, conference_obj=conference)
    
    return JsonResponse({
        'success': True,
        'message': f"Auto-recording {'enabled' if enabled else 'disabled'}."
    })


@login_required
def process_meeting_recordings(request, meeting_id):
    """Process and save recordings from a completed Zoom meeting to S3"""
    # Check if user is allowed to process recordings (admin or teacher)
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role not in ['admin', 'teacher']:
        messages.error(request, "You don't have permission to process recordings.")
        return redirect('video_conferences_list')
    
    # Get the conference
    conference = get_object_or_404(VideoConference, meeting_id=meeting_id)
    
    # Check if the user is authorized to process this meeting's recordings
    if request.user != conference.scheduled_by and profile.role != 'admin':
        messages.error(request, "You don't have permission to process recordings for this meeting.")
        return redirect('video_conferences_list')
    
    # Set the recording status to processing
    conference.recording_status = 'processing'
    conference.save()
    
    # Process the recordings
    from core.zoom_service import download_recording_to_s3
    
    result = download_recording_to_s3(meeting_id, conference_obj=conference)
    
    if result.get('success'):
        messages.success(request, "Meeting recordings processed successfully.")
        
        # Get the recording URL from result
        recording_url = result.get('recording_url')
        
        # Get participants to notify about the recording availability
        if recording_url:
            try:
                # Get all participants of this conference
                from .models import VideoConferenceParticipant
                participants = VideoConferenceParticipant.objects.filter(
                    conference=conference
                ).select_related('user')
                
                # Create list of users to notify about recording availability
                recipients = [p.user for p in participants if p.user.is_active and p.user.email]
                
                # Send recording availability notifications if there are recipients
                if recipients:
                    from core.email_service import send_meeting_update_notification
                    
                    notification_result = send_meeting_update_notification(
                        meeting=conference,
                        recipients=recipients,
                        update_type='Recording Available',
                        recording_url=recording_url
                    )
                    
                    if notification_result:
                        messages.success(request, f"Recording availability notification sent to {len(recipients)} participants.")
                    else:
                        messages.warning(request, "Recording processed, but there was an issue sending notifications.")
            except Exception as e:
                logger.error(f"Error sending recording availability notifications: {str(e)}")
                messages.warning(request, f"Recording processed, but could not send notifications: {str(e)}")
    else:
        messages.error(request, f"Error processing recordings: {result.get('error', 'Unknown error')}")
    
    return redirect('video_conference_detail', pk=conference.id)


@login_required
def recordings_list(request):
    """List recorded sessions"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    query = request.GET.get('q', '')
    subject_id = request.GET.get('subject', '')
    
    # Filter recordings by class level for students
    if profile.role == 'student':
        recordings = RecordedSession.objects.filter(
            class_level=profile.class_level
        ).order_by('-recorded_date')
    else:
        # Teachers and admins can see all recordings
        recordings = RecordedSession.objects.all().order_by('-recorded_date')
        
        # For teachers, show only recordings they uploaded
        if profile.role == 'teacher':
            recordings = recordings.filter(uploaded_by=request.user)
    
    # Apply search filters
    if query:
        recordings = recordings.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    
    if subject_id:
        recordings = recordings.filter(subject_id=subject_id)
    
    # Get subjects for filter dropdown
    subjects = Subject.objects.all()
    
    # Pagination
    paginator = Paginator(recordings, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'recordings/list.html', {
        'page_obj': page_obj,
        'subjects': subjects,
        'query': query,
        'selected_subject': subject_id,
    })


@login_required
def recording_detail(request, pk):
    """View a recorded session with class-level access control"""
    recording = get_object_or_404(RecordedSession, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Check if student has access to this recording
    if profile.role == 'student' and profile.class_level != recording.class_level:
        messages.error(request, "You don't have access to this recording. It's for a different class level.")
        return redirect('recordings_list')
    
    # Only teachers who uploaded the recording or admins can access if not their class level
    if profile.role == 'teacher' and recording.uploaded_by != request.user and profile.class_level != recording.class_level:
        messages.error(request, "You don't have access to this recording. It's for a different class level.")
        return redirect('recordings_list')
    
    # Increment view count
    recording.views += 1
    recording.save()
    
    return render(request, 'recordings/detail.html', {'recording': recording, 'profile': profile})


@login_required
def recording_upload(request):
    """Upload a recorded session"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Check if user is teacher or admin
    if profile.role not in ['teacher', 'admin']:
        messages.error(request, "You don't have permission to upload recordings.")
        return redirect('recordings_list')
    
    if request.method == 'POST':
        form = RecordedSessionForm(request.POST)
        if form.is_valid():
            recording = form.save(commit=False)
            recording.uploaded_by = request.user
            recording.save()
            messages.success(request, "Recording uploaded successfully!")
            return redirect('recording_detail', pk=recording.pk)
    else:
        form = RecordedSessionForm()
    
    return render(request, 'recordings/upload.html', {'form': form})


@login_required
def assignments_list(request):
    """List assignments"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Determine which assignments to show based on user role
    if profile.role == 'student':
        # Students see assignments for their class level
        active_assignments = Assignment.objects.filter(
            class_level=profile.class_level,
            due_date__gt=timezone.now()
        ).order_by('due_date')
        
        past_assignments = Assignment.objects.filter(
            class_level=profile.class_level,
            due_date__lte=timezone.now()
        ).order_by('-due_date')
        
        # Get student's submissions
        submissions = AssignmentSubmission.objects.filter(
            student=request.user
        ).values_list('assignment_id', flat=True)
        
    elif profile.role == 'teacher':
        # Teachers see assignments they created
        active_assignments = Assignment.objects.filter(
            created_by=request.user,
            due_date__gt=timezone.now()
        ).order_by('due_date')
        
        past_assignments = Assignment.objects.filter(
            created_by=request.user,
            due_date__lte=timezone.now()
        ).order_by('-due_date')
        
        # No submissions lookup needed for teachers
        submissions = []
        
    else:  # admin
        # Admins see all assignments
        active_assignments = Assignment.objects.filter(
            due_date__gt=timezone.now()
        ).order_by('due_date')
        
        past_assignments = Assignment.objects.filter(
            due_date__lte=timezone.now()
        ).order_by('-due_date')
        
        # No submissions lookup needed for admins
        submissions = []
    
    # Pagination
    active_paginator = Paginator(active_assignments, 5)
    active_page = request.GET.get('active_page')
    active_page_obj = active_paginator.get_page(active_page)
    
    past_paginator = Paginator(past_assignments, 5)
    past_page = request.GET.get('past_page')
    past_page_obj = past_paginator.get_page(past_page)
    
    return render(request, 'assignments/list.html', {
        'active_page_obj': active_page_obj,
        'past_page_obj': past_page_obj,
        'profile': profile,
        'submissions': submissions,
    })


@login_required
def assignment_detail(request, pk):
    """View assignment details"""
    assignment = get_object_or_404(Assignment, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Students can only view assignments for their class level
    if profile.role == 'student' and assignment.class_level != profile.class_level:
        messages.error(request, "You don't have access to this assignment.")
        return redirect('assignments_list')
    
    # Check if student has already submitted
    submission = None
    if profile.role == 'student':
        try:
            submission = AssignmentSubmission.objects.get(
                assignment=assignment,
                student=request.user
            )
        except AssignmentSubmission.DoesNotExist:
            submission = None
    
    # For teachers, get all submissions to this assignment
    submissions = []
    if profile.role in ['teacher', 'admin']:
        submissions = AssignmentSubmission.objects.filter(
            assignment=assignment
        ).select_related('student')
    
    return render(request, 'assignments/detail.html', {
        'assignment': assignment,
        'profile': profile,
        'submission': submission,
        'submissions': submissions,
    })


@login_required
def assignment_create(request):
    """Create a new assignment"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only teachers and admins can create assignments
    if profile.role not in ['teacher', 'admin']:
        messages.error(request, "You don't have permission to create assignments.")
        return redirect('assignments_list')
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.created_by = request.user
            assignment.save()
            messages.success(request, "Assignment created successfully!")
            return redirect('assignment_detail', pk=assignment.pk)
    else:
        form = AssignmentForm()
    
    return render(request, 'assignments/create.html', {'form': form})


@login_required
def assignment_submit(request, pk):
    """Submit an assignment"""
    assignment = get_object_or_404(Assignment, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only students can submit assignments
    if profile.role != 'student':
        messages.error(request, "Only students can submit assignments.")
        return redirect('assignment_detail', pk=assignment.pk)
    
    # Check if the assignment is for the student's class level
    if assignment.class_level != profile.class_level:
        messages.error(request, "This assignment is not for your class level.")
        return redirect('assignments_list')
    
    # Check if the assignment is past due
    if assignment.is_past_due:
        messages.warning(request, "This assignment is past due, but you can still submit.")
    
    # Check if student has already submitted
    try:
        submission = AssignmentSubmission.objects.get(
            assignment=assignment,
            student=request.user
        )
        messages.info(request, "You have already submitted this assignment.")
        return redirect('assignment_detail', pk=assignment.pk)
    except AssignmentSubmission.DoesNotExist:
        pass
    
    if request.method == 'POST':
        form = AssignmentSubmissionForm(request.POST)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.assignment = assignment
            submission.student = request.user
            submission.save()
            messages.success(request, "Assignment submitted successfully!")
            return redirect('assignment_detail', pk=assignment.pk)
    else:
        form = AssignmentSubmissionForm()
    
    return render(request, 'assignments/submission.html', {
        'form': form,
        'assignment': assignment,
    })


@login_required
def submission_grade(request, pk):
    """Grade an assignment submission"""
    submission = get_object_or_404(AssignmentSubmission, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only teachers and admins can grade submissions
    if profile.role not in ['teacher', 'admin']:
        messages.error(request, "You don't have permission to grade submissions.")
        return redirect('assignments_list')
    
    # Teachers can only grade assignments they created
    if profile.role == 'teacher' and submission.assignment.created_by != request.user:
        messages.error(request, "You can only grade submissions for your own assignments.")
        return redirect('assignments_list')
    
    if request.method == 'POST':
        form = AssignmentGradingForm(request.POST, instance=submission)
        if form.is_valid():
            graded_submission = form.save(commit=False)
            graded_submission.is_graded = True
            graded_submission.graded_at = timezone.now()
            graded_submission.graded_by = request.user
            graded_submission.save()
            messages.success(request, "Submission graded successfully!")
            return redirect('assignment_detail', pk=submission.assignment.pk)
    else:
        form = AssignmentGradingForm(instance=submission)
    
    return render(request, 'assignments/grade.html', {
        'form': form,
        'submission': submission,
    })


@login_required
def ai_tutor_chat(request):
    """AI tutor chat interface with role-based syllabus content"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Get or create an active AI session
    try:
        session = AITutorSession.objects.get(student=request.user, is_active=True)
    except AITutorSession.DoesNotExist:
        session = AITutorSession.objects.create(student=request.user)
    
    # Get chat history
    messages_history = AITutorMessage.objects.filter(session=session).order_by('timestamp')
    
    # Handle new questions - only for non-AJAX requests (fallback for non-JS browsers)
    if request.method == 'POST' and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        form = AITutorForm(request.POST)
        if form.is_valid():
            question = form.cleaned_data['question']
            subject_id = form.cleaned_data.get('subject')
            
            # Save the question
            question_msg = AITutorMessage.objects.create(
                session=session,
                message_type='question',
                content=question
            )
            
            # Get subject if provided
            subject = None
            if subject_id:
                try:
                    subject = Subject.objects.get(id=subject_id)
                    
                    # For students and teachers: validate subject is valid for their class level
                    if profile.role in ['student', 'teacher']:
                        # Check if this subject is assigned to their class level
                        subject_valid = ClassSubject.objects.filter(
                            class_level=profile.class_level,
                            subject=subject
                        ).exists()
                        
                        if not subject_valid:
                            # If not valid, add a warning message to the user
                            messages.warning(request, 
                                f"Note: {subject.name} is not in your class level's curriculum. " +
                                "The AI response may not align with your syllabus.")
                    
                    # Update session subject
                    session.subject = subject
                    session.save()
                except Subject.DoesNotExist:
                    pass
            
            # Get role and class level context for the AI
            role_context = f"student in class {profile.get_class_level_display()}" if profile.role == 'student' else \
                           f"teacher for class {profile.get_class_level_display()}" if profile.role == 'teacher' else \
                           "school administrator"
            
            # Get syllabus-relevant subjects for this class level
            class_subjects = []
            if profile.role in ['student', 'teacher'] and profile.class_level:
                class_subjects = list(ClassSubject.objects.filter(
                    class_level=profile.class_level
                ).select_related('subject').values_list('subject__name', flat=True))
                
                # Make sure we have a non-empty list of subjects for curriculum restriction
                if not class_subjects:
                    # If no subjects are explicitly assigned to this class level,
                    # use some default subjects based on the class level
                    if profile.class_level in ['1', '2', '3', '4', '5']:
                        class_subjects = ["Mathematics", "English", "Science", "Social Studies", "Art"]
                    elif profile.class_level in ['6', '7', '8']:
                        class_subjects = ["Mathematics", "English", "Science", "Social Science", "Languages"]
                    elif profile.class_level in ['9', '10']:
                        class_subjects = ["Mathematics", "Science", "Social Science", "English", "Languages"]
                    elif profile.class_level in ['11', '12']:
                        class_subjects = ["Physics", "Chemistry", "Biology", "Mathematics", "English", "Computer Science"]
                    elif profile.class_level == 'eng_com':
                        class_subjects = ["English Grammar", "Vocabulary", "Reading Comprehension", "Writing Skills", "Speaking"]
            
            # Get AI response with appropriate role and syllabus context
            ai_response = get_ai_response(
                question, 
                subject_name=subject.name if subject else None,
                role=profile.role,
                class_level=profile.class_level,
                class_subjects=class_subjects
            )
            
            # Save the response
            AITutorMessage.objects.create(
                session=session,
                message_type='answer',
                content=ai_response
            )
            
            return redirect('ai_tutor_chat')
    else:
        form = AITutorSessionForm()
    
    # Get role-appropriate subjects for dropdown
    if profile.role in ['student', 'teacher']:
        # For students and teachers, only show subjects for their class level
        subject_ids = ClassSubject.objects.filter(
            class_level=profile.class_level
        ).values_list('subject_id', flat=True)
        subjects = Subject.objects.filter(id__in=subject_ids)
    else:
        # Admins can see all subjects
        subjects = Subject.objects.all()
    
    # Get past sessions for history dropdown
    past_sessions = AITutorSession.objects.filter(
        student=request.user
    ).order_by('-started_at')
    
    return render(request, 'ai_tutor/chat.html', {
        'form': form,
        'messages_history': messages_history,
        'subjects': subjects,
        'current_subject': session.subject,
        'current_session': session,
        'past_sessions': past_sessions,
        'profile': profile,  # Pass profile to template
    })


@login_required
def ai_tutor_history(request, session_id=None):
    """View chat history for a specific session"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # If session_id is provided, get that specific session
    if session_id:
        session = get_object_or_404(AITutorSession, id=session_id, student=request.user)
    else:
        # Otherwise get the most recent completed session
        session = AITutorSession.objects.filter(
            student=request.user, 
            is_active=False
        ).order_by('-last_activity').first()
    
    # Get all past sessions for the sidebar
    past_sessions = AITutorSession.objects.filter(
        student=request.user
    ).order_by('-started_at')
    
    # Get messages for the selected session
    messages_history = []
    if session:
        messages_history = AITutorMessage.objects.filter(session=session).order_by('timestamp')
    
    return render(request, 'ai_tutor/history.html', {
        'session': session,
        'past_sessions': past_sessions,
        'messages_history': messages_history,
    })


@login_required
@require_POST
def end_ai_session(request):
    """End the current AI tutor session"""
    # Close active session
    session = get_object_or_404(AITutorSession, student=request.user, is_active=True)
    session.is_active = False
    session.save()
    
    messages.success(request, "AI tutor session has been ended and saved to your history.")
    return redirect('ai_tutor_history')


@login_required
@require_POST
def generate_practice_questions_view(request):
    """Generate practice questions using AI with class-specific content"""
    topic = request.POST.get('topic', '')
    count = request.POST.get('count', '3')
    difficulty = request.POST.get('difficulty', 'medium')
    
    try:
        count = int(count)
        if count < 1 or count > 10:
            count = 3
    except ValueError:
        count = 3
    
    if not topic:
        return JsonResponse({'error': 'Topic is required'}, status=400)
    
    # Get user profile to enforce role and class-level constraints
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Create a contextual prompt that respects the user's class level
    contextualized_topic = topic
    
    # For students, restrict to their class level syllabus
    if profile.role == 'student' and profile.class_level:
        # Get syllabus-relevant subjects for this class level
        class_subjects = list(ClassSubject.objects.filter(
            class_level=profile.class_level
        ).select_related('subject').values_list('subject__name', flat=True))
        
        # If no explicit subjects found, use default ones based on class level
        if not class_subjects:
            if profile.class_level in ['1', '2', '3', '4', '5']:
                class_subjects = ["Mathematics", "English", "Science", "Social Studies", "Art"]
            elif profile.class_level in ['6', '7', '8']:
                class_subjects = ["Mathematics", "English", "Science", "Social Science", "Languages"]
            elif profile.class_level in ['9', '10']:
                class_subjects = ["Mathematics", "Science", "Social Science", "English", "Languages"]
            elif profile.class_level in ['11', '12']:
                class_subjects = ["Physics", "Chemistry", "Biology", "Mathematics", "English", "Computer Science"]
            elif profile.class_level == 'eng_com':
                class_subjects = ["English Grammar", "Vocabulary", "Reading Comprehension", "Writing Skills", "Speaking"]
        
        # Add class level context to the topic
        class_level_display = get_class_level_display(profile.class_level)
        contextualized_topic = f"{topic} for {class_level_display} students"
    
    # Generate practice questions with appropriate context
    questions = generate_practice_questions(contextualized_topic, count, difficulty)
    
    return JsonResponse({'questions': questions})


def get_class_level_display(class_level):
    """Helper function to convert class_level code to display name"""
    if class_level == 'eng_com':
        return "English Communication Program"
    else:
        try:
            return f"Class {int(class_level)}"
        except (ValueError, TypeError):
            return f"Class {class_level}"


@login_required
def rename_ai_session(request):
    """Rename an AI tutor session"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        session_id = request.POST.get('session_id')
        title = request.POST.get('title', '').strip()
        
        if not session_id or not title:
            return JsonResponse({'success': False, 'error': 'Session ID and title are required'})
        
        try:
            session = AITutorSession.objects.get(id=session_id, student=request.user)
            session.title = title
            session.save()
            return JsonResponse({'success': True})
        except AITutorSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def pin_ai_session(request):
    """Pin or unpin an AI tutor session"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        session_id = request.POST.get('session_id')
        is_pinned = request.POST.get('is_pinned') == '1'
        
        if not session_id:
            return JsonResponse({'success': False, 'error': 'Session ID is required'})
        
        try:
            session = AITutorSession.objects.get(id=session_id, student=request.user)
            session.is_pinned = is_pinned
            session.save()
            return JsonResponse({'success': True})
        except AITutorSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def delete_ai_session(request):
    """Delete an AI tutor session"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        session_id = request.POST.get('session_id')
        
        if not session_id:
            return JsonResponse({'success': False, 'error': 'Session ID is required'})
        
        try:
            session = AITutorSession.objects.get(id=session_id, student=request.user)
            session.delete()
            return JsonResponse({'success': True})
        except AITutorSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def export_ai_session_pdf(request, session_id):
    """Export an AI tutor session as PDF"""
    try:
        session = AITutorSession.objects.get(id=session_id, student=request.user)
        messages = session.messages.all().order_by('timestamp')
        
        # This is a placeholder - in a real implementation, you would
        # use a library like reportlab or weasyprint to generate a PDF
        response = HttpResponse("PDF export not fully implemented yet.", content_type="text/plain")
        response['Content-Disposition'] = f'attachment; filename="chat_session_{session_id}.txt"'
        return response
        
    except AITutorSession.DoesNotExist:
        return HttpResponse("Session not found", status=404)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)


@login_required
def export_ai_session_email(request, session_id):
    """Email an AI tutor session to the user"""
    try:
        session = AITutorSession.objects.get(id=session_id, student=request.user)
        
        # This is a placeholder - in a real implementation, you would
        # format the email content and send it using SendGrid or Django's email backend
        return HttpResponse("Email export not fully implemented yet.", content_type="text/plain")
        
    except AITutorSession.DoesNotExist:
        return HttpResponse("Session not found", status=404)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)


@login_required
@require_POST
def add_thread_reply(request):
    """Handle thread replies to existing AI messages"""
    parent_message_id = request.POST.get('parent_message_id')
    content = request.POST.get('content', '').strip()
    
    if not parent_message_id or not content:
        return JsonResponse({'success': False, 'error': 'Missing parent message ID or content'})
    
    try:
        # Get the parent message and its session
        parent_message = AITutorMessage.objects.get(id=parent_message_id)
        session = parent_message.session
        
        # Verify this is the user's session
        if session.student != request.user:
            return JsonResponse({'success': False, 'error': 'Unauthorized access to this message'})
        
        # Create the user's thread reply
        user_reply = AITutorMessage.objects.create(
            session=session,
            message_type='thread_question',
            content=content,
            parent_message=parent_message
        )
        
        # Import the AI service
        from .ai_service import get_ai_response
        
        # Get subject context if available
        subject = session.subject
        subject_name = subject.name if subject else None
        
        # Get user role and class level for context
        user_profile = request.user.profile
        role = user_profile.role
        class_level = user_profile.class_level
        
        # Get AI response (with thread context)
        thread_context = f"This is a thread reply to your previous answer: '{parent_message.content}'. "
        thread_context += f"The user is asking: {content}"
        
        ai_response = get_ai_response(
            content, 
            subject_name=subject_name,
            role=role,
            class_level=class_level,
            thread_context=thread_context
        )
        
        # Create the AI's thread response
        ai_reply = AITutorMessage.objects.create(
            session=session,
            message_type='thread_answer',
            content=ai_response,
            parent_message=parent_message
        )
        
        # Format timestamps for the response
        user_timestamp = user_reply.timestamp.strftime('%I:%M %p')
        ai_timestamp = ai_reply.timestamp.strftime('%I:%M %p')
        
        return JsonResponse({
            'success': True,
            'thread': {
                'user_reply': {
                    'id': user_reply.id,
                    'content': user_reply.content,
                    'timestamp': user_timestamp
                },
                'ai_reply': {
                    'id': ai_reply.id,
                    'content': ai_reply.content,
                    'timestamp': ai_timestamp
                }
            }
        })
        
    except AITutorMessage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Parent message not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def edit_message(request):
    """Edit a user's message and regenerate AI responses"""
    message_id = request.POST.get('message_id')
    new_content = request.POST.get('content', '').strip()
    
    if not message_id or not new_content:
        return JsonResponse({'success': False, 'error': 'Missing message ID or content'})
    
    try:
        # Get the message and its session
        message = AITutorMessage.objects.get(id=message_id)
        session = message.session
        
        # Verify this is the user's message and session
        if session.student != request.user or message.message_type != 'question':
            return JsonResponse({
                'success': False, 
                'error': 'You can only edit your own questions'
            })
        
        # Save original content for reference
        original_content = message.content
        
        # Update the message
        message.content = new_content
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save()
        
        # Get all messages after this one
        subsequent_messages = AITutorMessage.objects.filter(
            session=session,
            timestamp__gt=message.timestamp
        ).order_by('timestamp')
        
        # Delete all subsequent messages (they'll be regenerated)
        message_ids_to_delete = list(subsequent_messages.values_list('id', flat=True))
        subsequent_messages.delete()
        
        # Import the AI service
        from .ai_service import get_ai_response
        
        # Get subject context if available
        subject = session.subject
        subject_name = subject.name if subject else None
        
        # Get user role and class level for context
        user_profile = request.user.profile
        role = user_profile.role
        class_level = user_profile.class_level
        
        # Get new AI response based on edited question
        ai_response = get_ai_response(
            new_content, 
            subject_name=subject_name,
            role=role,
            class_level=class_level,
            edit_context=f"This question was edited. Original: '{original_content}'"
        )
        
        # Create the new AI response
        new_ai_message = AITutorMessage.objects.create(
            session=session,
            message_type='answer',
            content=ai_response
        )
        
        return JsonResponse({
            'success': True,
            'edited_message': {
                'id': message.id,
                'content': message.content,
                'timestamp': message.edited_at.strftime('%I:%M %p') if message.edited_at else message.timestamp.strftime('%I:%M %p'),
                'is_edited': message.is_edited
            },
            'new_response': {
                'id': new_ai_message.id,
                'content': new_ai_message.content,
                'timestamp': new_ai_message.timestamp.strftime('%I:%M %p')
            },
            'deleted_message_ids': message_ids_to_delete
        })
        
    except AITutorMessage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Message not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def ajax_ai_chat_view(request):
    """AJAX endpoint for AI chat interactions"""
    # Print headers for debugging
    print(f"Request method: {request.method}")
    print(f"Request headers: {request.headers}")
    
    # Accept both AJAX and non-AJAX requests for testing
    # If not Ajax, we can turn this on for debugging
    # if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    #     return JsonResponse({'error': 'AJAX requests only'}, status=400)
    
    user = request.user
    profile = get_object_or_404(UserProfile, user=user)
    
    # Get question from request (handle both GET and POST)
    if request.method == 'POST':
        question = request.POST.get('question', '').strip()
        subject_id = request.POST.get('subject', '')
    else:
        question = request.GET.get('question', '').strip()
        subject_id = request.GET.get('subject', '')
        
    print(f"Question received: {question}")
    print(f"Subject ID: {subject_id}")
    
    if not question:
        return JsonResponse({'error': 'Question is required'}, status=400)
    
    # Get or create an active AI session
    try:
        session = AITutorSession.objects.get(student=user, is_active=True)
    except AITutorSession.DoesNotExist:
        session = AITutorSession.objects.create(student=user)
    
    # Get subject if provided
    subject = None
    if subject_id:
        try:
            subject = Subject.objects.get(id=subject_id)
            
            # For students and teachers: validate subject is valid for their class level
            if profile.role in ['student', 'teacher']:
                # Check if this subject is assigned to their class level
                subject_valid = ClassSubject.objects.filter(
                    class_level=profile.class_level,
                    subject=subject
                ).exists()
                
                if not subject_valid:
                    subject = None
            
            session.subject = subject
            session.save()
        except Subject.DoesNotExist:
            pass
    
    # Save the question
    question_msg = AITutorMessage.objects.create(
        session=session,
        message_type='question',
        content=question
    )
    
    # Get appropriate context
    if profile.role in ['student', 'teacher']:
        # Get the subjects assigned to this class level
        subject_ids = ClassSubject.objects.filter(
            class_level=profile.class_level
        ).values_list('subject_id', flat=True)
        class_subjects = list(Subject.objects.filter(id__in=subject_ids).values_list('name', flat=True))
    else:
        class_subjects = list(Subject.objects.all().values_list('name', flat=True))
    
    # Get AI response with contextual awareness
    ai_response = get_ai_response(
        question=question,
        subject_name=subject.name if subject else None,
        role=profile.role,
        class_level=profile.class_level,
        class_subjects=class_subjects
    )
    
    # Save the response
    response_msg = AITutorMessage.objects.create(
        session=session,
        message_type='answer',
        content=ai_response
    )
    
    # Update last activity time
    session.last_activity = timezone.now()
    session.save()
    
    # Format timestamp for the response
    timestamp = response_msg.timestamp.strftime('%I:%M %p')
    
    # Return the response as JSON
    return JsonResponse({
        'response': ai_response,
        'timestamp': timestamp,
        'question_id': question_msg.id,
        'response_id': response_msg.id
    })


@login_required
def user_settings(request):
    """User settings and preferences page"""
    user = request.user
    settings, created = UserSettings.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        form = UserSettingsForm(request.POST, instance=settings, user=user)
        if form.is_valid():
            settings = form.save(commit=False)
            
            # Handle the default_class_level field for teachers/admins
            if hasattr(user, 'userprofile') and user.userprofile.role in ['teacher', 'admin']:
                settings.default_class_level = form.cleaned_data.get('default_class_level', '')
            
            settings.save()
            messages.success(request, "Settings updated successfully!")
            return redirect('user_settings')
    else:
        form = UserSettingsForm(instance=settings, user=user)
    
    return render(request, 'settings/user_settings.html', {
        'form': form,
        'user': user,
        'profile': hasattr(user, 'userprofile') and user.userprofile,
    })


@login_required
def class_subjects_list(request):
    """List and manage subjects assigned to classes (admin and teacher only)"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Only admin and teachers can manage subject assignments
    if profile.role not in ['admin', 'teacher']:
        messages.error(request, "You don't have permission to manage class subjects.")
        return redirect('dashboard')
    
    # Get all classes with assigned subjects
    if profile.role == 'admin':
        # Admins can see all class-subject assignments
        class_subjects = ClassSubject.objects.all().select_related('subject').order_by('class_level', 'subject__name')
    else:
        # Teachers can only see and manage their assigned class
        class_subjects = ClassSubject.objects.filter(assigned_by=request.user).select_related('subject').order_by('class_level', 'subject__name')
    
    # Group by class level for easier UI organization
    class_level_subjects = {}
    for cs in class_subjects:
        class_name = cs.get_class_level_display()
        if class_name not in class_level_subjects:
            class_level_subjects[class_name] = []
        class_level_subjects[class_name].append(cs)
    
    # Get all available subjects for dropdown
    subjects = Subject.objects.all().order_by('name')
    
    # Get all class levels
    class_levels = UserProfile.CLASS_CHOICES
    
    return render(request, 'class_subjects/list.html', {
        'class_level_subjects': class_level_subjects,
        'subjects': subjects,
        'class_levels': class_levels,
        'profile': profile,
    })


@login_required
def class_subject_add(request):
    """Add a new subject to a class level"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Only admin and teachers can add subject assignments
    if profile.role not in ['admin', 'teacher']:
        messages.error(request, "You don't have permission to manage class subjects.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ClassSubjectForm(request.POST)
        if form.is_valid():
            class_subject = form.save(commit=False)
            class_subject.assigned_by = request.user
            
            # Check if assignment already exists
            existing = ClassSubject.objects.filter(
                class_level=class_subject.class_level,
                subject=class_subject.subject
            ).exists()
            
            if existing:
                messages.warning(request, f"The subject '{class_subject.subject}' is already assigned to {class_subject.get_class_level_display()}.")
            else:
                class_subject.save()
                messages.success(request, f"Subject '{class_subject.subject}' has been assigned to {class_subject.get_class_level_display()}.")
            
            return redirect('class_subjects_list')
    else:
        form = ClassSubjectForm()
    
    return render(request, 'class_subjects/add.html', {
        'form': form,
        'profile': profile,
    })


@login_required
def class_subject_edit(request, pk):
    """Edit a class-subject assignment"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Only admin and teachers can edit class-subject assignments
    if profile.role not in ['admin', 'teacher']:
        messages.error(request, "You don't have permission to edit subject assignments.")
        return redirect('dashboard')
    
    class_subject = get_object_or_404(ClassSubject, pk=pk)
    
    # Teachers can only edit their own assignments
    if profile.role == 'teacher' and class_subject.assigned_by != request.user:
        messages.error(request, "You can only edit class-subject assignments that you created.")
        return redirect('class_subjects_list')
    
    if request.method == 'POST':
        form = ClassSubjectForm(request.POST, instance=class_subject)
        if form.is_valid():
            updated_assignment = form.save(commit=False)
            updated_assignment.assigned_by = request.user
            updated_assignment.assigned_at = timezone.now()
            updated_assignment.save()
            
            messages.success(request, f"Subject assignment has been updated successfully.")
            return redirect('class_subjects_list')
    else:
        form = ClassSubjectForm(instance=class_subject)
    
    return render(request, 'class_subjects/edit.html', {
        'form': form,
        'class_subject': class_subject,
        'profile': profile,
    })


def class_subject_delete(request, pk):
    """Delete a subject-class assignment"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Only admin and teachers can delete subject assignments
    if profile.role not in ['admin', 'teacher']:
        messages.error(request, "You don't have permission to manage class subjects.")
        return redirect('dashboard')
    
    class_subject = get_object_or_404(ClassSubject, pk=pk)
    
    # Teachers can only delete their own assignments
    if profile.role == 'teacher' and class_subject.assigned_by != request.user:
        messages.error(request, "You can only delete class-subject assignments that you created.")
        return redirect('class_subjects_list')
    
    if request.method == 'POST':
        subject_name = class_subject.subject.name
        class_level_name = class_subject.get_class_level_display()
        class_subject.delete()
        messages.success(request, f"Subject '{subject_name}' has been removed from {class_level_name}.")
        return redirect('class_subjects_list')
    
    return render(request, 'class_subjects/delete.html', {
        'class_subject': class_subject,
        'profile': profile,
    })


@login_required
def subject_list(request):
    """List all subjects in the system"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Only admin and teachers can view subject management
    if profile.role not in ['admin', 'teacher']:
        messages.error(request, "You don't have permission to access subject management.")
        return redirect('dashboard')
    
    # Get all subjects ordered by name
    subjects = Subject.objects.all().order_by('name')
    
    # Get the class subjects for each subject to show where they're assigned
    class_assignments_map = {}
    for subject in subjects:
        class_assignments_map[subject.id] = ClassSubject.objects.filter(subject=subject)
    
    return render(request, 'subjects/list.html', {
        'subjects': subjects,
        'profile': profile,
        'class_assignments_map': class_assignments_map,
    })


@login_required
def subject_add(request):
    """Add a new subject to the system"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Only admin and teachers can add new subjects
    if profile.role not in ['admin', 'teacher']:
        messages.error(request, "You don't have permission to create new subjects.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save()
            messages.success(request, f"Subject '{subject.name}' has been created successfully.")
            
            # Redirect to add this subject to a class if the user came from class_subject_add
            if 'next' in request.GET and request.GET['next'] == 'class_subject_add':
                return redirect('class_subject_add')
            
            # Redirect to subject list if coming from there
            if 'next' in request.GET and request.GET['next'] == 'subject_list':
                return redirect('subject_list')
            
            return redirect('class_subjects_list')
    else:
        form = SubjectForm()
    
    return render(request, 'class_subjects/subject_add.html', {
        'form': form,
        'profile': profile,
    })


@login_required
def subject_detail(request, pk):
    """View details of a specific subject"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Only admin and teachers can view subject details in the management area
    if profile.role not in ['admin', 'teacher']:
        messages.error(request, "You don't have permission to view subject details.")
        return redirect('dashboard')
    
    subject = get_object_or_404(Subject, pk=pk)
    
    # Get all class levels this subject is assigned to
    class_assignments = ClassSubject.objects.filter(subject=subject).order_by('class_level')
    
    # Get study materials for this subject
    study_materials = StudyMaterial.objects.filter(subject=subject).order_by('-upload_date')[:5]
    
    # Get assignments for this subject
    assignments = Assignment.objects.filter(subject=subject).order_by('-created_at')[:5]
    
    # Get video conferences for this subject
    conferences = VideoConference.objects.filter(subject=subject).order_by('-start_time')[:5]
    
    return render(request, 'subjects/detail.html', {
        'subject': subject,
        'class_assignments': class_assignments,
        'study_materials': study_materials,
        'assignments': assignments,
        'conferences': conferences,
        'profile': profile,
    })


@login_required
def subject_edit(request, pk):
    """Edit an existing subject"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Only admin and teachers can edit subjects
    if profile.role not in ['admin', 'teacher']:
        messages.error(request, "You don't have permission to edit subjects.")
        return redirect('dashboard')
    
    subject = get_object_or_404(Subject, pk=pk)
    
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, f"Subject '{subject.name}' has been updated successfully.")
            return redirect('subject_detail', pk=subject.pk)
    else:
        form = SubjectForm(instance=subject)
    
    return render(request, 'subjects/edit.html', {
        'form': form,
        'subject': subject,
        'profile': profile,
    })


@login_required
def subject_delete(request, pk):
    """Delete an existing subject"""
    # Get or create user profile to avoid 404 errors
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    # Only admin can delete subjects
    if profile.role != 'admin':
        messages.error(request, "Only administrators can delete subjects.")
        return redirect('subject_list')
    
    subject = get_object_or_404(Subject, pk=pk)
    
    # Check if the subject is in use
    class_assignments = ClassSubject.objects.filter(subject=subject)
    study_materials = StudyMaterial.objects.filter(subject=subject)
    assignments = Assignment.objects.filter(subject=subject)
    video_conferences = VideoConference.objects.filter(subject=subject)
    recorded_sessions = RecordedSession.objects.filter(subject=subject)
    
    # Collect usage information
    usage = {
        'class_assignments': class_assignments.count(),
        'study_materials': study_materials.count(),
        'assignments': assignments.count(),
        'video_conferences': video_conferences.count(),
        'recorded_sessions': recorded_sessions.count(),
    }
    
    # Calculate total usage
    total_usage = sum(usage.values())
    
    if request.method == 'POST':
        if request.POST.get('confirm_delete') == 'yes':
            subject_name = subject.name
            subject.delete()
            messages.success(request, f"Subject '{subject_name}' has been deleted.")
            return redirect('subject_list')
    
    return render(request, 'subjects/delete.html', {
        'subject': subject,
        'usage': usage,
        'total_usage': total_usage,
        'profile': profile,
    })


# User Management Views for Administrators

@login_required
def user_management(request):
    """List all users for administrative management"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only allow admins to access this page
    if profile.role != 'admin':
        messages.error(request, "You don't have permission to access user management.")
        return redirect('dashboard')
    
    # Get query parameters for filtering
    role_filter = request.GET.get('role', '')
    class_filter = request.GET.get('class', '')
    search_query = request.GET.get('q', '')
    
    # Base queryset
    users = UserProfile.objects.select_related('user').order_by('user__username')
    
    # Apply filters
    if role_filter:
        users = users.filter(role=role_filter)
        
    if class_filter:
        users = users.filter(class_level=class_filter)
        
    if search_query:
        users = users.filter(
            Q(user__username__icontains=search_query) | 
            Q(user__first_name__icontains=search_query) | 
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(users, 20)  # Show 20 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin/user_management.html', {
        'page_obj': page_obj,
        'role_filter': role_filter,
        'class_filter': class_filter,
        'search_query': search_query,
        'role_choices': UserProfile.ROLE_CHOICES,
        'class_choices': UserProfile.CLASS_CHOICES,
        'profile': profile,
    })


@login_required
def edit_user_access(request, user_id):
    """Edit a user's role and permissions"""
    admin_profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only allow admins to access this page
    if admin_profile.role != 'admin':
        messages.error(request, "You don't have permission to edit user access.")
        return redirect('dashboard')
    
    # Get the user to edit
    target_user = get_object_or_404(User, id=user_id)
    user_profile, created = UserProfile.objects.get_or_create(
        user=target_user,
        defaults={
            'role': 'student',
            'class_level': '1',
        }
    )
    
    if request.method == 'POST':
        form = UserAccessForm(request.POST, instance=user_profile, target_user=target_user)
        if form.is_valid():
            # Save profile and user changes (handled in form.save())
            form.save()
            
            messages.success(request, f"User {target_user.username}'s access has been updated.")
            return redirect('user_management')
    else:
        form = UserAccessForm(instance=user_profile, target_user=target_user)
    
    return render(request, 'admin/edit_user_access.html', {
        'form': form,
        'target_user': target_user,
        'profile': admin_profile,
    })


@login_required
@require_POST
def toggle_user_active(request, user_id):
    """Quickly toggle a user's active status"""
    admin_profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only allow admins to access this action
    if admin_profile.role != 'admin':
        messages.error(request, "You don't have permission to modify user status.")
        return redirect('dashboard')
    
    # Get the user to toggle
    target_user = get_object_or_404(User, id=user_id)
    
    # Don't allow deactivating your own account
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('user_management')
    
    # Toggle active status
    target_user.is_active = not target_user.is_active
    target_user.save()
    
    status = "activated" if target_user.is_active else "deactivated"
    messages.success(request, f"User {target_user.username} has been {status}.")
    
    return redirect('user_management')



@login_required
@csrf_exempt
def generate_practice_questions_view(request):
    """Generate practice questions using AI with class-specific content"""
    if request.method == 'POST':
        # Check if it's a JSON request
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
                topic = data.get('topic', '')
                count = data.get('count', '3')
                difficulty = data.get('difficulty', 'medium')
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
        else:
            # Regular form submission
            topic = request.POST.get('topic', '')
            count = request.POST.get('count', '3')
            difficulty = request.POST.get('difficulty', 'medium')
        
        try:
            count = int(count)
            if count < 1 or count > 10:
                count = 3
        except ValueError:
            count = 3
        
        if not topic:
            return JsonResponse({'error': 'Topic is required'}, status=400)
        
        # Get user profile to enforce role and class-level constraints
        profile = get_object_or_404(UserProfile, user=request.user)
        
        # Create a contextual prompt that respects the user's class level
        contextualized_topic = topic
        
        # For students, restrict to their class level syllabus
        if profile.role == 'student' and profile.class_level:
            # Get syllabus-relevant subjects for this class level
            class_subjects = list(ClassSubject.objects.filter(
                class_level=profile.class_level
            ).select_related('subject').values_list('subject__name', flat=True))
            
            # If no explicit subjects found, use default ones based on class level
            if not class_subjects:
                if profile.class_level in ['1', '2', '3', '4', '5']:
                    class_subjects = ["Mathematics", "English", "Science", "Social Studies", "Art"]
                elif profile.class_level in ['6', '7', '8']:
                    class_subjects = ["Mathematics", "English", "Science", "Social Science", "Languages"]
                elif profile.class_level in ['9', '10']:
                    class_subjects = ["Mathematics", "Science", "Social Science", "English", "Languages"]
                elif profile.class_level in ['11', '12']:
                    class_subjects = ["Physics", "Chemistry", "Biology", "Mathematics", "English", "Computer Science"]
                elif profile.class_level == 'eng_com':
                    class_subjects = ["English Grammar", "Vocabulary", "Reading Comprehension", "Writing Skills", "Speaking"]
            
            # Add class level context to the topic
            class_level_display = get_class_level_display(profile.class_level)
            contextualized_topic = f"{topic} for {class_level_display} students"
        
        # Generate practice questions with appropriate context
        try:
            questions = generate_practice_questions(contextualized_topic, count, difficulty)
            return JsonResponse({'questions': questions})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# Zoom OAuth Helper Functions
def has_zoom_oauth_token(user):
    """Check if a user has a valid Zoom OAuth token"""
    try:
        from core.models import ZoomOAuthToken
        return ZoomOAuthToken.objects.filter(user=user, is_active=True).exists()
    except Exception as e:
        logger.error(f"Error checking Zoom OAuth token: {str(e)}")
        return False

# Zoom OAuth Integration Views
@login_required
def zoom_oauth_authorize(request):
    """
    Redirect user to Zoom OAuth authorization page
    """
    if request.user.profile.role not in ['teacher', 'admin']:
        messages.error(request, "Only teachers and administrators can connect to Zoom.")
        return redirect('dashboard')
        
    from core.zoom_oauth_service import get_oauth_authorization_url, is_oauth_configured
    
    if not is_oauth_configured():
        messages.error(request, "Zoom OAuth integration is not properly configured.")
        return redirect('dashboard')
    
    # Generate a state parameter for CSRF protection
    state = str(request.user.id)
    request.session['zoom_oauth_state'] = state
    
    # Get authorization URL
    auth_url = get_oauth_authorization_url(request, state)
    
    # Redirect to Zoom for authorization
    return redirect(auth_url)


@login_required
def zoom_oauth_callback(request):
    """
    Handle callback from Zoom OAuth authorization
    """
    success = False
    error_message = ""
    
    if request.user.profile.role not in ['teacher', 'admin']:
        error_message = "Only teachers and administrators can connect to Zoom."
        return render(request, 'video/zoom_oauth_callback.html', {
            'success': False,
            'error_message': error_message
        })
    
    error = request.GET.get('error')
    if error:
        error_message = f"Zoom authorization failed: {error}"
        return render(request, 'video/zoom_oauth_callback.html', {
            'success': False,
            'error_message': error_message
        })
    
    code = request.GET.get('code')
    state = request.GET.get('state')
    
    # Verify state to prevent CSRF
    session_state = request.session.get('zoom_oauth_state')
    if not state or not session_state or state != session_state:
        error_message = "Invalid OAuth state parameter. Please try again for security reasons."
        return render(request, 'video/zoom_oauth_callback.html', {
            'success': False,
            'error_message': error_message
        })
    
    # Clear state from session
    request.session.pop('zoom_oauth_state', None)
    
    if not code:
        error_message = "No authorization code received from Zoom."
        return render(request, 'video/zoom_oauth_callback.html', {
            'success': False,
            'error_message': error_message
        })
    
    # Exchange authorization code for token
    from core.zoom_oauth_service import get_oauth_token
    from core.models import ZoomOAuthToken
    
    # Get the redirect URI (must match the one used for authorization)
    redirect_uri = request.build_absolute_uri(reverse('zoom_oauth_callback'))
    
    # Get token from Zoom
    token_data = get_oauth_token(code, redirect_uri)
    
    if not token_data or 'error' in token_data:
        error_message = token_data.get('error', 'Unknown error')
        return render(request, 'video/zoom_oauth_callback.html', {
            'success': False,
            'error_message': f"Failed to obtain Zoom token: {error_message}"
        })
    
    # Save token to database
    try:
        token, created = ZoomOAuthToken.objects.get_or_create(user=request.user)
        token.save_token_response(token_data)
        success = True
    except Exception as e:
        error_message = f"Error saving Zoom token: {str(e)}"
        return render(request, 'video/zoom_oauth_callback.html', {
            'success': False,
            'error_message': error_message
        })
    
    # Render success page
    return render(request, 'video/zoom_oauth_callback.html', {
        'success': success,
        'error_message': error_message
    })


@login_required
def zoom_oauth_meetings(request):
    """
    Display user's Zoom meetings using OAuth
    """
    if request.user.profile.role not in ['teacher', 'admin']:
        messages.error(request, "Only teachers and administrators can view Zoom meetings.")
        return redirect('dashboard')
    
    # Get user's OAuth token
    from core.models import ZoomOAuthToken
    from core.zoom_oauth_service import get_user_meetings_oauth, refresh_oauth_token, is_oauth_configured
    
    if not is_oauth_configured():
        messages.error(request, "Zoom OAuth integration is not properly configured.")
        return redirect('dashboard')
    
    meetings = []
    error_message = None
    has_token = False
    
    # For AJAX requests just checking token status
    check_only = request.GET.get('check_only', 'false').lower() == 'true'
    
    try:
        token = ZoomOAuthToken.objects.filter(user=request.user).latest('created_at')
        has_token = True
        
        # If we're only checking for token existence, return early
        if check_only:
            return JsonResponse({'has_token': has_token})
        
        # Check if token is expired and needs refresh
        if token.is_expired:
            token_data = refresh_oauth_token(token.refresh_token)
            if token_data:
                token.save_token_response(token_data)
            else:
                error_message = "Could not refresh Zoom token. Please reconnect your account."
                return render(request, 'video/zoom_meetings.html', {
                    'meetings': [],
                    'error_message': error_message,
                    'has_token': False
                })
        
        # Get user's meetings
        result = get_user_meetings_oauth(token.access_token)
        
        if result.get('success'):
            meetings = result.get('meetings', [])
        else:
            error_message = result.get('error', 'Failed to retrieve meetings')
    
    except ZoomOAuthToken.DoesNotExist:
        # No token for user
        has_token = False
        
        # If we're only checking for token existence, return early
        if check_only:
            return JsonResponse({'has_token': False})
    except Exception as e:
        error_message = str(e)
        
        # If we're only checking for token existence, return early with error
        if check_only:
            return JsonResponse({'has_token': False, 'error': str(e)})
    
    # Return HTML template for full page requests
    return render(request, 'video/zoom_meetings.html', {
        'meetings': meetings,
        'error_message': error_message,
        'has_token': has_token
    })


@login_required
def zoom_oauth_create_meeting(request):
    """
    Create a Zoom meeting using OAuth tokens with support for specific participants
    """
    if request.user.profile.role not in ['teacher', 'admin']:
        messages.error(request, "Only teachers and administrators can create Zoom meetings.")
        return redirect('dashboard')
    
    if request.method != 'POST':
        return redirect('video_conference_create')
    
    # Extract meeting details from form
    topic = request.POST.get('title')
    start_time_str = request.POST.get('start_time')
    end_time_str = request.POST.get('end_time')
    description = request.POST.get('description', '')
    subject_id = request.POST.get('subject')
    class_level = request.POST.get('class_level')
    is_recurring = request.POST.get('is_recurring') == 'on'
    enable_sdk = request.POST.get('enable_sdk') == 'on'
    
    # Get selected participants if any (will process later)
    selected_participant_ids = request.POST.getlist('selected_participants')
    
    if not all([topic, start_time_str, end_time_str, subject_id, class_level]):
        messages.error(request, "Please provide all required fields.")
        return redirect('video_conference_create')
    
    # Parse start and end times
    try:
        start_time = timezone.datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        start_time = timezone.make_aware(start_time)
        
        end_time = timezone.datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        end_time = timezone.make_aware(end_time)
        
        # Calculate duration in minutes
        duration = int((end_time - start_time).total_seconds() / 60)
    except ValueError:
        messages.error(request, "Invalid time format. Please use the datetime-local picker.")
        return redirect('video_conference_create')
    
    # Get user's OAuth token
    from core.models import ZoomOAuthToken, VideoConference, Subject, VideoConferenceParticipant
    from core.zoom_oauth_service import create_meeting_oauth, refresh_oauth_token, is_oauth_configured
    
    if not is_oauth_configured():
        messages.error(request, "Zoom OAuth integration is not properly configured.")
        return redirect('video_conference_create')
    
    # Get the subject
    subject_id = request.POST.get('subject')
    class_level = request.POST.get('class_level')
    
    try:
        subject = Subject.objects.get(id=subject_id)
    except Subject.DoesNotExist:
        messages.error(request, "Invalid subject selected.")
        return redirect('video_conference_create')
    
    # Create a new VideoConference object
    conference = VideoConference(
        title=topic,
        description=description,
        subject=subject,
        class_level=class_level,
        platform='zoom',
        scheduled_by=request.user,
        start_time=start_time,
        end_time=end_time,
        is_recurring=is_recurring,
        enable_sdk=enable_sdk,
        status='scheduled',
        used_oauth=True  # Mark as created with OAuth
    )
    
    # Save it first to get an ID
    conference.save()
    
    # Try to create the meeting using OAuth
    try:
        success = conference.create_zoom_meeting_oauth(use_current_user=True)
        
        if success:
            messages.success(request, "Zoom meeting created successfully!")
            
            # Send email notifications
            try:
                # Import here to avoid circular imports
                from core.email_service import send_meeting_invitation
                
                # Handle selected participants if any
                if selected_participant_ids:
                    # Get the selected users
                    selected_participants = User.objects.filter(id__in=selected_participant_ids)
                    
                    # Create participant records
                    for user in selected_participants:
                        # Determine participant type based on user's role
                        try:
                            user_role = user.userprofile.role
                            participant_type = 'teacher' if user_role == 'teacher' else 'student'
                        except:
                            participant_type = 'student'  # Default
                        
                        # Create the participant relationship
                        VideoConferenceParticipant.objects.create(
                            conference=conference,
                            user=user,
                            participant_type=participant_type
                        )
                    
                    # Send emails to selected participants
                    if selected_participants.exists():
                        email_result = send_meeting_invitation(conference, selected_participants, is_targeted=True)
                        if email_result:
                            messages.success(request, f"Email invitations sent to {selected_participants.count()} selected participants.")
                        else:
                            messages.warning(request, "Conference scheduled, but there was an issue sending email invitations.")
                else:
                    # Get all students in this class level
                    students = User.objects.filter(
                        userprofile__role='student',
                        userprofile__class_level=class_level
                    )
                    
                    # Add them as participants
                    for student in students:
                        VideoConferenceParticipant.objects.create(
                            conference=conference,
                            user=student,
                            participant_type='student'
                        )
                    
                    # Send email to all students in class level
                    if students.exists():
                        email_result = send_meeting_invitation(conference, students)
                        if email_result:
                            messages.success(request, f"Email invitations sent to {students.count()} students in {conference.get_class_level_display()}.")
                        else:
                            messages.warning(request, "Conference scheduled, but there was an issue sending email invitations.")
            except Exception as e:
                messages.warning(request, f"Conference scheduled, but there was an issue managing participants: {str(e)}")
                
            return redirect('video_conferences_list')
        else:
            # If OAuth creation failed and no fallback worked, delete the conference
            conference.delete()
            messages.error(request, "Failed to create Zoom meeting. Please check your Zoom connection.")
            return redirect('video_conference_create')
            
    except Exception as e:
        # If an error occurred, delete the conference and show error
        conference.delete()
        messages.error(request, f"Error creating Zoom meeting: {str(e)}")
        return redirect('video_conference_create')


def video_conference_delete(request, pk):
    """
    Delete a video conference
    
    Args:
        request: The HTTP request
        pk: The VideoConference ID to delete
        
    Returns:
        Redirect to video conferences list
    """
    if not request.user.is_authenticated:
        return redirect('login')
        
    try:
        # Get the conference
        conference = VideoConference.objects.get(id=pk)
        
        # Check if user has permission to delete this meeting
        if conference.scheduled_by != request.user and request.user.userprofile.role != 'admin':
            messages.error(request, 'You do not have permission to delete this meeting')
            return redirect('video_conferences_list')
        
        # Get participants to notify before deleting the conference
        from .models import VideoConferenceParticipant
        participants = VideoConferenceParticipant.objects.filter(
            conference=conference
        ).select_related('user')
        
        # Create list of users to notify about cancellation
        recipients = [p.user for p in participants if p.user.is_active and p.user.email]
        
        # Store conference details for notification before deletion
        meeting_details = {
            'title': conference.title,
            'start_time': conference.start_time,
            'subject': conference.subject,
            'class_level': conference.class_level,
            'scheduled_by': conference.scheduled_by,
            'platform': conference.platform,
            'meeting_id': conference.meeting_id,
            'get_class_level_display': conference.get_class_level_display
        }
        
        # If this is a Zoom meeting, try to delete it through the API
        if conference.platform == 'zoom' and conference.meeting_id:
            success = conference.delete_zoom_meeting()
            
            if not success:
                messages.warning(request, 'Could not delete meeting from Zoom, but it will be removed from the database.')
        
        # Delete the conference record
        conference.delete()
        
        # Send cancellation notifications if there are recipients
        if recipients:
            try:
                from core.email_service import send_meeting_update_notification
                
                # Create a simple meeting object with the stored details
                class SimpleMeeting:
                    def __init__(self, details):
                        self.title = details['title']
                        self.start_time = details['start_time']
                        self.subject = details['subject']
                        self.class_level = details['class_level']
                        self.scheduled_by = details['scheduled_by']
                        self.platform = details['platform']
                        self.meeting_id = details['meeting_id']
                        self.get_class_level_display = details['get_class_level_display']
                
                # Send meeting cancellation notification
                notification_result = send_meeting_update_notification(
                    meeting=SimpleMeeting(meeting_details),
                    recipients=recipients,
                    update_type='Meeting Cancelled'
                )
                
                if notification_result:
                    messages.success(request, f'Meeting cancellation notification sent to {len(recipients)} participants')
            except Exception as e:
                logger.error(f"Error sending cancellation notifications: {str(e)}")
                messages.warning(request, f'Meeting deleted but could not send cancellation notifications: {str(e)}')
        
        messages.success(request, 'Meeting deleted successfully')
        return redirect('video_conferences_list')
            
    except VideoConference.DoesNotExist:
        messages.error(request, 'Meeting not found')
        return redirect('video_conferences_list')
    except Exception as e:
        messages.error(request, f'Error deleting meeting: {str(e)}')
        return redirect('video_conferences_list')


def zoom_oauth_delete_meeting(request, meeting_id):
    """
    Delete a Zoom meeting using OAuth authentication
    
    Args:
        request: The HTTP request
        meeting_id: The VideoConference ID to delete
        
    Returns:
        Redirect to video conferences list
    """
    if not request.user.is_authenticated:
        return redirect('login')
    
    if request.user.userprofile.role not in ['teacher', 'admin']:
        messages.error(request, "Only teachers and administrators can delete Zoom meetings.")
        return redirect('dashboard')
        
    try:
        # Get the conference
        from core.models import ZoomOAuthToken, VideoConference
        from core.zoom_oauth_service import delete_meeting_oauth, refresh_oauth_token, is_oauth_configured
        
        conference = VideoConference.objects.get(id=meeting_id)
        
        # Check if user has permission to delete this meeting
        if conference.scheduled_by != request.user and request.user.userprofile.role != 'admin':
            messages.error(request, 'You do not have permission to delete this meeting')
            return redirect('video_conferences_list')
            
        # Check if this is a Zoom meeting
        if conference.platform != 'zoom' or not conference.meeting_id:
            # Not a Zoom meeting or no meeting ID, just delete from database
            conference.delete()
            messages.success(request, 'Meeting deleted successfully')
            return redirect('video_conferences_list')
        
        # Store meeting ID before deleting the conference record
        zoom_meeting_id = conference.meeting_id
        
        # Try to delete the Zoom meeting
        try:
            # Delete using the VideoConference's method which handles OAuth vs JWT
            success = conference.delete_zoom_meeting()
            
            # Delete the conference record from database
            conference.delete()
            
            if success:
                messages.success(request, 'Meeting deleted successfully')
            else:
                messages.warning(request, 'Meeting deleted from database, but there was an issue deleting it from Zoom')
                
        except Exception as e:
            # If Zoom API deletion fails, still delete from database
            conference.delete()
            messages.warning(request, f'Meeting deleted from database, but there was an error with Zoom: {str(e)}')
            
        return redirect('video_conferences_list')
            
    except VideoConference.DoesNotExist:
        messages.error(request, 'Meeting not found')
        return redirect('video_conferences_list')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('video_conferences_list')


# Payment Gateway Views
def payment_checkout(request, user_id):
    """
    Redirects to Stripe checkout for student registration payment
    """
    # Only allow admins or the user themselves to access their checkout
    if request.user.is_authenticated:
        if request.user.id != user_id and request.user.userprofile.role != 'admin':
            messages.error(request, "You don't have permission to access this payment page.")
            return redirect('dashboard')
    
    # Get the user and profile
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    
    # Skip payment if user is exempt or already paid
    if profile.payment_status == 'exempt' or profile.payment_status == 'paid':
        messages.info(request, "Payment is not required for this account.")
        return redirect('dashboard')
    
    # Create the checkout session
    checkout_data = create_checkout_session(request, user_id=user_id)
    
    if not checkout_data:
        messages.error(request, "Failed to create payment session. Please try again later.")
        return redirect('register')
    
    # Render the checkout page
    return render(request, 'payment/checkout.html', {
        'checkout_session_id': checkout_data['id'],
        'checkout_url': checkout_data['url'],
        'user': user,
        'profile': profile,
        'fee_amount': 1000  # Fee amount in Rs.
    })

def payment_success(request):
    """
    Handle successful payment and activate student account
    """
    session_id = request.GET.get('session_id')
    
    if not session_id:
        messages.error(request, "Payment verification failed. Missing session information.")
        return redirect('dashboard')
    
    # Verify the checkout session
    payment_data = verify_checkout_session(session_id)
    
    if not payment_data or payment_data['status'] != 'paid':
        messages.error(request, "Payment verification failed. Please contact support.")
        return redirect('dashboard')
    
    # Get user ID from metadata
    user_id = payment_data['metadata'].get('user_id')
    
    if not user_id:
        messages.error(request, "Could not determine which user this payment belongs to.")
        return redirect('dashboard')
    
    # Update user profile payment status
    try:
        user = User.objects.get(id=user_id)
        profile = user.profile
        
        # Update payment information
        profile.payment_status = 'paid'
        profile.payment_date = timezone.now()
        profile.payment_amount = payment_data['amount_total']
        profile.payment_id = session_id
        profile.save()
        
        # Log the user in if not already logged in
        if not request.user.is_authenticated:
            login(request, user)
        
        messages.success(request, "Your payment was successful. Your account is now fully active!")
        return render(request, 'payment/success.html', {
            'user': user,
            'profile': profile,
            'payment': payment_data
        })
        
    except User.DoesNotExist:
        messages.error(request, "User not found. Please contact support.")
        return redirect('home')
    except Exception as e:
        messages.error(request, f"Error processing payment: {str(e)}")
        return redirect('dashboard')
        
def payment_cancel(request):
    """
    Handle canceled payment
    """
    # Redirect the user to try again or contact support
    messages.warning(request, "Your payment was canceled. Please try again or contact support for assistance.")
    return render(request, 'payment/cancel.html')

@csrf_exempt
def payment_webhook(request):
    """
    Handle Stripe webhook events
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    if not sig_header:
        return HttpResponse(status=400)
    
    try:
        # Process the webhook
        event_data = handle_stripe_webhook(payload, sig_header)
        
        if not event_data:
            return HttpResponse(status=400)
        
        # Process checkout.session.completed event
        if event_data.get('event_type') == 'checkout.session.completed':
            # Get user ID from metadata
            user_id = event_data.get('metadata', {}).get('user_id')
            
            if user_id:
                try:
                    # Update user profile
                    user = User.objects.get(id=user_id)
                    profile = user.profile
                    
                    # Update payment information
                    profile.payment_status = 'paid'
                    profile.payment_date = timezone.now()
                    profile.payment_amount = event_data.get('amount_total', 1000)
                    profile.payment_id = event_data.get('id', '')
                    profile.save()
                    
                    logger.info(f"Payment completed via webhook for user {user_id}")
                    
                except User.DoesNotExist:
                    logger.error(f"User not found for payment webhook: {user_id}")
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return HttpResponse(status=400)