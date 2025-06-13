from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import datetime, timedelta

from .models import UserProfile, Subject, StudyMaterial
from .learning_service import get_case_study, get_weekly_learning_summary
from .email_service import send_weekly_summary

@login_required
def case_study_view(request, subject_id=None):
    """View for case/scenario-based learning"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Check if a specific subject was requested
    if subject_id:
        subject = get_object_or_404(Subject, pk=subject_id)
    else:
        # Get a subject the user has been active in
        # This is a simple approach; in a real app this would be more sophisticated
        subjects = Subject.objects.all()
        if subjects.exists():
            subject = subjects.first()
        else:
            messages.error(request, "No subjects available for case studies.")
            return redirect('dashboard')
    
    # Get difficulty level from request or default to medium
    difficulty = request.GET.get('difficulty', 'medium')
    if difficulty not in ['easy', 'medium', 'hard']:
        difficulty = 'medium'
    
    # Generate case study
    case_study = get_case_study(subject, profile.class_level, difficulty)
    
    # Get related study materials
    related_materials = StudyMaterial.objects.filter(
        subject=subject,
        class_level=profile.class_level
    ).order_by('-upload_date')[:5]
    
    return render(request, 'learning/case_study.html', {
        'profile': profile,
        'subject': subject,
        'case_study': case_study,
        'difficulty': difficulty,
        'related_materials': related_materials
    })

@login_required
def weekly_summary_view(request):
    """View for displaying the weekly learning summary"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only students can view their weekly summary
    if profile.role != 'student':
        messages.error(request, "Weekly summaries are only available for students.")
        return redirect('dashboard')
    
    # Get the weekly summary data
    summary_data = get_weekly_learning_summary(request.user)
    
    return render(request, 'learning/weekly_summary.html', {
        'profile': profile,
        'stats': summary_data['stats'],
        'highlights': summary_data['highlights'],
        'week_start': (timezone.now() - timedelta(days=7)).strftime('%B %d, %Y'),
        'week_end': timezone.now().strftime('%B %d, %Y')
    })

@login_required
@require_POST
def send_weekly_summary_email(request):
    """Send weekly summary via email"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only students can send their weekly summary
    if profile.role != 'student':
        return JsonResponse({'success': False, 'error': 'Only students can send weekly summaries'})
    
    # Get the weekly summary data
    summary_data = get_weekly_learning_summary(request.user)
    
    # Send the email
    success = send_weekly_summary(request.user, summary_data['stats'], summary_data['highlights'])
    
    if success:
        return JsonResponse({'success': True, 'message': 'Weekly summary sent to your email'})
    else:
        return JsonResponse({
            'success': False, 
            'error': 'There was a problem sending the email. Please try again later.'
        })

@login_required
def areas_of_improvement(request):
    """View for displaying areas of improvement based on user activity"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only students can view areas of improvement
    if profile.role != 'student':
        messages.error(request, "This feature is only available for students.")
        return redirect('dashboard')
    
    # Get the weekly summary which includes improvement areas
    summary_data = get_weekly_learning_summary(request.user)
    
    # Additional improvement suggestions based on topics
    topic = request.GET.get('topic', '')
    additional_suggestions = []
    
    if topic:
        # In a real implementation, this would use the AI service to generate
        # personalized improvement suggestions for the specific topic
        from .ai_service import get_ai_response
        prompt = f"Suggest 3 ways a student can improve in {topic} for {profile.class_level} level"
        ai_suggestions = get_ai_response(prompt)
        
        if ai_suggestions:
            additional_suggestions = [
                {'description': suggestion.strip(), 'suggestion': ''}
                for suggestion in ai_suggestions.split('\n') if suggestion.strip()
            ]
    
    return render(request, 'learning/improvement_areas.html', {
        'profile': profile,
        'improvement_areas': summary_data['highlights']['improvement_areas'] + additional_suggestions,
        'topic': topic,
        'subjects': Subject.objects.all()
    })