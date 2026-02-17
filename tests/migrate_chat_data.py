"""
AI Chat Data Migration Script
Migrates existing chat data from the old format to the new thread-based format
"""
import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate_chat_data():
    """Migrate existing chat data to the new thread-based format"""

    # Initialize Firebase
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()

        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {e}")
        return

    # Migrate planning chat data
    print("\n🔄 Migrating planning chat data...")
    migrate_mode_data(db, 'planning')

    # Migrate doubt chat data
    print("\n🔄 Migrating doubt chat data...")
    migrate_mode_data(db, 'doubt')

    print("\n✅ Migration completed successfully!")

def migrate_mode_data(db, mode):
    """Migrate data for a specific mode (planning or doubt)"""
    try:
        # Get all existing messages for this mode
        old_collection = f'chat_history_{mode}'
        messages_ref = db.collection('users')

        # Get all users who have chat data
        users_with_data = set()
        for user_doc in messages_ref.stream():
            user_id = user_doc.id
            user_messages_ref = messages_ref.document(user_id).collection(old_collection)
            if len(list(user_messages_ref.limit(1).stream())) > 0:
                users_with_data.add(user_id)

        print(f"📊 Found {len(users_with_data)} users with {mode} chat data")

        # Process each user
        for user_id in users_with_data:
            print(f"  👤 Migrating user {user_id}...")

            # Get all messages for this user and mode
            user_messages_ref = messages_ref.document(user_id).collection(old_collection)
            messages = []

            for msg_doc in user_messages_ref.order_by('timestamp').stream():
                msg_data = msg_doc.to_dict()
                messages.append({
                    'role': msg_data.get('role', 'user'),
                    'content': msg_data.get('content', ''),
                    'timestamp': msg_data.get('timestamp', datetime.utcnow().isoformat())
                })

            if not messages:
                print("    ⚠️ No messages found, skipping...")
                continue

            # Create a default thread for this user and mode
            thread_id = create_default_thread(db, user_id, mode, len(messages))

            # Add all messages to the thread
            add_messages_to_thread(db, user_id, mode, thread_id, messages)

            print(f"    ✅ Migrated {len(messages)} messages to thread {thread_id}")

    except Exception as e:
        print(f"❌ Error migrating {mode} data: {e}")

def create_default_thread(db, user_id, mode, message_count):
    """Create a default thread for existing chat data"""
    import uuid
    thread_id = str(uuid.uuid4())

    thread_metadata = {
        'thread_id': thread_id,
        'title': f'Imported {mode.title()} Conversations',
        'chatbot_type': mode,
        'created_at': datetime.utcnow().isoformat(),
        'last_message_at': datetime.utcnow().isoformat(),
        'message_count': message_count,
        'uid': user_id
    }

    # Save thread metadata
    thread_ref = db.collection('users').document(user_id).collection('ai_chat').document(mode).collection('threads').document(thread_id)
    thread_ref.set(thread_metadata)

    # Set as active thread
    active_thread_ref = db.collection('users').document(user_id).collection('ai_chat').document(mode).collection('metadata').document('active_thread')
    active_thread_ref.set({'thread_id': thread_id})

    return thread_id

def add_messages_to_thread(db, user_id, mode, thread_id, messages):
    """Add messages to a thread"""
    messages_ref = db.collection('users').document(user_id).collection('ai_chat').document(mode).collection('threads').document(thread_id).collection('messages')

    # Add each message with thread context
    for message in messages:
        message_data = {
            'role': message['role'],
            'content': message['content'],
            'timestamp': message['timestamp'],
            'thread_id': thread_id,
            'uid': user_id
        }
        messages_ref.add(message_data)

if __name__ == "__main__":
    print("🚀 Starting AI Chat Data Migration")
    print("=" * 50)

    # Confirm before proceeding
    response = input("⚠️  This will migrate existing chat data to the new format. Continue? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("❌ Migration cancelled")
        sys.exit(0)

    migrate_chat_data()
