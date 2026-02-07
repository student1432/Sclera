import firebase_admin
from firebase_admin import credentials, auth, firestore
import os
import sys

# Get base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to credentials
CRED_FILE = 'serviceAccountKey.json'
CRED_PATH = os.path.join(BASE_DIR, CRED_FILE)

# Check if credentials file exists
if not os.path.exists(CRED_PATH):
    print("="*60)
    print("❌ ERROR: Firebase credentials not found!")
    print("="*60)
    print(f"Looking for: {CRED_PATH}")
    print()
    print("To fix this:")
    print("1. Go to https://console.firebase.google.com")
    print("2. Select your project")
    print("3. Click gear icon → Project settings")
    print("4. Click 'Service accounts' tab")
    print("5. Click 'Generate new private key'")
    print("6. Save file as 'serviceAccountKey.json'")
    print(f"7. Put it in: {BASE_DIR}")
    print("="*60)
    sys.exit(1)

# Try to initialize Firebase
try:
    # Check if already initialized
    if not firebase_admin._apps:
        cred = credentials.Certificate(CRED_PATH)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully!")
    
    # Get Firestore client
    db = firestore.client()
    
except Exception as e:
    print("="*60)
    print("❌ ERROR: Failed to initialize Firebase!")
    print("="*60)
    print(f"Error: {e}")
    print()
    print("Possible causes:")
    print("- Credentials file is corrupted")
    print("- Wrong Firebase project")
    print("- Network connection issue")
    print()
    print("Try downloading fresh credentials from Firebase Console")
    print("="*60)
    sys.exit(1)