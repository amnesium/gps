// Custom JavaScript for GPU Priority Service - Idiap Research Institute

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initializeComponents();

    // Form validation
    const forms = document.querySelectorAll('form[data-validate]');
    forms.forEach(form => {
        form.addEventListener('submit', validateForm);
    });

    // Auto-resize textareas
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        autoResize(textarea);
        textarea.addEventListener('input', function() {
            autoResize(this);
        });
    });

    // Tooltip initialization
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            html: true,
            trigger: 'hover focus'
        });
    });

    // Confirmation dialogs
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const message = this.dataset.confirm;
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

    // Loading states for forms
    const submitButtons = document.querySelectorAll('form button[type="submit"]');
    submitButtons.forEach(button => {
        const form = button.closest('form');
        if (form) {
            form.addEventListener('submit', function() {
                button.innerHTML = 'Processing...';
                button.disabled = true;
            });
        }
    });

    // Enhanced search functionality
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        const debouncedSearch = debounce(performSearch, 300);
        searchInput.addEventListener('input', debouncedSearch);
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch();
            }
        });

        // Clear search on Escape
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                clearSearch();
            }
        });
    }
});

function initializeComponents() {
    // Add loading animation to page elements
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
    });

    // Initialize priority name input validation
    const priorityNameInputs = document.querySelectorAll('input[name="priority_name"]');
    priorityNameInputs.forEach(input => {
        input.addEventListener('input', function() {
            validatePriorityName(this);
        });
    });

    // Initialize enhanced modals
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        modal.addEventListener('shown.bs.modal', function() {
            const firstInput = modal.querySelector('input, textarea, select');
            if (firstInput) firstInput.focus();
        });
    });

    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K for search focus
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }

        // Ctrl/Cmd + N for new priority (only on main pages)
        if ((e.ctrlKey || e.metaKey) && e.key === 'n' && !e.target.matches('input, textarea')) {
            e.preventDefault();
            const newPriorityLink = document.querySelector('a[href*="priority"]');
            if (newPriorityLink) {
                window.location.href = newPriorityLink.href;
            }
        }
    });
}

function validateForm(e) {
    const form = e.target;
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    const errors = [];

    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            errors.push(`${getFieldLabel(field)} is required`);
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });

    // Custom validations
    const bugzillaField = form.querySelector('#bugzilla_ticket');
    if (bugzillaField && bugzillaField.value) {
        // Updated validation for numbers only
        const bugzillaPattern = /^\d+$/;
        if (!bugzillaPattern.test(bugzillaField.value.trim())) {
            bugzillaField.classList.add('is-invalid');
            errors.push('Invalid Bugzilla ticket format. Use numbers only (e.g., 12345)');
            isValid = false;
        }
    }

    const gpuCountField = form.querySelector('#gpu_count');
    if (gpuCountField && gpuCountField.value) {
        const count = parseInt(gpuCountField.value);
        if (count < 1) {
            gpuCountField.classList.add('is-invalid');
            errors.push('GPU count must be at least 1');
            isValid = false;
        }
    }

    const durationField = form.querySelector('#duration_days');
    if (durationField && durationField.value) {
        const days = parseInt(durationField.value);
        if (days < 1 || days > 14) {
            durationField.classList.add('is-invalid');
            errors.push('Duration must be between 1 and 14 days (maximum 2 weeks)');
            isValid = false;
        }
    }

    const priorityNameField = form.querySelector('input[name="priority_name"]');
    if (priorityNameField && priorityNameField.required && priorityNameField.value) {
        if (!validatePriorityName(priorityNameField)) {
            errors.push('Priority name must contain only letters, numbers, underscores, and hyphens');
            isValid = false;
        }
    }

    if (!isValid) {
        e.preventDefault();
        showToast(errors.join('  \n'), 'error');

        // Focus on first invalid field
        const firstInvalid = form.querySelector('.is-invalid');
        if (firstInvalid) {
            firstInvalid.focus();
            firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    return isValid;
}

function validatePriorityName(field) {
    const value = field.value.trim();
    const isValid = /^[a-zA-Z0-9_-]+$/.test(value) && value.length >= 2 && value.length <= 50;

    if (value && !isValid) {
        field.classList.add('is-invalid');
        return false;
    } else {
        field.classList.remove('is-invalid');
        return true;
    }
}

function getFieldLabel(field) {
    const label = document.querySelector(`label[for="${field.id}"]`);
    return label ? label.textContent.replace('*', '').trim() : field.name;
}

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

function showToast(message, type = 'info') {
    // Remove existing toasts
    const existingToasts = document.querySelectorAll('.custom-toast');
    existingToasts.forEach(toast => toast.remove());

    // Create toast element
    const toastId = 'toast-' + Date.now();
    const iconClass = type === 'success' ? 'fa-check-circle' : 
                     type === 'error' ? 'fa-exclamation-triangle' : 
                     type === 'warning' ? 'fa-exclamation-circle' : 'fa-info-circle';

    const toastHtml = `
        <div class="toast custom-toast" id="${toastId}" role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 1050;">
            <div class="toast-header">
                <i class="fas ${iconClass} me-2"></i>
                <strong class="me-auto">Notification</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', toastHtml);

    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: type === 'error' ? 5000 : 3000
    });

    toast.show();

    // Remove toast element after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        if (toastElement.parentNode) {
            toastElement.remove();
        }
    });
}

function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction() {
        const context = this;
        const args = arguments;
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

// Export functions for global use
window.GPUPriorityService = {
    validateForm,
    autoResize,
    showToast,
    debounce,
    validatePriorityName
};
