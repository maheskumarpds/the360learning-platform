// Simple utility to check user role in browser console
document.addEventListener('DOMContentLoaded', function() {
    // Get role from data attribute
    const userRole = document.body.getAttribute('data-user-role');
    console.log('User role detected:', userRole);
    
    // Check if management menu should be visible
    const managementMenu = document.querySelector('[data-menu-type="management"]');
    console.log('Management menu found:', managementMenu !== null);
    
    if (managementMenu) {
        console.log('Management menu display:', window.getComputedStyle(managementMenu).display);
        
        // Make sure it's really visible
        managementMenu.style.display = 'flex';
        console.log('Management menu visibility manually set to flex');
    } else {
        console.log('Menu detection failed - will try to inject it');
        
        // Failsafe approach
        const navbar = document.querySelector('.navbar-nav');
        if (navbar) {
            console.log('Found navbar, injecting management menu');
            
            // Create management menu
            const managementItem = document.createElement('li');
            managementItem.className = 'nav-item dropdown';
            managementItem.setAttribute('data-menu-type', 'management');
            
            // Determine if user is admin
            const isAdmin = document.body.getAttribute('data-user-role') === 'admin';
            const userRole = document.body.getAttribute('data-user-role');
            
            managementItem.innerHTML = `
                <a class="nav-link dropdown-toggle px-3" 
                   href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                   <i class="fas fa-cogs me-1"></i> Management
                </a>
                <ul class="dropdown-menu dropdown-menu-dark">
                    <!-- Subject Management - Available to both Admin and Teacher -->
                    <li><a class="dropdown-item" href="/subjects/">
                        <i class="fas fa-book fa-sm fa-fw me-2"></i>Subject Management
                    </a></li>
                    <li><a class="dropdown-item" href="/class-subjects/">
                        <i class="fas fa-book-reader fa-sm fa-fw me-2"></i>Class-Subject Assignments
                    </a></li>
                    
                    ${userRole === 'admin' ? `
                    <li><hr class="dropdown-divider bg-light opacity-25"></li>
                    <li><a class="dropdown-item" href="/user-management/">
                        <i class="fas fa-users-cog fa-sm fa-fw me-2"></i>User Management
                    </a></li>
                    ` : ''}
                    
                    <li><hr class="dropdown-divider bg-light opacity-25"></li>
                    <li><a class="dropdown-item" href="/materials/upload/">
                        <i class="fas fa-file-upload fa-sm fa-fw me-2"></i>Upload Study Material
                    </a></li>
                    <li><a class="dropdown-item" href="/recordings/upload/">
                        <i class="fas fa-film fa-sm fa-fw me-2"></i>Upload Recorded Session
                    </a></li>
                    <li><a class="dropdown-item" href="/assignments/create/">
                        <i class="fas fa-tasks fa-sm fa-fw me-2"></i>Create Assignment
                    </a></li>
                    <li><a class="dropdown-item" href="/quizzes/create/">
                        <i class="fas fa-question fa-sm fa-fw me-2"></i>Create Quiz
                    </a></li>
                    <li><a class="dropdown-item" href="/video-conferences/create/">
                        <i class="fas fa-calendar-plus fa-sm fa-fw me-2"></i>Schedule Conference
                    </a></li>
                </ul>
            `;
            
            // Insert before AI Tutor menu
            const aiTutorMenu = document.querySelector('.navbar-nav li:nth-child(4)');
            if (aiTutorMenu) {
                navbar.insertBefore(managementItem, aiTutorMenu);
                console.log('Management menu injected before AI Tutor menu');
            } else {
                navbar.appendChild(managementItem);
                console.log('Management menu appended to navbar');
            }
        }
    }
});