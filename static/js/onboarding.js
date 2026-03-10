/**
 * Sclera Onboarding System
 * Provides contextual, step-by-step tutorials for new users
 */

class OnboardingManager {
    constructor() {
        this.currentStep = 0;
        this.isActive = false;
        this.tutorialSteps = [];
        this.overlay = null;
        this.callout = null;
        this.hasCompletedTutorial = this.checkTutorialStatus();

        this.init();
    }

    init() {
        // Check if tutorial should start from URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('tutorial') === 'start') {
            // Remove the parameter from URL
            window.history.replaceState({}, document.title, window.location.pathname);
            // Start tutorial immediately
            setTimeout(() => this.startTutorial(), 500);
            return;
        }

        // Check if this is first visit and tutorial not completed
        const isFirstVisit = !localStorage.getItem('sclera_visited');

        if (isFirstVisit && !this.hasCompletedTutorial) {
            localStorage.setItem('sclera_visited', 'true');
            // Show welcome modal after a brief delay
            setTimeout(() => this.showWelcomeModal(), 800);
        }

        // Listen for manual tutorial start
        window.addEventListener('startTutorial', () => this.startTutorial());
    }

    checkTutorialStatus() {
        // Check both localStorage and server-side status
        const localStatus = localStorage.getItem('sclera_tutorial_completed');
        return localStatus === 'true';
    }

    showWelcomeModal() {
        const modal = document.createElement('div');
        modal.className = 'onboarding-modal-overlay';
        modal.innerHTML = `
            <div class="onboarding-modal">
                <div class="onboarding-modal-header">
                    <span class="material-symbols-outlined" style="font-size: 3rem; color: var(--accent);">school</span>
                    <h2>Welcome to Sclera!</h2>
                    <p>Your comprehensive study operating system</p>
                </div>
                <div class="onboarding-modal-body">
                    <p>Would you like a quick tour of the dashboard? We'll show you all the powerful features available to help you succeed.</p>
                    <div class="onboarding-features">
                        <div class="onboarding-feature">
                            <span class="material-symbols-outlined">trending_up</span>
                            <span>Track your progress</span>
                        </div>
                        <div class="onboarding-feature">
                            <span class="material-symbols-outlined">calendar_today</span>
                            <span>Manage your schedule</span>
                        </div>
                        <div class="onboarding-feature">
                            <span class="material-symbols-outlined">explore</span>
                            <span>Discover careers</span>
                        </div>
                        <div class="onboarding-feature">
                            <span class="material-symbols-outlined">auto_stories</span>
                            <span>Master subjects</span>
                        </div>
                    </div>
                </div>
                <div class="onboarding-modal-footer">
                    <button class="onboarding-btn onboarding-btn-secondary" onclick="onboardingManager.skipTutorial()">
                        Skip for now
                    </button>
                    <button class="onboarding-btn onboarding-btn-primary" onclick="onboardingManager.startTutorial()">
                        Start Tutorial
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Animate in
        setTimeout(() => modal.classList.add('active'), 10);
    }

    startTutorial() {
        // Close welcome modal if open
        const modal = document.querySelector('.onboarding-modal-overlay');
        if (modal) {
            modal.classList.remove('active');
            setTimeout(() => modal.remove(), 300);
        }

        // Load tutorial steps
        this.tutorialSteps = this.getTutorialSteps();
        this.currentStep = 0;
        this.isActive = true;

        // Add class to body for blur effect
        document.body.classList.add('onboarding-active');

        // Create overlay and callout elements
        this.createOverlay();
        this.createCallout();

        // Start the tour
        setTimeout(() => this.showStep(0), 500);
    }

    getTutorialSteps() {
        // Define all tutorial steps for the dashboard
        const accountType = document.body.dataset.accountType || 'student';

        if (accountType === 'student') {
            return [
                {
                    target: '.bento-profile',
                    title: 'Your Profile',
                    description: 'Access your profile settings and personal information. Click here to customize your account.',
                    position: 'bottom'
                },
                {
                    target: '.bento-streak',
                    title: 'Study Streak',
                    description: 'Track your daily study consistency. Build momentum by studying every day to maintain your streak!',
                    position: 'bottom'
                },
                {
                    target: '.bento-explore',
                    title: 'Career Exploration',
                    description: 'Discover career paths that match your interests. Explore different fields and plan your future.',
                    position: 'bottom'
                },
                {
                    target: '.bento-perf',
                    title: 'Analytics Dashboard',
                    description: 'View detailed insights about your study patterns, time spent, and performance trends over time.',
                    position: 'bottom'
                },
                {
                    target: '.bento-academic',
                    title: 'Academic Progress',
                    description: 'Monitor your overall academic progress across all subjects. See completion rates and chapter statistics.',
                    position: 'right'
                },
                {
                    target: '.bento-schedule',
                    title: 'Calendar',
                    description: 'Manage your schedule, view upcoming events, and plan your study sessions effectively.',
                    position: 'left'
                },
                {
                    target: '.bento-tasks',
                    title: 'Task Management',
                    description: 'Create, track, and complete tasks. Stay organized and boost your productivity.',
                    position: 'top'
                },
                {
                    target: '.bento-subjects',
                    title: 'Subject Mastery',
                    description: 'Track progress in individual subjects. See detailed breakdowns of your mastery in each area.',
                    position: 'top'
                },
                // Navigation items
                {
                    target: 'a[href*="/dashboard"]',
                    title: 'Home',
                    description: 'Return to this main dashboard view anytime to see your overview.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: 'a[href*="/calendar"]',
                    title: 'Calendar View',
                    description: 'Access your full calendar with detailed event management and scheduling tools.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: 'a[href*="/academic"]',
                    title: 'Academic Dashboard',
                    description: 'Deep dive into your academic progress, syllabus, and subject-specific details.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: 'a[href*="/study-mode"]',
                    title: 'Study Mode',
                    description: 'Enter focused study sessions with timers, break reminders, and distraction-free environment.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: 'a[href*="/interests"]',
                    title: 'Career Center',
                    description: 'Explore careers, courses, and internships. Plan your professional journey.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: 'a[href*="/community"]',
                    title: 'Community',
                    description: 'Connect with other learners, share knowledge, and collaborate on projects.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: 'a[href*="/master-library"]',
                    title: 'Library',
                    description: 'Access your study materials, notes, and resources in one organized place.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: 'a[href*="/ai-assistant"]',
                    title: 'AI Assistant',
                    description: 'Get instant help with your studies. Ask questions and receive personalized guidance.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: 'a[href*="/docs"]',
                    title: 'Documentation',
                    description: 'Access help articles, guides, and tutorials to make the most of Sclera.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: 'a[href*="/statistics"]',
                    title: 'Statistics',
                    description: 'View comprehensive analytics, charts, and insights about your learning journey.',
                    position: 'bottom',
                    highlight: 'notch'
                },
                {
                    target: '#themeToggle',
                    title: 'Theme Toggle',
                    description: 'Switch between dark and light modes to match your preference.',
                    position: 'bottom',
                    highlight: 'action'
                },
                {
                    target: '.profile-btn',
                    title: 'Profile Menu',
                    description: 'Access settings, logout, and other account options from this menu.',
                    position: 'bottom',
                    highlight: 'action'
                }
            ];
        }

        return [];
    }

    createOverlay() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'onboarding-overlay';
        document.body.appendChild(this.overlay);

        // Animate in
        setTimeout(() => this.overlay.classList.add('active'), 10);
    }

    createCallout() {
        this.callout = document.createElement('div');
        this.callout.className = 'onboarding-callout';
        this.callout.innerHTML = `
            <div class="onboarding-callout-header">
                <h3 class="onboarding-callout-title"></h3>
                <button class="onboarding-callout-close" onclick="onboardingManager.endTutorial()">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>
            <div class="onboarding-callout-body">
                <p class="onboarding-callout-description"></p>
            </div>
            <div class="onboarding-callout-footer">
                <div class="onboarding-progress">
                    <span class="onboarding-progress-text">Step <span class="current-step">1</span> of <span class="total-steps">0</span></span>
                    <div class="onboarding-progress-bar">
                        <div class="onboarding-progress-fill"></div>
                    </div>
                </div>
                <div class="onboarding-callout-actions">
                    <button class="onboarding-btn onboarding-btn-secondary onboarding-btn-prev" onclick="onboardingManager.previousStep()">
                        Previous
                    </button>
                    <button class="onboarding-btn onboarding-btn-primary onboarding-btn-next" onclick="onboardingManager.nextStep()">
                        Next
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(this.callout);
    }

    showStep(stepIndex) {
        if (stepIndex < 0 || stepIndex >= this.tutorialSteps.length) {
            this.endTutorial();
            return;
        }

        this.currentStep = stepIndex;
        const step = this.tutorialSteps[stepIndex];
        const targetElement = document.querySelector(step.target);

        if (!targetElement) {
            // Skip to next step if target not found
            this.nextStep();
            return;
        }

        // Update callout content
        this.callout.querySelector('.onboarding-callout-title').textContent = step.title;
        this.callout.querySelector('.onboarding-callout-description').textContent = step.description;
        this.callout.querySelector('.current-step').textContent = stepIndex + 1;
        this.callout.querySelector('.total-steps').textContent = this.tutorialSteps.length;

        // Update progress bar
        const progress = ((stepIndex + 1) / this.tutorialSteps.length) * 100;
        this.callout.querySelector('.onboarding-progress-fill').style.width = `${progress}%`;

        // Update button states
        const prevBtn = this.callout.querySelector('.onboarding-btn-prev');
        const nextBtn = this.callout.querySelector('.onboarding-btn-next');

        prevBtn.disabled = stepIndex === 0;
        prevBtn.style.opacity = stepIndex === 0 ? '0.5' : '1';

        if (stepIndex === this.tutorialSteps.length - 1) {
            nextBtn.textContent = 'Finish';
        } else {
            nextBtn.textContent = 'Next';
        }

        // Highlight target element
        this.highlightElement(targetElement, step);

        // Position callout
        this.positionCallout(targetElement, step.position);

        // Scroll element into view
        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Animate callout in
        this.callout.classList.add('active');
    }

    highlightElement(element, step) {
        // Remove previous highlights
        document.querySelectorAll('.onboarding-highlight').forEach(el => {
            el.classList.remove('onboarding-highlight', 'onboarding-highlight-notch', 'onboarding-highlight-action');
        });

        // Add highlight to current element
        element.classList.add('onboarding-highlight');

        if (step.highlight === 'notch') {
            element.classList.add('onboarding-highlight-notch');
        } else if (step.highlight === 'action') {
            element.classList.add('onboarding-highlight-action');
        }
    }

    positionCallout(targetElement, position) {
        const targetRect = targetElement.getBoundingClientRect();
        const calloutRect = this.callout.getBoundingClientRect();
        const spacing = 20;

        let top, left;

        switch (position) {
            case 'top':
                top = targetRect.top - calloutRect.height - spacing;
                left = targetRect.left + (targetRect.width / 2) - (calloutRect.width / 2);
                this.callout.setAttribute('data-position', 'top');
                break;
            case 'bottom':
                top = targetRect.bottom + spacing;
                left = targetRect.left + (targetRect.width / 2) - (calloutRect.width / 2);
                this.callout.setAttribute('data-position', 'bottom');
                break;
            case 'left':
                top = targetRect.top + (targetRect.height / 2) - (calloutRect.height / 2);
                left = targetRect.left - calloutRect.width - spacing;
                this.callout.setAttribute('data-position', 'left');
                break;
            case 'right':
                top = targetRect.top + (targetRect.height / 2) - (calloutRect.height / 2);
                left = targetRect.right + spacing;
                this.callout.setAttribute('data-position', 'right');
                break;
            default:
                top = targetRect.bottom + spacing;
                left = targetRect.left + (targetRect.width / 2) - (calloutRect.width / 2);
                this.callout.setAttribute('data-position', 'bottom');
        }

        // Keep callout within viewport
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        if (left < spacing) left = spacing;
        if (left + calloutRect.width > viewportWidth - spacing) {
            left = viewportWidth - calloutRect.width - spacing;
        }
        if (top < spacing) top = spacing;
        if (top + calloutRect.height > viewportHeight - spacing) {
            top = viewportHeight - calloutRect.height - spacing;
        }

        this.callout.style.top = `${top}px`;
        this.callout.style.left = `${left}px`;
    }

    nextStep() {
        if (this.currentStep < this.tutorialSteps.length - 1) {
            this.callout.classList.remove('active');
            setTimeout(() => this.showStep(this.currentStep + 1), 300);
        } else {
            this.completeTutorial();
        }
    }

    previousStep() {
        if (this.currentStep > 0) {
            this.callout.classList.remove('active');
            setTimeout(() => this.showStep(this.currentStep - 1), 300);
        }
    }

    skipTutorial() {
        const modal = document.querySelector('.onboarding-modal-overlay');
        if (modal) {
            modal.classList.remove('active');
            setTimeout(() => modal.remove(), 300);
        }

        // Mark as skipped (can be restarted from settings)
        localStorage.setItem('sclera_tutorial_skipped', 'true');
    }

    endTutorial() {
        this.isActive = false;

        document.body.classList.remove('onboarding-active');
        // Remove highlights
        document.querySelectorAll('.onboarding-highlight').forEach(el => {
            el.classList.remove('onboarding-highlight', 'onboarding-highlight-notch', 'onboarding-highlight-action');
        });

        // Fade out and remove elements
        if (this.callout) {
            this.callout.classList.remove('active');
            setTimeout(() => this.callout.remove(), 300);
        }

        if (this.overlay) {
            this.overlay.classList.remove('active');
            setTimeout(() => this.overlay.remove(), 300);
        }
    }

    completeTutorial() {
        this.endTutorial();

        // Mark tutorial as completed
        localStorage.setItem('sclera_tutorial_completed', 'true');

        // Send completion status to server
        fetch('/api/tutorial/complete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ completed: true })
        }).catch(err => console.log('Could not save tutorial status:', err));

        // Show completion message
        this.showCompletionMessage();
    }

    showCompletionMessage() {
        const message = document.createElement('div');
        message.className = 'onboarding-completion-message';
        message.innerHTML = `
            <div class="onboarding-completion-content">
                <span class="material-symbols-outlined" style="font-size: 3rem; color: var(--success);">check_circle</span>
                <h3>Tutorial Complete!</h3>
                <p>You're all set to make the most of Sclera. You can restart this tutorial anytime from Settings.</p>
            </div>
        `;

        document.body.appendChild(message);

        setTimeout(() => message.classList.add('active'), 10);
        setTimeout(() => {
            message.classList.remove('active');
            setTimeout(() => message.remove(), 300);
        }, 4000);
    }

    restartTutorial() {
        // Clear completion status
        localStorage.removeItem('sclera_tutorial_completed');
        localStorage.removeItem('sclera_tutorial_skipped');
        this.hasCompletedTutorial = false;

        // Start tutorial
        this.startTutorial();
    }
}

// Initialize onboarding manager when DOM is ready
let onboardingManager;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        onboardingManager = new OnboardingManager();
    });
} else {
    onboardingManager = new OnboardingManager();
}
