from gemini_analytics import gemini_analytics
from firebase_config import db
from datetime import datetime, timedelta
 
# Get active students
thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
students_query = db.collection('users').where('last_login_date', '>=', thirty_days_ago).limit(10)
 
student_uids = []
for student_doc in students_query.stream():
    student_uids.append(student_doc.id)
 
print(f'Processing {len(student_uids)} active students...')
 
# Process all students
for i, uid in enumerate(student_uids):
    print(f'Processing student {i+1}/{len(student_uids)}: {uid}')
    
    try:
        # Generate predictions
        risk_data, readiness_data = gemini_analytics.predict_student_risk_and_readiness(uid)
        
        if risk_data or readiness_data:
            gemini_analytics.store_student_predictions(uid, risk_data, readiness_data)
            risk_status = risk_data.get('risk', 'unknown') if risk_data else 'no_risk_data'
            print(f'  ✓ Stored predictions - Risk: {risk_status}')
        else:
            print(f'  ⚠ No predictions generated')
            
    except Exception as e:
        print(f'  ✗ Error: {str(e)}')
 
print('Batch processing complete!')