/**
 * Main JavaScript for the360learning Educational Platform
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Sidebar toggle functionality (for mobile)
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            document.querySelector('.sidebar').classList.toggle('show');
        });
    }
    
    // Search form functionality
    const searchForm = document.getElementById('searchForm');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const searchInput = document.getElementById('searchInput');
            if (searchInput.value.trim() === '') {
                e.preventDefault();
                searchInput.classList.add('is-invalid');
            } else {
                searchInput.classList.remove('is-invalid');
            }
        });
    }
    
    // File type preview functionality
    const materialTypeSelect = document.getElementById('id_file_type');
    const fileUrlInput = document.getElementById('id_file_url');
    
    if (materialTypeSelect && fileUrlInput) {
        // Preview based on file type
        const previewContainer = document.createElement('div');
        previewContainer.id = 'filePreview';
        previewContainer.classList.add('mt-3', 'd-none');
        fileUrlInput.parentNode.appendChild(previewContainer);
        
        // Update preview when URL changes
        fileUrlInput.addEventListener('blur', function() {
            updatePreview(materialTypeSelect.value, fileUrlInput.value);
        });
        
        // Update preview when file type changes
        materialTypeSelect.addEventListener('change', function() {
            updatePreview(materialTypeSelect.value, fileUrlInput.value);
        });
        
        function updatePreview(fileType, url) {
            if (!url) {
                previewContainer.classList.add('d-none');
                return;
            }
            
            previewContainer.classList.remove('d-none');
            previewContainer.innerHTML = '';
            
            switch (fileType) {
                case 'img':
                    previewContainer.innerHTML = `
                        <div class="card" style="max-width: 300px;">
                            <div class="card-header">Image Preview</div>
                            <img src="${url}" class="card-img-top" alt="Preview" onerror="this.onerror=null;this.src='';this.alt='Invalid image URL';this.parentNode.querySelector('.card-header').textContent='Preview unavailable';">
                        </div>
                    `;
                    break;
                case 'vid':
                    previewContainer.innerHTML = `
                        <div class="card">
                            <div class="card-header">Video Link</div>
                            <div class="card-body">
                                <a href="${url}" target="_blank" class="btn btn-sm btn-primary">
                                    <i class="fas fa-external-link-alt"></i> Open Video
                                </a>
                            </div>
                        </div>
                    `;
                    break;
                case 'pdf':
                case 'doc':
                case 'ppt':
                    let icon = fileType === 'pdf' ? 'fa-file-pdf' : 
                              fileType === 'doc' ? 'fa-file-word' : 'fa-file-powerpoint';
                    let type = fileType === 'pdf' ? 'PDF' : 
                              fileType === 'doc' ? 'Document' : 'Presentation';
                    
                    previewContainer.innerHTML = `
                        <div class="card">
                            <div class="card-header">${type} Link</div>
                            <div class="card-body text-center">
                                <i class="fas ${icon} fa-3x mb-3 text-primary"></i>
                                <div>
                                    <a href="${url}" target="_blank" class="btn btn-sm btn-primary">
                                        <i class="fas fa-external-link-alt"></i> Open ${type}
                                    </a>
                                </div>
                            </div>
                        </div>
                    `;
                    break;
                default:
                    previewContainer.innerHTML = `
                        <div class="card">
                            <div class="card-header">File Link</div>
                            <div class="card-body">
                                <a href="${url}" target="_blank" class="btn btn-sm btn-primary">
                                    <i class="fas fa-external-link-alt"></i> Open File
                                </a>
                            </div>
                        </div>
                    `;
            }
        }
    }
    
    // Due date validation
    const dueDateInput = document.getElementById('id_due_date');
    if (dueDateInput) {
        dueDateInput.addEventListener('change', function() {
            const selectedDate = new Date(this.value);
            const now = new Date();
            
            if (selectedDate < now) {
                this.classList.add('is-invalid');
                
                // Create feedback element if it doesn't exist
                let feedback = this.nextElementSibling;
                if (!feedback || !feedback.classList.contains('invalid-feedback')) {
                    feedback = document.createElement('div');
                    feedback.classList.add('invalid-feedback');
                    this.parentNode.appendChild(feedback);
                }
                
                feedback.textContent = 'Due date should be in the future.';
            } else {
                this.classList.remove('is-invalid');
                
                // Remove feedback if it exists
                const feedback = this.nextElementSibling;
                if (feedback && feedback.classList.contains('invalid-feedback')) {
                    feedback.textContent = '';
                }
            }
        });
    }
    
    // Handle profile image preview
    const profilePictureInput = document.getElementById('id_profile_picture');
    if (profilePictureInput) {
        // Create preview element
        const previewContainer = document.createElement('div');
        previewContainer.id = 'profilePreview';
        previewContainer.classList.add('mt-3', 'd-none');
        profilePictureInput.parentNode.appendChild(previewContainer);
        
        profilePictureInput.addEventListener('blur', function() {
            const imageUrl = this.value.trim();
            
            if (imageUrl) {
                previewContainer.classList.remove('d-none');
                previewContainer.innerHTML = `
                    <div class="card" style="max-width: 150px;">
                        <div class="card-header">Profile Picture Preview</div>
                        <img src="${imageUrl}" class="card-img-top" alt="Preview" 
                             style="height: 150px; object-fit: cover;"
                             onerror="this.onerror=null;this.src='';this.alt='Invalid image URL';this.parentNode.querySelector('.card-header').textContent='Preview unavailable';">
                    </div>
                `;
            } else {
                previewContainer.classList.add('d-none');
            }
        });
    }
    
    // Initialize class selection based on role
    const roleSelect = document.getElementById('id_role');
    const classLevelGroup = document.getElementById('div_id_class_level');
    
    if (roleSelect && classLevelGroup) {
        // Set initial state
        toggleClassLevelField();
        
        // Listen for changes
        roleSelect.addEventListener('change', toggleClassLevelField);
        
        function toggleClassLevelField() {
            if (roleSelect.value === 'student') {
                classLevelGroup.classList.remove('d-none');
                document.getElementById('id_class_level').setAttribute('required', 'required');
            } else {
                classLevelGroup.classList.add('d-none');
                document.getElementById('id_class_level').removeAttribute('required');
            }
        }
    }
    
    // Add confirmation for assignment submission
    const assignmentSubmitForm = document.querySelector('form.assignment-submit-form');
    if (assignmentSubmitForm) {
        assignmentSubmitForm.addEventListener('submit', function(e) {
            const confirmed = confirm('Are you sure you want to submit this assignment? You won\'t be able to edit it after submission.');
            if (!confirmed) {
                e.preventDefault();
            }
        });
    }
    
    // Add confirmation for assignment due date that is too soon
    const assignmentForm = document.querySelector('form.assignment-form');
    if (assignmentForm) {
        assignmentForm.addEventListener('submit', function(e) {
            const dueDateInput = document.getElementById('id_due_date');
            if (dueDateInput) {
                const dueDate = new Date(dueDateInput.value);
                const now = new Date();
                const hoursDiff = (dueDate - now) / (1000 * 60 * 60);
                
                if (hoursDiff < 24) {
                    const confirmed = confirm('The due date is less than 24 hours from now. Students may not have enough time. Are you sure you want to continue?');
                    if (!confirmed) {
                        e.preventDefault();
                    }
                }
            }
        });
    }
});
