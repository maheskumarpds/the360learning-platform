from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import learning_views
from . import quiz_views
from . import recording_views

urlpatterns = [
    # Home and authentication
    path('', views.home, name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home', template_name='registration/logged_out.html'), name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # User profiles and settings
    path('profile/<str:username>/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('settings/', views.user_settings, name='user_settings'),
    
    # Study Materials
    path('materials/', views.materials_list, name='materials_list'),
    path('materials/<int:pk>/', views.material_detail, name='material_detail'),
    path('materials/<int:pk>/download/', views.material_download, name='material_download'),
    path('materials/upload/', views.material_upload, name='material_upload'),
    
    # Video Conferences
    path('video-conferences/', views.video_conferences_list, name='video_conferences_list'),
    path('video-conferences/create/', views.video_conference_create, name='video_conference_create'),
    path('video-conferences/<int:pk>/', views.video_conference_detail, name='video_conference_detail'),
    path('video-conferences/<int:pk>/edit/', views.video_conference_edit, name='video_conference_edit'),
    path('video-conferences/<int:pk>/join/', views.video_conference_join, name='video_conference_join'),
    path('video-conferences/<int:pk>/delete/', views.video_conference_delete, name='video_conference_delete'),
    path('video-conferences/<int:pk>/toggle-auto-record/', views.toggle_auto_record, name='toggle_auto_record'),
    path('video-conferences/join-sdk/<int:pk>/', views.video_conference_join_sdk, name='video_conference_join_sdk'),
    path('video-conferences/api/get-signature/<int:meeting_id>/', views.get_zoom_signature, name='get_zoom_signature'),
    path('video-conferences/create-server-to-server/', views.server_to_server_meeting, name='server_to_server_meeting'),
    path('video-conferences/process-recordings/<str:meeting_id>/', views.process_meeting_recordings, name='process_recordings'),
    
    # Recorded Sessions
    path('recordings/', recording_views.recordings_list, name='recordings_list'),
    path('recordings/<int:recording_id>/', recording_views.recording_detail, name='recording_detail'),
    path('recordings/upload/', recording_views.upload_recording, name='recording_upload'),
    path('recordings/import-zoom/', recording_views.import_zoom_recording, name='import_zoom_recording'),
    path('recordings/<int:recording_id>/edit/', recording_views.edit_recording, name='recording_edit'),
    path('recordings/<int:recording_id>/delete/', recording_views.delete_recording, name='recording_delete'),
    
    # Assignments
    path('assignments/', views.assignments_list, name='assignments_list'),
    path('assignments/<int:pk>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/create/', views.assignment_create, name='assignment_create'),
    path('assignments/<int:pk>/submit/', views.assignment_submit, name='assignment_submit'),
    path('submissions/<int:pk>/grade/', views.submission_grade, name='submission_grade'),
    
    # AI Tutor
    path('ai-tutor/', views.ai_tutor_chat, name='ai_tutor_chat'),
    path('ai-tutor/ajax-chat/', views.ajax_ai_chat_view, name='ajax_ai_chat'),
    path('ai-tutor/history/', views.ai_tutor_history, name='ai_tutor_history'),
    path('ai-tutor/history/<int:session_id>/', views.ai_tutor_history, name='ai_tutor_history_session'),
    path('ai-tutor/end-session/', views.end_ai_session, name='end_ai_session'),
    path('ai-tutor/generate-questions/', views.generate_practice_questions_view, name='generate_practice_questions'),
    # AI Tutor Session Management
    path('ai-tutor/rename-session/', views.rename_ai_session, name='rename_ai_session'),
    path('ai-tutor/pin-session/', views.pin_ai_session, name='pin_ai_session'),
    path('ai-tutor/delete-session/', views.delete_ai_session, name='delete_ai_session'),
    path('ai-tutor/export-pdf/<int:session_id>/', views.export_ai_session_pdf, name='export_ai_session_pdf'),
    path('ai-tutor/export-email/<int:session_id>/', views.export_ai_session_email, name='export_ai_session_email'),
    path('ai-tutor/thread-reply/', views.add_thread_reply, name='add_thread_reply'),
    path('ai-tutor/edit-message/', views.edit_message, name='edit_message'),
    path('ai-tutor/generate-practice-questions/', views.generate_practice_questions_view, name='generate_practice_questions'),
    
    # Class Subjects Management
    path('class-subjects/', views.class_subjects_list, name='class_subjects_list'),
    path('class-subjects/add/', views.class_subject_add, name='class_subject_add'),
    path('class-subjects/<int:pk>/edit/', views.class_subject_edit, name='class_subject_edit'),
    path('class-subjects/<int:pk>/delete/', views.class_subject_delete, name='class_subject_delete'),
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/add/', views.subject_add, name='subject_add'),
    path('subjects/<int:pk>/', views.subject_detail, name='subject_detail'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),
    
    # Learning features
    path('case-study/', learning_views.case_study_view, name='case_study'),
    path('case-study/<int:subject_id>/', learning_views.case_study_view, name='case_study_subject'),
    path('weekly-summary/', learning_views.weekly_summary_view, name='weekly_summary'),
    path('weekly-summary/email/', learning_views.send_weekly_summary_email, name='send_weekly_summary_email'),
    path('improvement-areas/', learning_views.areas_of_improvement, name='areas_of_improvement'),
    
    # Password reset
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Payment Gateway
    path('payment/checkout/<int:user_id>/', views.payment_checkout, name='payment_checkout'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/cancel/', views.payment_cancel, name='payment_cancel'),
    path('payment/webhook/', views.payment_webhook, name='payment_webhook'),
    
    # Quizzes
    path('quizzes/', quiz_views.quizzes_list, name='quizzes_list'),
    path('quizzes/create/', quiz_views.quiz_create, name='quiz_create'),
    path('quiz/<int:quiz_id>/', quiz_views.quiz_detail, name='quiz_detail'),
    path('quiz/<int:quiz_id>/edit/', quiz_views.quiz_edit, name='quiz_edit'),
    path('quiz/<int:quiz_id>/take/', quiz_views.quiz_take, name='quiz_take'),
    path('quiz/<int:quiz_id>/results/<int:attempt_id>/', quiz_views.quiz_results, name='quiz_results'),
    path('quiz/save-response/', quiz_views.save_response, name='save_response'),
    path('quiz/submit/', quiz_views.submit_quiz, name='submit_quiz'),
    
    # User Management (Admin Only)
    path('management/users/', views.user_management, name='user_management'),
    path('management/users/<int:user_id>/edit/', views.edit_user_access, name='edit_user_access'),
    path('management/users/<int:user_id>/toggle-active/', views.toggle_user_active, name='toggle_user_active'),
    
    # Zoom OAuth Integration
    path('zoom/oauth/authorize/', views.zoom_oauth_authorize, name='zoom_oauth_authorize'),
    path('zoom/oauth/callback/', views.zoom_oauth_callback, name='zoom_oauth_callback'),
    path('zoom/oauth/meetings/', views.zoom_oauth_meetings, name='zoom_oauth_meetings'),
    path('zoom/oauth/create-meeting/', views.zoom_oauth_create_meeting, name='zoom_oauth_create_meeting'),
    path('zoom/oauth/delete-meeting/<int:meeting_id>/', views.zoom_oauth_delete_meeting, name='zoom_oauth_delete_meeting'),
]
