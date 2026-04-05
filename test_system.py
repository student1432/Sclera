"""
test_system.py — SaveMyExams-style MCQ Test System for Sclera Academic
"""
import re, uuid, random, time, os, logging
from datetime import datetime
from typing import List, Dict, Optional

from firebase_config import db
from firebase_admin import firestore

logger = logging.getLogger(__name__)


class TestSystem:

    _qcount_cache: Dict = {}
    _qcount_ts: float   = 0.0
    _CACHE_TTL           = 300   # 5 min

    def __init__(self):
        self.db = db

    # ── Slug / topic-id ───────────────────────────────────────────────────────

    @staticmethod
    def slugify(text: str) -> str:
        t = text.lower().strip()
        t = re.sub(r"['\"/\\]", "", t)
        t = re.sub(r"[^a-z0-9]+", "-", t)
        return t.strip("-")

    def make_topic_id(self, board, grade, subject, chapter, topic) -> str:
        return "_".join([
            board.lower(), str(grade),
            self.slugify(subject), self.slugify(chapter), self.slugify(topic),
        ])

    # ── Question bank ─────────────────────────────────────────────────────────

    def add_question(self, q: dict) -> str:
        qid = q.get("question_id") or str(uuid.uuid4())
        q["question_id"] = qid
        q.setdefault("created_at", datetime.utcnow())
        q.setdefault("times_used", 0)
        q.setdefault("times_correct", 0)
        q.setdefault("is_active", True)
        self.db.collection("questions").document(qid).set(q)
        return qid

    def get_questions_for_topic(
        self,
        topic_id: str,
        difficulty: Optional[str] = None,
        num_questions: int = 10,
    ) -> List[dict]:
        q = (
            self.db.collection("questions")
            .where("topic_id", "==", topic_id)
            .where("is_active", "==", True)
        )
        if difficulty and difficulty != "mixed":
            q = q.where("difficulty", "==", difficulty)
        docs = list(q.stream())
        questions = [self._full_q(d.to_dict()) for d in docs]
        random.shuffle(questions)
        return questions[:num_questions]

    def get_questions_for_mock(
        self,
        board: str,
        grade: str,
        subject: Optional[str] = None,
        num_questions: int = 30,
    ) -> List[dict]:
        q = (
            self.db.collection("questions")
            .where("board", "==", board.lower())
            .where("grade", "==", str(grade))
            .where("is_active", "==", True)
        )
        if subject:
            q = q.where("subject", "==", subject)
        docs = list(q.limit(num_questions * 4).stream())
        questions = [self._full_q(d.to_dict()) for d in docs]
        random.shuffle(questions)
        return questions[:num_questions]

    def get_all_question_counts(self) -> Dict[str, Dict]:
        now = time.time()
        if now - self._qcount_ts < self._CACHE_TTL and self._qcount_cache:
            return self._qcount_cache
        counts: Dict[str, Dict] = {}
        for d in self.db.collection("questions").where("is_active", "==", True).stream():
            q    = d.to_dict()
            tid  = q.get("topic_id", "")
            diff = q.get("difficulty", "medium")
            if tid not in counts:
                counts[tid] = {"total": 0, "easy": 0, "medium": 0, "hard": 0}
            counts[tid]["total"] += 1
            if diff in counts[tid]:
                counts[tid][diff] += 1
        TestSystem._qcount_cache = counts
        TestSystem._qcount_ts = now
        return counts

    def invalidate_count_cache(self):
        TestSystem._qcount_ts = 0.0

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(
        self,
        user_id: str,
        questions: List[dict],
        mode: str,
        topic_id: Optional[str] = None,
        subject: Optional[str] = None,
        time_limit_minutes: Optional[int] = None,
    ) -> str:
        sid = str(uuid.uuid4())
        self.db.collection("test_sessions").document(sid).set({
            "session_id": sid,
            "user_id": user_id,
            "mode": mode,
            "topic_id": topic_id,
            "subject": subject,
            "question_ids": [q["question_id"] for q in questions],
            "time_limit_minutes": time_limit_minutes,
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "answers": [],
        })
        batch = self.db.batch()
        for q in questions:
            ref = self.db.collection("questions").document(q["question_id"])
            batch.update(ref, {"times_used": firestore.Increment(1)})
        batch.commit()
        return sid

    def check_answer(
        self,
        user_id: str,
        session_id: str,
        question_id: str,
        selected_option: int,
        submit_answer: bool = True,
    ) -> dict:
        """Check answer and optionally submit it for scoring."""
        sess_doc = self.db.collection("test_sessions").document(session_id).get()
        if not sess_doc.exists:
            raise ValueError("Session not found")
        sess = sess_doc.to_dict()
        if sess["user_id"] != user_id:
            raise PermissionError("Not your session")

        # Get question
        q_doc = self.db.collection("questions").document(question_id).get()
        if not q_doc.exists:
            raise ValueError("Question not found")
        q = q_doc.to_dict()

        correct_index = q["correct_option_index"]
        is_correct    = selected_option == correct_index

        # Only submit for scoring if submit_answer is True
        if submit_answer:
            self.db.collection("test_sessions").document(session_id).update({
                "answers": firestore.ArrayUnion([{
                    "question_id": question_id,
                    "selected_option": selected_option,
                    "is_correct": is_correct,
                    "topic_id": q.get("topic_id", ""),
                    "answered_at": datetime.utcnow().isoformat(),
                    "submitted_at": datetime.utcnow().isoformat(),  # Track submission time
                }])
            })
            
            # Update question statistics
            if is_correct:
                self.db.collection("questions").document(question_id).update(
                    {"times_correct": firestore.Increment(1)}
                )
            
            # Update topic performance
            topic_id = q.get("topic_id", "")
            if topic_id:
                self._update_topic_performance(user_id, topic_id, is_correct)

        return {
            "is_correct": is_correct,
            "correct_option_index": correct_index,
            "explanation": q.get("explanation", ""),
            "topic_id": topic_id,
            "submitted": submit_answer,
        }

    def complete_session(self, user_id: str, session_id: str) -> dict:
        sess_doc = self.db.collection("test_sessions").document(session_id).get()
        if not sess_doc.exists:
            raise ValueError("Session not found")
        sess = sess_doc.to_dict()
        if sess["user_id"] != user_id:
            raise PermissionError("Not your session")

        answers = sess.get("answers", [])
        total_questions = len(sess.get("question_ids", []))
        
        # Count only submitted answers for scoring
        submitted_answers = [a for a in answers if a.get("submitted_at")]
        submitted_count = len(submitted_answers)
        correct = sum(1 for a in submitted_answers if a.get("is_correct"))
        
        # Calculate score based on submitted answers only
        score = round(correct / submitted_count * 100, 1) if submitted_count > 0 else 0.0
        
        now = datetime.utcnow()

        self.db.collection("test_sessions").document(session_id).update({
            "completed_at": now, 
            "score": score,
            "correct_count": correct, 
            "submitted_count": submitted_count,
            "total_count": total_questions,
            "attempted_count": len(answers),  # Track attempted (selected) vs submitted
        })

        results = []
        for a in submitted_answers:  # Only include submitted answers in results
            qd = self.db.collection("questions").document(a["question_id"]).get()
            if qd.exists:
                q = qd.to_dict()
                results.append({
                    "question_id": a["question_id"],
                    "text": q.get("text", ""),
                    "options": q.get("options", []),
                    "correct_option_index": q.get("correct_option_index"),
                    "selected_option": a.get("selected_option"),
                    "is_correct": a.get("is_correct"),
                    "explanation": q.get("explanation", ""),
                    "topic_id": a.get("topic_id"),
                    "submitted_at": a.get("submitted_at"),
                })

        attempt_id = self.db.collection("users").document(user_id).collection("quiz_attempts").document().id
        self.db.collection("users").document(user_id).collection("quiz_attempts").document(attempt_id).set({
            "attempt_id": attempt_id,
            "session_id": session_id,
            "mode": sess.get("mode"),
            "topic_id": sess.get("topic_id"),
            "subject": sess.get("subject"),
            "board": sess.get("board"),
            "grade": sess.get("grade"),
            "score": score,
            "correct_count": correct,
            "submitted_count": submitted_count,
            "total_count": total_questions,
            "attempted_count": len(answers),
            "completed_at": now,
            "results": results,
        })

        return {
            "attempt_id": attempt_id,
            "score": score,
            "correct_count": correct,
            "submitted_count": submitted_count,
            "total_count": total_questions,
            "attempted_count": len(answers),
            "results": results,
        }

    # ── Performance ───────────────────────────────────────────────────────────

    def _update_topic_performance(self, user_id: str, topic_id: str, is_correct: bool):
        ref = (
            self.db.collection("users").document(user_id)
            .collection("topic_performance").document(topic_id)
        )
        doc  = ref.get()
        now  = datetime.utcnow()
        data = doc.to_dict() if doc.exists else {
            "topic_id": topic_id, "total_attempted": 0,
            "total_correct": 0, "accuracy": 0.0,
            "confidence": "not_started", "last_practiced": now,
            "recent_attempts": []  # Track recent attempts for better confidence calculation
        }
        data["total_attempted"] = data.get("total_attempted", 0) + 1
        if is_correct:
            data["total_correct"] = data.get("total_correct", 0) + 1
        t = data["total_attempted"]
        c = data["total_correct"]
        data["accuracy"]       = c / t if t > 0 else 0.0
        
        # Recent attempts logic - keep last 2 attempts for confidence calculation
        recent = data.get("recent_attempts", [])
        recent.append({"correct": is_correct, "timestamp": now})
        # Keep only last 2 attempts
        data["recent_attempts"] = recent[-2:] if len(recent) > 2 else recent
        
        # Calculate confidence based on recent performance (last 2 attempts)
        if len(data["recent_attempts"]) >= 1:  # Need at least 1 recent attempt
            recent_correct = sum(1 for attempt in data["recent_attempts"] if attempt["correct"])
            recent_accuracy = recent_correct / len(data["recent_attempts"])
            data["confidence"] = "confident" if recent_accuracy >= 0.70 else "practiced"
        else:
            # For first attempt, use overall accuracy
            data["confidence"] = "confident" if data["accuracy"] >= 0.70 else "practiced"
        
        data["last_practiced"] = now
        ref.set(data)
        
        # Invalidate question count cache to ensure fresh data
        self.invalidate_count_cache()

    def get_all_performances(self, user_id: str) -> Dict[str, dict]:
        docs = (
            self.db.collection("users").document(user_id)
            .collection("topic_performance").stream()
        )
        return {d.id: d.to_dict() for d in docs}

    # ── Attempt retrieval ─────────────────────────────────────────────────────

    def get_attempt(self, user_id: str, attempt_id: str) -> Optional[dict]:
        doc = (
            self.db.collection("users").document(user_id)
            .collection("quiz_attempts").document(attempt_id).get()
        )
        if not doc.exists:
            return None
        a = doc.to_dict()
        for k in ("started_at", "completed_at"):
            v = a.get(k)
            if hasattr(v, "isoformat"):
                a[k] = v.isoformat()
        return a

    def get_recent_attempts(self, user_id: str, limit: int = 8) -> List[dict]:
        docs = list(
            self.db.collection("users").document(user_id)
            .collection("quiz_attempts")
            .order_by("completed_at", direction=firestore.Query.DESCENDING)
            .limit(limit).stream()
        )
        out = []
        for d in docs:
            a = d.to_dict()
            
            # Check if required fields exist
            if not a.get('attempt_id'):
                continue
                
            a.pop("results", None)
            for k in ("started_at", "completed_at"):
                v = a.get(k)
                if hasattr(v, "isoformat"):
                    a[k] = v.isoformat()
            out.append(a)
        return out

    # ── AI explanation ────────────────────────────────────────────────────────

    def get_ai_explanation(
        self,
        question_text: str,
        options: List[str],
        correct_index: int,
        stored_explanation: str,
    ) -> Optional[str]:
        try:
            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key:
                return None
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash-lite")
            correct_ans = options[correct_index] if correct_index < len(options) else ""
            prompt = (
                f"A student answered this MCQ incorrectly. Write a clear 2-3 sentence explanation.\n"
                f"Question: {question_text}\n"
                f"Correct answer: {correct_ans}\n"
                f"Base explanation: {stored_explanation}\n"
                f"Explain WHY this is correct in simple student-friendly language. Plain text only."
            )
            return model.generate_content(prompt).text.strip()
        except Exception as e:
            logger.warning(f"AI explanation failed: {e}")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _full_q(q: dict) -> dict:
        """Return all fields (correct_option_index included — stripped at API layer)."""
        return {
            "question_id":          q.get("question_id", ""),
            "text":                 q.get("text", ""),
            "options":              q.get("options", []),
            "correct_option_index": q.get("correct_option_index", 0),
            "difficulty":           q.get("difficulty", "medium"),
            "topic_id":             q.get("topic_id", ""),
            "subject":              q.get("subject", ""),
            "chapter":              q.get("chapter", ""),
        }

    @staticmethod
    def _client_q(q: dict) -> dict:
        """Strip correct answer before sending to browser."""
        return {k: q[k] for k in ("question_id", "text", "options", "difficulty", "topic_id", "subject", "chapter") if k in q}


test_system = TestSystem()
