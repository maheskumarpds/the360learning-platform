from .models import Subject

def subjects_processor(request):
    """
    Context processor to make subjects available in all templates
    """
    subjects = Subject.objects.all()
    
    # Get user role if authenticated
    is_teacher = False
    is_admin = False
    
    if request.user.is_authenticated:
        try:
            user_profile = request.user.profile
            is_teacher = user_profile.role == 'teacher'
            is_admin = user_profile.role == 'admin'
        except:
            pass
    
    return {
        'global_subjects': subjects,
        'is_teacher': is_teacher,
        'is_admin': is_admin,
    }
