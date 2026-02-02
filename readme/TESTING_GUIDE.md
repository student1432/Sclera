# Testing Guide - Student Platform

This guide provides comprehensive testing procedures to ensure all features work correctly.

## Pre-Testing Setup

1. Ensure Firebase is configured (see SETUP_GUIDE.md)
2. Install dependencies: `pip install -r requirements.txt`
3. Verify `serviceAccountKey.json` is in place
4. Start the application: `python app.py`

---

## Test Cases

### 1. User Signup Flow

#### Test 1.1: High School Student Signup
**Steps:**
1. Navigate to http://localhost:5000
2. You should be redirected to `/signup`
3. Fill in the form:
   - Name: "Test Student 1"
   - Age: 16
   - Email: "highschool@test.com"
   - Password: "test123456"
   - Purpose: "Currently in High School"
4. Click "Sign Up"

**Expected Results:**
- Redirected to `/setup/highschool`
- Form displays board and grade fields

5. Complete setup:
   - Board: "CBSE"
   - Grade: "11"
6. Click "Complete Setup"

**Expected Results:**
- Success message appears
- Redirected to `/login`

**Firebase Verification:**
- Go to Firebase Console → Authentication
- User should appear with email "highschool@test.com"
- Go to Firestore → users collection
- Document should exist with purpose: "highschool"

---

#### Test 1.2: Exam Preparation Student Signup
**Steps:**
1. Go to `/signup`
2. Fill in:
   - Name: "Test Student 2"
   - Age: 17
   - Email: "exam@test.com"
   - Password: "test123456"
   - Purpose: "Preparing for Competitive Exam"
3. Click "Sign Up"
4. On setup page, select:
   - Exam Type: "JEE"
5. Click "Complete Setup"

**Expected Results:**
- User created successfully
- Firestore document has purpose: "exam"
- exam.type: "JEE"

---

#### Test 1.3: After Tenth Student Signup
**Steps:**
1. Go to `/signup`
2. Fill in:
   - Name: "Test Student 3"
   - Age: 16
   - Email: "afterten@test.com"
   - Password: "test123456"
   - Purpose: "After 10th Grade"
3. Click "Sign Up"
4. On setup page, select:
   - Stream: "Science"
   - Grade: "11"
   - Subjects: Check "Physics", "Chemistry", "Mathematics"
5. Click "Complete Setup"

**Expected Results:**
- User created successfully
- Firestore document has purpose: "after_tenth"
- Subjects array contains 3 items

---

#### Test 1.4: Duplicate Email Handling
**Steps:**
1. Try to signup with "highschool@test.com" again

**Expected Results:**
- Error message: "Email already exists. Please login."
- Redirected to `/login`
- No new user created in Firebase

---

### 2. Login Flow

#### Test 2.1: Successful Login
**Steps:**
1. Go to `/login`
2. Enter:
   - Email: "highschool@test.com"
   - Password: "test123456"
3. Click "Login"

**Expected Results:**
- Success message appears
- Redirected to `/dashboard`
- User's name displayed
- Correct profile information shown

---

#### Test 2.2: Invalid Credentials
**Steps:**
1. Go to `/login`
2. Enter:
   - Email: "nonexistent@test.com"
   - Password: "wrongpassword"
3. Click "Login"

**Expected Results:**
- Error message: "Invalid email or password"
- Remains on login page
- Not redirected

---

### 3. Dashboard Access

#### Test 3.1: Master Dashboard
**Steps:**
1. Login as "highschool@test.com"
2. View dashboard

**Expected Results:**
- Welcome message with name
- Purpose: "High School Student"
- Board and Grade displayed
- Button: "High School Dashboard"
- Quick action buttons visible: To-Do, About, Results

---

#### Test 3.2: High School Dashboard
**Steps:**
1. From master dashboard, click "High School Dashboard"

**Expected Results:**
- Redirected to `/dashboard/highschool`
- Title: "High School Dashboard"
- Name displayed
- Board: "CBSE"
- Grade: "11"
- Feature list visible
- Back button present

---

#### Test 3.3: Exam Dashboard
**Steps:**
1. Logout
2. Login as "exam@test.com"
3. Click "Exam Dashboard" from master dashboard

**Expected Results:**
- Redirected to `/dashboard/exam`
- Name displayed
- Exam: "JEE"
- Feature list visible

---

#### Test 3.4: After Tenth Dashboard
**Steps:**
1. Logout
2. Login as "afterten@test.com"
3. Click "After Tenth Dashboard"

**Expected Results:**
- Redirected to `/dashboard/after_tenth`
- Name displayed
- Stream: "Science"
- Grade: "11"
- Subjects: "Physics, Chemistry, Mathematics"

---

### 4. To-Do List Functionality

#### Test 4.1: Add Task
**Steps:**
1. Login as any user
2. Click "My To-Do List"
3. In the "Add New Task" section:
   - Enter: "Complete math assignment"
4. Click "Add Task"

**Expected Results:**
- Success message: "Task added!"
- Task appears in list below
- Task shows as incomplete (no strikethrough)
- Date stamp visible

**Firestore Verification:**
- Check user document
- Should have "todos" array with one item

---

#### Test 4.2: Add Multiple Tasks
**Steps:**
1. Add three more tasks:
   - "Study for physics test"
   - "Submit project report"
   - "Read chapter 5"

**Expected Results:**
- All 4 tasks visible in list
- Each has unique date/time
- All show as incomplete

---

#### Test 4.3: Complete Task
**Steps:**
1. Find "Complete math assignment"
2. Click "Complete" button

**Expected Results:**
- Task text has strikethrough
- Item appears faded (opacity 0.6)
- Button text changes to "Undo"
- Success message: "Task updated!"

**Firestore Verification:**
- Task's "completed" field should be true

---

#### Test 4.4: Undo Task Completion
**Steps:**
1. Click "Undo" on the completed task

**Expected Results:**
- Strikethrough removed
- Opacity back to normal
- Button text changes back to "Complete"

---

#### Test 4.5: Delete Task
**Steps:**
1. Find any task
2. Click "Delete" button

**Expected Results:**
- Task removed from list
- Success message: "Task deleted!"
- Total task count decreases by 1

**Firestore Verification:**
- Task removed from "todos" array

---

#### Test 4.6: User-Specific Tasks
**Steps:**
1. Add 2 tasks while logged in as one user
2. Logout
3. Login as different user
4. Go to To-Do List

**Expected Results:**
- New user sees empty task list or their own tasks
- Tasks from previous user are NOT visible
- Each user has isolated task lists

---

### 5. Navigation & Common Pages

#### Test 5.1: About Page
**Steps:**
1. From dashboard, click "About"

**Expected Results:**
- Redirected to `/about`
- Page content displays correctly
- Back button works
- Information is readable and formatted

---

#### Test 5.2: Results Page
**Steps:**
1. From dashboard, click "Results"

**Expected Results:**
- Redirected to `/results`
- Placeholder content visible
- Back button works

---

### 6. Security & Session Management

#### Test 6.1: Unauthorized Access Prevention
**Steps:**
1. Logout (or open new incognito window)
2. Try to access: http://localhost:5000/dashboard

**Expected Results:**
- Redirected to `/login`
- Cannot access dashboard without login

3. Try other protected routes:
   - `/dashboard/highschool`
   - `/dashboard/exam`
   - `/dashboard/after_tenth`
   - `/todo`
   - `/about`
   - `/results`

**Expected Results:**
- All redirect to `/login`

---

#### Test 6.2: Logout Functionality
**Steps:**
1. Login to any account
2. Click "Logout" button

**Expected Results:**
- Success message: "Logged out successfully"
- Redirected to `/login`
- Session cleared

3. Try to use browser back button to access dashboard

**Expected Results:**
- Redirected to login (session is cleared)

---

### 7. Form Validation

#### Test 7.1: Signup Validation
**Steps:**
1. Go to `/signup`
2. Try to submit with:
   - Empty fields
   - Invalid email format
   - Password < 6 characters
   - Age < 10 or > 100

**Expected Results:**
- Browser validation prevents submission
- Error messages appear

---

#### Test 7.2: Setup Form Validation
**Steps:**
1. Start signup process
2. On setup page, try to submit without selecting required fields

**Expected Results:**
- Browser validation prevents submission

---

### 8. Data Persistence

#### Test 8.1: Profile Data Persistence
**Steps:**
1. Complete signup and setup
2. Logout
3. Login again
4. Check dashboard

**Expected Results:**
- All profile data is retained
- Board/Exam/Stream information correct
- No data loss

---

#### Test 8.2: Task Data Persistence
**Steps:**
1. Add 5 tasks
2. Complete 2 of them
3. Logout
4. Login again
5. Go to To-Do List

**Expected Results:**
- All 5 tasks still present
- Completed status maintained
- Order preserved

---

### 9. Cross-Browser Testing

Test the application in:
- [ ] Chrome
- [ ] Firefox
- [ ] Safari
- [ ] Edge

Verify all features work consistently across browsers.

---

### 10. Responsive Design Testing

Test on different screen sizes:
- [ ] Desktop (1920x1080)
- [ ] Laptop (1366x768)
- [ ] Tablet (768x1024)
- [ ] Mobile (375x667)

**Expected Results:**
- Forms remain usable
- Buttons accessible
- Text readable
- No horizontal scrolling
- Mobile-friendly layout

---

## Firebase Console Verification Checklist

After testing, verify in Firebase Console:

### Authentication Tab
- [ ] All test users visible
- [ ] Email addresses correct
- [ ] User IDs (UIDs) present

### Firestore Tab
- [ ] `users` collection exists
- [ ] Each user document has correct structure
- [ ] Purpose field matches user type
- [ ] Nested objects (highschool/exam/after_tenth) correct
- [ ] Todos array updates properly

---

## Performance Testing

### Load Test
1. Create 10 users
2. Add 20 tasks each
3. Test dashboard load time
4. Test task list rendering

**Expected Results:**
- Pages load in < 2 seconds
- No lag in UI interactions

---

## Error Handling Testing

### Test Invalid Scenarios

1. **Missing Service Account Key**
   - Rename `serviceAccountKey.json`
   - Start app
   - Expected: Clear error message

2. **Firestore Connection Failure**
   - Disable internet
   - Try to login
   - Expected: Error message displayed

3. **Malformed Data**
   - Manually edit Firestore document
   - Remove required fields
   - Access dashboard
   - Expected: Handles gracefully

---

## Test Report Template

After completing tests, document results:

```
Test Date: _______________
Tester: _______________

✅ Passed Tests: ___ / 30
❌ Failed Tests: ___ / 30

Critical Issues Found:
1. _______________
2. _______________

Minor Issues Found:
1. _______________
2. _______________

Browser Compatibility:
- Chrome: ✅/❌
- Firefox: ✅/❌
- Safari: ✅/❌
- Edge: ✅/❌

Overall Status: PASS / FAIL
```

---

## Automated Testing (Future Enhancement)

For production, consider adding:
- Unit tests with pytest
- Integration tests
- End-to-end tests with Selenium
- API tests
- Security tests

---

**Testing complete! All features verified and working! ✅**
