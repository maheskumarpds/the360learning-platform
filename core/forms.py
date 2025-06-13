from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.forms import ModelForm
from .models import (
    UserProfile, 
    Subject, 
    StudyMaterial, 
    VideoConference, 
    RecordedSession,
    Assignment, 
    AssignmentSubmission,
    AITutorSession,
    Quiz,
    QuizQuestion,
    UserSettings,
    ClassSubject
)

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    
    # Add UserProfile fields
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=True)
    class_level = forms.ChoiceField(choices=UserProfile.CLASS_CHOICES, required=True)
    bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    phone_number = forms.CharField(max_length=15, required=False)
    profile_picture = forms.URLField(required=False)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['role', 'class_level', 'bio', 'phone_number', 'profile_picture']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }

class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = [
            'email_assignments', 'email_meetings', 'email_weekly_summary',
            'dark_mode', 'font_size', 'preferred_learning_style',
            'default_class_level', 'ai_responses_length'
        ]
        widgets = {
            'dark_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_assignments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_meetings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_weekly_summary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'font_size': forms.Select(attrs={'class': 'form-select'}),
            'preferred_learning_style': forms.Select(attrs={'class': 'form-select'}),
            'default_class_level': forms.Select(attrs={'class': 'form-select'}),
            'ai_responses_length': forms.Select(attrs={'class': 'form-select'}),
        }

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'description', 'icon']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class ClassSubjectForm(forms.ModelForm):
    class Meta:
        model = ClassSubject
        fields = ['class_level', 'subject']
        widgets = {
            'class_level': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
        }

class StudyMaterialForm(forms.ModelForm):
    class Meta:
        model = StudyMaterial
        fields = ['title', 'description', 'subject', 'class_level', 'file_type', 'file', 'file_url']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'class_level': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'file_type': forms.Select(attrs={'class': 'form-select'}),
        }

class VideoConferenceForm(forms.ModelForm):
    # Add hidden field for Zoom OAuth usage
    use_zoom_oauth = forms.BooleanField(required=False, widget=forms.HiddenInput(), initial=False)
    # Field to select specific participants
    selected_participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
        help_text="Optionally select specific users to invite to this meeting. If none selected, all users in the class level will be invited."
    )
    
    class Meta:
        model = VideoConference
        fields = ['title', 'description', 'subject', 'class_level', 'platform', 'start_time', 'end_time', 'is_recurring', 'enable_sdk', 'meeting_link', 'meeting_id', 'meeting_password']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'class_level': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'platform': forms.Select(attrs={'class': 'form-select'}),
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_sdk': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'meeting_link': forms.URLInput(attrs={'class': 'form-control'}),
            'meeting_id': forms.TextInput(attrs={'class': 'form-control'}),
            'meeting_password': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        platform = cleaned_data.get('platform')
        meeting_link = cleaned_data.get('meeting_link')
        meeting_id = cleaned_data.get('meeting_id')
        meeting_password = cleaned_data.get('meeting_password')
        use_zoom_oauth = self.data.get('use_zoom_oauth') == 'on'
        
        # If using Zoom with OAuth, skip meeting detail validation
        if platform == 'zoom' and use_zoom_oauth:
            # Mark meeting fields as valid even if empty
            self.used_oauth = True
            return cleaned_data
            
        # If Zoom without OAuth
        if platform == 'zoom':
            if not meeting_id:
                self.add_error('meeting_id', 'Meeting ID is required for Zoom meetings')
                
        # If Google Meet
        elif platform == 'meet':
            if not (meeting_link or meeting_id):
                self.add_error('meeting_link', 'Either Meeting Link or Meeting ID is required for Google Meet')
                
        # If Microsoft Teams
        elif platform == 'teams':
            if not meeting_link:
                self.add_error('meeting_link', 'Meeting Link is required for Microsoft Teams meetings')
        
        return cleaned_data

class RecordedSessionForm(forms.ModelForm):
    class Meta:
        model = RecordedSession
        fields = ['title', 'description', 'subject', 'class_level', 'recording_url', 'thumbnail_url', 'duration_minutes', 'recorded_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'class_level': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'recorded_date': forms.DateInput(attrs={'type': 'date'}),
            'duration_minutes': forms.NumberInput(attrs={'min': 1}),
        }

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'subject', 'class_level', 'difficulty', 'instructions', 'attachment_url', 'due_date', 'total_points']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'instructions': forms.Textarea(attrs={'rows': 5}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'class_level': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
        }

class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['submission_text', 'attachment_url']
        widgets = {
            'submission_text': forms.Textarea(attrs={'rows': 6}),
        }

class GradeSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['points_earned', 'feedback']
        widgets = {
            'feedback': forms.Textarea(attrs={'rows': 4}),
        }

class AITutorSessionForm(forms.ModelForm):
    class Meta:
        model = AITutorSession
        fields = ['title', 'subject']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-select'}),
        }

class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'subject', 'class_level', 'time_limit', 'passing_score', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'class_level': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class QuizQuestionForm(forms.ModelForm):
    class Meta:
        model = QuizQuestion
        fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option', 'explanation']
        widgets = {
            'question_text': forms.Textarea(attrs={'rows': 3}),
            'explanation': forms.Textarea(attrs={'rows': 2}),
            'correct_option': forms.Select(attrs={'class': 'form-select'}),
        }

class UserAccessForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['role', 'class_level']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'class_level': forms.Select(attrs={'class': 'form-select'}),
        }