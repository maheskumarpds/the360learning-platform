/**
 * AI Tutor Chat Interface
 * Handles chat interactions with AJAX
 */

// Execute when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get the form and important elements
    const chatForm = document.getElementById('aiTutorForm');
    const chatContainer = document.getElementById('chatMessages');
    const questionInput = document.getElementById('id_question');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    // Mobile sidebar toggle elements
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebar = document.querySelector('.chat-sidebar');
    
    // Initialize mobile sidebar toggle
    setupMobileSidebar();

    // Setup subject dropdown interaction
    setupSubjectDropdown();
    
    // Scroll to the bottom of the chat
    scrollChatToBottom();
    
    // Focus on the input field
    if (questionInput) {
        questionInput.focus();
    }
    
    // Add an event listener for handling form submission via AJAX
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Prevent the default form submission
            
            const question = questionInput.value.trim();
            if (!question) return; // Don't submit empty questions
            
            // Get subject if present
            const subjectInput = document.getElementById('id_subject');
            const subject = subjectInput ? subjectInput.value : '';
            
            // Add the user message to the chat
            addUserMessageToChat(question);
            
            // Clear the input field
            questionInput.value = '';
            
            // Show the typing indicator
            showTypingIndicator();
            
            // Send the question to the backend
            sendQuestionToServer(question, subject);
        });
    }
    
    // Add event listener for Enter key to submit form
    if (questionInput) {
        questionInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                
                if (questionInput.value.trim() !== '') {
                    // Manually trigger the form submission
                    const event = new Event('submit', {
                        bubbles: true,
                        cancelable: true
                    });
                    chatForm.dispatchEvent(event);
                }
            }
        });
    }
    
    // Setup click handlers for suggested questions
    const suggestionButtons = document.querySelectorAll('.suggestion-btn');
    if (suggestionButtons.length > 0) {
        suggestionButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                questionInput.value = this.textContent.trim();
                chatForm.dispatchEvent(new Event('submit', {
                    bubbles: true,
                    cancelable: true
                }));
            });
        });
    }
    
    /**
     * Send the question to the server via AJAX
     */
    function sendQuestionToServer(question, subject) {
        // Prepare form data
        const formData = new FormData();
        formData.append('question', question);
        if (subject) {
            formData.append('subject', subject);
        }
        
        // Use Fetch API to make the AJAX request
        fetch('/ai-tutor/ajax-chat/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Server responded with an error');
            }
            return response.json();
        })
        .then(data => {
            // Remove the typing indicator
            removeTypingIndicator();
            
            // Update the message ID for the user's message if available
            if (data.question_id) {
                const tempMessageEl = document.querySelector('.chat-question:last-of-type');
                if (tempMessageEl) {
                    tempMessageEl.id = `message-${data.question_id}`;
                    const editButton = tempMessageEl.querySelector('.btn-message-action');
                    if (editButton) {
                        editButton.setAttribute('data-message-id', data.question_id);
                        
                        // Refresh the edit listeners for the updated ID
                        setupEditButtonListeners();
                    }
                }
            }
            
            // Add the AI response to the chat with message ID if available
            addAIResponseToChat(data.response, data.timestamp, data.response_id);
        })
        .catch(error => {
            console.error('Error:', error);
            
            // Remove the typing indicator
            removeTypingIndicator();
            
            // Show an error message
            addErrorMessage('Sorry, there was an error processing your request. Please try again.');
        });
    }
    
    /**
     * Add a user message to the chat container
     */
    function addUserMessageToChat(message, questionId = 'temp-message') {
        // Format the message with current time
        const now = new Date();
        const timeString = now.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
        
        // Create the HTML for the message with accessibility improvements
        const messageHTML = `
            <div class="chat-message chat-question" id="message-${questionId}" role="article" aria-labelledby="message-sender-${questionId}" aria-describedby="message-content-${questionId}">
                <div class="message-with-avatar">
                    <div class="user-avatar" aria-hidden="true">
                        <i class="fas fa-user"></i>
                    </div>
                    <span class="visually-hidden" id="message-sender-${questionId}">You</span>
                    <div class="message-content" id="message-content-${questionId}">
                        ${message.replace(/\n/g, '<br>')}
                        <span class="chat-timestamp" aria-label="Sent at ${timeString}">${timeString}</span>
                        <div class="message-actions">
                            <button type="button" class="btn-message-action" aria-label="Edit message" data-message-id="${questionId}">
                                <i class="fas fa-pencil-alt"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Check if we need to clear the empty state message
        const emptyState = chatContainer.querySelector('.text-center.py-5');
        if (emptyState) {
            chatContainer.innerHTML = '';
        }
        
        // Add the message to the chat
        chatContainer.insertAdjacentHTML('beforeend', messageHTML);
        
        // Setup edit button listener
        setupEditButtonListeners();
        
        // Scroll to bottom
        scrollChatToBottom();
        
        return questionId;
    }
    
    /**
     * Add an AI response to the chat container
     */
    function addAIResponseToChat(message, timestamp, responseId) {
        // Create the HTML for the message with accessibility improvements and action buttons
        const messageHTML = `
            <div class="chat-message chat-answer" id="message-${responseId}" role="article" aria-labelledby="message-sender-${responseId}" aria-describedby="message-content-${responseId}">
                <div class="message-with-avatar">
                    <div class="ai-avatar" aria-hidden="true">
                        <i class="fas fa-robot"></i>
                    </div>
                    <span class="visually-hidden" id="message-sender-${responseId}">AI Tutor</span>
                    <div class="message-content" id="message-content-${responseId}">
                        ${message.replace(/\n/g, '<br>')}
                        <span class="chat-timestamp" aria-label="Sent at ${timestamp || getCurrentTimeString()}">${timestamp || getCurrentTimeString()}</span>
                        <div class="message-actions">
                            <button type="button" class="btn-message-action" aria-label="Copy response" data-message-id="${responseId}">
                                <i class="fas fa-copy"></i>
                            </button>
                            <button type="button" class="btn-thread-reply" aria-label="Reply in thread" data-message-id="${responseId}">
                                <i class="fas fa-reply"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add the message to the chat
        chatContainer.insertAdjacentHTML('beforeend', messageHTML);
        
        // Setup action listeners for the new message
        setupThreadReplyListeners();
        setupCopyButtonListeners();
        
        // Scroll to bottom
        scrollChatToBottom();
    }
    
    /**
     * Show a typing indicator in the chat
     */
    function showTypingIndicator() {
        // Create typing indicator if not already present
        if (!document.getElementById('typingIndicator')) {
            // Add the CSS for the typing animation if needed
            if (!document.getElementById('typingIndicatorStyle')) {
                const style = document.createElement('style');
                style.id = 'typingIndicatorStyle';
                style.textContent = `
                    .typing-indicator {
                        padding: 6px 10px;
                        display: inline-flex;
                    }
                    
                    .typing-indicator span {
                        height: 8px;
                        width: 8px;
                        background-color: #10a37f;
                        border-radius: 50%;
                        display: inline-block;
                        margin: 0 2px;
                        opacity: 0.8;
                        animation: typing 1.3s infinite;
                    }
                    
                    .typing-indicator span:nth-child(2) {
                        animation-delay: 0.15s;
                    }
                    
                    .typing-indicator span:nth-child(3) {
                        animation-delay: 0.3s;
                    }
                    
                    @keyframes typing {
                        0%, 100% {
                            transform: translateY(0);
                            opacity: 0.8;
                        }
                        50% {
                            transform: translateY(-5px);
                            opacity: 0.5;
                        }
                    }
                `;
                document.head.appendChild(style);
            }
            
            // Create and add the typing indicator
            const indicatorHTML = `
                <div class="chat-message chat-answer" id="typingIndicator">
                    <div class="message-with-avatar">
                        <div class="ai-avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div class="message-content">
                            <div class="typing-indicator">
                                <span></span><span></span><span></span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            chatContainer.insertAdjacentHTML('beforeend', indicatorHTML);
            scrollChatToBottom();
        }
    }
    
    /**
     * Remove the typing indicator from the chat
     */
    function removeTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    /**
     * Add an error message to the chat
     */
    function addErrorMessage(message) {
        const errorHTML = `
            <div class="chat-message chat-error">
                <div class="message-with-avatar">
                    <div class="ai-avatar">
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                    <div class="message-content alert alert-danger py-2 px-3 m-0">
                        ${message}
                    </div>
                </div>
            </div>
        `;
        
        chatContainer.insertAdjacentHTML('beforeend', errorHTML);
        scrollChatToBottom();
    }
    
    /**
     * Setup the subject dropdown interactions
     */
    function setupSubjectDropdown() {
        const dropdownItems = document.querySelectorAll('#subjectDropdown + .dropdown-menu .dropdown-item');
        const subjectInput = document.getElementById('id_subject');
        const currentSubject = document.getElementById('currentSubject');
        
        if (dropdownItems.length > 0 && subjectInput && currentSubject) {
            dropdownItems.forEach(item => {
                item.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const subjectId = this.getAttribute('data-subject');
                    subjectInput.value = subjectId || '';
                    currentSubject.textContent = subjectId ? this.textContent : 'General';
                });
            });
        }
    }
    
    /**
     * Scroll the chat container to the bottom
     */
    function scrollChatToBottom() {
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    }
    
    /**
     * Get the current time as a formatted string
     */
    function getCurrentTimeString() {
        const now = new Date();
        return now.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
    }
    
    /**
     * Set up thread reply button listeners
     */
    function setupThreadReplyListeners() {
        document.querySelectorAll('.btn-thread-reply').forEach(btn => {
            if (!btn.hasAttribute('data-listener-attached')) {
                btn.setAttribute('data-listener-attached', 'true');
                
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    const messageId = this.getAttribute('data-message-id');
                    const messageEl = document.getElementById(`message-${messageId}`);
                    
                    // Check if thread replies container exists, if not create it
                    let threadRepliesEl = messageEl.querySelector('.thread-replies');
                    if (!threadRepliesEl) {
                        threadRepliesEl = document.createElement('div');
                        threadRepliesEl.className = 'thread-replies';
                        threadRepliesEl.id = `thread-${messageId}`;
                        messageEl.appendChild(threadRepliesEl);
                    }
                    
                    // Check if reply form already exists
                    if (threadRepliesEl.querySelector('.thread-reply-form')) {
                        return; // Form already visible
                    }
                    
                    // Create reply form
                    const formHTML = `
                        <div class="thread-reply-form">
                            <textarea class="thread-reply-textarea" placeholder="Add your reply to this thread..."></textarea>
                            <div class="thread-reply-actions">
                                <button type="button" class="thread-reply-cancel">Cancel</button>
                                <button type="button" class="thread-reply-submit">Reply</button>
                            </div>
                        </div>
                    `;
                    
                    // Add form to thread replies
                    threadRepliesEl.insertAdjacentHTML('beforeend', formHTML);
                    
                    // Focus textarea
                    const textarea = threadRepliesEl.querySelector('.thread-reply-textarea');
                    textarea.focus();
                    
                    // Handle cancel
                    threadRepliesEl.querySelector('.thread-reply-cancel').addEventListener('click', function() {
                        threadRepliesEl.querySelector('.thread-reply-form').remove();
                    });
                    
                    // Handle submit
                    threadRepliesEl.querySelector('.thread-reply-submit').addEventListener('click', function() {
                        const replyContent = textarea.value.trim();
                        if (replyContent) {
                            // Remove form
                            threadRepliesEl.querySelector('.thread-reply-form').remove();
                            
                            // Add "thinking" indicator
                            const typingIndicatorHTML = `
                                <div class="thread-message thread-ai-typing">
                                    <div class="thread-header">
                                        <div class="thread-avatar thread-user">
                                            <i class="fas fa-user"></i>
                                        </div>
                                        <div class="thread-name">You</div>
                                    </div>
                                    <div class="typing-indicator">
                                        <span></span><span></span><span></span>
                                    </div>
                                </div>
                            `;
                            threadRepliesEl.insertAdjacentHTML('beforeend', typingIndicatorHTML);
                            
                            // Get CSRF token
                            const csrfTokenEl = document.querySelector('[name=csrfmiddlewaretoken]');
                            const csrfToken = csrfTokenEl ? csrfTokenEl.value : '';
                            
                            // Submit thread reply to server
                            const formData = new FormData();
                            formData.append('parent_message_id', messageId);
                            formData.append('content', replyContent);
                            formData.append('csrfmiddlewaretoken', csrfToken);
                            
                            fetch('/ai-tutor/thread-reply/', {
                                method: 'POST',
                                headers: {
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'X-CSRFToken': csrfToken
                                },
                                body: formData
                            })
                            .then(response => response.json())
                            .then(data => {
                                // Remove thinking indicator
                                const typingIndicator = threadRepliesEl.querySelector('.thread-ai-typing');
                                if (typingIndicator) {
                                    typingIndicator.remove();
                                }
                                
                                if (data.success) {
                                    // Add the thread messages
                                    const userReplyHTML = `
                                        <div class="thread-message thread-user-message" id="thread-message-${data.thread.user_reply.id}">
                                            <div class="thread-header">
                                                <div class="thread-avatar thread-user">
                                                    <i class="fas fa-user"></i>
                                                </div>
                                                <div class="thread-name">You</div>
                                            </div>
                                            <div class="thread-content">${data.thread.user_reply.content.replace(/\n/g, '<br>')}</div>
                                            <div class="thread-timestamp">${data.thread.user_reply.timestamp}</div>
                                        </div>
                                    `;
                                    threadRepliesEl.insertAdjacentHTML('beforeend', userReplyHTML);
                                    
                                    const aiReplyHTML = `
                                        <div class="thread-message thread-ai-message" id="thread-message-${data.thread.ai_reply.id}">
                                            <div class="thread-header">
                                                <div class="thread-avatar thread-ai">
                                                    <i class="fas fa-robot"></i>
                                                </div>
                                                <div class="thread-name">AI Tutor</div>
                                            </div>
                                            <div class="thread-content">${data.thread.ai_reply.content.replace(/\n/g, '<br>')}</div>
                                            <div class="thread-timestamp">${data.thread.ai_reply.timestamp}</div>
                                        </div>
                                    `;
                                    threadRepliesEl.insertAdjacentHTML('beforeend', aiReplyHTML);
                                    
                                    // Scroll to show the new thread
                                    threadRepliesEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                                } else {
                                    // Show error
                                    const errorHTML = `
                                        <div class="thread-message thread-error">
                                            <div class="thread-content">Error: ${data.error}</div>
                                        </div>
                                    `;
                                    threadRepliesEl.insertAdjacentHTML('beforeend', errorHTML);
                                }
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                
                                // Remove thinking indicator
                                const typingIndicator = threadRepliesEl.querySelector('.thread-ai-typing');
                                if (typingIndicator) {
                                    typingIndicator.remove();
                                }
                                
                                // Show error
                                const errorHTML = `
                                    <div class="thread-message thread-error">
                                        <div class="thread-content">An error occurred. Please try again.</div>
                                    </div>
                                `;
                                threadRepliesEl.insertAdjacentHTML('beforeend', errorHTML);
                            });
                        }
                    });
                });
            }
        });
    }
    
    /**
     * Set up copy button listeners
     */
    function setupCopyButtonListeners() {
        document.querySelectorAll('.btn-message-action').forEach(btn => {
            if (btn.getAttribute('aria-label') === 'Copy response' && !btn.hasAttribute('data-listener-attached')) {
                btn.setAttribute('data-listener-attached', 'true');
                
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    const messageId = this.getAttribute('data-message-id');
                    const messageEl = document.getElementById(`message-${messageId}`);
                    const contentEl = messageEl.querySelector('.message-content');
                    
                    // Get content without timestamp and buttons
                    let contentText = contentEl.innerHTML;
                    contentText = contentText.split('<span class="chat-timestamp">')[0];
                    contentText = contentText.replace(/<br>/g, '\n').replace(/<[^>]*>/g, '').trim();
                    
                    // Copy to clipboard
                    navigator.clipboard.writeText(contentText)
                        .then(() => {
                            // Show success feedback
                            const originalIcon = this.innerHTML;
                            this.innerHTML = '<i class="fas fa-check"></i>';
                            this.style.color = '#10a37f';
                            
                            // Reset after 2 seconds
                            setTimeout(() => {
                                this.innerHTML = originalIcon;
                                this.style.color = '';
                            }, 2000);
                        })
                        .catch(error => {
                            console.error('Error copying text: ', error);
                            alert('Failed to copy response to clipboard');
                        });
                });
            }
        });
    }
    
    /**
     * Set up edit button listeners
     */
    function setupEditButtonListeners() {
        document.querySelectorAll('.btn-message-action').forEach(btn => {
            if (btn.getAttribute('aria-label') === 'Edit message' && !btn.hasAttribute('data-listener-attached')) {
                btn.setAttribute('data-listener-attached', 'true');
                
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    const messageId = this.getAttribute('data-message-id');
                    const messageEl = document.getElementById(`message-${messageId}`);
                    const contentEl = messageEl.querySelector('.message-content');
                    
                    // Skip if this is a temporary message
                    if (messageId === 'temp-message') {
                        return;
                    }
                    
                    // Get content without timestamp and buttons
                    let contentText = contentEl.innerHTML;
                    contentText = contentText.split('<span class="chat-timestamp">')[0];
                    contentText = contentText.replace(/<br>/g, '\n').replace(/<[^>]*>/g, '').trim();
                    
                    // Create edit form
                    const formHTML = `
                        <div class="edit-message-form">
                            <textarea class="edit-message-textarea">${contentText}</textarea>
                            <div class="edit-message-actions">
                                <button type="button" class="edit-message-cancel">Cancel</button>
                                <button type="button" class="edit-message-save">Save & Submit</button>
                            </div>
                        </div>
                    `;
                    
                    // Store original content
                    contentEl.setAttribute('data-original-content', contentEl.innerHTML);
                    
                    // Replace content with form
                    contentEl.innerHTML = formHTML;
                    
                    // Focus textarea
                    const textarea = contentEl.querySelector('.edit-message-textarea');
                    textarea.focus();
                    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
                    
                    // Handle cancel
                    contentEl.querySelector('.edit-message-cancel').addEventListener('click', function() {
                        contentEl.innerHTML = contentEl.getAttribute('data-original-content');
                    });
                    
                    // Handle save
                    contentEl.querySelector('.edit-message-save').addEventListener('click', function() {
                        const newContent = textarea.value.trim();
                        if (newContent) {
                            // Set "Editing..." status
                            contentEl.innerHTML = `
                                <p>${newContent}</p>
                                <div class="typing-indicator edit-indicator">
                                    <span></span><span></span><span></span>
                                </div>
                            `;
                            
                            // Get CSRF token
                            const csrfTokenEl = document.querySelector('[name=csrfmiddlewaretoken]');
                            const csrfToken = csrfTokenEl ? csrfTokenEl.value : '';
                            
                            // Prepare data for submission
                            const formData = new FormData();
                            formData.append('message_id', messageId);
                            formData.append('content', newContent);
                            formData.append('csrfmiddlewaretoken', csrfToken);
                            
                            // Send edit to server
                            fetch('/ai-tutor/edit-message/', {
                                method: 'POST',
                                headers: {
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'X-CSRFToken': csrfToken
                                },
                                body: formData
                            })
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    // Update the current message
                                    contentEl.innerHTML = `
                                        <p>${data.edited_message.content}</p>
                                        <span class="chat-timestamp">${data.edited_message.timestamp}</span>
                                        <span class="edited-indicator">(edited)</span>
                                        <div class="message-actions">
                                            <button type="button" class="btn-message-action" aria-label="Edit message" data-message-id="${messageId}">
                                                <i class="fas fa-pencil-alt"></i>
                                            </button>
                                        </div>
                                    `;
                                    
                                    // Remove all subsequent messages that were deleted on server
                                    data.deleted_message_ids.forEach(id => {
                                        const deletedMessageEl = document.getElementById(`message-${id}`);
                                        if (deletedMessageEl) {
                                            deletedMessageEl.remove();
                                        }
                                    });
                                    
                                    // Add the new AI response
                                    addAIResponseToChat(data.new_response.content, data.new_response.timestamp, data.new_response.id);
                                    
                                    // Setup edit button listener for the updated message
                                    setupEditButtonListeners();
                                } else {
                                    // Restore original content on error
                                    contentEl.innerHTML = contentEl.getAttribute('data-original-content');
                                    
                                    // Show error
                                    alert('Error: ' + data.error);
                                }
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                
                                // Restore original content
                                contentEl.innerHTML = contentEl.getAttribute('data-original-content');
                                
                                // Show error
                                alert('An error occurred while editing the message.');
                            });
                        }
                    });
                });
            }
        });
    }
    
    /**
     * Set up the mobile sidebar toggle functionality
     */
    function setupMobileSidebar() {
        if (sidebarToggle && sidebar && sidebarOverlay) {
            // Toggle sidebar when the button is clicked
            sidebarToggle.addEventListener('click', function() {
                sidebar.classList.toggle('active');
                sidebarOverlay.classList.toggle('active');
                document.body.classList.toggle('sidebar-open');
            });
            
            // Close sidebar when clicking on the overlay
            sidebarOverlay.addEventListener('click', function() {
                sidebar.classList.remove('active');
                sidebarOverlay.classList.remove('active');
                document.body.classList.remove('sidebar-open');
            });
            
            // Close sidebar when clicking on a history item (mobile only)
            const historyItems = document.querySelectorAll('.chat-history-item a');
            if (historyItems.length > 0) {
                historyItems.forEach(item => {
                    item.addEventListener('click', function() {
                        // Only on mobile devices
                        if (window.innerWidth <= 768) {
                            setTimeout(() => {
                                sidebar.classList.remove('active');
                                sidebarOverlay.classList.remove('active');
                                document.body.classList.remove('sidebar-open');
                            }, 150);
                        }
                    });
                });
            }
            
            // Add keyboard shortcut to toggle sidebar (/) - like ChatGPT
            document.addEventListener('keydown', function(e) {
                // Slash key to focus on text input
                if (e.key === '/' && !e.ctrlKey && !e.altKey && 
                    !document.querySelector('input:focus, textarea:focus')) {
                    e.preventDefault();
                    questionInput && questionInput.focus();
                }
                
                // Escape key to close sidebar on mobile
                if (e.key === 'Escape' && window.innerWidth <= 768) {
                    sidebar.classList.remove('active');
                    sidebarOverlay.classList.remove('active');
                    document.body.classList.remove('sidebar-open');
                }
            });
        }
    }
});