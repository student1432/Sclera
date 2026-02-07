from firebase_config import db
from datetime import datetime, timedelta
import random

def seed_data():
    # 1. Find a teacher or admin to associate the institution
    inst_id = "INST_001"
    
    # Check if institution exists, else create
    inst_ref = db.collection('institutions').document(inst_id)
    if not inst_ref.get().exists:
        inst_ref.set({
            'name': 'Test Academy',
            'created_at': datetime.utcnow().isoformat()
        })
    
    # 2. Create a test student
    student_uid = "test_student_ai_001"
    student_ref = db.collection('users').document(student_uid)
    
    # Set up declining results for AI verification (Momentum < -5)
    exam_results = [
        {'date': (datetime.utcnow() - timedelta(days=10)).isoformat(), 'score': 85, 'max_score': 100, 'test_types': 'Unit Test 1', 'percentage': 85},
        {'date': (datetime.utcnow() - timedelta(days=5)).isoformat(), 'score': 70, 'max_score': 100, 'test_types': 'Unit Test 2', 'percentage': 70},
    ]
    
    # Set up stagnation verification (last login > 7 days ago)
    last_login_date = (datetime.utcnow() - timedelta(days=10)).isoformat()
    
    student_data = {
        'uid': student_uid,
        'name': 'Verification Student',
        'email': 'verify@example.com',
        'role': 'student',
        'institution_id': inst_id,
        'class_ids': ['test_class_1'],
        'last_login_date': last_login_date,
        'exam_results': exam_results,
        'created_at': datetime.utcnow().isoformat()
    }
    student_ref.set(student_data)
    
    # 3. Create test class
    class_ref = db.collection('classes').document('test_class_1')
    class_ref.set({
        'name': 'AI Test Class',
        'institution_id': inst_id,
        'students': [student_uid]
    })
    
    # 4. Seed Heatmap Data (Study Sessions)
    print("Seeding heatmap sessions...")
    # Add sessions for the last 7 days at various hours
    for day in range(7):
        curr_date = datetime.utcnow() - timedelta(days=day)
        # Add 3 sessions per day at different hours
        for hour in [9, 14, 20]:
            session_time = curr_date.replace(hour=hour, minute=0, second=0)
            session_id = f"session_{day}_{hour}"
            student_ref.collection('study_sessions').document(session_id).set({
                'start_time': session_time.isoformat(),
                'duration_seconds': 3600,
                'last_updated': session_time.isoformat()
            })
    
    print(f"Successfully seeded data for Student: {student_uid}")
    print(f"Institution ID: {inst_id}")
    print("AI Verification: This student should show as 'critical' or 'stagnating/declining' on the dashboard.")
    print("Heatmap Verification: The heatmap should now show activity blocks.")

if __name__ == "__main__":
    seed_data()
