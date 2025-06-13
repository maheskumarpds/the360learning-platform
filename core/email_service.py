import os
import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# Try to import SendGrid if available
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition, ContentId, Email, To, Content
    import base64
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

# Setup logging
logger = logging.getLogger(__name__)

# Configure logging to print to console for debugging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)

# Get SendGrid API key from environment
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')

# Use Gmail SMTP settings if available
USE_GMAIL = hasattr(settings, 'EMAIL_HOST') and settings.EMAIL_HOST == 'smtp.gmail.com'

def send_email(to_emails, subject, html_content, from_email=None, attachments=None):
    """
    Send email using either Django's Gmail SMTP settings, SendGrid (if API key is available), 
    or Django's default email backend
    
    Args:
        to_emails (list/str): Email recipient(s)
        subject (str): Email subject
        html_content (str): HTML content for the email
        from_email (str, optional): Sender email, defaults to DEFAULT_FROM_EMAIL in settings
        attachments (list, optional): List of attachment dictionaries with 'file_path', 'file_name', 'file_type' keys
        
    Returns:
        bool: Success or failure
    """
    # Convert single email to list
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    
    # Use settings default for from_email if not specified
    if from_email is None:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'senthil@kalsdatalabs.com')
    
    # Create plain text version of the HTML content
    plain_text_content = strip_tags(html_content)
    
    # Priority 1: Use Django's configured SMTP (Gmail) if available
    if USE_GMAIL:
        try:
            logger.info(f"Attempting to send email via Gmail SMTP to {to_emails}")
            
            # Log SMTP settings for debugging
            logger.info(f"Using SMTP settings: HOST={settings.EMAIL_HOST}, PORT={settings.EMAIL_PORT}, USER={settings.EMAIL_HOST_USER}")
            
            # Create EmailMultiAlternatives for better HTML email handling
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_text_content,
                from_email=from_email,
                to=to_emails
            )
            
            # Attach HTML content
            email.attach_alternative(html_content, "text/html")
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    with open(attachment['file_path'], 'rb') as f:
                        email.attach(
                            attachment['file_name'],
                            f.read(),
                            attachment['file_type']
                        )
            
            # Send the email - priority to Gmail SMTP
            email.send(fail_silently=False)
            logger.info(f"Email sent successfully via Gmail SMTP to {to_emails}")
            return True
        except Exception as e:
            logger.error(f"Gmail SMTP error: {str(e)}")
            # Fall back to next method
    
    # Priority 2: Try SendGrid if API key is available
    if SENDGRID_API_KEY and SENDGRID_AVAILABLE:
        try:
            logger.info(f"Attempting to send email via SendGrid to {to_emails}")
            
            # Create SendGrid mail object
            from_email_obj = Email(from_email)
            
            # For single recipient
            if len(to_emails) == 1:
                to_email_obj = To(to_emails[0])
                message = Mail(
                    from_email=from_email_obj,
                    to_emails=to_email_obj,
                    subject=subject,
                    html_content=Content("text/html", html_content)
                )
            else:
                # For multiple recipients
                message = Mail(
                    from_email=from_email_obj,
                    subject=subject,
                )
                message.add_content(Content("text/html", html_content))
                
                for email in to_emails:
                    message.add_to(To(email))
            
            # Add plain text content as alternative
            message.add_content(Content("text/plain", plain_text_content))
            
            # Add SendGrid specific settings to improve deliverability
            message.tracking_settings = {
                "click_tracking": {"enable": True, "enable_text": True},
                "open_tracking": {"enable": True},
                "subscription_tracking": {"enable": False}
            }
            
            # Add a category for tracking in SendGrid dashboard
            message.add_category("the360learning")
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    with open(attachment['file_path'], 'rb') as f:
                        file_content = base64.b64encode(f.read()).decode()
                        attached_file = Attachment(
                            FileContent(file_content),
                            FileName(attachment['file_name']),
                            FileType(attachment['file_type']),
                            Disposition('attachment')
                        )
                        message.add_attachment(attached_file)
            
            # Send the email with detailed logging
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            logger.info(f"Using SendGrid API key: {SENDGRID_API_KEY[:5]}...{SENDGRID_API_KEY[-5:]}")
            response = sg.send(message)
            
            status_code = response.status_code
            if status_code >= 200 and status_code < 300:
                logger.info(f"Email sent successfully via SendGrid to {to_emails} with status code {status_code}")
                logger.info(f"SendGrid response headers: {response.headers}")
                return True
            else:
                logger.error(f"SendGrid API returned status code {status_code}")
                logger.error(f"SendGrid response body: {response.body}")
                # Fall back to Django's default email backend
        except Exception as e:
            logger.error(f"SendGrid error: {str(e)}")
            # Fall back to Django's default email backend
    
    # Priority 3: Use Django's default email backend as last resort
    try:
        logger.info(f"Attempting to send email via Django's default email backend to {to_emails}")
        send_mail(
            subject=subject,
            message=plain_text_content,
            from_email=from_email,
            recipient_list=to_emails,
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f"Email sent successfully via Django's default email backend to {to_emails}")
        return True
    except Exception as e:
        logger.error(f"Django email error: {str(e)}")
        return False

def send_meeting_invitation(meeting, participants, is_targeted=False):
    """
    Send meeting invitation email
    
    Args:
        meeting (VideoConference): The meeting object
        participants (list): List of User objects to invite
        is_targeted (bool): Whether this is a targeted invitation for specific participants
        
    Returns:
        bool: Success or failure
    """
    try:
        logger.info(f"Preparing to send meeting invitation for '{meeting.title}' to {len(participants)} participants")
        subject = f"Invitation: {meeting.title} - {meeting.start_time.strftime('%B %d, %Y at %I:%M %p')}"
        
        # Convert participants list to email addresses
        to_emails = [user.email for user in participants if user.email]
        
        # If no valid emails, return False
        if not to_emails:
            logger.warning("No valid email addresses found for participants")
            return False
        
        logger.info(f"Sending invitation emails to: {', '.join(to_emails)}")
        
        # Render email template
        try:
            html_content = render_to_string('email/meeting_invitation.html', {
                'meeting': meeting,
                'subject_name': meeting.subject.name if meeting.subject else '',
                'class_level': meeting.get_class_level_display(),
                'host_name': meeting.scheduled_by.get_full_name() or meeting.scheduled_by.username,
                'is_targeted_invitation': is_targeted
            })
            logger.info("Email template rendered successfully")
        except Exception as e:
            logger.error(f"Error rendering email template: {str(e)}")
            return False
        
        # Check if SendGrid is properly configured
        if SENDGRID_API_KEY:
            logger.info("SendGrid API key is configured")
        else:
            logger.warning("SendGrid API key is not configured, will use Django's default email backend")
        
        # Send the email
        result = send_email(to_emails, subject, html_content)
        if result:
            logger.info(f"Successfully sent meeting invitation emails to {len(to_emails)} recipients")
        else:
            logger.error("Failed to send meeting invitation emails")
        
        return result
    except Exception as e:
        logger.error(f"Unexpected error in send_meeting_invitation: {str(e)}")
        return False

def send_weekly_summary(user, stats, highlights):
    """
    Send weekly learning summary email
    
    Args:
        user (User): The user to send summary to
        stats (dict): Dictionary containing user's learning statistics
        highlights (dict): Dictionary containing learning highlights
        
    Returns:
        bool: Success or failure
    """
    if not user.email:
        return False
    
    subject = f"Your Weekly Learning Summary - {user.get_full_name() or user.username}"
    
    # Render email template
    html_content = render_to_string('email/weekly_summary.html', {
        'user': user,
        'stats': stats,
        'highlights': highlights
    })
    
    # Send the email
    return send_email(user.email, subject, html_content)

def send_assignment_notification(assignment, students):
    """
    Send notification about a new assignment
    
    Args:
        assignment (Assignment): The assignment object
        students (list): List of User objects to notify
        
    Returns:
        bool: Success or failure
    """
    subject = f"New Assignment: {assignment.title}"
    
    # Convert students list to email addresses
    to_emails = [user.email for user in students if user.email]
    
    # If no valid emails, return False
    if not to_emails:
        return False
    
    # Render email template
    html_content = render_to_string('email/assignment_notification.html', {
        'assignment': assignment,
        'subject_name': assignment.subject.name if assignment.subject else '',
        'due_date': assignment.due_date.strftime('%B %d, %Y at %I:%M %p'),
        'teacher_name': assignment.created_by.get_full_name() or assignment.created_by.username
    })
    
    # Send the email
    return send_email(to_emails, subject, html_content)


def send_user_signup_notification(user, user_profile):
    """
    Send notification to a user when they sign up
    
    Args:
        user (User): The user who signed up
        user_profile (UserProfile): The user's profile
        
    Returns:
        bool: Success or failure
    """
    # For registration, we'll send immediately to ensure we can provide feedback to the user
    try:
        if not user.email:
            logger.warning(f"No email address found for user {user.username}")
            return False
        
        logger.info(f"Sending signup notification to {user.email}")
        
        from django.contrib.sites.shortcuts import get_current_site
        from django.urls import reverse
        
        # Get the site domain
        try:
            domain = os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
            if not domain:
                # Fallback to the PUBLIC_URL or localhost
                domain = os.environ.get('PUBLIC_URL', 'localhost:5000')
        except Exception as e:
            logger.error(f"Error getting domain: {str(e)}")
            domain = 'localhost:5000'
        
        # Construct login URL
        try:
            login_url = f"https://{domain}{reverse('login')}"
            logger.info(f"Login URL for welcome email: {login_url}")
        except Exception as e:
            logger.error(f"Error constructing login URL: {str(e)}")
            login_url = "#"
        
        subject = "Welcome to the360learning!"
        
        # Render email template
        try:
            html_content = render_to_string('email/user_signup_notification.html', {
                'user': user,
                'user_profile': user_profile,
                'login_url': login_url
            })
            
            # Send the email - Direct call for immediate feedback
            result = send_email(user.email, subject, html_content)
            
            if result:
                logger.info(f"Successfully sent signup notification to {user.email}")
            else:
                logger.error(f"Failed to send signup notification to {user.email}")
            
            return result
        except Exception as e:
            logger.error(f"Error rendering signup email template: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error in send_user_signup_notification: {str(e)}")
        return False
    
    
def send_user_login_notification(user, request=None):
    """
    Send notification to a user when they log in
    
    Args:
        user (User): The user who logged in
        request (HttpRequest, optional): The request object to extract IP and user agent
        
    Returns:
        bool: Success or failure
    """
    # Run this in a separate thread to prevent blocking login
    from threading import Thread
    
    def send_login_notification_async(user, request):
        try:
            if not user.email:
                logger.warning(f"No email address found for user {user.username}")
                return False
            
            # Get user settings to check if login notifications are enabled
            try:
                from core.models import UserSettings
                settings, created = UserSettings.objects.get_or_create(user=user)
                
                # Skip if login notifications are disabled in user settings
                if hasattr(settings, 'email_login_notification') and not settings.email_login_notification:
                    logger.info(f"Login notifications disabled for {user.username}")
                    return True
            except Exception as e:
                logger.warning(f"Could not check user notification settings: {str(e)}")
            
            logger.info(f"Sending login notification to {user.email}")
            
            from django.urls import reverse
            import datetime
            
            # Get the login time
            login_time = datetime.datetime.now()
            
            # Get IP address and user agent if request is provided
            ip_address = "Unknown"
            user_agent = "Unknown"
            
            if request:
                # Get IP from request
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0]
                else:
                    ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
                    
                # Get user agent
                user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
            
            # Get the site domain
            try:
                domain = os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
                if not domain:
                    # Fallback to the PUBLIC_URL or localhost
                    domain = os.environ.get('PUBLIC_URL', 'localhost:5000')
            except Exception as e:
                logger.error(f"Error getting domain: {str(e)}")
                domain = 'localhost:5000'
            
            # Construct account URL
            try:
                account_url = f"https://{domain}{reverse('profile_edit')}"
            except Exception as e:
                logger.error(f"Error constructing account URL: {str(e)}")
                account_url = "#"
            
            subject = "New Login to Your the360learning Account"
            
            # Get user role
            user_role = "Unknown"
            try:
                from core.models import UserProfile
                profile = UserProfile.objects.get(user=user)
                user_role = profile.get_role_display()
            except Exception as e:
                logger.error(f"Error getting user role: {str(e)}")
            
            # Render email template
            try:
                html_content = render_to_string('email/user_login_notification.html', {
                    'user': user,
                    'login_time': login_time,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'user_role': user_role,
                    'account_url': account_url
                })
                
                # Send the email
                result = send_email(user.email, subject, html_content)
                
                if result:
                    logger.info(f"Successfully sent login notification to {user.email}")
                else:
                    logger.error(f"Failed to send login notification to {user.email}")
                
                return result
            except Exception as e:
                logger.error(f"Error sending login notification: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error in send_login_notification_async: {str(e)}")
            return False
    
    # Start a thread to send the notification without blocking login
    try:
        thread = Thread(target=send_login_notification_async, args=(user, request))
        thread.daemon = True  # Make thread a daemon so it doesn't block application exit
        thread.start()
        return True  # Return success immediately; actual success is logged by the thread
    except Exception as e:
        logger.error(f"Error starting notification thread: {str(e)}")
        return False


def send_meeting_update_notification(meeting, recipients, update_type, changes=None, recording_url=None):
    """
    Send notification when a meeting is updated, created, cancelled, or has a recording available
    
    Args:
        meeting (VideoConference): The meeting object
        recipients (list): List of User objects to notify
        update_type (str): Type of update ('Meeting Scheduled', 'Meeting Updated', 'Meeting Cancelled', 'Recording Available')
        changes (list, optional): List of changes made to the meeting
        recording_url (str, optional): URL to the recording if available
        
    Returns:
        bool: Success or failure
    """
    if not recipients:
        logger.warning(f"No recipients specified for meeting update notification")
        return False
    
    # Convert recipients list to email addresses
    to_emails = [user.email for user in recipients if user.email]
    
    # If no valid emails, return False
    if not to_emails:
        logger.warning(f"No valid email addresses found for recipients")
        return False
    
    subject_prefixes = {
        'Meeting Scheduled': 'New Meeting:',
        'Meeting Updated': 'Meeting Updated:',
        'Meeting Cancelled': 'Meeting Cancelled:',
        'Recording Available': 'Recording Available:'
    }
    
    subject_prefix = subject_prefixes.get(update_type, 'Meeting:')
    subject = f"{subject_prefix} {meeting.title}"
    
    logger.info(f"Sending {update_type} notification for meeting '{meeting.title}' to {len(to_emails)} recipients")
    
    # Prepare individual emails for each recipient to personalize them
    success_count = 0
    for recipient in recipients:
        if not recipient.email:
            continue
        
        # Render email template
        try:
            html_content = render_to_string('email/meeting_update_notification.html', {
                'meeting': meeting,
                'recipient': recipient,
                'update_type': update_type,
                'changes': changes,
                'recording_url': recording_url
            })
            
            # Send the individual email
            if send_email(recipient.email, subject, html_content):
                success_count += 1
        except Exception as e:
            logger.error(f"Error sending meeting update to {recipient.email}: {str(e)}")
    
    if success_count > 0:
        logger.info(f"Successfully sent {update_type} notifications to {success_count} recipients")
        return True
    else:
        logger.error(f"Failed to send any {update_type} notifications")
        return False