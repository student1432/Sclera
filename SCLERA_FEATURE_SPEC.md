# Sclera — Full Feature Specification

This document provides a comprehensive overview of the Sclera Student Academic Operating System, detailing its technical stack, user roles, and functional modules.

---

## 1. COMPACT FEATURE OVERVIEW

### **Core Platform**
- **Multi-Role Auth:** Student, Teacher, and Institutional Admin flows.
- **Academic Backbone:** Dynamic syllabus engine for School (CBSE/ICSE), Exam Prep (JEE/NEET), and After-10th streams.
- **Study Mode:** Pomodoro-based focus sessions with atomic Firestore logging.
- **AI Integration:** ScleraAI (Gemini) for planning and doubt resolution.
- **Document System:** Hierarchical folder structure with Markdown/HTML export.
- **Community:** Bubble study groups with real-time Chat and Shared TODOs.

### **Institutional Layer**
- **Class Management:** Code-based enrollment and file distribution.
- **Analytics:** 30-day activity heatmaps and predictive "At-Risk" student detection.
- **Curriculum Control:** 3-tier syllabus exclusion system (Admin > Teacher > Student).

---

## 2. DETAILED TECHNICAL SPECIFICATION

### 2.1 Technical Stack
- **Backend:** Flask 2.3.3 (Python) with SocketIO (WebSockets).
- **Database:** Firebase Firestore (NoSQL).
- **Authentication:** Firebase Admin SDK + custom bcrypt/password hashing layer.
- **AI Engine:** Google Gemini API (via `google-generativeai`).
- **Real-time:** Flask-SocketIO (threading mode) for live chat and indicators.
- **Security:** Flask-Talisman (CSP/HSTS), Flask-Limiter (Rate limiting).
- **Storage:** Local file system for PFP/Banners/Uploads (indexed in Firestore).

### 2.2 User Roles & Onboarding
#### **Student**
- **Purpose Selection:** `school`, `exam_prep`, or `after_tenth`.
- **Dynamic Setup:** Configures boards (CBSE/ICSE/IB), grades (8-12), or specific competitive exams (JEE/NEET).
- **Login Streaks:** Daily counter with session persistence.

#### **Teacher**
- **Join Flow:** Requires a one-time invite code from an Admin to activate.
- **Class Ownership:** Can create multiple classes, each with unique 6-character invite codes.
- **Student Oversight:** Access to individual student progress and at-risk status.

#### **Admin (Institution)**
- **Registration:** Concurrent creation of Admin account and Institution entity.
- **Management:** Full control over teacher roster (disable/delete) and student enrollment.
- **Syllabus Control:** Can set Level 1 exclusions for the entire institution.

### 2.3 Academic Management System
#### **Dashboard & Progress**
- **Dynamic Syllabus:** Renders based on Grade/Board/Purpose.
- **Completion Tracking:** Toggle-based chapter status.
- **3-Tier Exclusions:**
  1. **Institution Level:** Global removals (e.g., deleted chapters).
  2. **Class Level:** Teacher-specific focus areas.
  3. **Personal Level:** Student-specific elective exclusions.
- **Performance Metrics:** Average %, Highest %, and Test-Type grouping.

#### **Study Mode & Analytics**
- **Pomodoro Timer:** Interactive timer with session break support.
- **Study TODOs:** Per-session task lists stored in Firestore subcollections.
- **AI Analytics Engine:**
  - **Momentum:** Score gradient across the last 4 exams.
  - **Consistency:** Session density and login patterns.
  - **Readiness:** Weighted composite of syllabus completion (40%) and exam avg (60%).

### 2.4 Collaboration & Community
#### **Bubbles (Study Groups)**
- **Creation:** Creator-owned groups with invitation-based joining.
- **Real-time Chat:** Messaging with typing indicators, join/leave notices, and soft-delete.
- **Shared TODOs:** Collaborative task lists with live broadcast of updates.
- **File Sharing:** Bubble-specific file uploads with security validation.
- **Leaderboards:** Internal bubble rankings (opt-in based on privacy consent).

#### **Connections**
- **Discovery:** People search by name (min 2 chars) with privacy filters.
- **Networking:** Connection requests with custom messages.
- **Privacy:** Granular visibility for PFP, grade, school, and progress.

### 2.5 Resource & Career Portal
- **Master Library:** Global view of all supported academic syllabi.
- **Career Explorer:** Database of 50+ career paths with domain/skill tags.
- **Course & Internship Catalog:** Integrated listings with search/filter capabilities (provider, location, price type).
- **Interest Tracking:** Saved careers widget on the main dashboard.

### 2.6 Documentation System (Docs)
- **Editor:** Markdown-compatible document creation.
- **Organization:** Recursive folder structure with parent/child nesting.
- **History:** Versioning for document edits.
- **Export:** Multi-format export (Markdown, HTML, Plain Text).

### 2.7 Security & Monitoring
- **Rate Limiting:** IP-based limits on Login, Signup, and API endpoints.
- **Sanitization:** Bleach-based HTML sanitization for all user-generated content (Chat/Docs).
- **Login Guard:** Asymmetric role-based redirects (prevents admins from accessing student routes).
- **Activity Heatmap:** 7x24 grid visualization of peak study hours (rolling 30-day window).
- **At-Risk Detection:** Automatic flagging of students with 7+ days inactivity or declining momentum.
