import os
import logging
import random
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F

from .models import (
    UserProfile, StudyMaterial, VideoConference, RecordedSession,
    Assignment, AssignmentSubmission, AITutorSession, AITutorMessage
)
from .ai_service import get_ai_response, extract_key_points, generate_practice_questions

# Setup logging
logger = logging.getLogger(__name__)

def get_weekly_learning_summary(user):
    """
    Generate weekly learning summary for a user
    
    Args:
        user: User object
        
    Returns:
        dict: Contains statistics and highlights for the user's learning activity
    """
    profile = UserProfile.objects.get(user=user)
    one_week_ago = timezone.now() - timedelta(days=7)
    
    # Get basic statistics
    stats = {
        'materials_viewed': StudyMaterial.objects.filter(
            views_by_users__user=user,
            views_by_users__viewed_at__gte=one_week_ago
        ).distinct().count(),
        
        'assignments_completed': AssignmentSubmission.objects.filter(
            student=user,
            submitted_at__gte=one_week_ago
        ).count(),
        
        'classes_attended': VideoConference.objects.filter(
            attendees__user=user,
            attendees__attended_at__gte=one_week_ago
        ).distinct().count(),
        
        'study_hours': AITutorSession.objects.filter(
            student=user,
            started_at__gte=one_week_ago
        ).aggregate(hours=Sum('duration'))['hours'] or 0,
    }
    
    # Get learning highlights
    highlights = {
        'top_subjects': get_top_subjects(user, one_week_ago),
        'recent_achievements': get_achievements(user, one_week_ago),
        'improvement_areas': get_improvement_areas(user, profile),
        'upcoming_deadlines': get_upcoming_deadlines(user, profile)
    }
    
    return {
        'stats': stats,
        'highlights': highlights
    }

def get_top_subjects(user, since_date):
    """Get the subjects a user has spent the most time on"""
    # This would typically use time tracking data, but for simplicity 
    # we'll use a proxy of activity count per subject
    top_subjects = []
    
    # Count AI tutor sessions by subject
    ai_sessions = AITutorSession.objects.filter(
        student=user,
        started_at__gte=since_date
    ).values('subject__name').annotate(
        count=Count('id'),
        total_duration=Sum('duration')
    ).order_by('-total_duration')[:3]
    
    for session in ai_sessions:
        top_subjects.append({
            'name': session['subject__name'],
            'hours': round(session['total_duration'] / 60, 1) if session['total_duration'] else 0
        })
    
    return top_subjects

def get_achievements(user, since_date):
    """Get recent learning achievements"""
    achievements = []
    
    # Check for completed assignments with good grades
    good_grades = AssignmentSubmission.objects.filter(
        student=user,
        submitted_at__gte=since_date,
        is_graded=True,
        points_earned__gte=F('assignment__total_points') * 0.8  # 80% or higher
    ).select_related('assignment')
    
    for submission in good_grades:
        achievements.append(
            f"Scored {submission.points_earned}/{submission.assignment.total_points} on '{submission.assignment.title}'"
        )
    
    # Check for high participation in AI tutor sessions
    ai_session_count = AITutorSession.objects.filter(
        student=user,
        started_at__gte=since_date
    ).count()
    
    if ai_session_count >= 5:
        achievements.append(f"Completed {ai_session_count} AI tutoring sessions this week")
    
    # Check for materials viewed
    materials_viewed = StudyMaterial.objects.filter(
        views_by_users__user=user,
        views_by_users__viewed_at__gte=since_date
    ).distinct().count()
    
    if materials_viewed >= 10:
        achievements.append(f"Studied {materials_viewed} different learning materials")
    
    return achievements[:3]  # Return top 3 achievements

def get_improvement_areas(user, profile):
    """Identify areas where the student could improve"""
    improvement_areas = []
    
    # Check for missing assignment submissions
    missing_assignments = Assignment.objects.filter(
        class_level=profile.class_level,
        due_date__lt=timezone.now()
    ).exclude(
        assignmentsubmission__student=user
    )[:2]
    
    for assignment in missing_assignments:
        improvement_areas.append({
            'description': f"Missing submission for '{assignment.title}'",
            'suggestion': "Try to complete assignments before their due dates"
        })
    
    # Check low activity in certain subjects
    all_subjects = set(AITutorSession.objects.filter(
        student=user
    ).values_list('subject__name', flat=True).distinct())
    
    active_subjects = set(AITutorSession.objects.filter(
        student=user,
        started_at__gte=timezone.now() - timedelta(days=14)
    ).values_list('subject__name', flat=True).distinct())
    
    inactive_subjects = all_subjects - active_subjects
    
    for subject in list(inactive_subjects)[:2]:
        improvement_areas.append({
            'description': f"Low recent activity in {subject}",
            'suggestion': f"Consider scheduling more study time for {subject}"
        })
    
    return improvement_areas

def get_upcoming_deadlines(user, profile):
    """Get upcoming assignment deadlines"""
    one_week_ahead = timezone.now() + timedelta(days=7)
    
    return Assignment.objects.filter(
        class_level=profile.class_level,
        due_date__gt=timezone.now(),
        due_date__lt=one_week_ahead
    ).order_by('due_date').values('title', 'due_date')[:5]

def get_case_study(subject, class_level, difficulty='medium'):
    """
    Generate a case study or scenario for subject-based learning
    
    Args:
        subject: Subject object or name
        class_level: Class level string
        difficulty: Difficulty level (easy, medium, hard)
        
    Returns:
        dict: Contains scenario, questions, and learning points
    """
    # This would typically connect to OpenAI to generate realistic scenarios
    # For now, we'll use a simple approach
    
    subject_name = subject.name if hasattr(subject, 'name') else subject
    
    # We'd connect to OpenAI here with a prompt like:
    # "Generate a realistic {difficulty} case study for {subject_name} at {class_level} level..."
    
    # For now, we'll use generate_practice_questions from the AI service
    questions = generate_practice_questions(
        topic=f"{subject_name} for {class_level}", 
        num_questions=3, 
        difficulty=difficulty
    )
    
    return {
        'title': f"Case Study: Applied {subject_name}",
        'scenario': f"This is a {difficulty} level scenario for {subject_name} at {class_level} level. " + 
                   "Students will need to apply concepts from recent lessons to solve this real-world problem.",
        'questions': questions,
        'learning_points': extract_key_points(f"{subject_name} key concepts for {class_level}", 3)
    }