// Frontend logic for fetching and displaying AI Job Recommendations

document.addEventListener("DOMContentLoaded", () => {
    // Determine if we are on a portfolio page by checking the slug variable
    if (typeof PORTFOLIO_SLUG !== "undefined" && PORTFOLIO_SLUG) {
        initJobRecommendations();
    }
});

let currentJobs = [];
let isFetchingJobs = false;

function initJobRecommendations() {
    const jobsContainer = document.getElementById("ai-jobs-list");
    if (!jobsContainer) return;

    // Check if jobs are already loaded
    if (jobsContainer.children.length > 0 && !document.getElementById("jobs-loading")) {
        return;
    }

    fetchJobs();

    // Set up filter listener
    const filterBtn = document.getElementById("apply-filters-btn");
    if (filterBtn) {
        filterBtn.addEventListener("click", () => {
            fetchJobs();
        });
    }
}

async function fetchJobs() {
    if (isFetchingJobs) return;

    const container = document.getElementById("ai-jobs-list");
    if (!container) return;

    isFetchingJobs = true;
    container.innerHTML = '<div id="jobs-loading" class="loading-spinner-jobs"></div>';

    try {
        // Build query string from filters
        let url = `/api/portfolio/${PORTFOLIO_SLUG}/jobs`;
        const params = new URLSearchParams();

        const locFilter = document.getElementById("filter-location");
        if (locFilter && locFilter.value) params.append("location", locFilter.value);

        const roleFilter = document.getElementById("filter-role");
        if (roleFilter && roleFilter.value) params.append("what", roleFilter.value);

        const typeFilter = document.getElementById("filter-type");
        if (typeFilter && typeFilter.value === "remote") params.append("remote", "true");
        // No explicit support for hybrid/onsite in simplistic adzuna remote flag

        if (params.toString()) {
            url += `?${params.toString()}`;
        }

        const response = await fetch(url);
        if (!response.ok) throw new Error("Failed to fetch jobs");

        const data = await response.json();
        currentJobs = data.jobs || [];

        renderJobs();

    } catch (error) {
        console.error("Error fetching jobs:", error);
        container.innerHTML = `
            <div class="glass" style="padding: 24px; text-align: center; color: var(--error);">
                <p>Unable to load AI job recommendations at this time.</p>
                <button onclick="fetchJobs()" class="btn btn-primary" style="margin-top: 12px;">Try Again</button>
            </div>
        `;
    } finally {
        isFetchingJobs = false;
    }
}

function renderJobs() {
    const container = document.getElementById("ai-jobs-list");
    if (!container) return;

    if (currentJobs.length === 0) {
        container.innerHTML = `
            <div class="glass" style="padding: 24px; text-align: center; color: var(--text-dim);">
                <p>No matching jobs found right now based on your profile and filters.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = currentJobs.map((job, index) => {
        // Calculate match ring rotation based on score (0-100)
        // Ensure minimum 1% for visuals if score is missing
        const score = job.match_score || 0;
        const color = score >= 80 ? 'var(--success)' : (score >= 60 ? 'var(--warning, #f59e0b)' : 'var(--error, #ef4444)');

        const salaryText = (job.salary_min)
            ? `$${Math.round(job.salary_min / 1000)}k${job.salary_max ? ' - $' + Math.round(job.salary_max / 1000) + 'k' : '+'}`
            : 'Salary unlisted';

        return `
            <div class="job-card" style="animation: messageBounce ${0.3 + (index * 0.1)}s forwards; opacity: 0; transform: translateY(20px);">
                <div class="job-card-header">
                    <div>
                        <h3 class="job-title">${escapeHTML(job.title || 'Untitled Role')}</h3>
                        <div class="job-company">${escapeHTML(job.company || 'Unknown Company')}</div>
                        <div style="display: flex; gap: 16px; margin-bottom: 12px;">
                            <div class="job-location">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                                ${escapeHTML(job.location || 'Remote/Unknown')}
                            </div>
                            <div class="job-salary">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                                ${salaryText}
                            </div>
                        </div>
                    </div>
                    
                    <div class="match-ring-container" title="Match Score: ${score}%">
                        <div class="match-ring" style="--percentage: ${score}%; --success: ${color};"></div>
                        <div class="match-score">${score}%</div>
                    </div>
                </div>
                
                <div class="job-reasoning">
                    <strong>AI Note:</strong> ${escapeHTML(job.match_reason || 'Good fit for your skills.')}
                </div>
                
                <div class="job-actions">
                    <a href="${job.url}" target="_blank" rel="noopener noreferrer" class="btn-apply">
                        Apply Now
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:6px;"><path d="M5 12h14"></path><path d="M12 5l7 7-7 7"></path></svg>
                    </a>
                </div>
            </div>
        `;
    }).join("");
}

// Simple HTML escaper to prevent XSS from API data
function escapeHTML(str) {
    if (!str) return '';
    return str.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
