# Feature Guide & User Flow

## Overview
This platform is a comprehensive educational and productivity ecosystem designed for Students, Teachers, and Institution Administrators. It integrates academic tracking, collaborative study groups (Bubbles), career guidance, institutional management, AI assistance, and document management.

---

## 1. Authentication & Role-Based Access

### Features
* **Multi-Role Login/Signup**: Dedicated portals for Students (`/login/student`), Teachers (`/login/teacher`), and Institution Admins (`/login/admin`).
* **Profile Setup**: Step-by-step onboarding for academic paths (e.g., `/setup/highschool`, `/setup/exam`).
* **Tutorials**: Interactive tutorials for first-time users.

### User Flow
1. User lands on `/landing` or `/`.
2. Selects role (Student, Teacher, or Admin) and navigates to the respective signup/login page.
3. Completes onboarding (e.g., selecting high school or exam prep path).
4. Redirected to the corresponding role-based Dashboard.

---

## 2. Student Dashboard & Academics

### Features
* **Academic Master Library**: Track progress across subjects and chapters (`/master-library`).
* **Study Mode & Timers**: Dedicated focus mode with time tracking (`/study-mode`).
* **Goals & Task Management**: Set goals and manage daily tasks/todos (`/goals`, `/tasks`, `/todo`).
* **Performance Statistics**: Visual insights into study time, upcoming events, and totals (`/statistics`).
* **Calendar Integration**: Manage and view upcoming study sessions and personal events (`/calendar`).

### User Flow
1. Student accesses Dashboard (`/dashboard`).
2. Views quick stats, upcoming calendar events, and active todos.
3. Enters **Study Mode** to start a focused session, triggering the study timer.
4. Updates academic progress in the **Master Library** by toggling completed chapters.

---

## 3. Institution & Class Management

### Features
* **Admin Dashboard**: Manage teachers (invite/disable/delete) and students.
* **Teacher Dashboard**: Create and manage classes, upload files, define syllabus.
* **Student Class Portal**: Join classes via code, view class files, and track class-specific syllabus.
* **Announcements**: Broadcast messages and nudge students.

### User Flow
1. **Admin**: Generates invite links for teachers.
2. **Teacher**: Joins institution, creates a Class (`/institution/teacher/classes/create`), and uploads study materials (`/institution/teacher/class/<class_id>/upload`).
3. **Student**: Uses class code to join (`/student/join/class`), downloads materials, and views the class syllabus.

---

## 4. Community & Collaboration (Bubbles)

### Features
* **Bubbles (Study Groups)**: Create or join private/public study groups (`/bubbles`).
* **Real-time Chat**: Group communication within bubbles (`/bubble/<bubble_id>/chat`).
* **Shared Resources**: Collaborate on Bubble-specific Todos and Files.
* **Connections**: Send, accept, decline, or block user connection requests.
* **Leaderboards**: Competitive privacy-aware leaderboards.

### User Flow
1. User navigates to Community (`/community`) or Bubbles (`/bubbles`).
2. Creates a new Bubble or accepts an invitation.
3. Inside the Bubble, users chat, upload shared files, and manage group tasks.
4. Users can search for peers (`/api/people/search`) and send connection requests.

---

## 5. AI Assistant (Sclera)

### Features
* **Dual Modes**: Dedicated modes for 'Planning' and 'Doubt Clearing'.
* **Thread Management**: Create, switch, rename, delete, and view history of AI chat threads.
* **Export functionality**: Export AI chat history to different formats.

### User Flow
1. User opens the AI Assistant (`/ai-assistant`).
2. Grants consent (first time).
3. Creates a new thread for either Planning or Doubt clearing.
4. Interacts with the AI model (Gemini/OpenAI powered).
5. Exports the conversation for later reference.

---

## 6. Career Guidance

### Features
* **Exploration Hub**: Browse Careers, Courses, and Internships.
* **Search & Filters**: Advanced filtering APIs to find specific paths.
* **Bookmarks**: Toggle/save interested careers.
* **Path-specific Dashboards**: Tailored views for post-10th grade or specific exam preparations.

### User Flow
1. Student navigates to Interests (`/interests`).
2. Searches for a career or course (`/api/search/careers`).
3. Clicks on a specific Career (`/career/<career_id>`) to view details, related courses, and internships.
4. Saves the career to their profile.

---

## 7. Document Management (Docs)

### Features
* **Rich Text Documents**: Create, read, update, and delete documents (`/docs`).
* **Folder Organization**: Group documents into folders.
* **Version Control**: Access previous versions of documents.
* **Exporting**: Download documents in various formats.

### User Flow
1. User opens Docs (`/docs`).
2. Creates a new Folder or Document.
3. Edits document content via the rich-text interface.
4. Views document history or exports it as PDF/Word.

---

## 8. Profile & Settings

### Features
* **Public Profiles**: Viewable profiles based on privacy settings (`/api/user/<user_uid>/public-profile`).
* **Resume Builder**: Generate and edit a professional resume (`/profile/resume`).
* **Customization**: Upload profile pictures and banners.
* **Settings/Privacy**: Manage notifications, connection preferences, and privacy toggles.

### User Flow
1. User clicks on their Profile (`/profile`).
2. Edits details, uploads a custom banner/picture.
3. Uses the Resume feature to auto-compile their academic and career data into a formatted resume.
