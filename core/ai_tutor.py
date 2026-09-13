import os
import json
import time
import uuid
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict, Counter
from pathlib import Path

from brain import ask_nova
from core.context_engine import get_connection
from core.second_brain import knowledge_graph, spaced_repetition, create_node, search_nodes, link_nodes


DB_DIR = "database"
TUTOR_DB = os.path.join(DB_DIR, "ai_tutor.db")

os.makedirs(DB_DIR, exist_ok=True)


def init_tutor_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            difficulty TEXT,
            prerequisites TEXT,
            learning_objectives TEXT,
            estimated_hours REAL,
            tags TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            id TEXT PRIMARY KEY,
            topic_id TEXT NOT NULL,
            status TEXT DEFAULT 'not_started',
            mastery_level REAL DEFAULT 0.0,
            time_spent INTEGER DEFAULT 0,
            sessions_count INTEGER DEFAULT 0,
            last_studied REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_sessions (
            id TEXT PRIMARY KEY,
            topic_id TEXT NOT NULL,
            session_type TEXT,
            duration INTEGER,
            content_covered TEXT,
            notes TEXT,
            rating INTEGER,
            started_at REAL NOT NULL,
            ended_at REAL,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id TEXT PRIMARY KEY,
            topic_id TEXT NOT NULL,
            question TEXT NOT NULL,
            question_type TEXT,
            options TEXT,
            correct_answer TEXT,
            explanation TEXT,
            difficulty TEXT,
            tags TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id TEXT PRIMARY KEY,
            question_id TEXT NOT NULL,
            user_answer TEXT,
            is_correct BOOLEAN,
            time_taken INTEGER,
            confidence INTEGER,
            attempted_at REAL NOT NULL,
            FOREIGN KEY (question_id) REFERENCES quiz_questions(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_paths (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            topic_ids TEXT,
            estimated_hours REAL,
            difficulty TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS path_progress (
            id TEXT PRIMARY KEY,
            path_id TEXT NOT NULL,
            current_topic_index INTEGER DEFAULT 0,
            completed_topics TEXT,
            started_at REAL NOT NULL,
            estimated_completion REAL,
            FOREIGN KEY (path_id) REFERENCES learning_paths(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS explanations (
            id TEXT PRIMARY KEY,
            topic_id TEXT NOT NULL,
            question TEXT NOT NULL,
            explanation TEXT NOT NULL,
            explanation_type TEXT,
            difficulty TEXT,
            rating INTEGER,
            generated_at REAL NOT NULL,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        )
    """)

    conn.commit()
    conn.close()


init_tutor_db()


class TopicManager:
    def __init__(self):
        self._seed_topics()

    def _seed_topics(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM topics")
        count = cursor.fetchone()[0]
        conn.close()

        if count > 0:
            return

        seed_topics = [
            {
                "name": "Python Basics",
                "description": "Variables, data types, control flow, functions",
                "category": "programming",
                "difficulty": "beginner",
                "prerequisites": [],
                "objectives": ["Understand variables and types", "Write basic control flow", "Define and call functions"],
                "estimated_hours": 5,
                "tags": ["python", "basics"]
            },
            {
                "name": "Data Structures",
                "description": "Arrays, linked lists, stacks, queues, trees, graphs",
                "category": "computer_science",
                "difficulty": "intermediate",
                "prerequisites": [],
                "objectives": ["Implement basic data structures", "Analyze time/space complexity", "Choose appropriate structure"],
                "estimated_hours": 10,
                "tags": ["algorithms", "data_structures"]
            },
            {
                "name": "Machine Learning Fundamentals",
                "description": "Supervised/unsupervised learning, evaluation, common algorithms",
                "category": "ai_ml",
                "difficulty": "intermediate",
                "prerequisites": ["Python Basics", "Statistics Basics"],
                "objectives": ["Understand ML pipeline", "Train/evaluate models", "Handle overfitting"],
                "estimated_hours": 15,
                "tags": ["ml", "ai", "python"]
            },
            {
                "name": "Web Development with FastAPI",
                "description": "Build REST APIs with Python FastAPI",
                "category": "web_development",
                "difficulty": "intermediate",
                "prerequisites": ["Python Basics"],
                "objectives": ["Create REST endpoints", "Handle requests/responses", "Database integration"],
                "estimated_hours": 8,
                "tags": ["fastapi", "web", "api"]
            },
            {
                "name": "Git Version Control",
                "description": "Git basics, branching, merging, collaboration",
                "category": "tools",
                "difficulty": "beginner",
                "prerequisites": [],
                "objectives": ["Initialize repositories", "Commit changes", "Branch and merge", "Resolve conflicts"],
                "estimated_hours": 4,
                "tags": ["git", "version_control"]
            }
        ]

        for topic_data in seed_topics:
            self.create_topic(**topic_data)

    def create_topic(self, name: str, description: str, category: str,
                     difficulty: str, prerequisites: List[str],
                     objectives: List[str], estimated_hours: float,
                     tags: List[str]) -> str:
        topic_id = str(uuid.uuid4())[:8]

        prereq_ids = []
        for prereq_name in prerequisites:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM topics WHERE name = ?", (prereq_name,))
            row = cursor.fetchone()
            conn.close()
            if row:
                prereq_ids.append(row[0])

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO topics (id, name, description, category, difficulty, prerequisites,
                              learning_objectives, estimated_hours, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            topic_id, name, description, category, difficulty,
            json.dumps(prereq_ids), json.dumps(objectives),
            estimated_hours, json.dumps(tags), time.time(), time.time()
        ))
        conn.commit()
        conn.close()

        self._init_user_progress(topic_id)

        return topic_id

    def _init_user_progress(self, topic_id: str):
        progress_id = str(uuid.uuid4())[:8]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_progress (id, topic_id, status, mastery_level, created_at, updated_at)
            VALUES (?, ?, 'not_started', 0.0, ?, ?)
        """, (progress_id, topic_id, time.time(), time.time()))
        conn.commit()
        conn.close()

    def get_topic(self, topic_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "category": row[3], "difficulty": row[4],
                "prerequisites": json.loads(row[5]) if row[5] else [],
                "objectives": json.loads(row[6]) if row[6] else [],
                "estimated_hours": row[7],
                "tags": json.loads(row[8]) if row[8] else [],
                "created_at": row[9], "updated_at": row[10]
            }
        return None

    def get_topic_by_name(self, name: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM topics WHERE name = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "category": row[3], "difficulty": row[4],
                "prerequisites": json.loads(row[5]) if row[5] else [],
                "objectives": json.loads(row[6]) if row[6] else [],
                "estimated_hours": row[7],
                "tags": json.loads(row[8]) if row[8] else [],
                "created_at": row[9], "updated_at": row[10]
            }
        return None

    def list_topics(self, category: str = None, difficulty: str = None) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()

        sql = "SELECT * FROM topics WHERE 1=1"
        params = []

        if category:
            sql += " AND category = ?"
            params.append(category)
        if difficulty:
            sql += " AND difficulty = ?"
            params.append(difficulty)

        sql += " ORDER BY category, difficulty, name"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {"id": r[0], "name": r[1], "description": r[2],
             "category": r[3], "difficulty": r[4],
             "prerequisites": json.loads(r[5]) if r[5] else [],
             "objectives": json.loads(r[6]) if r[6] else [],
             "estimated_hours": r[7],
             "tags": json.loads(r[8]) if r[8] else [],
             "created_at": r[9], "updated_at": r[10]}
            for r in rows
        ]

    def get_progress(self, topic_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_progress WHERE topic_id = ?", (topic_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "topic_id": row[1], "status": row[2],
                "mastery_level": row[3], "time_spent": row[3],
                "sessions_count": row[4], "last_studied": row[5],
                "created_at": row[6], "updated_at": row[7]
            }
        return None

    def update_progress(self, topic_id: str, mastery_delta: float = 0,
                        time_spent: int = 0, status: str = None) -> bool:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM user_progress WHERE topic_id = ?", (topic_id,))
        row = cursor.fetchone()
        if not row:
            return False

        progress_id = row[0]
        new_mastery = max(0.0, min(1.0, row[3] + mastery_delta))
        new_time = row[4] + time_spent
        new_sessions = row[5] + (1 if time_spent > 0 else 0)
        new_status = status or row[2]

        if new_mastery >= 0.95:
            new_status = "mastered"
        elif new_mastery >= 0.7:
            new_status = "completed"
        elif new_mastery > 0:
            new_status = "in_progress"

        cursor.execute("""
            UPDATE user_progress
            SET mastery_level = ?, time_spent = ?, sessions_count = ?,
                status = ?, last_studied = ?, updated_at = ?
            WHERE id = ?
        """, (new_mastery, new_time, new_sessions, new_status, time.time(), time.time(), progress_id))
        conn.commit()
        conn.close()
        return True

    def get_overall_stats(self) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM topics")
        total_topics = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM user_progress WHERE status = 'mastered'")
        mastered = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM user_progress WHERE status = 'completed'")
        completed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM user_progress WHERE status = 'in_progress'")
        in_progress = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(time_spent) FROM user_progress")
        total_time = cursor.fetchone()[0] or 0

        cursor.execute("SELECT AVG(mastery_level) FROM user_progress")
        avg_mastery = cursor.fetchone()[0] or 0

        conn.close()

        return {
            "total_topics": total_topics,
            "mastered": mastered,
            "completed": completed,
            "in_progress": in_progress,
            "not_started": total_topics - mastered - completed - in_progress,
            "total_time_hours": total_time / 3600,
            "avg_mastery": avg_mastery
        }


class ExplanationGenerator:
    EXPLANATION_TYPES = {
        "concept": "Explain the core concept clearly with key points",
        "analogy": "Explain using a relatable real-world analogy",
        "step_by_step": "Break down into clear sequential steps",
        "visual": "Describe a mental model or diagram that could be drawn",
        "code_example": "Provide a practical code example with comments",
        "feynman": "Explain as if teaching a 12-year-old (Feynman technique)",
        "comparison": "Compare with similar concepts, highlight differences",
        "why": "Explain the 'why' - motivation and purpose behind the concept",
        "pitfalls": "Common mistakes, misconceptions, and how to avoid them",
        "applications": "Real-world applications and use cases"
    }

    def __init__(self):
        pass

    def generate(self, topic_name: str, explanation_type: str = "concept",
                 difficulty: str = "intermediate", context: Dict = None) -> str:
        topic_info = topic_manager.get_topic_by_name(topic_name)
        if not topic_info:
            topics = topic_manager.list_topics()
            for t in topics:
                if topic_name.lower() in t["name"].lower():
                    topic_info = t
                    break

        if not topic_info:
            topic_info = {"name": topic_name, "description": "", "difficulty": difficulty}

        type_prompt = self.EXPLANATION_TYPES.get(explanation_type, self.EXPLANATION_TYPES["concept"])

        difficulty_prompts = {
            "beginner": "Use simple language, avoid jargon, provide concrete examples.",
            "intermediate": "Use appropriate technical terms, assume some prior knowledge.",
            "advanced": "Use precise technical language, include nuances and edge cases.",
            "expert": "Assume deep knowledge, focus on nuances, optimizations, and research frontiers."
        }

        context_str = json.dumps(context or {}, indent=2)
        topic_desc = topic_info.get("description", "No description available")

        prompt = f"""Generate a {explanation_type} explanation for: {topic_info['name']}

Topic description: {topic_desc}
Target difficulty: {difficulty}
{type_prompt}

{difficulty_prompts.get(difficulty, difficulty_prompts['intermediate'])}

Context: {context_str}

Format as clear, structured explanation with:
1. Brief overview (2-3 sentences)
2. Main explanation (structured with headings if appropriate)
3. Key takeaways (3-5 bullet points)
4. Next steps or related topics to explore"""

        response = ask_nova(prompt)

        self._store_explanation(topic_info.get("id", ""), topic_name, explanation_type, response)

        return response

    def _store_explanation(self, topic_id: str, question: str, exp_type: str, explanation: str):
        exp_id = str(uuid.uuid4())[:8]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO explanations (id, topic_id, question, explanation, explanation_type, difficulty, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (exp_id, topic_id or "", question, explanation, exp_type, "intermediate", time.time()))
        conn.commit()
        conn.close()

    def get_explanations(self, topic_id: str = None, limit: int = 20) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        if topic_id:
            cursor.execute("SELECT * FROM explanations WHERE topic_id = ? ORDER BY generated_at DESC LIMIT ?", (topic_id, limit))
        else:
            cursor.execute("SELECT * FROM explanations ORDER BY generated_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "topic_id": r[1], "question": r[2], "explanation": r[3],
             "type": r[4], "difficulty": r[5], "rating": r[6], "generated_at": r[7]}
            for r in rows
        ]


class QuizGenerator:
    def __init__(self):
        pass

    def generate_quiz(self, topic_name: str, num_questions: int = 5,
                      difficulty: str = "medium", types: List[str] = None) -> List[Dict]:
        """Generate quiz questions for a topic."""

        types = types or ["multiple_choice", "true_false", "short_answer"]

        topic_info = topic_manager.get_topic_by_name(topic_name)
        if not topic_info:
            topics = topic_manager.list_topics()
            for t in topics:
                if topic_name.lower() in t["name"].lower():
                    topic_info = t
                    break

        if not topic_info:
            return []

        import ollama
        import json
        import re

        prompt = f'{num_questions} {topic_name} quiz questions. JSON only: [{{"q":"question","a":"answer","t":"type"}}]'
        
        direct_response = ollama.chat(
            model="qwen3:8b",
            options={"num_predict": 800, "temperature": 0.1},
            messages=[
                {"role": "system", "content": "Output ONLY valid JSON array. No text, no reasoning."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # qwen3:8b outputs JSON in content field when prompt is minimal
        response = direct_response["message"].get("content", "")
        if not response:
            response = direct_response["message"].get("thinking", "")

        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                raw_questions = json.loads(json_match.group())

                # Convert to full format
                questions = []
                for rq in raw_questions:
                    questions.append({
                        "question": rq.get("q", ""),
                        "type": "short_answer",
                        "options": [],
                        "correct_answer": rq.get("a", ""),
                        "explanation": f"Based on {topic_name} concepts",
                        "difficulty": difficulty,
                        "tags": [topic_name.lower().replace(" ", "_")]
                    })

                return questions
        except Exception as e:
            print(f"Quiz generation error: {e}")
            pass

        return []

    def _store_question(self, topic_name: str, question: Dict):
        topic_info = topic_manager.get_topic_by_name(topic_name)
        if not topic_info:
            return

        q_id = str(uuid.uuid4())[:8]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO quiz_questions (id, topic_id, question, question_type, options, correct_answer, explanation, difficulty, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            q_id, topic_info["id"], question["question"], question["type"],
            json.dumps(question.get("options", [])), question["correct_answer"],
            question.get("explanation", ""), question.get("difficulty", "medium"),
            json.dumps(question.get("tags", [])), time.time()
        ))
        conn.commit()
        conn.close()

    def get_questions(self, topic_id: str = None, limit: int = 20) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        if topic_id:
            cursor.execute("SELECT * FROM quiz_questions WHERE topic_id = ? LIMIT ?", (topic_id, limit))
        else:
            cursor.execute("SELECT * FROM quiz_questions LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "topic_id": r[1], "question": r[2], "type": r[3],
             "options": json.loads(r[4]) if r[4] else [], "correct": r[5],
             "explanation": r[6], "difficulty": r[7], "tags": json.loads(r[8]) if r[8] else []}
            for r in rows
        ]

    def attempt_question(self, question_id: str, user_answer: str, confidence: int = 3, time_taken: int = 0) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM quiz_questions WHERE id = ?", (question_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"error": "Question not found"}

        correct = row[5].strip().lower()
        user = user_answer.strip().lower()

        if row[3] == "multiple_choice":
            options = json.loads(row[4]) if row[4] else []
            is_correct = user == correct or (user.isdigit() and int(user) - 1 < len(options) and options[int(user) - 1].lower() == correct)
        else:
            is_correct = user == correct or correct in user or user in correct

        attempt_id = str(uuid.uuid4())[:8]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO quiz_attempts (id, question_id, user_answer, is_correct, time_taken, confidence, attempted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (attempt_id, question_id, user_answer, is_correct, time_taken, confidence, time.time()))
        conn.commit()
        conn.close()

        return {
            "attempt_id": attempt_id,
            "is_correct": is_correct,
            "correct_answer": row[5],
            "explanation": row[6]
        }

    def get_stats(self, topic_id: str = None) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()

        if topic_id:
            cursor.execute("SELECT * FROM quiz_attempts WHERE question_id IN (SELECT id FROM quiz_questions WHERE topic_id = ?)", (topic_id,))
        else:
            cursor.execute("SELECT * FROM quiz_attempts")

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {"total_attempts": 0}

        total = len(rows)
        correct = sum(1 for r in rows if r[3])
        avg_confidence = sum(r[5] for r in rows) / total if total > 0 else 0
        avg_time = sum(r[4] for r in rows) / total if total > 0 else 0

        return {
            "total_attempts": total,
            "correct": correct,
            "accuracy": correct / total if total > 0 else 0,
            "avg_confidence": avg_confidence,
            "avg_time_seconds": avg_time
        }


class LearningPathManager:
    def __init__(self):
        pass

    def create_path(self, name: str, description: str, topic_names: List[str],
                    estimated_hours: float = 0, difficulty: str = "intermediate") -> str:
        path_id = str(uuid.uuid4())[:8]

        topic_ids = []
        for name in topic_names:
            topic = topic_manager.get_topic_by_name(name)
            if topic:
                topic_ids.append(topic["id"])

        if not estimated_hours:
            estimated_hours = sum(topic_manager.get_topic(tid).get("estimated_hours", 0) for tid in topic_ids)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO learning_paths (id, name, description, topic_ids, estimated_hours, difficulty, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (path_id, name, description, json.dumps(topic_ids), estimated_hours, difficulty, time.time(), time.time()))
        conn.commit()
        conn.close()

        self._init_path_progress(path_id)

        return path_id

    def _init_path_progress(self, path_id: str):
        progress_id = str(uuid.uuid4())[:8]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO path_progress (id, path_id, current_topic_index, completed_topics, started_at)
            VALUES (?, ?, 0, '[]', ?)
        """, (progress_id, path_id, time.time()))
        conn.commit()
        conn.close()

    def get_path(self, path_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM learning_paths WHERE id = ?", (path_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "topic_ids": json.loads(row[3]) if row[3] else [],
                "estimated_hours": row[4], "difficulty": row[5],
                "created_at": row[6], "updated_at": row[7]
            }
        return None

    def list_paths(self) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM learning_paths ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "description": r[2],
             "topic_ids": json.loads(r[3]) if r[3] else [],
             "estimated_hours": r[4], "difficulty": r[5]}
            for r in rows
        ]

    def get_progress(self, path_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM path_progress WHERE path_id = ?", (path_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "path_id": row[1], "current_index": row[2],
                "completed": json.loads(row[3]) if row[3] else [],
                "started_at": row[4], "estimated_completion": row[5]
            }
        return None

    def advance_path(self, path_id: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM path_progress WHERE path_id = ?", (path_id,))
        row = cursor.fetchone()
        if not row:
            return False

        progress_id, path_id_db, current_index, completed_json, started_at, est_completion = row
        completed = json.loads(completed_json) if row[3] else []

        path = self.get_path(path_id)
        if not path:
            return False

        topic_ids = path["topic_ids"]
        if current_index >= len(topic_ids):
            return False

        current_topic = topic_ids[current_index]
        completed.append(current_topic)
        new_index = current_index + 1

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE path_progress
            SET current_topic_index = ?, completed_topics = ?, estimated_completion = ?
            WHERE id = ?
        """, (new_index, json.dumps(completed),
              time.time() + 86400 * 7 if new_index < len(topic_ids) else time.time(),
              row[0]))
        conn.commit()
        conn.close()
        return True

    def get_current_topic(self, path_id: str) -> Optional[Dict]:
        progress = self.get_progress(path_id)
        if not progress:
            return None

        path = self.get_path(progress["path_id"])
        if not path:
            return None

        topic_ids = path["topic_ids"]
        if progress["current_topic_index"] >= len(topic_ids):
            return None

        topic_id = topic_ids[progress["current_topic_index"]]
        return topic_manager.get_topic(topic_id)


class AITutor:
    def __init__(self):
        self.topic_manager = TopicManager()
        self.explanation_gen = ExplanationGenerator()
        self.quiz_gen = QuizGenerator()
        self.path_manager = LearningPathManager()

    def explain(self, topic_name: str, explanation_type: str = "concept",
                difficulty: str = "intermediate") -> str:
        return self.explanation_gen.generate(topic_name, explanation_type, difficulty)

    def quiz(self, topic_name: str, num_questions: int = 5,
             difficulty: str = "medium") -> List[Dict]:
        return self.quiz_gen.generate_quiz(topic_name, num_questions)

    def answer_question(self, question: str, topic_name: str = None) -> str:
        context = ""
        if topic_name:
            topic = topic_manager.get_topic_by_name(topic_name)
            if topic:
                context = f"Topic: {topic['name']}\nDescription: {topic['description']}"

        prompt = f"""You are an expert tutor. Answer this learning question clearly and helpfully.

Question: {question}
{f'Context: {topic_name}' if topic_name else ''}

Guidelines:
- Be encouraging and clear
- Use examples and analogies
- Break down complex ideas
- Suggest practice exercises
- Point to related topics"""

        if topic_name:
            prompt += f"\nTopic context: {topic_name}"

        return ask_nova(prompt)

    def suggest_next_topic(self, completed_topics: List[str] = None) -> List[Dict]:
        if completed_topics is None:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT topic_id FROM user_progress WHERE status IN ('mastered', 'completed')")
            completed = [r[0] for r in cursor.fetchall()]
        else:
            completed = [topic_manager.get_topic_by_name(t)["id"] for t in completed_topics if topic_manager.get_topic_by_name(t)]

        all_topics = topic_manager.list_topics()
        candidates = []

        for topic in all_topics:
            if topic["id"] in completed:
                continue

            prereqs = topic.get("prerequisites", [])
            if all(p in completed for p in prereqs):
                candidates.append(topic)

        difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2, "expert": 3}
        candidates.sort(key=lambda t: (difficulty_order.get(t["difficulty"], 1), len(t.get("prerequisites", []))))

        return candidates[:5]

    def get_dashboard(self) -> Dict:
        stats = topic_manager.get_overall_stats()
        suggestions = self.suggest_next_topic()

        return {
            "stats": stats,
            "suggested_topics": suggestions[:3],
            "recommendations": self._get_recommendations()
        }

    def _get_recommendations(self) -> List[str]:
        recs = []
        stats = topic_manager.get_overall_stats()

        if stats["in_progress"] > 3:
            recs.append("Focus on completing current topics before starting new ones")
        if stats["not_started"] > stats["total_topics"] * 0.8:
            recs.append("Start with beginner topics to build foundation")
        if stats["avg_mastery"] < 0.3:
            recs.append("Review fundamentals before advancing")

        return recs

    def create_study_plan(self, goal: str, hours_per_week: int = 5) -> Dict:
        all_topics = topic_manager.list_topics()
        relevant = [t for t in all_topics if goal.lower() in t["name"].lower() or goal.lower() in t.get("description", "").lower()]

        if not relevant:
            relevant = [t for t in topic_manager.list_topics(difficulty="beginner")[:5]]

        total_hours = sum(t["estimated_hours"] for t in relevant)
        weeks = max(1, total_hours / max(1, hours_per_week))

        plan = {
            "goal": goal,
            "topics": [{"name": t["name"], "hours": t["estimated_hours"], "difficulty": t["difficulty"]} for t in relevant],
            "total_hours": sum(t["estimated_hours"] for t in relevant),
            "estimated_weeks": round(weeks, 1),
            "hours_per_week": hours_per_week,
            "milestones": []
        }

        cumulative = 0
        for t in relevant:
            cumulative += t["estimated_hours"]
            plan["milestones"].append({
                "topic": t["name"],
                "cumulative_hours": cumulative,
                "target_week": round(cumulative / hours_per_week, 1)
            })

        return plan


# Global instances
topic_manager = TopicManager()
explanation_generator = ExplanationGenerator()
quiz_generator = QuizGenerator()
learning_path_manager = LearningPathManager()
ai_tutor = AITutor()


# Convenience functions
def explain(topic_name: str, explanation_type: str = "concept", difficulty: str = "intermediate") -> str:
    return explanation_generator.generate(topic_name, explanation_type, difficulty)

def quiz(topic_name: str, num_questions: int = 5, difficulty: str = "medium") -> List[Dict]:
    return quiz_generator.generate_quiz(topic_name, num_questions)

def ask_tutor(question: str, topic_name: str = None) -> str:
    return ai_tutor.answer_question(question, topic_name)

def suggest_next() -> List[Dict]:
    return ai_tutor.suggest_next_topic()

def get_dashboard() -> Dict:
    return ai_tutor.get_dashboard()

def create_learning_path(name: str, description: str, topics: List[str], **kwargs) -> str:
    return learning_path_manager.create_path(name, "", [], **kwargs)

def get_dashboard() -> Dict:
    return ai_tutor.get_dashboard()

def create_study_plan(goal: str, hours_per_week: int = 5) -> Dict:
    return ai_tutor.create_study_plan(goal, hours_per_week)

def get_topic_progress(topic_name: str) -> Optional[Dict]:
    topic = topic_manager.get_topic_by_name(topic_name)
    if topic:
        return topic_manager.get_progress(topic["id"])
    return None

def start_topic(topic_name: str) -> bool:
    topic = topic_manager.get_topic_by_name(topic_name)
    if topic:
        return topic_manager.update_progress(topic["id"], status="in_progress")
    return False

def complete_topic(topic_name: str) -> bool:
    topic = topic_manager.get_topic_by_name(topic_name)
    if topic:
        return topic_manager.update_progress(topic["id"], mastery_delta=1.0, status="completed")
    return False

def get_topic_progress(topic_name: str) -> Optional[Dict]:
    topic = topic_manager.get_topic_by_name(topic_name)
    if topic:
        return topic_manager.get_progress(topic["id"])
    return None


def tutor_debug() -> str:
    stats = topic_manager.get_overall_stats()
    return f"AI Tutor Dashboard:\nTotal topics: {stats['total_topics']}\nMastered: {stats['mastered']}\nCompleted: {stats['completed']}\nIn progress: {stats['in_progress']}\nAvg mastery: {stats['avg_mastery']:.0%}\nTotal study time: {stats['total_time_hours']:.1f}h"


if __name__ == "__main__":
    print("AI Tutor module loaded.")
    print("Available functions:")
    print("  explain(topic, type, difficulty)")
    print("  quiz(topic, num_questions, difficulty)")
    print("  ask_tutor(question, topic)")
    print("  suggest_next()")
    print("  get_dashboard()")
    print("  create_study_plan(goal, hours_per_week)")