# Sclera: Development Roadmap & Deployment Readiness

This document tracks intentional development tools, remaining product tasks, and the final verification checklist for Sclera's production deployment.

---

## 1. Intentional Development Tools

### 🛠 Unauthenticated Debug Endpoints
**Status:** Active for development velocity.
*   **Description:** Routes like `/api/people/search/debug` and `/api/debug/users` provide rapid database inspection.
*   **Production Step:** Remove or gate behind `require_admin_v2` decorator before public release.
*   **Verification:** GET requests to these routes should return 404 or 403 in the production environment.

### 🛠 AI Assistant Internal Testing Mode
**Status:** Active for development velocity.
*   **Description:** The AI consent check is temporarily bypassed in `app.py` and `ai_assistant.py` to facilitate rapid testing of Gemini integration.
*   **Production Step:** Re-enable the `user_data.get('ai_consent')` checks.
*   **Verification:** Users must see and agree to the consent modal before API interactions occur.

### 🛠 Local Debug Mode
**Status:** Active.
*   **Description:** `DEBUG=true` is utilized in local and staging environments for detailed stack traces.
*   **Production Step:** Set `FLASK_ENV=production` and `DEBUG=false` in the production environment variables.

---

## 2. Product & Community Completion

### 🛠 Invite-Based Bubbles System
**Status:** In Progress.
*   **Lapse:** "Join by code" has been purged. The system is transitioning to a high-trust, invite-only architecture.
*   **Action:** Finalize the invitation acceptance flow and member moderation controls.
*   **Steps:**
    1.  Ensure invitation IDs are unique and verifiable.
    2.  Update `templates/bubbles.html` to reflect the new invitation-centric UI.

### 🛠 Unified Task Management
**Status:** In Progress.
*   **Lapse:** Redundancy between `study_todos` and `quick_todos`.
*   **Action:** Consolidate into a single high-fidelity task model to ensure data consistency across the Academic and Main dashboards.

---

## 3. Pre-Deployment (Production Phase)

### 🛠 Operational Configuration
*   **Task:** Replace all placeholder emails (e.g., `support@studyos.example.com`) and sample SMTP credentials with production-ready institutional configurations.
*   **Timing:** To be executed during the final "Live" deployment window.

---

## 4. Verification Checklist
- [ ] `app.py`: All development-only `@app.route` debug paths removed.
- [ ] `config.py`: Production SMTP and email parameters verified.
- [ ] `templates/`: All `TODO` markers addressed or logged as maintenance tickets.
- [ ] `firestore.indexes.json`: Verify that composite indexes for Institutional Broadcast/Nudge are deployed.
- [ ] `ai_assistant.py`: Consent bypass logic removed and verified.
