# migrate_existing_users.py
# Run this ONCE if you have existing users without password hashes

from firebase_config import db
import hashlib

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def migrate_user_passwords():
    """
    Migration script for existing users.
    
    WARNING: Since Firebase Admin SDK doesn't store passwords in Firestore,
    existing users will need to:
    1. Use password reset feature (if implemented), OR
    2. Create new accounts
    
    This script shows how to add password_hash field for users if you know their passwords.
    """
    print("=" * 60)
    print("PASSWORD HASH MIGRATION SCRIPT")
    print("=" * 60)
    print("\nIMPORTANT: This script cannot retrieve existing passwords from Firebase Auth.")
    print("Firebase Auth does not expose password hashes for security reasons.")
    print("\nOptions for existing users:")
    print("1. They create new accounts (RECOMMENDED)")
    print("2. You manually add password hashes if you know their passwords")
    print("3. Implement password reset functionality")
    print("\nTo manually add a password hash for a specific user:")
    print("Run this script and enter the user's email and password when prompted.")
    print("=" * 60)
    
    choice = input("\nDo you want to add password hash for a specific user? (yes/no): ")
    
    if choice.lower() != 'yes':
        print("Migration cancelled.")
        return
    
    email = input("Enter user email: ")
    password = input("Enter password: ")
    
    # Find user by email
    users_ref = db.collection('users')
    query = users_ref.where('email', '==', email).limit(1)
    results = query.stream()
    
    user_found = False
    for doc in results:
        user_found = True
        user_data = doc.to_dict()
        uid = doc.id
        
        # Hash password
        password_hash = hash_password(password)
        
        # Update user document
        db.collection('users').document(uid).update({
            'password_hash': password_hash
        })
        
        print(f"\n✅ Password hash added for user: {email}")
        print(f"UID: {uid}")
    
    if not user_found:
        print(f"\n❌ No user found with email: {email}")

if __name__ == '__main__':
    migrate_user_passwords()
