# Complete Firebase Setup Guide

This guide will walk you through setting up Firebase for the Student Platform from scratch.

## Table of Contents
1. [Create Firebase Project](#1-create-firebase-project)
2. [Enable Authentication](#2-enable-authentication)
3. [Create Firestore Database](#3-create-firestore-database)
4. [Download Service Account Key](#4-download-service-account-key)
5. [Configure Security Rules](#5-configure-security-rules)
6. [Test Your Setup](#6-test-your-setup)

---

## 1. Create Firebase Project

### Step-by-step:

1. **Go to Firebase Console**
   - Visit: https://console.firebase.google.com/
   - Sign in with your Google account

2. **Create New Project**
   - Click "Add project" or "Create a project"
   - Enter project name: `student-platform` (or your preferred name)
   - Click "Continue"

3. **Google Analytics (Optional)**
   - Choose whether to enable Google Analytics
   - If enabled, select or create an Analytics account
   - Click "Create project"

4. **Wait for Setup**
   - Firebase will set up your project (takes 30-60 seconds)
   - Click "Continue" when ready

✅ **Checkpoint**: You should now see your Firebase project dashboard

---

## 2. Enable Authentication

### Step-by-step:

1. **Navigate to Authentication**
   - In the left sidebar, click "Build"
   - Click "Authentication"
   - Click "Get started"

2. **Enable Email/Password Sign-in**
   - Click on "Sign-in method" tab at the top
   - Find "Email/Password" in the providers list
   - Click on it to open settings
   - Toggle "Enable" to ON
   - Click "Save"

3. **Verify Setup**
   - "Email/Password" should now show "Enabled" status

✅ **Checkpoint**: Email/Password authentication is now enabled

---

## 3. Create Firestore Database

### Step-by-step:

1. **Navigate to Firestore**
   - In the left sidebar, click "Build"
   - Click "Firestore Database"
   - Click "Create database"

2. **Choose Security Rules**
   - Select "Start in test mode" (for development)
   - **Note**: We'll set proper rules in Step 5
   - Click "Next"

3. **Select Location**
   - Choose a Cloud Firestore location closest to your users
   - Example: `us-central` for USA
   - **Important**: Location cannot be changed later
   - Click "Enable"

4. **Wait for Database Creation**
   - Firestore will set up your database (takes 30-60 seconds)

✅ **Checkpoint**: You should see an empty Firestore database

---

## 4. Download Service Account Key

### Step-by-step:

1. **Navigate to Project Settings**
   - Click the gear icon ⚙️ next to "Project Overview"
   - Click "Project settings"

2. **Go to Service Accounts**
   - Click on "Service accounts" tab at the top

3. **Generate Private Key**
   - You'll see a section "Firebase Admin SDK"
   - Verify Python is selected as the language
   - Click "Generate new private key"

4. **Download the Key**
   - A popup will appear warning you to keep the key secure
   - Click "Generate key"
   - A JSON file will download: `your-project-name-firebase-adminsdk-xxxxx.json`

5. **Rename and Move the File**
   - Rename the downloaded file to: `serviceAccountKey.json`
   - Move it to your project root directory (same folder as `app.py`)

6. **Verify File Location**
   ```
   student_platform/
   ├── app.py
   ├── firebase_config.py
   ├── serviceAccountKey.json  ← Should be here
   ├── requirements.txt
   └── ...
   ```

⚠️ **CRITICAL SECURITY NOTE**:
- NEVER commit this file to Git/GitHub
- Keep it secure and private
- Add it to `.gitignore` (already done in the project)

✅ **Checkpoint**: `serviceAccountKey.json` is in your project root

---

## 5. Configure Security Rules

### Development Rules (Already Set)

When you selected "test mode", Firestore automatically set these rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if request.time < timestamp.date(2026, 3, 1);
    }
  }
}
```

**Note**: These rules allow anyone to read/write until the expiration date.

### Production Rules (IMPORTANT!)

Before deploying to production, update your rules:

1. **Navigate to Firestore Rules**
   - Go to Firestore Database
   - Click "Rules" tab at the top

2. **Replace with Production Rules**
   ```javascript
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       // Users collection
       match /users/{userId} {
         // Only authenticated users can access their own data
         allow read, write: if request.auth != null && request.auth.uid == userId;
       }
     }
   }
   ```

3. **Publish Rules**
   - Click "Publish"
   - Confirm the changes

✅ **Checkpoint**: Security rules are configured

---

## 6. Test Your Setup

### Verify Everything Works:

1. **Install Dependencies**
   ```bash
   cd student_platform
   pip install -r requirements.txt
   ```

2. **Check File Structure**
   ```
   student_platform/
   ├── app.py ✓
   ├── firebase_config.py ✓
   ├── serviceAccountKey.json ✓
   ├── requirements.txt ✓
   ├── templates/ ✓
   └── static/ ✓
   ```

3. **Run the Application**
   ```bash
   python app.py
   ```

4. **Expected Output**
   ```
   * Serving Flask app 'app'
   * Debug mode: on
   * Running on http://0.0.0.0:5000
   ```

5. **Test in Browser**
   - Open: http://localhost:5000
   - You should see the signup page
   - Try creating an account

6. **Verify in Firebase Console**
   - Go to Authentication → Users
   - Your test user should appear
   - Go to Firestore Database
   - You should see a `users` collection with your user document

✅ **Success**: Your Firebase setup is complete!

---

## Common Issues & Solutions

### Issue: "serviceAccountKey.json not found"
**Solution**: 
- Verify file is in project root
- Check filename is exactly `serviceAccountKey.json`
- Ensure no extra spaces in filename

### Issue: "Permission denied" in Firestore
**Solution**:
- Check Firestore rules are set correctly
- Verify user is authenticated
- Check UID matches document ID

### Issue: "Authentication failed"
**Solution**:
- Verify Email/Password is enabled in Firebase Console
- Check credentials are correct
- Clear browser cookies and try again

### Issue: "Module not found" errors
**Solution**:
```bash
pip install --upgrade firebase-admin Flask
```

---

## Security Checklist

Before going to production:

- [ ] Service account key is NOT in version control
- [ ] `.gitignore` includes `serviceAccountKey.json`
- [ ] Firestore security rules are set to production mode
- [ ] Flask secret key is a fixed, secure value
- [ ] Environment variables are used for sensitive data
- [ ] HTTPS is enabled
- [ ] Password reset functionality is implemented
- [ ] Email verification is enabled

---

## Additional Firebase Features (Optional)

### Enable Email Verification
1. Go to Authentication → Settings
2. Under "User actions", enable "Email verification"

### Set Up Password Reset
1. Go to Authentication → Templates
2. Customize "Password reset" email template

### Add Storage (for file uploads)
1. Go to Build → Storage
2. Click "Get started"
3. Follow the setup wizard

---

## Need Help?

### Firebase Documentation
- Firebase Console: https://console.firebase.google.com/
- Auth Docs: https://firebase.google.com/docs/auth
- Firestore Docs: https://firebase.google.com/docs/firestore

### Project Documentation
- See `README.md` for application usage
- Check `app.py` comments for code details

---

**Setup complete! You're ready to build amazing student experiences! 🚀**
