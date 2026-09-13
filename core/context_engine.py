"""
Context Engine - Phase 8
SQLite-based context persistence for conversations, preferences, and session state.
Fully local, no cloud, no costs.
"""

import sqlite3
import json
import os
import time
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

DB_DIR = "database"
DB_NAME = "context.db"
DB_PATH = os.path.join(DB_DIR, DB_NAME)

os.makedirs(DB_DIR, exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def initialize_context_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Conversation history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            metadata TEXT  -- JSON for extra data
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_conv_session
        ON conversations(session_id, timestamp)
    """)

    # User preferences
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            updated REAL NOT NULL
        )
    """)

    # Session state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            started REAL NOT NULL,
            last_active REAL NOT NULL,
            state TEXT,  -- JSON for session state
            summary TEXT
        )
    """)

    # Task tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            task_type TEXT NOT NULL,  -- 'coding', 'research', 'writing', etc.
            description TEXT,
            status TEXT DEFAULT 'active',  -- 'active', 'completed', 'paused'
            context TEXT,  -- JSON for task-specific context
            created REAL NOT NULL,
            updated REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_session
        ON tasks(session_id, status)
    """)

    # File/Project context
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_path TEXT UNIQUE NOT NULL,
            project_name TEXT,
            last_file TEXT,
            open_files TEXT,  -- JSON array
            git_branch TEXT,
            git_status TEXT,
            language TEXT,
            framework TEXT,
            updated REAL NOT NULL
        )
    """)

    # Knowledge facts (supplement to semantic memory)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_key TEXT UNIQUE NOT NULL,
            fact_value TEXT NOT NULL,
            source TEXT,  -- 'user', 'learned', 'inferred'
            confidence REAL DEFAULT 1.0,
            tags TEXT,  -- JSON array
            created REAL NOT NULL,
            last_accessed REAL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_tags
        ON knowledge_facts(tags)
    """)

    conn.commit()
    conn.close()


# Initialize on import
initialize_context_db()


# ==========================================
# CONVERSATION HISTORY
# ==========================================

def add_conversation(session_id: str, role: str, content: str, metadata: Dict = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO conversations (session_id, role, content, timestamp, metadata)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, role, content, time.time(), json.dumps(metadata or {})))
    conn.commit()
    conn.close()


def get_conversation_history(session_id: str, limit: int = 50) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content, timestamp, metadata
        FROM conversations
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()

    return [
        {"role": r[0], "content": r[1], "timestamp": r[2], "metadata": json.loads(r[3]) if r[3] else {}}
        for r in reversed(rows)
    ]


def clear_conversation(session_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# ==========================================
# USER PREFERENCES
# ==========================================

def set_preference(key: str, value: Any, category: str = "general"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO preferences (key, value, category, updated)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,
            category=excluded.category,
            updated=excluded.updated
    """, (key, json.dumps(value), category, time.time()))
    conn.commit()
    conn.close()


def get_preference(key: str, default=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return default


def get_preferences_by_category(category: str) -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM preferences WHERE category = ?", (category,))
    rows = cursor.fetchall()
    conn.close()
    return {k: json.loads(v) for k, v in rows}


def delete_preference(key: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM preferences WHERE key = ?", (key,))
    conn.commit()
    conn.close()


# ==========================================
# SESSION MANAGEMENT
# ==========================================

def create_session(session_id: str = None) -> str:
    if session_id is None:
        session_id = f"session_{int(time.time())}"

    conn = get_connection()
    cursor = conn.cursor()
    now = time.time()
    cursor.execute("""
        INSERT INTO sessions (session_id, started, last_active, state, summary)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, now, now, json.dumps({}), ""))
    conn.commit()
    conn.close()
    return session_id


def update_session_activity(session_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sessions SET last_active = ? WHERE session_id = ?
    """, (time.time(), session_id))
    conn.commit()
    conn.close()


def set_session_state(session_id: str, state: Dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sessions SET state = ? WHERE session_id = ?
    """, (json.dumps(state), session_id))
    conn.commit()
    conn.close()


def get_session_state(session_id: str) -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT state FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return json.loads(row[0])
    return {}


def set_session_summary(session_id: str, summary: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET summary = ? WHERE session_id = ?", (summary, session_id))
    conn.commit()
    conn.close()


def get_recent_sessions(limit: int = 10) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_id, started, last_active, summary
        FROM sessions
        ORDER BY last_active DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"session_id": r[0], "started": r[1], "last_active": r[2], "summary": r[3]}
        for r in rows
    ]


# ==========================================
# TASK TRACKING
# ==========================================

def create_task(session_id: str, task_type: str, description: str, context: Dict = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = time.time()
    cursor.execute("""
        INSERT INTO tasks (session_id, task_type, description, status, context, created, updated)
        VALUES (?, ?, ?, 'active', ?, ?, ?)
    """, (session_id, task_type, description, json.dumps(context or {}), now, now))
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return task_id


def update_task(task_id: int, status: str = None, context: Dict = None):
    conn = get_connection()
    cursor = conn.cursor()
    updates = []
    params = []
    if status:
        updates.append("status = ?")
        params.append(status)
    if context is not None:
        updates.append("context = ?")
        params.append(json.dumps(context))
    updates.append("updated = ?")
    params.append(time.time())
    params.append(task_id)

    cursor.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_active_tasks(session_id: str) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, task_type, description, status, context, created, updated
        FROM tasks
        WHERE session_id = ? AND status = 'active'
        ORDER BY created DESC
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "task_type": r[1], "description": r[2], "status": r[3],
         "context": json.loads(r[4]), "created": r[5], "updated": r[6]}
        for r in rows
    ]


def get_task_history(session_id: str, limit: int = 20) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, task_type, description, status, context, created, updated
        FROM tasks
        WHERE session_id = ?
        ORDER BY created DESC
        LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "task_type": r[1], "description": r[2], "status": r[3],
         "context": json.loads(r[4]), "created": r[5], "updated": r[6]}
        for r in rows
    ]


# ==========================================
# PROJECT CONTEXT
# ==========================================

def update_project_context(
    project_path: str,
    project_name: str = None,
    last_file: str = None,
    open_files: List[str] = None,
    git_branch: str = None,
    git_status: str = None,
    language: str = None,
    framework: str = None
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO project_context (
            project_path, project_name, last_file, open_files,
            git_branch, git_status, language, framework, updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_path) DO UPDATE SET
            project_name=excluded.project_name,
            last_file=excluded.last_file,
            open_files=excluded.open_files,
            git_branch=excluded.git_branch,
            git_status=excluded.git_status,
            language=excluded.language,
            framework=excluded.framework,
            updated=excluded.updated
    """, (
        project_path,
        project_name,
        last_file,
        json.dumps(open_files or []),
        git_branch,
        git_status,
        language,
        framework,
        time.time()
    ))
    conn.commit()
    conn.close()


def get_project_context(project_path: str) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT project_path, project_name, last_file, open_files,
               git_branch, git_status, language, framework, updated
        FROM project_context
        WHERE project_path = ?
    """, (project_path,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "project_path": row[0],
            "project_name": row[1],
            "last_file": row[2],
            "open_files": json.loads(row[3]) if row[3] else [],
            "git_branch": row[4],
            "git_status": row[5],
            "language": row[6],
            "framework": row[7],
            "updated": row[8]
        }
    return None


def get_recent_projects(limit: int = 10) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT project_path, project_name, last_file, language, framework, updated
        FROM project_context
        ORDER BY updated DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"project_path": r[0], "project_name": r[1], "last_file": r[2],
         "language": r[3], "framework": r[4], "updated": r[5]}
        for r in rows
    ]


# ==========================================
# KNOWLEDGE FACTS
# ==========================================

def add_knowledge_fact(fact_key: str, fact_value: str, source: str = "user",
                       confidence: float = 1.0, tags: List[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    now = time.time()
    cursor.execute("""
        INSERT INTO knowledge_facts (fact_key, fact_value, source, confidence, tags, created, last_accessed)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fact_key) DO UPDATE SET
            fact_value=excluded.fact_value,
            source=excluded.source,
            confidence=excluded.confidence,
            tags=excluded.tags,
            last_accessed=excluded.last_accessed
    """, (fact_key, fact_value, source, confidence, json.dumps(tags or []), now, now))
    conn.commit()
    conn.close()


def get_knowledge_fact(fact_key: str) -> Optional[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fact_value FROM knowledge_facts WHERE fact_key = ?
    """, (fact_key,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE knowledge_facts SET last_accessed = ? WHERE fact_key = ?", (time.time(), fact_key))
        conn.commit()
    conn.close()
    return row[0] if row else None


def search_knowledge_facts(query: str, limit: int = 10) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fact_key, fact_value, source, confidence, tags, created
        FROM knowledge_facts
        WHERE fact_key LIKE ? OR fact_value LIKE ?
        ORDER BY confidence DESC, last_accessed DESC
        LIMIT ?
    """, (f"%{query}%", f"%{query}%", limit))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"fact_key": r[0], "fact_value": r[1], "source": r[2],
         "confidence": r[3], "tags": json.loads(r[4]) if r[4] else [], "created": r[5]}
        for r in rows
    ]


def get_all_knowledge_facts(limit: int = 100) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fact_key, fact_value, source, confidence, tags, created
        FROM knowledge_facts
        ORDER BY confidence DESC, last_accessed DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"fact_key": r[0], "fact_value": r[1], "source": r[2],
         "confidence": r[3], "tags": json.loads(r[4]) if r[4] else [], "created": r[5]}
        for r in rows
    ]


# ==========================================
# CONTEXT ASSEMBLY FOR LLM
# ==========================================

def build_context_for_llm(session_id: str, include_history: int = 10,
                          include_tasks: bool = True,
                          include_project: bool = True,
                          include_preferences: bool = True) -> str:
    """Build a context string for LLM consumption."""
    parts = []

    # Session summary
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT summary FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        parts.append(f"Session Summary: {row[0]}")

    # Preferences
    if include_preferences:
        prefs = get_preferences_by_category("general")
        if prefs:
            pref_str = ", ".join(f"{k}={v}" for k, v in prefs.items())
            parts.append(f"User Preferences: {pref_str}")

    # Active tasks
    if include_tasks:
        tasks = get_active_tasks(session_id)
        if tasks:
            task_str = "; ".join(f"{t['task_type']}: {t['description']}" for t in tasks)
            parts.append(f"Active Tasks: {task_str}")

    # Project context
    if include_project:
        projects = get_recent_projects(1)
        if projects:
            p = projects[0]
            proj_str = f"{p['project_name']} ({p['language']})"
            if p['last_file']:
                proj_str += f" - last: {p['last_file']}"
            parts.append(f"Current Project: {proj_str}")

    # Conversation history
    if include_history > 0:
        history = get_conversation_history(session_id, include_history)
        if history:
            conv_str = "\n".join(f"{h['role']}: {h['content']}" for h in history)
            parts.append(f"Recent Conversation:\n{conv_str}")

    return "\n\n".join(parts)


# ==========================================
# CONVENIENCE: GLOBAL SESSION
# ==========================================

_current_session_id = None


def get_current_session() -> str:
    global _current_session_id
    if _current_session_id is None:
        _current_session_id = create_session()
    return _current_session_id


def set_current_session(session_id: str):
    global _current_session_id
    _current_session_id = session_id


if __name__ == "__main__":
    # Test
    sid = create_session()
    print(f"Created session: {sid}")

    add_conversation(sid, "user", "Hello")
    add_conversation(sid, "assistant", "Hi there!")
    add_conversation(sid, "user", "What's my name?")

    print("History:", get_conversation_history(sid))

    set_preference("theme", "dark")
    set_preference("voice", "en-US-AndrewNeural")
    print("Prefs:", get_preferences_by_category("general"))

    task_id = create_task(sid, "coding", "Build a REST API", {"language": "python", "framework": "fastapi"})
    print("Task:", get_active_tasks(sid))

    update_project_context("/home/user/nova", "Nova", "main.py", ["main.py", "commands.py"],
                          "main", "clean", "python", "fastapi")
    print("Project:", get_project_context("/home/user/nova"))

    add_knowledge_fact("user.name", "Ujjwal", "user", 1.0, ["personal"])
    add_knowledge_fact("user.language", "Python", "learned", 0.9, ["coding"])
    print("Knowledge:", search_knowledge_facts("user"))

    print("\nLLM Context:")
    print(build_context_for_llm(sid))