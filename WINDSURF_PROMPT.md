# Sclera Feature Implementation Prompt

Use this prompt in Windsurf for high-fidelity implementation of new features within the Sclera ecosystem.

---

**Task: Implement [Feature Name]**

**Objective:**
[Describe the goal of the feature]

**Architectural Context:**
Sclera is a high-fidelity **Student Academic Operating System** built with a three-layer architecture:
1.  **Identity Layer:** Flask session management and Firebase Auth.
2.  **Academic Backbone:** Structured syllabi in `templates/academic_data.py`.
3.  **Execution Layer:** Real-time analytics and productivity tools (Calendar, Goals, Notes).

**Key Technical Details:**
*   **Backend:** Python 3 (Flask v3.0.0).
*   **Database:** Firebase Firestore (NoSQL).
*   **Frontend:** HTML5 with Jinja2 templates, Tailwind CSS, and a "Dark Academic" aesthetic.
*   **AI:** Google Gemini integration via `ai_assistant.py`.

**Instructions for Implementation:**
*   **Consistency:** Adhere to the "Dark Academic" design philosophy (minimalist, sharp borders, structured typography).
*   **Security:** Utilize the existing `require_login` and `require_admin_v2` decorators.
*   **Data Integrity:** Use atomic updates (`firestore.Increment`, `firestore.ArrayUnion`) where appropriate.
*   **Documentation:** Update `SUMMARY.md` and `TECH_REPORT.md` if new modules or significant architectural changes are introduced.

**Development Tools:**
*   Utilize existing `/api/debug/*` routes for database inspection during development.
*   The AI Assistant consent check is currently set to bypass for testing efficiency.

---
