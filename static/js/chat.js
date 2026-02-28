/* ============================================================
   CareerNova-AI  -  Premium Chat Experience
   Enhanced AI Interactions & Animations
   ============================================================ */

const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
let conversationHistory = [];

// Enhanced bubble creation with animations
function appendBubble(text, role) {
    const div = document.createElement('div');
    div.className = `chat-bubble ${role}`;

    // Add typing effect for bot messages
    if (role === 'bot') {
        div.innerHTML = '<div class="markdown-body typing-text"></div>';
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Simulate typing effect
        let parsedText = typeof marked !== 'undefined' ? marked.parse(text) : escapeHtml(text);
        typeHtmlContent(div.querySelector('.typing-text'), parsedText, 10);
    } else {
        div.innerHTML = `<p>${escapeHtml(text)}</p>`;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Add subtle entrance animation
        div.style.opacity = '0';
        div.style.transform = 'translateY(10px)';
        setTimeout(() => {
            div.style.transition = 'all 0.3s ease-out';
            div.style.opacity = '1';
            div.style.transform = 'translateY(0)';
        }, 10);
    }
}

// Typing animation for HTML content
function typeHtmlContent(element, htmlContent, delay = 10) {
    element.innerHTML = htmlContent;

    // Instead of literally typing out HTML tags which breaks rendering,
    // we just fade the element in for HTML content to keep it simple and clean.
    element.style.opacity = '0';
    element.style.transition = 'opacity 0.5s ease-in';

    setTimeout(() => {
        element.style.opacity = '1';
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 50);
}

function showTyping() {
    const el = document.createElement('div');
    el.className = 'typing-indicator';
    el.id = 'typing';
    el.innerHTML = '<span></span><span></span><span></span>';

    // Add entrance animation
    el.style.opacity = '0';
    el.style.transform = 'translateY(10px)';

    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Animate in
    setTimeout(() => {
        el.style.transition = 'all 0.3s ease-out';
        el.style.opacity = '1';
        el.style.transform = 'translateY(0)';
    }, 10);
}

function hideTyping() {
    const el = document.getElementById('typing');
    if (el) {
        // Animate out
        el.style.transition = 'all 0.2s ease-out';
        el.style.opacity = '0';
        el.style.transform = 'translateY(-10px)';
        setTimeout(() => el.remove(), 200);
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// -----------------------------------------------------------------------------
// Chat Panel Visibility Toggling
// -----------------------------------------------------------------------------
function toggleChat() {
    const container = document.getElementById('chat-panel-container');
    if (container.classList.contains('collapsed')) {
        container.classList.remove('collapsed');
        setTimeout(() => {
            const input = document.getElementById('chat-input');
            if (input) input.focus();
        }, 300); // wait for animation
    } else {
        container.classList.add('collapsed');
    }
}

// Enhanced message sending with loading states
async function sendMessage(e) {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    // Add user message immediately
    appendBubble(message, 'user');
    conversationHistory.push({ role: 'user', content: message });

    // Clear input and disable
    chatInput.value = '';
    chatSend.disabled = true;
    setLoadingState(true);

    // Show typing indicator
    showTyping();

    try {
        const resp = await fetch('/api/chat/' + PORTFOLIO_SLUG, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                message: message,
                history: conversationHistory.slice(-6).map(msg => ({ role: msg.role, content: msg.content })),
            }),
        });

        const data = await resp.json();
        hideTyping();

        if (!resp.ok) {
            appendBubble(data.detail || 'Something went wrong. Please try again.', 'bot');
        } else {
            // Add bot response to history
            conversationHistory.push({ role: 'assistant', content: data.answer });
            // Display bot response
            appendBubble(data.answer, 'bot');

            // Update Mode Indicator
            if (data.mode) {
                updateChatModeIndicator(data.mode);
            }
        }
    } catch (err) {
        hideTyping();
        appendBubble('Network error. Please try again.', 'bot');
    } finally {
        // Re-enable input
        chatSend.disabled = false;
        setLoadingState(false);
        chatInput.focus();
    }
}

// Enhanced loading state for send button
function setLoadingState(loading) {
    if (loading) {
        chatSend.innerHTML = '<span class="chat-loading"></span>';
        chatSend.style.pointerEvents = 'none';
    } else {
        chatSend.innerHTML = 'Send';
        chatSend.style.pointerEvents = 'auto';
    }
}

// Auto-resize textarea
function initAutoResize() {
    chatInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
}

// Enhanced scroll behavior
function initSmoothScroll() {
    // Custom scroll behavior for chat messages
    if (chatMessages) {
        chatMessages.addEventListener('scroll', function () {
            // Add parallax effect to background elements
            const scrollPercent = this.scrollTop / (this.scrollHeight - this.clientHeight);
            document.documentElement.style.setProperty('--scroll-progress', scrollPercent);
        });
    }
}

// Add custom CSS for chat enhancements
function addChatStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .chat-loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid transparent;
            border-top: 2px solid currentColor;
            border-radius: 50%;
            animation: chatSpin 1s linear infinite;
        }
        
        @keyframes chatSpin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .typing-text {
            white-space: pre-wrap;
            min-height: 1.5em;
        }
        
        .chat-bubble {
            transition: all 0.2s ease-out;
        }
        
        .chat-bubble:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        /* Custom scrollbar for chat */
        .chat-messages::-webkit-scrollbar {
            width: 6px;
        }
        
        .chat-messages::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .chat-messages::-webkit-scrollbar-thumb {
            background: var(--glass-border);
            border-radius: 3px;
        }
        
        .chat-messages::-webkit-scrollbar-thumb:hover {
            background: var(--accent);
        }
    `;
    document.head.appendChild(style);
}

// UI Mode Indicator Update
function updateChatModeIndicator(mode) {
    const indicator = document.getElementById('chat-mode-indicator');
    const hint = document.getElementById('chat-mode-hint');
    if (!indicator || !hint) return;

    // Reset classes
    indicator.className = 'mode-indicator';

    if (mode === 'INTERVIEW') {
        indicator.classList.add('interview');
        indicator.title = "Interview Question Mode";
        hint.textContent = "I'm generating interview questions based on your profile.";
    } else if (mode === 'ATS') {
        indicator.classList.add('ats');
        indicator.title = "ATS Analysis Mode";
        hint.textContent = "I'm analyzing your resume against ATS criteria.";
    } else {
        indicator.classList.add('rag');
        indicator.title = "Resume Q&A Mode";
        hint.textContent = "Ask anything about their experience, skills, or projects.";
    }
}

// Initialize chat enhancements
document.addEventListener('DOMContentLoaded', () => {
    initAutoResize();
    initSmoothScroll();
    addChatStyles();

    // Focus input on load
    setTimeout(() => chatInput.focus(), 500);

    // Add submit on Enter (but allow Shift+Enter for new lines)
    chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!chatSend.disabled && this.value.trim()) {
                sendMessage(new Event('submit'));
            }
        }
    });
});