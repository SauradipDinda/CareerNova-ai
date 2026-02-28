/* ============================================================
   CareerNova-AI  -  Premium SaaS Theme System & Utilities
   ============================================================ */

// Theme System
class ThemeManager {
    constructor() {
        this.currentTheme = this.getStoredTheme() || this.getSystemTheme();
        this.init();
    }

    getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    getStoredTheme() {
        return localStorage.getItem('theme');
    }

    setStoredTheme(theme) {
        localStorage.setItem('theme', theme);
    }

    applyTheme(theme) {
        document.documentElement.classList.add('theme-transition');
        document.documentElement.setAttribute('data-theme', theme);

        // Update theme toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
        }

        // Remove transition class after animation completes
        setTimeout(() => {
            document.documentElement.classList.remove('theme-transition');
        }, 500);
    }

    toggleTheme() {
        const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        this.currentTheme = newTheme;
        this.setStoredTheme(newTheme);
        this.applyTheme(newTheme);
    }

    init() {
        this.applyTheme(this.currentTheme);

        // Add event listener to theme toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!this.getStoredTheme()) {
                this.currentTheme = e.matches ? 'dark' : 'light';
                this.applyTheme(this.currentTheme);
            }
        });
    }
}

// Initialize theme manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});

/* --- Cookie/Token sync ---
   Ensures the access_token is always available as a cookie for
   server-side page loads, even in embedded iframe contexts where
   Set-Cookie from API responses may be blocked.                */
(function syncToken() {
    const token = localStorage.getItem('access_token');
    if (token) {
        const hasC = document.cookie.split(';').some(c => c.trim().startsWith('access_token='));
        if (!hasC) {
            document.cookie = 'access_token=' + token + '; path=/; max-age=86400; samesite=lax';
        }
    }
})();

function showAlert(message, type) {
    let box = document.getElementById('alert-box');
    if (!box) {
        box = document.createElement('div');
        box.id = 'alert-box';
        box.style.position = 'fixed';
        box.style.top = '20px';
        box.style.right = '20px';
        box.style.zIndex = '9999';
        document.body.appendChild(box);
    }

    // Clear existing classes and add new ones
    box.className = 'alert ' + type;
    box.innerHTML = `
        <span class="alert-icon">${type === 'success' ? '✅' : type === 'error' ? '❌' : '⚠️'}</span>
        <span>${message}</span>
    `;
    box.classList.remove('hidden');
    box.classList.remove('fade-out');

    // Auto hide after 5 seconds
    setTimeout(() => {
        box.classList.add('fade-out');
        setTimeout(() => box.classList.add('hidden'), 300);
    }, 5000);
}

function getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('access_token');
    if (token) {
        headers['Authorization'] = 'Bearer ' + token;
    }
    return headers;
}

async function apiFetch(url, options = {}) {
    // Handle FormData specially - don't set Content-Type header
    const isFormData = options.body instanceof FormData;

    const defaults = {
        headers: isFormData ? {} : getAuthHeaders(),
        credentials: 'include',
    };

    const merged = { ...defaults, ...options };

    // For FormData, let the browser set the proper Content-Type with boundary
    if (isFormData) {
        // Remove Content-Type from headers to let browser set it
        if (merged.headers['Content-Type']) {
            delete merged.headers['Content-Type'];
        }
    } else if (options.headers) {
        merged.headers = { ...getAuthHeaders(), ...options.headers };
    }

    let resp;
    try {
        resp = await fetch(url, merged);
    } catch (fetchError) {
        throw new Error(`Network error: ${fetchError.message}`);
    }

    let data;
    try {
        data = await resp.json();
    } catch (jsonError) {
        // If response is not JSON (e.g., HTML error page)
        const text = await resp.text();
        throw new Error(`Server error (${resp.status}): ${text.substring(0, 200)}...`);
    }

    if (!resp.ok) {
        // Handle error properly - extract detail message
        const errorMessage = data.detail || data.message || 'Request failed';
        // If detail is an array (validation errors), join them
        if (Array.isArray(errorMessage)) {
            throw new Error(errorMessage.map(e => e.msg || e).join(', '));
        }
        // If detail is an object, stringify it properly
        if (typeof errorMessage === 'object') {
            throw new Error(JSON.stringify(errorMessage));
        }
        throw new Error(errorMessage);
    }
    return data;
}

// Enhanced scroll reveal animation
function initScrollReveal() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('viewport-revealed');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    // Observe elements with data-animate attribute
    document.querySelectorAll('[data-animate]').forEach(el => {
        observer.observe(el);
    });
}

// Enhanced loading states
function setLoadingState(button, loading = true) {
    if (loading) {
        button.disabled = true;
        button.setAttribute('data-original-text', button.textContent);
        button.innerHTML = '<span class="loading-spinner"></span> Please wait...';
    } else {
        button.disabled = false;
        const originalText = button.getAttribute('data-original-text');
        if (originalText) {
            button.textContent = originalText;
        }
    }
}

// Form validation with real-time feedback
function initFormValidation() {
    const inputs = document.querySelectorAll('input[required], textarea[required]');
    inputs.forEach(input => {
        input.addEventListener('blur', function () {
            if (!this.value.trim()) {
                this.classList.add('invalid');
            } else {
                this.classList.remove('invalid');
                this.classList.add('valid');
            }
        });

        input.addEventListener('input', function () {
            if (this.value.trim()) {
                this.classList.remove('invalid');
                this.classList.add('valid');
            } else {
                this.classList.remove('valid');
            }
        });
    });
}

// Dynamic Typing Effect
function initTypingEffect() {
    const typingElement = document.querySelector('.typing-text');
    if (!typingElement) return;

    const textToType = typingElement.getAttribute('data-text');
    if (!textToType) return;

    // Start with empty text
    typingElement.textContent = '';

    let charIndex = 0;
    const typeSpeed = 50; // ms per character
    const startDelay = 1500; // wait 1.5s before typing starts (after hero stagger)

    setTimeout(() => {
        const typeInterval = setInterval(() => {
            if (charIndex < textToType.length) {
                typingElement.textContent += textToType.charAt(charIndex);
                charIndex++;
            } else {
                clearInterval(typeInterval);
            }
        }, typeSpeed);
    }, startDelay);
}

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initScrollReveal();
    initFormValidation();
    initTypingEffect();

    // Add loading spinner styles
    const style = document.createElement('style');
    style.textContent = `
        .loading-spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid transparent;
            border-top: 2px solid currentColor;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        input.invalid {
            border-color: var(--danger) !important;
            box-shadow: 0 0 0 4px var(--danger-glow) !important;
        }
        input.valid {
            border-color: var(--success) !important;
            box-shadow: 0 0 0 4px var(--success-glow) !important;
        }
    `;
    document.head.appendChild(style);
});

/* Auth form handler */
async function handleAuth(e) {
    e.preventDefault();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const btn = document.getElementById('auth-btn');

    const isSignup = typeof AUTH_MODE !== 'undefined' && AUTH_MODE === 'signup';
    const url = isSignup ? '/api/signup' : '/api/login';
    const body = { username, password };

    if (isSignup) {
        const emailEl = document.getElementById('email');
        if (emailEl) body.email = emailEl.value.trim();
    }

    setLoadingState(btn, true);

    try {
        const data = await apiFetch(url, { method: 'POST', body: JSON.stringify(body) });
        if (data.token) {
            localStorage.setItem('access_token', data.token);
            document.cookie = 'access_token=' + data.token + '; path=/; max-age=86400; samesite=lax';
        }
        window.location.href = '/dashboard';
    } catch (err) {
        showAlert(err.message, 'error');
        setLoadingState(btn, false);
    }
}

async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST', credentials: 'include' });
    } catch (e) { /* ignore */ }
    localStorage.removeItem('access_token');
    document.cookie = 'access_token=; path=/; max-age=0';
    window.location.href = '/';
}

async function exportPortfolioPPT(slug, btn) {
    if (!btn) return;

    const originalText = btn.innerHTML;
    btn.classList.add('btn-export-loading');

    try {
        const response = await fetch(`/api/portfolio/${slug}/export/ppt`, {
            method: 'GET',
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            let errorMsg = 'Failed to generate presentation';
            try {
                const errData = await response.json();
                if (errData.detail) errorMsg = typeof errData.detail === 'string' ? errData.detail : 'Request failed';
            } catch (e) { }
            throw new Error(errorMsg);
        }

        // Handle file download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        // Try to get filename from content-disposition header if available
        const disposition = response.headers.get('content-disposition');
        let filename = `${slug}_Portfolio.pptx`;
        if (disposition && disposition.includes('filename=')) {
            const matches = /filename="([^"]+)"/.exec(disposition);
            if (matches && matches[1]) filename = matches[1];
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        btn.classList.remove('btn-export-loading');

        if (typeof showAlert === 'function') {
            showAlert('Your Portfolio Presentation is Ready.', 'success');
        } else {
            alert('Your Portfolio Presentation is Ready.');
        }

    } catch (err) {
        btn.classList.remove('btn-export-loading');
        if (typeof showAlert === 'function') {
            showAlert(err.message, 'error');
        } else {
            alert('Error: ' + err.message);
        }
    }
}

async function exportAtsResume(slug, btnId) {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    const originalText = btn.innerHTML;
    btn.classList.add('btn-export-loading');

    try {
        const response = await fetch(`/api/portfolio/${slug}/export/docx`, {
            method: 'GET',
            headers: getAuthHeaders() // this attaches the token if available
        });

        if (!response.ok) {
            let errorMsg = 'Failed to generate resume';
            try {
                const errData = await response.json();
                if (errData.detail) errorMsg = typeof errData.detail === 'string' ? errData.detail : 'Request failed';
            } catch (e) { }
            throw new Error(errorMsg);
        }

        // Handle file download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        // Try to get filename from content-disposition header if available
        const disposition = response.headers.get('content-disposition');
        let filename = `${slug}_ATS_Resume.docx`;
        if (disposition && disposition.includes('filename=')) {
            const matches = /filename="([^"]+)"/.exec(disposition);
            if (matches && matches[1]) filename = matches[1];
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        btn.classList.remove('btn-export-loading');

        if (typeof showAlert === 'function') {
            showAlert('Your ATS-Optimized Resume is Ready.', 'success');
        } else {
            alert('Your ATS-Optimized Resume is Ready.');
        }

    } catch (err) {
        btn.classList.remove('btn-export-loading');
        if (typeof showAlert === 'function') {
            showAlert(err.message, 'error');
        } else {
            alert(err.message);
        }
    } finally {
        setLoadingState(btn, false);
    }
}
