# Sclera: Student Academic Operating System

Sclera is a high-fidelity academic workspace designed for high-performing students. It provides a focused, distraction-free environment that integrates academic planning, execution tracking, and career exploration.

## 🎯 Core Vision
Unlike gamified productivity apps, Sclera is built as a **"Focused Research Operating System."** It emphasizes a professional "Dark Academic" aesthetic, generous whitespace, and structured information hierarchy to minimize cognitive load and maximize focus.

## 🧱 Three-Layer Architecture
1.  **Identity Layer:** Manages secure authentication and rich student profiles, including skills, achievements, and academic interests.
2.  **Academic Backbone:** The centralized source of truth for syllabi. Supports various boards (CBSE, ICSE) and competitive exams (JEE, NEET, etc.). Features a **3-tier exclusion system** (Institutional, Class, and Personal levels) for precise syllabus tailoring.
3.  **Execution Layer:** A suite of productivity tools including Goals, Tasks, and an AI-powered Analytics Engine that tracks student performance.

## 🚀 Key Feature Modules
*   **Academic Dashboard:** Precision tracking of syllabus progress with an overhauled multi-island layout, performance analytics (Average, Last, Highest scores), and study-time visualizations.
*   **Academic Calendar:** Comprehensive tracking of exams, assignments, and tasks with Day, Week, and Month views.
*   **Study Mode (Pomodoro):** A focused study environment with an integrated timer, study-specific to-do lists, and automatic session recording.
*   **AI Progress Engine:** Calculates advanced metrics:
    *   **Momentum:** Score gradient over recent exams.
    *   **Readiness:** Weighted average of syllabus completion (40%) and exam performance (60%).
    *   **Consistency:** Based on study session density and regularity.
*   **Institutional Module:** A dedicated portal for schools and colleges:
    *   **Admin Dashboard:** Oversight of teachers/students and institutional analytics.
    *   **Teacher Dashboard:** Class management, file sharing, and progress monitoring.
    *   **Predictive Risk Analytics:** Identifies at-risk students using study session patterns.
    *   **Institutional Heatmap:** Visualizes peak activity hours across the institution.
*   **Sclera AI (The Core Intelligence):** An AI-powered workspace (via Google Gemini) for academic planning, doubt resolution, and institutional analysis.
*   **Community & Bubbles:** Social features for forming study groups ("Bubbles"), peer connections, and academic leaderboards.
*   **Interests & Careers:** Maps academic progress to career paths, relevant courses, and internships.

## 🛠 Technical Stack
*   **Backend:** Python 3 (Flask v3.0.0)
*   **Database & Auth:** Firebase (Firestore, Firebase Auth, Firebase Storage)
*   **AI Engine:** Google Gemini API
*   **Frontend:** HTML5, Tailwind CSS, custom Dark Academic CSS
*   **Security:** Bcrypt hashing, Talisman (CSP/Security Headers), Flask-Limiter
*   **Deployment:** Hybrid approach via Cloudflare and Render/Railway

## 📈 Development Status
Sclera has completed Phase 2 of its development, establishing a robust institutional layer and a sophisticated AI assistant system. It is production-ready with comprehensive documentation for deployment and testing.
