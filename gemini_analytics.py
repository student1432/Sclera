"""
Gemini Analytics Module for Sclera Academic
Provides AI-driven insights for at-risk prediction, readiness scoring, and study pattern clustering
"""
import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import logging

# Import existing modules
from firebase_config import db
from utils import logger
from utils.cache import cached, CacheManager
from templates.academic_data import get_syllabus

# Simple rate limiter to prevent too many concurrent API calls
class RateLimiter:
    def __init__(self, max_calls_per_minute: int = 10):
        self.max_calls = max_calls_per_minute
        self.calls = []
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        with self.lock:
            now = time.time()
            # Remove calls older than 1 minute
            self.calls = [call_time for call_time in self.calls if now - call_time < 60]
            
            if len(self.calls) >= self.max_calls:
                # Calculate how long to wait
                oldest_call = min(self.calls)
                wait_time = 60 - (now - oldest_call)
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
            
            self.calls.append(now)

# Circuit breaker to prevent repeated failures
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        with self.lock:
            if self.state == 'OPEN':
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = 'HALF_OPEN'
                    logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise Exception("Circuit breaker is OPEN - API calls disabled")
            
            try:
                result = func(*args, **kwargs)
                # Success - reset failure count and close circuit
                self.failure_count = 0
                if self.state == 'HALF_OPEN':
                    self.state = 'CLOSED'
                    logger.info("Circuit breaker CLOSED - API calls restored")
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = 'OPEN'
                    logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
                
                raise e

# Global rate limiter and circuit breaker
rate_limiter = RateLimiter(max_calls_per_minute=8)  # Conservative limit
circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=300)  # 5 min recovery


class GeminiAnalytics:
    """Main class for Gemini-powered analytics"""
    
    def __init__(self):
        """Initialize with existing AI assistant"""
        try:
            from ai_assistant import get_ai_assistant
            self.ai_assistant = get_ai_assistant()
            self.ai_available = self.ai_assistant.ai_available if self.ai_assistant else False
            
            # Initialize model management for dynamic switching
            self.exhausted_models = set()
            self.available_models = []
            self.current_model_index = 0
            
            if self.ai_available and hasattr(self.ai_assistant, 'available_models'):
                self.available_models = self.ai_assistant.available_models.copy()
                logger.info(f"Initialized with {len(self.available_models)} available models")
        except Exception as e:
            logger.error(f"Failed to initialize AI assistant: {str(e)}")
            self.ai_available = False
            self.exhausted_models = set()
            self.available_models = []
            self.current_model_index = 0
    
    def _get_working_model(self):
        """Get a working model, switching to next available if current is exhausted"""
        if not self.ai_available or not self.available_models:
            return None
        
        # Try to find a non-exhausted model
        for i in range(len(self.available_models)):
            model_name = self.available_models[self.current_model_index]
            
            if model_name not in self.exhausted_models:
                try:
                    # Try to create a new model instance
                    import google.generativeai as genai
                    model = genai.GenerativeModel(model_name=model_name)
                    logger.info(f"Using model: {model_name}")
                    return model
                except Exception as e:
                    logger.warning(f"Failed to create model {model_name}: {e}")
                    self._mark_model_exhausted()
                    continue
            else:
                # Move to next model if current is exhausted
                self.current_model_index = (self.current_model_index + 1) % len(self.available_models)
        
        # All models exhausted, reset after a delay
        logger.warning("All models exhausted, resetting exhausted list after delay")
        self.exhausted_models.clear()
        self.current_model_index = 0
        
        # Try one more time after reset
        if self.available_models:
            model_name = self.available_models[0]
            try:
                import google.generativeai as genai
                model = genai.GenerativeModel(model_name=model_name)
                logger.info(f"Reset complete, using model: {model_name}")
                return model
            except Exception as e:
                logger.error(f"Failed to create model after reset: {e}")
        
        return None
    
    def _mark_model_exhausted(self):
        """Mark current model as exhausted and move to next"""
        if self.available_models and self.current_model_index < len(self.available_models):
            exhausted_model = self.available_models[self.current_model_index]
            self.exhausted_models.add(exhausted_model)
            logger.info(f"Marked model as exhausted: {exhausted_model}")
            
            # Move to next model
            self.current_model_index = (self.current_model_index + 1) % len(self.available_models)
            next_model = self.available_models[self.current_model_index]
            logger.info(f"Switching to next model: {next_model}")
    
    def get_model_status(self):
        """Get current model status for debugging"""
        return {
            'available_models': self.available_models,
            'exhausted_models': list(self.exhausted_models),
            'current_model_index': self.current_model_index,
            'current_model': self.available_models[self.current_model_index] if self.available_models and self.current_model_index < len(self.available_models) else None
        }
    
    def build_student_features(self, uid: str) -> Dict[str, Any]:
        """
        Build comprehensive feature dictionary for a student
        Includes login frequency, study sessions, chapter completion, exam trends, heatmap patterns
        """
        try:
            # Get user document
            user_doc = db.collection('users').document(uid).get()
            if not user_doc.exists:
                return {}
            
            user_data = user_doc.to_dict()
            features = {
                'uid': uid,
                'name': user_data.get('name', 'Student'),
                'purpose': user_data.get('purpose', ''),
                'login_frequency': self._get_login_frequency(user_data),
                'study_sessions': self._get_study_session_features(uid),
                'chapter_completion': self._get_chapter_completion_features(user_data),
                'exam_trends': self._get_exam_trend_features(user_data),
                'heatmap_patterns': self._get_heatmap_patterns(uid)
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error building features for {uid}: {str(e)}")
            return {}
    
    def _get_login_frequency(self, user_data: Dict) -> Dict[str, Any]:
        """Calculate login frequency metrics"""
        last_login = user_data.get('last_login_date')
        streak = user_data.get('login_streak', 0)
        
        # Calculate days since last login
        days_since_login = 0
        if last_login:
            try:
                last_date = datetime.fromisoformat(last_login)
                days_since_login = (datetime.utcnow() - last_date).days
            except:
                pass
        
        return {
            'last_login_date': last_login,
            'days_since_login': days_since_login,
            'login_streak': streak,
            'recent_activity': days_since_login <= 7
        }
    
    def _get_study_session_features(self, uid: str) -> Dict[str, Any]:
        """Analyze study session patterns"""
        try:
            # Get last 30 days of sessions
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
            sessions_ref = db.collection('users').document(uid).collection('study_sessions').where('start_time', '>=', thirty_days_ago).stream()
            
            sessions = []
            total_duration = 0
            
            for session_doc in sessions_ref:
                session_data = session_doc.to_dict()
                sessions.append(session_data)
                total_duration += session_data.get('duration', 0)
            
            if not sessions:
                return {
                    'session_count_30d': 0,
                    'avg_duration': 0,
                    'total_duration_30d': 0,
                    'consistency_score': 0
                }
            
            # Calculate metrics
            avg_duration = total_duration / len(sessions)
            
            # Consistency: sessions per week
            sessions_by_week = defaultdict(int)
            for session in sessions:
                try:
                    session_date = datetime.fromisoformat(session['start_time'])
                    week_num = session_date.isocalendar()[1]
                    sessions_by_week[week_num] += 1
                except:
                    pass
            
            consistency_score = 0
            if sessions_by_week:
                avg_sessions_per_week = sum(sessions_by_week.values()) / len(sessions_by_week)
                consistency_score = min(100, avg_sessions_per_week * 20)  # Scale to 0-100
            
            return {
                'session_count_30d': len(sessions),
                'avg_duration': round(avg_duration, 2),
                'total_duration_30d': total_duration,
                'consistency_score': round(consistency_score, 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting study session features for {uid}: {str(e)}")
            return {'session_count_30d': 0, 'avg_duration': 0, 'total_duration_30d': 0, 'consistency_score': 0}
    
    def _get_chapter_completion_features(self, user_data: Dict) -> Dict[str, Any]:
        """Analyze chapter completion by subject"""
        try:
            chapters_completed = user_data.get('chapters_completed', {})
            purpose = user_data.get('purpose')
            
            if not chapters_completed:
                return {'overall_completion': 0, 'by_subject': {}, 'total_chapters': 0, 'completed_chapters': 0}
            
            # Get syllabus for total chapter counts
            total_by_subject = {}
            if purpose == 'school' and user_data.get('school'):
                school = user_data['school']
                syllabus = get_syllabus('school', school.get('board'), school.get('grade'), 
                                     subject_combination=school.get('subject_combination'))
                for subject, data in syllabus.items():
                    total_by_subject[subject] = len(data.get('chapters', {}))
            elif purpose == 'exam_prep' and user_data.get('exam'):
                syllabus = get_syllabus('exam', user_data['exam'].get('type'))
                for subject, data in syllabus.items():
                    total_by_subject[subject] = len(data.get('chapters', {}))
            
            # Calculate completion rates
            by_subject = {}
            total_chapters = 0
            completed_chapters = 0
            
            for subject, completed_chapters_dict in chapters_completed.items():
                total_chapters_subject = total_by_subject.get(subject, 0)
                completed_count = sum(1 for completed in completed_chapters_dict.values() if completed)
                
                if total_chapters_subject > 0:
                    completion_rate = (completed_count / total_chapters_subject) * 100
                    by_subject[subject] = round(completion_rate, 1)
                    total_chapters += total_chapters_subject
                    completed_chapters += completed_count
            
            overall_completion = (completed_chapters / total_chapters * 100) if total_chapters > 0 else 0
            
            return {
                'overall_completion': round(overall_completion, 1),
                'by_subject': by_subject,
                'total_chapters': total_chapters,
                'completed_chapters': completed_chapters
            }
            
        except Exception as e:
            logger.error(f"Error getting chapter completion features: {str(e)}")
            return {'overall_completion': 0, 'by_subject': {}, 'total_chapters': 0, 'completed_chapters': 0}
    
    def _get_exam_trend_features(self, user_data: Dict) -> Dict[str, Any]:
        """Analyze exam score trends and momentum"""
        try:
            exam_results = user_data.get('exam_results', [])
            
            if len(exam_results) < 2:
                return {
                    'recent_scores': [],
                    'avg_score': 0,
                    'momentum': 0,
                    'score_trend': 'insufficient_data'
                }
            
            # Sort by date and get last 4 exams
            sorted_results = sorted(exam_results, key=lambda x: x.get('date', ''), reverse=True)[:4]
            recent_scores = []
            
            for result in sorted_results:
                try:
                    if 'percentage' in result:
                        score = float(result['percentage'])
                    elif 'score' in result and 'max_score' in result:
                        score = (float(result['score']) / float(result['max_score'])) * 100
                    else:
                        continue
                    recent_scores.append(score)
                except:
                    continue
            
            if len(recent_scores) < 2:
                return {
                    'recent_scores': recent_scores,
                    'avg_score': 0,
                    'momentum': 0,
                    'score_trend': 'insufficient_data'
                }
            
            # Calculate metrics
            avg_score = sum(recent_scores) / len(recent_scores)
            
            # Momentum: difference between oldest and newest
            momentum = recent_scores[0] - recent_scores[-1]  # newest - oldest
            
            # Trend classification
            if momentum > 5:
                score_trend = 'improving'
            elif momentum < -5:
                score_trend = 'declining'
            else:
                score_trend = 'stable'
            
            return {
                'recent_scores': recent_scores,
                'avg_score': round(avg_score, 1),
                'momentum': round(momentum, 1),
                'score_trend': score_trend
            }
            
        except Exception as e:
            logger.error(f"Error getting exam trend features: {str(e)}")
            return {'recent_scores': [], 'avg_score': 0, 'momentum': 0, 'score_trend': 'error'}
    
    def _get_heatmap_patterns(self, uid: str) -> Dict[str, Any]:
        """Extract study pattern from heatmap data"""
        try:
            # Get last 30 days of sessions for heatmap
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
            sessions_ref = db.collection('users').document(uid).collection('study_sessions').where('start_time', '>=', thirty_days_ago).stream()
            
            # Aggregate by weekday and hour
            time_slots = defaultdict(int)
            total_sessions = 0
            
            for session_doc in sessions_ref:
                session_data = session_doc.to_dict()
                local_hour = session_data.get('local_hour')
                local_weekday = session_data.get('local_weekday')
                
                if local_hour is not None and local_weekday is not None:
                    slot_key = f"{local_weekday}-{local_hour}"
                    time_slots[slot_key] += 1
                    total_sessions += 1
            
            if total_sessions == 0:
                return {
                    'peak_times': [],
                    'study_pattern': 'no_data',
                    'consistency_score': 0
                }
            
            # Find top 3 most active time slots
            sorted_slots = sorted(time_slots.items(), key=lambda x: x[1], reverse=True)[:3]
            peak_times = [{"weekday": int(slot.split('-')[0]), "hour": int(slot.split('-')[1]), "count": count} 
                        for slot, count in sorted_slots]
            
            # Determine study pattern
            weekday_sessions = sum(count for slot, count in time_slots.items() if int(slot.split('-')[0]) < 5)  # Mon-Fri
            weekend_sessions = sum(count for slot, count in time_slots.items() if int(slot.split('-')[0]) >= 5)  # Sat-Sun
            
            if weekend_sessions > weekday_sessions * 1.5:
                study_pattern = 'weekend_warrior'
            elif any(slot['hour'] >= 22 for slot in peak_times):
                study_pattern = 'night_owl'
            elif any(6 <= slot['hour'] <= 9 for slot in peak_times):
                study_pattern = 'morning_regular'
            else:
                study_pattern = 'irregular'
            
            # Consistency: distribution across different times
            unique_slots = len(time_slots)
            max_possible_slots = 7 * 24  # 7 days * 24 hours
            consistency_score = (unique_slots / max_possible_slots) * 100
            
            return {
                'peak_times': peak_times,
                'study_pattern': study_pattern,
                'consistency_score': round(consistency_score, 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting heatmap patterns for {uid}: {str(e)}")
            return {'peak_times': [], 'study_pattern': 'error', 'consistency_score': 0}
    
    def at_risk_prompt(self, features: Dict[str, Any]) -> str:
        """Generate prompt for at-risk classification"""
        return f"""
You are an academic analytics expert. Based on the following student data, determine if the student is at risk of falling behind academically.

Student Data:
{json.dumps(features, indent=2)}

CRITICAL RISK THRESHOLDS:
- Overall completion rate < 25% = AUTOMATIC AT_RISK
- Any subject completion rate < 20% = AUTOMATIC AT_RISK  
- Study sessions < 5 in 30 days = AUTOMATIC AT_RISK
- No chapter completion despite 30+ days = AUTOMATIC AT_RISK

RISK CLASSIFICATION RULES:
1. If overall_completion < 25.0% → MUST classify as "at_risk"
2. If any subject completion < 20.0% → MUST classify as "at_risk"
3. If session_count_30d < 5 → MUST classify as "at_risk"
4. Only classify as "not_at_risk" if ALL conditions are met:
   * Overall completion ≥ 40%
   * All subjects ≥ 25% completion
   * Study sessions ≥ 10 in 30 days
   * Recent academic activity

Login frequency alone does NOT override low academic completion. A student who logs in daily but completes <25% of chapters IS at risk.

Return a JSON response with:
{{
  "risk": "at_risk" or "not_at_risk",
  "explanation": "Brief explanation focusing on completion rates and academic engagement",
  "confidence": 0.0 to 1.0,
  "key_factors": ["factor1", "factor2"] // Main factors influencing decision
}}

PRIORITIZE ACADEMIC COMPLETION OVER LOGIN ACTIVITY. Low completion = AT RISK, regardless of login frequency.
"""
    
    def readiness_prompt(self, features: Dict[str, Any]) -> str:
        """Generate prompt for readiness scoring"""
        return f"""
You are an academic readiness expert. Based on the following student data, calculate their academic readiness score (0-100) and provide a summary assessment.

Student Data:
{json.dumps(features, indent=2)}

Consider:
- Overall academic progress and completion rates
- Recent performance trends and momentum
- Study consistency and patterns
- Subject-specific strengths and weaknesses

Return a JSON response with:
{{
  "readiness_score": 0-100,
  "summary": "Brief assessment of readiness (2-3 sentences)",
  "strengths": ["strength1", "strength2"],
  "areas_for_improvement": ["area1", "area2"],
  "subject_insights": {{"subject": "Physics", "status": "strong/average/weak", "focus": "specific topic"}}
}}

Be encouraging but realistic. The score should reflect true preparedness.
"""
    
    def clustering_prompt(self, class_students_data: List[Dict[str, Any]]) -> str:
        """Generate prompt for study pattern clustering"""
        # Summarize each student for the prompt
        student_summaries = []
        for student in class_students_data:
            summary = {
                'uid': student['uid'],
                'name': student['name'],
                'study_pattern': student.get('heatmap_patterns', {}).get('study_pattern', 'unknown'),
                'consistency_score': student.get('heatmap_patterns', {}).get('consistency_score', 0),
                'peak_times': student.get('heatmap_patterns', {}).get('peak_times', [])[:2],  # Top 2 times
                'session_frequency': student.get('study_sessions', {}).get('session_count_30d', 0)
            }
            student_summaries.append(summary)
        
        return f"""
You are an educational data scientist specializing in study pattern analysis. Based on the following class data, identify natural clusters of students with similar study habits.

Class Student Data:
{json.dumps(student_summaries, indent=2)}

Analyze patterns like:
- Study timing preferences (morning, afternoon, evening, late night)
- Consistency levels
- Weekend vs weekday preferences
- Study frequency patterns

Return a JSON response with an array of clusters:
{{
  "clusters": [
    {{
      "label": "Descriptive cluster name (e.g., 'Night Owls', 'Morning Regulars')",
      "description": "Brief description of this group's study habits",
      "student_uids": ["uid1", "uid2"],
      "common_characteristics": ["characteristic1", "characteristic2"],
      "performance_note": "General observation about this group's academic performance"
    }}
  ]
}}

Create 3-5 meaningful clusters that capture the main study patterns in the class.
"""
    
    def call_gemini_with_rate_limit(self, prompt: str, retries: int = 3) -> Optional[Dict[str, Any]]:
        """Call Gemini API with improved rate limiting and dynamic model switching"""
        if not self.ai_available:
            logger.warning("Gemini AI not available for analytics")
            return None
        
        def _make_api_call():
            # Wait if we've made too many calls recently
            rate_limiter.wait_if_needed()
            
            for attempt in range(retries):
                try:
                    # Add initial delay for first attempt to avoid immediate rate limiting
                    if attempt == 0:
                        time.sleep(0.5)
                    
                    # Try to get a working model
                    model = self._get_working_model()
                    if not model:
                        raise Exception("No working AI models available")
                    
                    # Use the model to call Gemini
                    chat = model.start_chat(history=[])
                    response = chat.send_message(prompt, stream=False)
                    
                    if response and hasattr(response, 'text'):
                        # Parse JSON response
                        try:
                            # Extract JSON from response text
                            response_text = response.text.strip()
                            
                            # Handle responses with explanatory text + JSON code blocks
                            if '```json' in response_text:
                                # Extract JSON code block
                                start_idx = response_text.find('```json') + 7
                                end_idx = response_text.find('```', start_idx)
                                if end_idx != -1:
                                    response_text = response_text[start_idx:end_idx].strip()
                            elif response_text.startswith('```json'):
                                # Handle case where response starts with ```json
                                response_text = response_text[7:-3]  # Remove ```json and ```
                            elif response_text.startswith('{') and response_text.endswith('}'):
                                # Direct JSON response
                                pass  # Use as-is
                            else:
                                # Try to find JSON in the text
                                import re
                                json_pattern = r'\{[\s\S]*\}'
                                match = re.search(json_pattern, response_text)
                                if match:
                                    response_text = match.group(0)
                            
                            return json.loads(response_text)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse Gemini JSON response: {e}")
                            logger.error(f"Response text: {response.text}")
                            if attempt < retries - 1:
                                time.sleep(2)  # Wait before retry on parse error
                            continue
                    else:
                        logger.error("Empty response from Gemini")
                        if attempt < retries - 1:
                            time.sleep(2)  # Wait before retry on empty response
                        continue
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    # Check for rate limit errors
                    if 'rate limit' in error_msg or 'quota' in error_msg or '429' in error_msg or 'resource exhausted' in error_msg:
                        # Mark current model as exhausted and try next
                        self._mark_model_exhausted()
                        logger.warning(f"Model exhausted, switching to next available model")
                        
                        # More conservative exponential backoff: 5s, 10s, 20s
                        wait_time = 5 * (2 ** attempt)
                        logger.warning(f"Rate limit hit, waiting {wait_time}s before retry {attempt + 1}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Gemini API error: {e}")
                        if attempt == retries - 1:
                            raise e  # Re-raise to trigger circuit breaker
                        time.sleep(3)  # Wait 3s for other errors
            
            logger.error(f"Failed to get Gemini response after {retries} attempts")
            raise Exception("All retry attempts failed")
        
        try:
            return circuit_breaker.call(_make_api_call)
        except Exception as e:
            if "Circuit breaker is OPEN" in str(e):
                logger.warning("Circuit breaker prevented API call due to repeated failures")
                return None
            else:
                logger.error(f"API call failed: {e}")
                return None
    
    def process_students_in_batches(self, student_uids: List[str], batch_size: int = 30, 
                                delay_between_batches: float = 3.0) -> List[Dict[str, Any]]:
        """Process students in smaller batches with longer delays to respect rate limits"""
        results = []
        total_batches = (len(student_uids) + batch_size - 1) // batch_size
        
        for i in range(0, len(student_uids), batch_size):
            batch_uids = student_uids[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            logger.info(f"Processing batch {batch_num}/{total_batches} with {len(batch_uids)} students")
            
            batch_results = []
            for uid in batch_uids:
                try:
                    features = self.build_student_features(uid)
                    if features:
                        batch_results.append({'uid': uid, 'features': features})
                except Exception as e:
                    logger.error(f"Error processing student {uid}: {e}")
                    continue
            
            results.extend(batch_results)
            
            # Add longer delay between batches (except last batch)
            if i + batch_size < len(student_uids):
                logger.info(f"Waiting {delay_between_batches}s before next batch...")
                time.sleep(delay_between_batches)
        
        return results
    
    def predict_student_risk_and_readiness(self, uid: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Predict both risk and readiness for a student with manual caching"""
        # Check cache first
        cache_key = f"gemini_risk:predict_student_risk_and_readiness:{uid}"
        cached_result = CacheManager.get(cache_key)
        if cached_result:
            logger.info(f"Using cached risk/readiness prediction for student {uid}")
            return cached_result.get('risk'), cached_result.get('readiness')
        
        try:
            features = self.build_student_features(uid)
            if not features:
                return None, None
            
            # Combine both predictions in one API call to save requests
            combined_prompt = f"""
{self.at_risk_prompt(features)}

---

{self.readiness_prompt(features)}

Return a single JSON response with both predictions:
{{
  "risk_prediction": {{
    "risk": "at_risk" or "not_at_risk",
    "explanation": "Brief explanation",
    "confidence": 0.0 to 1.0,
    "key_factors": ["factor1", "factor2"]
  }},
  "readiness_prediction": {{
    "readiness_score": 0-100,
    "summary": "Brief assessment",
    "strengths": ["strength1", "strength2"],
    "areas_for_improvement": ["area1", "area2"],
    "subject_insights": {{"subject": "Physics", "status": "strong/average/weak", "focus": "specific topic"}}
  }}
}}
"""
            
            response = self.call_gemini_with_rate_limit(combined_prompt)
            
            if response:
                risk_data = response.get('risk_prediction')
                readiness_data = response.get('readiness_prediction')
                
                # Cache the result
                result_to_cache = {'risk': risk_data, 'readiness': readiness_data}
                CacheManager.set(cache_key, result_to_cache, timeout=3600)  # 1 hour cache
                logger.info(f"Cached risk/readiness prediction for student {uid}")
                
                return risk_data, readiness_data
            else:
                return None, None
                
        except Exception as e:
            logger.error(f"Error predicting for student {uid}: {e}")
            return None, None
    
    def analyze_class_study_patterns(self, class_id: str) -> List[Dict[str, Any]]:
        """Analyze study patterns for all students in a class with manual caching"""
        # Check cache first
        cache_key = f"gemini_cluster:analyze_class_study_patterns:{class_id}"
        cached_result = CacheManager.get(cache_key)
        if cached_result:
            logger.info(f"Using cached clustering for class {class_id}")
            return cached_result
        
        try:
            # Get class document
            class_doc = db.collection('classes').document(class_id).get()
            if not class_doc.exists:
                return []
            
            class_data = class_doc.to_dict()
            student_uids = class_data.get('student_uids', [])
            
            if not student_uids:
                return []
            
            # Build features for all students in class
            class_students_data = []
            for uid in student_uids:
                features = self.build_student_features(uid)
                if features:
                    features['uid'] = uid
                    class_students_data.append(features)
            
            # Call Gemini for clustering
            prompt = self.clustering_prompt(class_students_data)
            response = self.call_gemini_with_rate_limit(prompt)
            
            if response and 'clusters' in response:
                clusters = response['clusters']
                
                # Cache the result
                CacheManager.set(cache_key, clusters, timeout=7200)  # 2 hour cache
                logger.info(f"Cached clustering result for class {class_id}")
                
                return clusters
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error analyzing class patterns for {class_id}: {e}")
            return []
    
    def store_student_predictions(self, uid: str, risk_data: Optional[Dict], readiness_data: Optional[Dict]):
        """Store risk and readiness predictions in Firestore"""
        try:
            user_ref = db.collection('users').document(uid)
            timestamp = datetime.utcnow().isoformat()
            
            updates = {}
            
            if risk_data:
                updates['risk_prediction'] = {
                    **risk_data,
                    'last_updated': timestamp,
                    'prompt_version': 'v2'  # Track new prompt version
                }
            
            if readiness_data:
                updates['readiness_prediction'] = {
                    **readiness_data,
                    'last_updated': timestamp,
                    'prompt_version': 'v2'  # Track new prompt version
                }
            
            if updates:
                user_ref.update(updates)
                logger.info(f"Stored predictions for student {uid}")
            
        except Exception as e:
            logger.error(f"Error storing predictions for {uid}: {e}")
    
    def store_class_clusters(self, class_id: str, clusters: List[Dict[str, Any]]):
        """Store study pattern clusters in Firestore"""
        try:
            class_ref = db.collection('classes').document(class_id)
            timestamp = datetime.utcnow().isoformat()
            
            cluster_data = {
                'study_clusters': clusters,
                'last_clustered': timestamp
            }
            
            class_ref.update(cluster_data)
            logger.info(f"Stored {len(clusters)} clusters for class {class_id}")
            
        except Exception as e:
            logger.error(f"Error storing clusters for class {class_id}: {e}")


# Global instance
gemini_analytics = GeminiAnalytics()
