/**
 * Video Conference JavaScript for the360learning Educational Platform
 * 
 * This file handles the integration with various video conferencing platforms
 * Currently supporting integration with Zoom (including SDK), Google Meet, and Microsoft Teams
 */

class VideoConferenceManager {
    constructor() {
        this.platform = '';
        this.meetingId = '';
        this.meetingPassword = '';
        this.meetingLink = '';
        this.meetingSignature = '';
        this.participantName = '';
        this.participantEmail = '';
        this.useSDK = false;
        this.apiKey = '';
    }
    
    /**
     * Initialize the video conference 
     * @param {Object} config - Configuration object with platform details
     */
    initialize(config) {
        this.platform = config.platform || '';
        this.meetingId = config.meetingId || '';
        this.meetingPassword = config.meetingPassword || '';
        this.meetingLink = config.meetingLink || '';
        this.participantName = config.participantName || 'Guest';
        this.participantEmail = config.participantEmail || '';
        this.meetingSignature = config.signature || '';
        this.useSDK = config.useSDK || false;
        this.apiKey = config.apiKey || '';
        
        console.log(`Initializing ${this.platform} conference`);
        
        // Check if we have the necessary information
        if (!this.meetingLink && !this.meetingId) {
            this.showError('Meeting information is missing');
            return false;
        }
        
        return true;
    }
    
    /**
     * Join the video conference
     */
    joinConference() {
        if (this.platform === 'zoom') {
            this.joinZoom();
        } else if (this.platform === 'meet') {
            this.joinGoogleMeet();
        } else if (this.platform === 'teams') {
            this.joinMicrosoftTeams();
        } else {
            this.showError('Unsupported platform');
        }
    }
    
    /**
     * Join a Zoom meeting
     */
    joinZoom() {
        try {
            // Check if we should use the SDK interface
            if (this.useSDK && this.meetingId && this.meetingSignature) {
                console.log('Using Zoom SDK to join meeting');
                this.showSuccess('Redirecting to Zoom SDK interface...');
                
                // Navigate to the SDK page
                window.location.href = `/video-conferences/join-sdk/${this.meetingId}/`;
                return;
            }
            
            // For direct linking to Zoom meetings
            if (this.meetingLink) {
                window.open(this.meetingLink, '_blank');
                return;
            }
            
            // Without the Zoom SDK, we'll use direct URL format
            let zoomUrl = `https://zoom.us/j/${this.meetingId}`;
            if (this.meetingPassword) {
                zoomUrl += `?pwd=${this.meetingPassword}`;
            }
            
            window.open(zoomUrl, '_blank');
            this.showSuccess('Opening Zoom meeting in a new tab');
        } catch (error) {
            this.showError('Error joining Zoom meeting: ' + error.message);
        }
    }
    
    /**
     * Join a Google Meet conference
     */
    joinGoogleMeet() {
        try {
            if (this.meetingLink) {
                window.open(this.meetingLink, '_blank');
                this.showSuccess('Opening Google Meet in a new tab');
                return;
            }
            
            if (this.meetingId) {
                const meetUrl = `https://meet.google.com/${this.meetingId}`;
                window.open(meetUrl, '_blank');
                this.showSuccess('Opening Google Meet in a new tab');
                return;
            }
            
            this.showError('Google Meet link or code is required');
        } catch (error) {
            this.showError('Error joining Google Meet: ' + error.message);
        }
    }
    
    /**
     * Join a Microsoft Teams meeting
     */
    joinMicrosoftTeams() {
        try {
            if (this.meetingLink) {
                window.open(this.meetingLink, '_blank');
                this.showSuccess('Opening Microsoft Teams in a new tab');
                return;
            }
            
            this.showError('Microsoft Teams meeting link is required');
        } catch (error) {
            this.showError('Error joining Microsoft Teams meeting: ' + error.message);
        }
    }
    
    /**
     * Show an error message
     * @param {string} message - The error message to display
     */
    showError(message) {
        const statusElement = document.getElementById('conferenceStatus');
        if (statusElement) {
            statusElement.innerHTML = `
                <div class="alert alert-danger alert-dismissible fade show" role="alert">
                    <strong>Error:</strong> ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
        } else {
            console.error(message);
        }
    }
    
    /**
     * Show a success message
     * @param {string} message - The success message to display
     */
    showSuccess(message) {
        const statusElement = document.getElementById('conferenceStatus');
        if (statusElement) {
            statusElement.innerHTML = `
                <div class="alert alert-success alert-dismissible fade show" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
        } else {
            console.log(message);
        }
    }
}

// Initialize the conference manager when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const joinButton = document.getElementById('joinConferenceBtn');
    
    if (joinButton) {
        const conferenceManager = new VideoConferenceManager();
        
        joinButton.addEventListener('click', function() {
            // Get conference details from data attributes
            const platform = joinButton.dataset.platform;
            const meetingId = joinButton.dataset.meetingId;
            const password = joinButton.dataset.password;
            const link = joinButton.dataset.link;
            const userName = joinButton.dataset.username || 'the360learning User';
            
            const config = {
                platform: platform,
                meetingId: meetingId,
                meetingPassword: password,
                meetingLink: link,
                participantName: userName
            };
            
            if (conferenceManager.initialize(config)) {
                conferenceManager.joinConference();
            }
        });
    }
    
    // Platform selection in the create conference form
    const platformSelect = document.getElementById('id_platform');
    const meetingIdGroup = document.getElementById('div_id_meeting_id');
    const passwordGroup = document.getElementById('div_id_meeting_password');
    const linkGroup = document.getElementById('div_id_meeting_link');
    const zoomSdkOption = document.getElementById('zoom_sdk_option');
    const zoomOAuthOption = document.getElementById('zoom_oauth_option');
    const oauthInfo = document.getElementById('oauth_info');
    const viewZoomMeetings = document.getElementById('view_zoom_meetings');
    
    // Function to check if user has Zoom OAuth connected
    function checkZoomOAuthStatus() {
        if (zoomOAuthOption) {
            fetch('/zoom/oauth/meetings/?check_only=true')
                .then(response => response.json())
                .then(data => {
                    if (data.has_token) {
                        document.getElementById('oauth_status').innerText = 'Your Zoom account is connected. You can create meetings with your account.';
                        if (viewZoomMeetings) viewZoomMeetings.style.display = 'inline-block';
                    } else {
                        document.getElementById('oauth_status').innerHTML = 'Your Zoom account is not connected. <a href="/zoom/oauth/authorize/" class="alert-link">Connect now</a> to create meetings with your account.';
                    }
                    
                    if (oauthInfo) oauthInfo.style.display = 'block';
                })
                .catch(error => {
                    console.error('Error checking Zoom OAuth status:', error);
                    if (oauthInfo) {
                        document.getElementById('oauth_status').innerText = 'Could not check Zoom OAuth status.';
                        oauthInfo.style.display = 'block';
                    }
                });
        }
    }
    
    if (platformSelect && meetingIdGroup && passwordGroup && linkGroup) {
        platformSelect.addEventListener('change', function() {
            const platform = this.value;
            
            // Show/hide fields based on platform
            if (platform === 'zoom') {
                meetingIdGroup.classList.remove('d-none');
                passwordGroup.classList.remove('d-none');
                linkGroup.classList.remove('d-none');
                
                // Show Zoom SDK option for Zoom platform
                if (zoomSdkOption) {
                    zoomSdkOption.style.display = 'block';
                }
                
                // Show Zoom OAuth option for Zoom platform
                if (zoomOAuthOption) {
                    zoomOAuthOption.style.display = 'block';
                    checkZoomOAuthStatus();
                }
            } else if (platform === 'meet') {
                meetingIdGroup.classList.remove('d-none');
                passwordGroup.classList.add('d-none');
                linkGroup.classList.remove('d-none');
                
                // Hide Zoom options for other platforms
                if (zoomSdkOption) zoomSdkOption.style.display = 'none';
                if (zoomOAuthOption) zoomOAuthOption.style.display = 'none';
                if (oauthInfo) oauthInfo.style.display = 'none';
                if (viewZoomMeetings) viewZoomMeetings.style.display = 'none';
            } else if (platform === 'teams') {
                meetingIdGroup.classList.add('d-none');
                passwordGroup.classList.add('d-none');
                linkGroup.classList.remove('d-none');
                
                // Hide Zoom options for other platforms
                if (zoomSdkOption) zoomSdkOption.style.display = 'none';
                if (zoomOAuthOption) zoomOAuthOption.style.display = 'none';
                if (oauthInfo) oauthInfo.style.display = 'none';
                if (viewZoomMeetings) viewZoomMeetings.style.display = 'none';
            }
        });
        
        // Trigger the change event to set initial state
        platformSelect.dispatchEvent(new Event('change'));
    }
    
    // Handle visibility of meeting fields and form submission with OAuth option
    const conferenceForm = document.querySelector('form');
    const useZoomOAuth = document.getElementById('use_zoom_oauth');
    const manualMeetingFields = document.getElementById('manual_meeting_fields');
    const oauthMeetingInfo = document.getElementById('oauth_meeting_info');
    
    // Function to toggle meeting fields visibility based on OAuth setting
    function toggleMeetingFieldsVisibility() {
        if (platformSelect.value === 'zoom' && useZoomOAuth && useZoomOAuth.checked) {
            // Hide manual fields when using OAuth
            if (manualMeetingFields) manualMeetingFields.style.display = 'none';
            if (oauthMeetingInfo) oauthMeetingInfo.style.display = 'block';
        } else {
            // Show manual fields when not using OAuth
            if (manualMeetingFields) manualMeetingFields.style.display = 'block';
            if (oauthMeetingInfo) oauthMeetingInfo.style.display = 'none';
        }
    }
    
    // Add listener to OAuth checkbox to toggle fields
    if (useZoomOAuth) {
        useZoomOAuth.addEventListener('change', toggleMeetingFieldsVisibility);
        
        // Initial call to set visibility
        setTimeout(toggleMeetingFieldsVisibility, 100);
    }
    
    if (conferenceForm && useZoomOAuth) {
        conferenceForm.addEventListener('submit', function(e) {
            const platform = platformSelect ? platformSelect.value : '';
            
            // If Zoom selected and OAuth enabled, make sure the checkbox value is passed
            if (platform === 'zoom' && useZoomOAuth.checked) {
                // No need to intercept the form submission or change the action
                // Just ensure the hidden input is set with the same value
                // Add a hidden input to ensure the value is passed correctly
                const hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = 'use_zoom_oauth';
                hiddenInput.value = 'on';
                conferenceForm.appendChild(hiddenInput);
                
                // Let the form submit normally
                console.log('Submitting with Zoom OAuth enabled');
            }
        });
    }
});
