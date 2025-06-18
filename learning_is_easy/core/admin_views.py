from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.db import transaction
import json
from datetime import datetime, timedelta

from .models import UserProfile, AdminAuditLog, UserFeatureAccess
from .forms import AdminUserForm, UserProfileForm


def is_admin(user):
    """Check if user is an admin"""
    if not user.is_authenticated:
        return False
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.role == 'admin'
    except UserProfile.DoesNotExist:
        return False


def admin_login_view(request):
    """Admin login view"""
    if request.user.is_authenticated and is_admin(request.user):
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user:
            if is_admin(user):
                login(request, user)
                # Log admin login
                AdminAuditLog.objects.create(
                    admin_user=user,
                    action='Admin Login',
                    details=f'Admin {user.username} logged in'
                )
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Access denied. Admin privileges required.')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'admin_panel/login.html')


@login_required
@user_passes_test(is_admin)
def admin_logout_view(request):
    """Admin logout view"""
    # Log admin logout
    AdminAuditLog.objects.create(
        admin_user=request.user,
        action='Admin Logout',
        details=f'Admin {request.user.username} logged out'
    )
    logout(request)
    return redirect('admin_login')


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Admin dashboard with overview statistics"""
    # Get user statistics
    total_users = User.objects.count()
    students_count = UserProfile.objects.filter(role='student').count()
    teachers_count = UserProfile.objects.filter(role='teacher').count()
    admins_count = UserProfile.objects.filter(role='admin').count()
    
    # Recent activity (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_users = User.objects.filter(date_joined__gte=seven_days_ago).count()
    recent_logins = User.objects.filter(last_login__gte=seven_days_ago).count()
    
    # Recent audit logs
    recent_logs = AdminAuditLog.objects.select_related('admin_user').order_by('-timestamp')[:10]
    
    # Feature usage statistics
    feature_stats = UserFeatureAccess.objects.values('feature_name').annotate(
        enabled_count=Count('id', filter=Q(is_enabled=True)),
        disabled_count=Count('id', filter=Q(is_enabled=False))
    )
    
    context = {
        'total_users': total_users,
        'students_count': students_count,
        'teachers_count': teachers_count,
        'admins_count': admins_count,
        'recent_users': recent_users,
        'recent_logins': recent_logins,
        'recent_logs': recent_logs,
        'feature_stats': feature_stats,
    }
    
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def user_management(request):
    """User management with search and filtering"""
    users = User.objects.select_related('profile').all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Role filtering
    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(userprofile__role=role_filter)
    
    # Status filtering
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'role_choices': UserProfile.ROLE_CHOICES,
    }
    
    return render(request, 'admin_panel/user_management.html', context)


@login_required
@user_passes_test(is_admin)
def user_detail(request, user_id):
    """View and edit user details"""
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    
    if request.method == 'POST':
        user_form = AdminUserForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                user_form.save()
                profile_form.save()
                
                # Log the change
                AdminAuditLog.objects.create(
                    admin_user=request.user,
                    action='User Updated',
                    details=f'Updated user {user.username} profile and information',
                    target_user=user
                )
                
                messages.success(request, f'User {user.username} updated successfully.')
                return redirect('admin_user_detail', user_id=user.id)
    else:
        user_form = AdminUserForm(instance=user)
        profile_form = UserProfileForm(instance=profile)
    
    # Get user's feature access
    feature_access = UserFeatureAccess.objects.filter(user=user)
    
    context = {
        'user_obj': user,
        'profile': profile,
        'user_form': user_form,
        'profile_form': profile_form,
        'feature_access': feature_access,
    }
    
    return render(request, 'admin_panel/user_detail.html', context)


@login_required
@user_passes_test(is_admin)
def create_user(request):
    """Create a new user"""
    if request.method == 'POST':
        user_form = AdminUserForm(request.POST)
        
        if user_form.is_valid():
            with transaction.atomic():
                user = user_form.save()
                
                # Create user profile
                UserProfile.objects.create(
                    user=user,
                    role=request.POST.get('role', 'student'),
                    class_level=request.POST.get('class_level', 'class_1')
                )
                
                # Log the creation
                AdminAuditLog.objects.create(
                    admin_user=request.user,
                    action='User Created',
                    details=f'Created new user {user.username}',
                    target_user=user
                )
                
                messages.success(request, f'User {user.username} created successfully.')
                return redirect('admin_user_detail', user_id=user.id)
    else:
        user_form = AdminUserForm()
    
    context = {
        'user_form': user_form,
        'role_choices': UserProfile.ROLE_CHOICES,
        'class_choices': UserProfile.CLASS_LEVEL_CHOICES,
    }
    
    return render(request, 'admin_panel/create_user.html', context)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def delete_user(request, user_id):
    """Delete a user"""
    user = get_object_or_404(User, id=user_id)
    
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('user_detail', user_id=user.id)
    
    username = user.username
    
    # Log the deletion before deleting
    AdminAuditLog.objects.create(
        admin_user=request.user,
        action='User Deleted',
        details=f'Deleted user {username}',
        target_user=user
    )
    
    user.delete()
    messages.success(request, f'User {username} deleted successfully.')
    return redirect('user_management')


@login_required
@user_passes_test(is_admin)
def feature_access_management(request):
    """Manage feature access for users"""
    # Get all users with their feature access
    users = User.objects.select_related('profile').prefetch_related('feature_access').all()
    
    # Available features
    available_features = [
        ('chatbot', 'Chatbot'),
        ('study_materials', 'Study Materials'),
        ('zoom_meeting', 'Zoom Meeting'),
        ('video_playback', 'Video Playback'),
        ('whatsapp_integration', 'WhatsApp Integration'),
        ('ai_tutor', 'AI Tutor'),
        ('assignments', 'Assignments'),
        ('quizzes', 'Quizzes'),
        ('recordings', 'Recordings'),
        ('live_classes', 'Live Classes')
    ]
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(users, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'available_features': available_features,
    }
    
    return render(request, 'admin_panel/feature_access.html', context)


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@login_required
@user_passes_test(is_admin)
@require_POST
def toggle_feature_access(request):
    """Toggle feature access for a user via AJAX"""
    try:
        user_id = request.POST.get('user_id')
        feature_name = request.POST.get('feature_name')
        is_enabled_str = request.POST.get('is_enabled', 'false')
        is_enabled = is_enabled_str.lower() == 'true'
        
        user = get_object_or_404(User, id=user_id)
        
        # Get or create feature access
        feature_access, created = UserFeatureAccess.objects.get_or_create(
            user=user,
            feature_name=feature_name,
            defaults={'is_enabled': is_enabled, 'enabled_by': request.user}
        )
        
        if not created:
            # Update the state
            feature_access.is_enabled = is_enabled
            feature_access.enabled_by = request.user
            feature_access.save()
        
        # Log the change
        action = f"{'Enabled' if feature_access.is_enabled else 'Disabled'} {feature_name} for {user.username}"
        AdminAuditLog.objects.create(
            admin_user=request.user,
            action=action,
            target_user=user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return JsonResponse({
            'success': True, 
            'enabled': feature_access.is_enabled,
            'message': f'{feature_name} {"enabled" if feature_access.is_enabled else "disabled"} for {user.username}'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_admin)
def audit_logs(request):
    """View audit logs"""
    logs = AdminAuditLog.objects.select_related('admin_user', 'target_user').order_by('-timestamp')
    
    # Filter by action
    action_filter = request.GET.get('action', '')
    if action_filter:
        logs = logs.filter(action__icontains=action_filter)
    
    # Filter by admin user
    admin_filter = request.GET.get('admin', '')
    if admin_filter:
        logs = logs.filter(admin_user__username__icontains=admin_filter)
    
    # Filter by date range
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'action_filter': action_filter,
        'admin_filter': admin_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'admin_panel/audit_logs.html', context)


@login_required
@user_passes_test(is_admin)
def bulk_operations(request):
    """Bulk operations on users"""
    if request.method == 'POST':
        operation = request.POST.get('operation')
        user_ids = request.POST.getlist('user_ids')
        
        if not user_ids:
            messages.error(request, 'No users selected.')
            return redirect('user_management')
        
        users = User.objects.filter(id__in=user_ids)
        
        if operation == 'activate':
            users.update(is_active=True)
            AdminAuditLog.objects.create(
                admin_user=request.user,
                action='Bulk User Activation',
                details=f'Activated {len(user_ids)} users'
            )
            messages.success(request, f'Activated {len(user_ids)} users.')
            
        elif operation == 'deactivate':
            users.update(is_active=False)
            AdminAuditLog.objects.create(
                admin_user=request.user,
                action='Bulk User Deactivation',
                details=f'Deactivated {len(user_ids)} users'
            )
            messages.success(request, f'Deactivated {len(user_ids)} users.')
            
        elif operation == 'delete':
            # Don't delete self
            users = users.exclude(id=request.user.id)
            count = users.count()
            AdminAuditLog.objects.create(
                admin_user=request.user,
                action='Bulk User Deletion',
                details=f'Deleted {count} users'
            )
            users.delete()
            messages.success(request, f'Deleted {count} users.')
    
    return redirect('user_management')