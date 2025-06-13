from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()

@register.filter
def time_until(value):
    """
    Returns a string representing time until the given datetime.
    e.g., "2 days", "3 hours", "1 day, 2 hours"
    """
    if not value:
        return ''
    
    now = timezone.now()
    if now > value:
        return 'Past due'
    
    delta = value - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if days > 0:
        if hours > 0:
            return f'{days} day{"s" if days != 1 else ""}, {hours} hour{"s" if hours != 1 else ""}'
        return f'{days} day{"s" if days != 1 else ""}'
    elif hours > 0:
        if minutes > 0:
            return f'{hours} hour{"s" if hours != 1 else ""}, {minutes} min{"s" if minutes != 1 else ""}'
        return f'{hours} hour{"s" if hours != 1 else ""}'
    else:
        return f'{minutes} minute{"s" if minutes != 1 else ""}'


@register.filter
def file_icon(file_type):
    """
    Returns appropriate Font Awesome icon class for a file type
    """
    icons = {
        'pdf': 'fa-file-pdf',
        'doc': 'fa-file-word',
        'ppt': 'fa-file-powerpoint',
        'img': 'fa-file-image',
        'vid': 'fa-file-video',
        'aud': 'fa-file-audio',
        'other': 'fa-file',
    }
    return icons.get(file_type, 'fa-file')


@register.filter
def platform_icon(platform):
    """
    Returns appropriate Font Awesome icon class for a video platform
    """
    icons = {
        'zoom': 'fa-video',
        'meet': 'fa-comments',
        'teams': 'fa-users',
    }
    return icons.get(platform, 'fa-video')


@register.filter
def class_level_display(class_level):
    """
    Returns a formatted display for class level
    """
    if class_level == 'eng_com':
        return 'English Communication'
    return f'Class {class_level}'


@register.filter
def subject_icon(subject_name):
    """
    Returns an appropriate Font Awesome icon for a subject
    """
    icons = {
        'Mathematics': 'fa-calculator',
        'Science': 'fa-flask',
        'English': 'fa-book',
        'Hindi': 'fa-language',
        'Social Studies': 'fa-globe',
        'Computer Science': 'fa-laptop-code',
        'Physics': 'fa-atom',
        'Chemistry': 'fa-vial',
        'Biology': 'fa-leaf',
        'History': 'fa-landmark',
        'Geography': 'fa-mountain',
        'Economics': 'fa-chart-line',
        'Physical Education': 'fa-running',
        'Art': 'fa-palette',
        'Music': 'fa-music',
    }
    return icons.get(subject_name, 'fa-book')


@register.filter
def active_count(queryset):
    """Return count of active quizzes in a queryset"""
    return queryset.filter(is_active=True).count()


@register.filter
def average(queryset, field_name):
    """Calculate average value of a field in a queryset"""
    if not queryset or len(queryset) == 0:
        return 0
    
    total = sum(getattr(obj, field_name, 0) for obj in queryset)
    return total / len(queryset)


@register.filter
def passing_count(queryset):
    """Count items in a queryset where score >= passing_score"""
    if not queryset:
        return 0
    
    count = 0
    for item in queryset:
        if hasattr(item, 'score') and hasattr(item, 'quiz') and hasattr(item.quiz, 'passing_score'):
            if item.score >= item.quiz.passing_score:
                count += 1
    return count


@register.filter
def percentage(value, total):
    """Calculate percentage of value out of total"""
    if not total:
        return 0
    if hasattr(total, '__len__'):
        total_count = len(total)
        if total_count == 0:
            return 0
        return (value / total_count) * 100
    return (value / total) * 100
