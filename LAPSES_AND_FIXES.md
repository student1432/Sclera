# Sclera: Critical Lapses & Remediation Roadmap

This report identifies high-priority technical and operational lapses in the Sclera platform and provides exact steps for remediation.

---

## 1. Technical Security Lapses

### ⚠️ Unauthenticated Debug Endpoints
**Lapse:** Routes like `/api/people/search/debug` and `/api/debug/users` are active and bypass all session/login checks.
*   **Impact:** Massive data leak risk; allows anyone to scrape user lists and PII.
*   **Fix:** Remove these routes from `app.py` or wrap them in an `admin_required` decorator.
*   **Steps:**
    1.  Delete lines ~2356 to ~2444 in `app.py`.
    2.  Verify that GET requests to `/api/debug/users` return 404.

### ⚠️ AI Consent Bypass
**Lapse:** The `ai_assistant` and `api/ai/chat/*` routes contain hardcoded bypasses for AI consent (`ai_consent = True`).
*   **Impact:** Violates user privacy preferences and potentially legal compliance (GDPR/CCPA).
*   **Fix:** Re-enable the commented-out consent checks in `app.py`.
*   **Steps:**
    1.  Uncomment `if not user_data.get('ai_consent', False):` in chat endpoints.
    2.  Remove `ai_consent = True # Force consent for debugging`.

### ⚠️ Persistent Debug Mode
**Lapse:** `DEBUG=true` is set in `.env`, and `config.py` defaults to `DevelopmentConfig`.
*   **Impact:** Server reveals detailed stack traces on error, exposing internal logic to attackers.
*   **Fix:** Change `.env` to `FLASK_ENV=production` and `DEBUG=false`.

---

## 2. Product & Feature Lapses

### ⚠️ Skeletal "Bubbles" System
**Lapse:** The community social feature has non-functional "TODO" placeholders for joining by code and bubble management in `templates/bubbles.html`.
*   **Impact:** Broken user experience; social loops cannot be closed.
*   **Fix:** Implement the `/api/bubbles/join` logic and CRUD for bubble members.
*   **Steps:**
    1.  Create a `BubbleManager` class in `utils/`.
    2.  Connect frontend buttons to actual Firestore `ArrayUnion` operations.

### ⚠️ Over-Purging of Modules
**Lapse:** "Projects" and "Notes" modules were removed, leaving the "Student Operating System" without primary storage/organization utilities.
*   **Impact:** Reduced utility; users must leave the app to organize their study materials.
*   **Fix:** Restore and optimize these modules as integrated "Lightweight" components.

---

## 3. Operational Lapses

### ⚠️ Placeholder Support Infrastructure
**Lapse:** The contact form sends emails to `support@studyos.example.com`.
*   **Impact:** Users cannot get help; zero professional credibility.
*   **Fix:** Update `MAIL_DEFAULT_SENDER` and recipient list to a verified domain email.
*   **Steps:**
    1.  Configure SendGrid or Gmail SMTP in `config.py`.
    2.  Update the `recipients` list in `app.py` line ~3806.

### ⚠️ Inconsistent Data Models
**Lapse:** To-dos are stored in two different ways: `study_todos` (subcollection) and `quick_todos` (field list).
*   **Impact:** Code bloat and confusing UX across different dashboards.
*   **Fix:** Consolidate into a single `UserTask` model.

---

## 4. Growth & Monetization Lapses

### ⚠️ Missing Revenue Logic
**Lapse:** No implementation of the previously designed payment gateway (Razorpay).
*   **Impact:** Burning server/API costs with no revenue stream.
*   **Fix:** Execute the `WINDSURF_PROMPT.md` to gate Institutional features.

---

## 5. Verification Checklist
- [ ] `app.py`: All `DEBUG` logs removed.
- [ ] `app.py`: `/api/debug/*` routes deleted.
- [ ] `config.py`: Placeholder emails replaced.
- [ ] `templates/`: All `TODO` comments addressed or converted to Jira tickets.
- [ ] `firestore.indexes.json`: Composite indexes generated for Nudge/Broadcast features.
