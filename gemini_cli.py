"""
Flask CLI Commands for Gemini Analytics
Provides commands for daily batch processing and analytics updates
"""
import click
from flask import current_app
from firebase_config import db
from datetime import datetime, timedelta
from utils import logger
from gemini_analytics import gemini_analytics


def init_cli_commands(app):
    """Initialize CLI commands with Flask app context"""
    
    @app.cli.command("update-analytics-predictions")
    @click.option("--batch-size", default=50, help="Number of students to process per batch")
    @click.option("--delay", default=1.2, help="Delay between batches in seconds")
    @click.option("--dry-run", is_flag=True, help="Show what would be processed without making changes")
    def update_predictions(batch_size, delay, dry_run):
        """Update risk and readiness predictions for all active students"""
        with app.app_context():
            logger.info("Starting daily analytics prediction update")
            
            # Get active students (logged in within last 30 days)
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
            students_query = db.collection('users').where('last_login_date', '>=', thirty_days_ago).limit(500)
            
            student_uids = []
            for student_doc in students_query.stream():
                student_uids.append(student_doc.id)
            
            if not student_uids:
                logger.info("No active students found for analytics update")
                return
            
            logger.info(f"Found {len(student_uids)} active students to process")
            
            if dry_run:
                logger.info(f"DRY RUN: Would process {len(student_uids)} students in batches of {batch_size}")
                return
            
            # Process students in batches
            batch_results = gemini_analytics.process_students_in_batches(
                student_uids, batch_size=batch_size, delay_between_batches=delay
            )
            
            # Generate predictions for each student
            processed_count = 0
            error_count = 0
            
            for student_data in batch_results:
                uid = student_data['uid']
                try:
                    risk_data, readiness_data = gemini_analytics.predict_student_risk_and_readiness(uid)
                    
                    if risk_data or readiness_data:
                        gemini_analytics.store_student_predictions(uid, risk_data, readiness_data)
                        processed_count += 1
                    else:
                        logger.warning(f"No predictions generated for student {uid}")
                        error_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing predictions for {uid}: {e}")
                    error_count += 1
            
            logger.info(f"Analytics update complete: {processed_count} processed, {error_count} errors")
    
    @app.cli.command("update-class-clusters")
    @click.option("--class-id", help="Specific class ID to cluster (optional)")
    @click.option("--institution-id", help="Process all classes in institution (optional)")
    @click.option("--force", is_flag=True, help="Force update even if recently clustered")
    def update_class_clusters(class_id, institution_id, force):
        """Update study pattern clusters for classes"""
        with app.app_context():
            logger.info("Starting class clustering update")
            
            classes_to_process = []
            
            if class_id:
                # Process specific class
                class_doc = db.collection('classes').document(class_id).get()
                if class_doc.exists:
                    classes_to_process = [{'id': class_id, 'data': class_doc.to_dict()}]
                else:
                    logger.error(f"Class {class_id} not found")
                    return
            elif institution_id:
                # Process all classes in institution
                classes_query = db.collection('classes').where('institution_id', '==', institution_id)
                for class_doc in classes_query.stream():
                    classes_to_process.append({'id': class_doc.id, 'data': class_doc.to_dict()})
            else:
                logger.error("Must provide either --class-id or --institution-id")
                return
            
            logger.info(f"Processing {len(classes_to_process)} classes for clustering")
            
            processed_count = 0
            error_count = 0
            
            for class_info in classes_to_process:
                cid = class_info['id']
                class_data = class_info['data']
                
                try:
                    # Check if recently clustered (unless forced)
                    if not force:
                        last_clustered = class_data.get('last_clustered')
                        if last_clustered:
                            last_date = datetime.fromisoformat(last_clustered)
                            if (datetime.utcnow() - last_date).days < 7:
                                logger.info(f"Skipping class {cid} - clustered within last 7 days")
                                continue
                    
                    # Generate clusters
                    clusters = gemini_analytics.analyze_class_study_patterns(cid)
                    
                    if clusters:
                        gemini_analytics.store_class_clusters(cid, clusters)
                        processed_count += 1
                        logger.info(f"Generated {len(clusters)} clusters for class {cid}")
                    else:
                        logger.warning(f"No clusters generated for class {cid}")
                        error_count += 1
                        
                except Exception as e:
                    logger.error(f"Error clustering class {cid}: {e}")
                    error_count += 1
            
            logger.info(f"Class clustering complete: {processed_count} processed, {error_count} errors")
    
    @app.cli.command("analytics-status")
    def analytics_status():
        """Show current analytics processing status"""
        with app.app_context():
            logger.info("Checking analytics status")
            
            # Count students with recent predictions
            seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            
            risk_predictions = 0
            readiness_predictions = 0
            
            users_query = db.collection('users').limit(100)
            for user_doc in users_query.stream():
                user_data = user_doc.to_dict()
                
                if user_data.get('risk_prediction', {}).get('last_updated', ''):
                    pred_date = user_data['risk_prediction']['last_updated']
                    if pred_date >= seven_days_ago:
                        risk_predictions += 1
                
                if user_data.get('readiness_prediction', {}).get('last_updated', ''):
                    pred_date = user_data['readiness_prediction']['last_updated']
                    if pred_date >= seven_days_ago:
                        readiness_predictions += 1
            
            # Count classes with recent clusters
            clustered_classes = 0
            classes_query = db.collection('classes').limit(50)
            for class_doc in classes_query.stream():
                class_data = class_doc.to_dict()
                if class_data.get('last_clustered', ''):
                    cluster_date = class_data['last_clustered']
                    if (datetime.utcnow() - datetime.fromisoformat(cluster_date)).days < 7:
                        clustered_classes += 1
            
            print(f"""
Analytics Status Report:
==================
Students with recent risk predictions: {risk_predictions}
Students with recent readiness predictions: {readiness_predictions}
Classes with recent clusters: {clustered_classes}
Gemini AI Available: {gemini_analytics.ai_available}
Last updated: {datetime.utcnow().isoformat()}
""")


def register_cli_commands(app):
    """Register all CLI commands with Flask app"""
    init_cli_commands(app)
    
    @app.cli.command("clear-old-predictions")
    @click.option('--confirm', default=False, help='Confirm clearing old predictions')
    def clear_old_predictions(confirm):
        """Clear old AI predictions to force refresh with new prompt"""
        if not confirm:
            print("⚠️  This will clear all existing AI predictions!")
            print("Add --confirm to proceed")
            return
        
        print("Clearing old AI predictions...")
        
        try:
            # Clear all risk and readiness predictions
            users_ref = db.collection('users').stream()
            cleared_count = 0
            
            for user_doc in users_ref:
                user_data = user_doc.to_dict()
                uid = user_doc.id
                
                # Check if user has old predictions
                has_old_predictions = False
                if user_data.get('risk_prediction') or user_data.get('readiness_prediction'):
                    has_old_predictions = True
                
                if has_old_predictions:
                    # Clear predictions
                    updates = {
                        'risk_prediction': None,
                        'readiness_prediction': None
                    }
                    db.collection('users').document(uid).update(updates)
                    cleared_count += 1
            
            print(f"✅ Cleared predictions for {cleared_count} students")
            print("🔄 Run batch predictions to generate new ones:")
            print("   python sclera.py batch-predict-students")
            
        except Exception as e:
            print(f"❌ Error clearing predictions: {e}")
    
    @app.cli.command("test-risk-detection")
    @click.option('--student-id', default='test', help='Test student ID')
    @click.option('--scenario', default='low_completion', help='Test scenario: low_completion, no_sessions, daily_login_no_work')
    def test_risk_detection(student_id, scenario):
        """Test risk detection with different student scenarios"""
        print(f"Testing risk detection with scenario: {scenario}")
        print("=" * 50)
        
        from gemini_analytics import gemini_analytics
        
        # Test scenarios
        scenarios = {
            'low_completion': {
                'uid': student_id,
                'name': 'Test Student - Low Completion',
                'last_login_date': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'login_streak': 30,
                'chapters_completed': {},
                'exam_results': [],
                'purpose': 'school',
                'school': {'board': 'CBSE', 'grade': '10'}
            },
            'no_sessions': {
                'uid': student_id,
                'name': 'Test Student - No Sessions',
                'last_login_date': (datetime.utcnow() - timedelta(days=2)).isoformat(),
                'login_streak': 15,
                'chapters_completed': {'Mathematics': {'Algebra': True}, 'Science': {'Physics': True}},
                'exam_results': [{'percentage': 85, 'date': '2024-01-01'}],
                'purpose': 'school',
                'school': {'board': 'CBSE', 'grade': '10'}
            },
            'daily_login_no_work': {
                'uid': student_id,
                'name': 'Test Student - Daily Login No Work',
                'last_login_date': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'login_streak': 60,
                'chapters_completed': {},
                'exam_results': [],
                'purpose': 'school',
                'school': {'board': 'CBSE', 'grade': '10'}
            }
        }
        
        if scenario not in scenarios:
            print(f"Unknown scenario: {scenario}")
            print("Available scenarios:")
            for key in scenarios.keys():
                print(f"  - {key}")
            return
        
        # Build features and test
        test_data = scenarios[scenario]
        features = gemini_analytics.build_student_features(student_id)
        
        print(f"Student Data:")
        print(f"  Name: {test_data['name']}")
        print(f"  Login: {test_data['last_login_date']} (streak: {test_data['login_streak']})")
        print(f"  Chapters: {len(test_data['chapters_completed'])} completed")
        print(f"  Exams: {len(test_data['exam_results'])} results")
        print()
        
        print("Generated Features:")
        for key, value in features.items():
            if isinstance(value, dict):
                print(f"  {key}: {len(value)} items")
            elif isinstance(value, list):
                print(f"  {key}: {value}")
            else:
                print(f"  {key}: {value}")
        print()
        
        # Test risk prediction
        if gemini_analytics.ai_available:
            print("Testing AI Risk Prediction...")
            try:
                risk_data, readiness_data = gemini_analytics.predict_student_risk_and_readiness(student_id)
                if risk_data:
                    print(f"AI Risk Result: {risk_data['risk'].upper()}")
                    print(f"  Explanation: {risk_data.get('explanation', 'N/A')}")
                    print(f"  Confidence: {risk_data.get('confidence', 0):.2f}")
                    print(f"  Key Factors: {', '.join(risk_data.get('key_factors', []))}")
                else:
                    print("AI Risk Result: Failed to get prediction")
            except Exception as e:
                print(f"AI Risk Error: {e}")
        else:
            print("Gemini AI not available - using rule-based logic")
        
        print()
        print("Test completed!")
