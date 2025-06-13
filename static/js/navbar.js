/**
 * Navigation JavaScript for the360learning Educational Platform
 * 
 * This file handles the navigation dropdowns and menu interactions
 */

// Make sure Bootstrap's dropdown plugin works properly
document.addEventListener('DOMContentLoaded', function() {
    // Initialize dropdowns manually to ensure they work across all pages
    const dropdownElementList = document.querySelectorAll('.dropdown-toggle');
    dropdownElementList.forEach(function(dropdownToggleEl) {
        // Enable dropdown without requiring data attributes
        new bootstrap.Dropdown(dropdownToggleEl);
    });

    // Fix for dropdown item clicks not working in some contexts
    const dropdownItems = document.querySelectorAll('.dropdown-item');
    dropdownItems.forEach(function(item) {
        item.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            // If it's a link with href, follow it
            if (href && href !== '#') {
                window.location.href = href;
            }
        });
    });

    // Highlight active menu items
    const currentPath = window.location.pathname;
    
    // Mark the correct nav link as active based on current URL
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    navLinks.forEach(function(link) {
        const linkUrl = link.getAttribute('href');
        if (linkUrl && currentPath.includes(linkUrl) && linkUrl !== '/') {
            link.classList.add('active');
        }
    });
    
    // Mark dropdown items as active when they match current page
    dropdownItems.forEach(function(item) {
        const itemUrl = item.getAttribute('href');
        if (itemUrl && currentPath === itemUrl) {
            item.classList.add('active');
            // Find parent dropdown toggle and mark it active too
            const parentDropdown = item.closest('.dropdown');
            if (parentDropdown) {
                const dropdownToggle = parentDropdown.querySelector('.dropdown-toggle');
                if (dropdownToggle) {
                    dropdownToggle.classList.add('active');
                }
            }
        }
    });
});