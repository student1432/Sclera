# Windsurf Remediation Prompt: Sclera Platform Optimization

**Objective:** Fix critical logic errors, security vulnerabilities, and UX inconsistencies in the Sclera repository as identified in the `SCLERA_FAULT_AUDIT.md`. Perform these changes without breaking existing functionality or altering the established Dark Academic design philosophy.

### 1. Authentication & Onboarding Fixes
*   **Fix `after_tenth` Signup:** In `app.py` -> `signup()`, update the purpose validation logic. Ensure that `purpose == 'after_tenth'` is treated as a valid selection and does not trigger the "Invalid purpose" flash/redirect.
*   **Unify Dashboard Purpose Keys:** In `profile_dashboard()`, change the check for `purpose == 'exam'` to `purpose == 'exam_prep'` to match the onboarding purpose keys, ensuring the academic summary renders correctly.
*   **Standardize Status Guards:** Update `login_admin()` to allow login if status is `active` or `pending` (if applicable), or update `login_teacher()` to match the admin's more restrictive "must be active" logic to ensure role-based consistency.
*   **Remove Redundant Guards:** In the API routes (e.g., `create_calendar_event`, `update_calendar_event`), remove manual calls to `_institution_login_guard()` since it is already executed globally in the `before_request` hook.

### 2. Academic & Data Integrity Fixes
*   **Sync Performance Data:** In `get_dashboard_performance()`, update the logic to read from the `exam_results` list (using the percentage calculation) instead of the non-existent `results` dictionary.
*   **Stabilize Goal IDs:** In `goals_dashboard()`, stop using `len(goals)` as the ID. Implement timestamp-based string IDs (similar to the logic used in `tasks_dashboard`) to prevent collisions after deletions.
*   **Fix Class Roster Removal:** In `institution_admin_remove_student()`, update the `ArrayRemove` operation to target the `student_uids` key instead of the incorrect `students` key in the `classes` collection.
*   **Fix Chapter Exclusion Toggle:** In `toggle_chapter_exclusion()`, remove the redundant `None` initializations for `subject_name` and `chapter_name`. Ensure the function correctly extracts these from `request.form` and handles missing data gracefully without a silent no-op.

### 3. AI & Communication Fixes
*   **Align SCLERA Thread Modes:** Harmonize the mode lists between `create_sclera_thread` and `delete_sclera_thread`. Use a unified set: `['academic_planner', 'institutional', 'doubt_solver']`.
*   **Enable AI Consent Checks:** In `ai_chat_planning()` and `ai_chat_doubt()`, uncomment the consent validation logic. Ensure the AI only responds if `user_data.get('ai_consent')` is `True`.
*   **Fix Bubble Join Codes:** Update `create_bubble()` to generate and store a 6-character unique `invite_code`. Ensure `join_bubble_by_code()` can find bubbles using this field.
*   **Sanitize AI Responses:** Ensure `generate_sclera_response` properly handles the nested try/except blocks so that the fallback responses are reachable if the Gemini API fails.

### 4. Security & File System Hardening
*   **Decommission Debug Endpoints:** Completely remove the following routes:
    *   `/api/debug/users`
    *   `/api/people/search/debug`
    *   `/api/test/gemini`
*   **Secure Asset Filenames:** In `profile_edit()`, modify the filename generation for profile pictures and banners to exclude the raw UID. Use a UUID or a salted hash of the UID/Timestamp to prevent user enumeration.
*   **Improve File Size Validation:** Implement a pre-save check using `request.content_length` or by reading a small chunk of the stream to verify file size before committing the full upload to disk.

### 5. Frontend & Template Alignment
*   **Restore `after_tenth` UI Options:**
    *   In `signup.html` and `settings.html`, add `<option value="after_tenth">After 10th (Grade 11/12)</option>` to the purpose dropdowns.
    *   Create a basic `setup_after_tenth.html` template (copy `setup_highschool.html` and adapt fields) to prevent TemplateNotFound errors.
*   **Fix SocketIO Event Names:** In `bubble_chat.html`, update the JavaScript to:
    *   Emit `typing_start` (instead of `typing` with `is_typing: true`).
    *   Emit `typing_stop` (instead of `typing` with `is_typing: false`).
    *   Listen for `user_typing` (instead of `typing_status`).
*   **Inject Missing Context:**
    *   In `app.py` -> `bubble_chat()`, ensure the `bubble` dictionary passed to the template includes the `creator_name`.
    *   In `ai_assistant.html`, update the hardcoded "Dr. Jane Doe" sidebar to use placeholder `{{ name }}` or `{{ user.name }}` variables from Jinja where possible to minimize JS layout shift.

### 6. Support & Export UX
*   **Fix PDF Export:** In `export_document()`, either implement a basic PDF generation library (like `ReportLab` or `FPDF`) or update the UI to reflect that only `.txt`, `.md`, and `.html` are currently supported. Do not return a `.txt` file for a PDF request.
*   **Configure Support Email:** In `contact()`, replace the placeholder `support@studyos.example.com` with a configurable environment variable `SUPPORT_EMAIL`.

### **Preservation Rules:**
1.  Do **not** modify the Tailwind CSS classes or the "Dark Academic" theme.
2.  Maintain all existing `logger.info` and `logger.security_event` calls.
3.  Ensure all Firestore writes use `batch` operations where denormalized data is involved (e.g., Connections).

---

### Final Instructions for AI:
"Review the provided instructions carefully. Execute the fixes sequentially, starting with the Signup and Data Integrity bugs. After each fix, verify that the logic is sound and no existing decorators (`@require_login`, `@require_institution_role`) have been compromised."
