/* ============================================================
   CareerNova-AI  -  Dashboard Functionality
   Enhanced UI Interactions & API Handling
   ============================================================ */

// Enhanced API key saving
async function saveApiKey() {
    const input = document.getElementById('api-key-input');
    const btn = event.target;
    const apiKey = input.value.trim();

    if (!apiKey) {
        showAlert('Please enter your API key', 'error');
        return;
    }

    // Add loading state
    const originalText = btn.textContent;
    btn.innerHTML = '<span class="loading-spinner"></span> Saving...';
    btn.disabled = true;

    try {
        const data = await apiFetch('/api/settings/apikey', {
            method: 'PUT',
            body: JSON.stringify({ openrouter_api_key: apiKey })
        });

        showAlert('API key saved successfully!', 'success');
        // Add success animation
        input.classList.add('success-pulse');
        setTimeout(() => input.classList.remove('success-pulse'), 1000);

    } catch (err) {
        showAlert(err.message, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// Password Change Handling
async function changePassword(event) {
    event.preventDefault();
    const currentPasswordInput = document.getElementById('current-password');
    const newPasswordInput = document.getElementById('new-password');
    const btn = document.getElementById('password-btn');

    const currentPassword = currentPasswordInput.value.trim();
    const newPassword = newPasswordInput.value.trim();

    if (!currentPassword || !newPassword) {
        showAlert('Please fill in both password fields', 'error');
        return;
    }

    if (newPassword.length < 6) {
        showAlert('New password must be at least 6 characters', 'error');
        return;
    }

    const originalText = btn.textContent;
    btn.innerHTML = '<span class="loading-spinner"></span> Updating...';
    btn.disabled = true;

    try {
        const result = await apiFetch('/api/user/change-password', {
            method: 'POST',
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        showAlert(result.message || 'Password updated successfully!', 'success');
        currentPasswordInput.value = '';
        newPasswordInput.value = '';
    } catch (err) {
        showAlert(err.message, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// Enhanced resume upload with progress
async function uploadResume(event) {
    event.preventDefault();
    const fileInput = document.getElementById('resume-file');
    const btn = document.getElementById('upload-btn');
    const progressBar = document.getElementById('upload-progress');
    const progressFill = progressBar.querySelector('.progress-fill');
    const progressText = progressBar.querySelector('.progress-text');

    if (!fileInput.files[0]) {
        showAlert('Please select a PDF file', 'error');
        return;
    }

    // Show progress bar
    progressBar.classList.remove('hidden');
    progressBar.classList.add('animate-progress');

    // Update button state
    const originalText = btn.textContent;
    btn.innerHTML = '<span class="loading-spinner"></span> Uploading...';
    btn.disabled = true;

    // Simulate progress for better UX
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress >= 90) progress = 90;
        progressFill.style.width = progress + '%';
        progressText.textContent = `Uploading... ${Math.round(progress)}%`;
    }, 200);

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        // Upload and process file in one call
        const result = await apiFetch('/api/upload', {
            method: 'POST',
            body: formData,
            headers: {} // Override to let browser set proper content-type
        });

        // Stop upload progress simulation
        clearInterval(progressInterval);
        progressFill.style.width = '100%';
        progressText.textContent = 'Complete!';

        // Complete progress
        setTimeout(() => {
            progressBar.classList.add('hidden');
            progressBar.classList.remove('animate-progress');
            progressFill.style.width = '0%';
        }, 1500);

        showAlert(result.message || 'Portfolio generated successfully!', 'success');

        // Reload to show updated status
        setTimeout(() => window.location.reload(), 1500);

    } catch (err) {
        clearInterval(progressInterval);
        progressBar.classList.add('hidden');
        showAlert(err.message, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// Enhanced portfolio deletion
async function deletePortfolio() {
    if (!confirm('Are you sure you want to delete your portfolio? This cannot be undone.')) {
        return;
    }

    try {
        await apiFetch('/api/portfolio', { method: 'DELETE' });
        showAlert('Portfolio deleted successfully', 'success');
        setTimeout(() => window.location.reload(), 1500);
    } catch (err) {
        showAlert(err.message, 'error');
    }
}

// Add dashboard-specific styles
function addDashboardStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .success-pulse {
            animation: successPulse 0.5s ease-out;
            border-color: var(--success) !important;
            box-shadow: 0 0 0 4px var(--success-glow) !important;
        }
        
        @keyframes successPulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.02); }
            100% { transform: scale(1); }
        }
        
        .animate-progress {
            animation: progressGlow 2s infinite;
        }
        
        @keyframes progressGlow {
            0%, 100% { box-shadow: 0 0 10px rgba(99,102,241,0.2); }
            50% { box-shadow: 0 0 20px rgba(99,102,241,0.4); }
        }
        
        .progress-fill {
            transition: width 0.3s ease-out;
        }
        
        /* Card hover effects */
        .dash-card {
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .dash-card:hover {
            transform: translateY(-8px) scale(1.01);
        }
        
        /* Form input enhancements */
        .form-group input:focus {
            transform: translateY(-1px);
        }
        
        /* Button hover enhancements */
        .btn-primary {
            position: relative;
            overflow: hidden;
        }
        
        .btn-primary::after {
            content: '';
            position: absolute;
            top: -50%;
            left: -60%;
            width: 20px;
            height: 200%;
            background: rgba(255,255,255,0.3);
            transform: rotate(25deg);
            transition: all 0.6s;
        }
        
        .btn-primary:hover::after {
            left: 120%;
        }
    `;
    document.head.appendChild(style);
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    addDashboardStyles();

    // Add subtle entrance animations
    const cards = document.querySelectorAll('.dash-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        setTimeout(() => {
            card.style.transition = 'all 0.6s ease-out';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 200 + (index * 100));
    });

    // Add file input styling
    const fileInput = document.getElementById('resume-file');
    if (fileInput) {
        fileInput.addEventListener('change', function () {
            if (this.files[0]) {
                const fileName = this.files[0].name;
                const label = this.nextElementSibling || this.parentNode.querySelector('label');
                if (label) {
                    label.textContent = `Selected: ${fileName}`;
                    label.style.color = 'var(--success)';
                }
            }
        });
    }
});