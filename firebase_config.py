import firebase_admin
from firebase_admin import credentials, auth, firestore
import os

# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase Admin SDK with service account key"""
    try:
        # Check if already initialized
        firebase_admin.get_app()
    except ValueError:
        # Path to service account key
        cred_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
        
        if not os.path.exists(cred_path):
            raise FileNotFoundError(
                "serviceAccountKey.json not found. "
                "Please download it from Firebase Console and place it in the project root."
            )
        
        # Initialize with service account
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

# Initialize Firebase
initialize_firebase()

# Export auth and db clients
auth = auth
db = firestore.client()
