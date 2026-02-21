# Sclera — UX & System Fault Audit

This document details the critical bugs, security vulnerabilities, and architectural inconsistencies identified within the Sclera platform.

---

## 1. COMPACT FAULT LIST

### **Critical Logic Errors**
- **Broken Signup:** Users choosing "after tenth" cannot complete registration.
- **Syllabus Desync:** Performance metrics read from the wrong database keys (`results` vs `exam_results`).
- **Identity Mismatch:** AI thread creation and deletion use different mode naming conventions.
- **Fragile IDs:** Goal management uses list-length IDs, leading to collisions after deletions.

### **Security & Privacy Risks**
- **Debug Endpoints:** Unauthenticated user and model debugging APIs are live.
- **Consent Bypass:** AI assistant features ignore user consent settings (permanently set to `True` for debug).
- **Insecure Filenames:** Profile pictures are stored using UIDs, exposing user IDs in public URLs.
- **Password Redundancy:** Storing local hashes alongside Firebase Auth creates synchronization risk.

### **UX & Architectural Lapses**
- **Silent Failures:** Chapter exclusions and contact form submissions lack confirmation or proper validation.
- **Mismatched Exports:** "PDF" export silently returns a `.txt` file with no warning.
- **Route Confusion:** `/bubbles` shows a global leaderboard instead of a list of study groups.

---

## 2. DETAILED FAULT ANALYSIS

### 2.1 Critical Functional Bugs
- **Signup Lockout:** In `signup()`, the `purpose == 'after_tenth'` condition flashes an "Invalid purpose" error and redirects back, making this user path inaccessible.
- **Exclusion No-Op:** `toggle_chapter_exclusion` initializes `subject_name` and `chapter_name` to `None` and only checks form data if they are falsy. If the form fields are missing or named incorrectly, it silently fails.
- **Dead Initialization Code:** `initialize_profile_fields` re-fetches user data after an update and sets a local variable `name_top_statistics` that is never used or returned.
- **Unreachable Error Handling:** `generate_sclera_response` contains nested `try/except` blocks where the outer exception catch is unreachable because inner blocks handle exceptions or the logic flow never reaches the second catch.
- **Thread Management Conflict:**
  - `create_sclera_thread` validates against `['academic', 'institutional', 'research']`.
  - `delete_sclera_thread` validates against `['academic_planner', 'institutional', 'doubt_solver']`.
  - Threads created in one mode cannot be deleted or managed in others, causing UI desync.
- **Dashboard Performance API:** `get_dashboard_performance` reads from `user_data.get('results', {})` (dict), while the actual data is stored in `exam_results` (list) by the results dashboard. This causes performance widgets to always show zero data.

### 2.2 Security & Data Integrity
- **Live Debug APIs:**
  - `/api/debug/users`: Lists first 10 users and UIDs without authentication.
  - `/api/people/search/debug`: Unauthenticated people search.
  - `/api/test/gemini`: Exposes API key prefixes and tests all available models.
- **AI Consent Bypass:** Both AI chat endpoints have the user consent check commented out, violating privacy settings and potential compliance (GDPR/COPPA).
- **UID Enumeration:** Profile pictures are saved as `{uid}_{timestamp}_{original_filename}` in the `/static/profile_pictures` folder. This exposes UIDs and allows third parties to guess/scrape user assets.
- **Fragile Goal IDs:** Goals use `len(goals)` as an ID. If a user has 3 goals [0, 1, 2], deletes goal 1, and adds a new one, the new goal gets ID 2, causing a collision with the existing goal 2.
- **Denormalization Desync:** Connection states are stored in both a `connections` collection and as arrays on `user` documents. A failure in one update leaves the system in an inconsistent state.
- **Roster Removal Bug:** `institution_admin_remove_student` attempts to remove students from a `students` array in the `classes` collection, but the creation logic uses the key `student_uids`. Students are never actually removed from class rosters.

### 2.3 UX & User Flow Fallacies
- **Inconsistent Status Guards:** `login_teacher` blocks if status is `disabled`, but `login_admin` blocks if status is anything other than `active`. Teacher accounts in `pending` status have inconsistent access.
- **Missing Recovery Paths:** There is no `/forgot-password` route or password reset mechanism implemented.
- **Export Falsehoods:** The `export_document` API for `format == 'pdf'` returns a plain text file with a `.txt` extension. The user is misled about the supported file types.
- **Broken 'Join by Code' (Bubbles):** `join_bubble_by_code` looks for an `invite_code` field on the bubble document, but `create_bubble` does not generate or store this field.
- **Ambiguous Contact Form:** The form sends emails to `support@studyos.example.com`. Since this is a placeholder, user inquiries are effectively lost unless checked manually in Firestore.
- **Dashboard Summary Mismatch:** The main dashboard checks for `purpose == 'exam'`, but the onboarding and syllabus logic uses `purpose == 'exam_prep'`. This causes the academic summary to remain blank for these users.
- **Double Login Guards:** `_institution_login_guard` is registered in `before_request` (running for all routes) but is also manually called inside multiple individual API routes, leading to redundant logic execution.
