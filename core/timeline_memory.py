"""
Timeline Memory Agent - Phase 31
Timeline-based memory with event sourcing, temporal queries, life logging.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import hashlib
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from collections import defaultdict, deque, Counter
from enum import Enum
from pathlib import Path

DB_DIR = "database"
TM_DB = os.path.join(DB_DIR, "timeline_memory.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_tm_connection():
    import sqlite3
    conn = sqlite3.connect(TM_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_tm_db():
    conn = get_tm_connection()
    cursor = conn.cursor()

    # Timeline events (core event store)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timeline_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,        -- 'activity', 'thought', 'meeting', 'task', 'file', 'web', 'code', 'system'
            category TEXT,                   -- 'work', 'personal', 'learning', 'health', 'social'
            title TEXT NOT NULL,
            description TEXT,
            timestamp REAL NOT NULL,         -- when event occurred
            duration_seconds REAL,           -- how long it lasted
            source TEXT,                     -- 'manual', 'auto', 'import', 'inferred'
            confidence REAL DEFAULT 1.0,     -- for inferred events
            tags TEXT,                       -- JSON array
            metadata TEXT,                   -- JSON: flexible extra data
            correlations TEXT,               -- JSON array of related event IDs
            session_id TEXT,                 -- grouping identifier
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timeline_time ON timeline_events(timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timeline_type ON timeline_events(event_type)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timeline_category ON timeline_events(category)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timeline_session ON timeline_events(session_id)
    """)

    # Daily summaries (aggregated views)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,       -- YYYY-MM-DD
            total_events INTEGER DEFAULT 0,
            total_duration_seconds REAL DEFAULT 0,
            event_types TEXT,                -- JSON: count by type
            categories TEXT,                 -- JSON: count by category
            top_tags TEXT,                   -- JSON: most frequent tags
            productivity_score REAL,         -- 0-100
            focus_time_seconds REAL,         -- deep work time
            break_time_seconds REAL,
            meeting_time_seconds REAL,
            learning_time_seconds REAL,
            health_time_seconds REAL,
            mood_score REAL,                 -- 1-10
            energy_level REAL,               -- 1-10
            stress_level REAL,               -- 1-10
            highlights TEXT,                 -- JSON array of key events
            challenges TEXT,                 -- JSON array
            goals_progress TEXT,             -- JSON: goal -> progress
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Time blocks (scheduled/planned time)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS time_blocks (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,              -- YYYY-MM-DD
            start_time REAL NOT NULL,        -- timestamp
            end_time REAL NOT NULL,          -- timestamp
            title TEXT NOT NULL,
            block_type TEXT,                 -- 'work', 'meeting', 'break', 'personal', 'learning', 'exercise'
            category TEXT,
            description TEXT,
            color TEXT,                      -- hex color for calendar view
            is_recurring BOOLEAN DEFAULT 0,
            recurrence_rule TEXT,            -- RRULE string
            source TEXT,                     -- 'manual', 'calendar', 'inferred'
            related_event_id TEXT,           -- link to timeline event
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timeblocks_date ON time_blocks(date)
    """)

    # Life metrics (quantified self)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS life_metrics (
            id TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,       -- 'sleep_hours', 'steps', 'heart_rate', 'weight', 'mood', 'energy'
            value REAL NOT NULL,
            unit TEXT,                       -- 'hours', 'steps', 'bpm', 'kg', 'score'
            timestamp REAL NOT NULL,
            date TEXT NOT NULL,              -- YYYY-MM-DD
            source TEXT,                     -- 'manual', 'device', 'app', 'inferred'
            device_id TEXT,
            notes TEXT,
            created_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metrics_name_date ON life_metrics(metric_name, date)
    """)

    # Habits & routines
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            frequency TEXT NOT NULL,         -- 'daily', 'weekly', 'monthly', 'custom'
            target_count INTEGER DEFAULT 1,  -- times per period
            duration_minutes INTEGER,        -- expected duration
            preferred_time TEXT,             -- 'morning', 'afternoon', 'evening', 'HH:MM'
            category TEXT,                   -- 'health', 'learning', 'productivity', 'social'
            streak_current INTEGER DEFAULT 0,
            streak_longest INTEGER DEFAULT 0,
            total_completions INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            reminder_enabled BOOLEAN DEFAULT 0,
            reminder_time TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Habit completions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habit_completions (
            id TEXT PRIMARY KEY,
            habit_id TEXT NOT NULL,
            date TEXT NOT NULL,              -- YYYY-MM-DD
            completed_at REAL,
            count INTEGER DEFAULT 1,
            duration_minutes INTEGER,
            quality_score REAL,              -- 1-10
            notes TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (habit_id) REFERENCES habits(id)
        )
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_habit_date ON habit_completions(habit_id, date)
    """)

    # Goals & milestones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            goal_type TEXT,                  -- 'outcome', 'process', 'habit', 'project'
            category TEXT,                   -- 'career', 'health', 'learning', 'financial', 'personal'
            target_date REAL,                -- deadline
            target_value REAL,               -- quantitative target
            target_unit TEXT,
            current_value REAL DEFAULT 0,
            progress REAL DEFAULT 0,         -- 0-100
            status TEXT DEFAULT 'active',    -- 'active', 'paused', 'completed', 'abandoned', 'on_hold'
            priority INTEGER DEFAULT 3,      -- 1=high, 2=medium, 3=low
            parent_goal_id TEXT,             -- for sub-goals
            milestones TEXT,                 -- JSON array of {title, target_date, completed}
            related_habits TEXT,             -- JSON array of habit IDs
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Memory anchors (significant moments for recall)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_anchors (
            id TEXT PRIMARY KEY,
            anchor_type TEXT NOT NULL,       -- 'milestone', 'insight', 'decision', 'achievement', 'failure', 'meeting_person'
            title TEXT NOT NULL,
            description TEXT,
            timestamp REAL NOT NULL,
            significance REAL DEFAULT 5,     -- 1-10 importance
            emotions TEXT,                   -- JSON array: 'joy', 'frustration', 'excitement', 'pride', etc.
            people TEXT,                     -- JSON array of people involved
            location TEXT,
            lessons_learned TEXT,
            related_events TEXT,             -- JSON array of timeline event IDs
            tags TEXT,                       -- JSON array
            is_private BOOLEAN DEFAULT 1,
            created_at REAL NOT NULL
        )
    """)

    # Temporal queries cache
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_cache (
            id TEXT PRIMARY KEY,
            query_hash TEXT UNIQUE NOT NULL,
            query_params TEXT,               -- JSON
            results TEXT,                    -- JSON
            expires_at REAL NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    # Narrative threads (storylines across time)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS narrative_threads (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            thread_type TEXT,                -- 'project', 'relationship', 'learning', 'health_journey', 'career'
            start_date REAL,
            end_date REAL,
            status TEXT DEFAULT 'active',    -- 'active', 'completed', 'archived'
            key_events TEXT,                 -- JSON array of event IDs
            themes TEXT,                     -- JSON array
            people TEXT,                     -- JSON array
            progress REAL DEFAULT 0,         -- 0-100
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_tm_db()


class TimelineEventStore:
    """Event-sourced timeline storage with temporal queries."""

    def __init__(self):
        pass

    def add_event(self, event_type: str, title: str, timestamp: float = None,
                  description: str = "", category: str = "", duration: float = None,
                  source: str = "manual", confidence: float = 1.0,
                  tags: List[str] = None, metadata: Dict = None,
                  correlations: List[str] = None, session_id: str = "") -> str:
        """Add a timeline event."""
        event_id = f"evt_{int(time.time() * 1000) % 100000000:08d}"
        ts = timestamp or time.time()

        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO timeline_events (id, event_type, category, title, description,
                                        timestamp, duration_seconds, source, confidence,
                                        tags, metadata, correlations, session_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (event_id, event_type, category, title, description,
              ts, duration, source, confidence,
              json.dumps(tags or []), json.dumps(metadata or {}),
              json.dumps(correlations or []), session_id, time.time(), time.time()))
        conn.commit()
        conn.close()

        # Invalidate daily summary cache
        self._invalidate_daily_summary(ts)

        return event_id

    def get_event(self, event_id: str) -> Optional[Dict]:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM timeline_events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return self._row_to_event(row)
        return None

    def get_events(self, start_time: float = None, end_time: float = None,
                   event_type: str = None, category: str = None,
                   tags: List[str] = None, session_id: str = None,
                   limit: int = 100, offset: int = 0) -> List[Dict]:
        """Query events with temporal filters."""
        conn = get_tm_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM timeline_events WHERE 1=1"
        params = []

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if category:
            query += " AND category = ?"
            params.append(category)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if tags:
            # Simple tag matching (would use JSON_CONTAINS in production)
            for tag in tags:
                query += " AND tags LIKE ?"
                params.append(f"%{tag}%")

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_event(r) for r in rows]

    def _row_to_event(self, row) -> Dict:
        return {
            "id": row[0], "event_type": row[1], "category": row[2],
            "title": row[3], "description": row[4], "timestamp": row[5],
            "duration_seconds": row[6], "source": row[7], "confidence": row[8],
            "tags": json.loads(row[9]) if row[9] else [],
            "metadata": json.loads(row[10]) if row[10] else {},
            "correlations": json.loads(row[11]) if row[11] else [],
            "session_id": row[12], "created_at": row[13], "updated_at": row[14]
        }

    def update_event(self, event_id: str, **kwargs) -> bool:
        allowed = ["title", "description", "category", "duration_seconds",
                   "confidence", "tags", "metadata", "correlations"]
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in allowed:
                updates.append(f"{k} = ?")
                params.append(json.dumps(v) if k in ["tags", "metadata", "correlations"] else v)
        if not updates:
            return False
        updates.append("updated_at = ?")
        params.append(time.time())
        params.append(event_id)

        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE timeline_events SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        return True

    def delete_event(self, event_id: str) -> bool:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM timeline_events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
        return True

    def get_day_events(self, date: str) -> List[Dict]:
        """Get all events for a specific day (YYYY-MM-DD)."""
        dt = datetime.strptime(date, "%Y-%m-%d")
        start = dt.timestamp()
        end = (dt + timedelta(days=1)).timestamp()
        return self.get_events(start_time=start, end_time=end, limit=1000)

    def get_week_events(self, week_start: str) -> List[Dict]:
        """Get all events for a week (YYYY-MM-DD)."""
        dt = datetime.strptime(week_start, "%Y-%m-%d")
        start = dt.timestamp()
        end = (dt + timedelta(days=7)).timestamp()
        return self.get_events(start_time=start, end_time=end, limit=5000)

    def search_events(self, query: str, limit: int = 50) -> List[Dict]:
        """Full-text search across events."""
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM timeline_events 
            WHERE title LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY timestamp DESC LIMIT ?
        """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_event(r) for r in rows]

    def _invalidate_daily_summary(self, timestamp: float):
        date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM daily_summaries WHERE date = ?", (date,))
        conn.commit()
        conn.close()


class DailySummaryEngine:
    """Generates daily summaries from timeline events."""

    def __init__(self, event_store: TimelineEventStore):
        self.event_store = event_store

    def generate_summary(self, date: str) -> Dict:
        """Generate or retrieve daily summary."""
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_summaries WHERE date = ?", (date,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_summary(row)

        # Generate from events
        events = self.event_store.get_day_events(date)
        return self._compute_summary(date, events)

    def _compute_summary(self, date: str, events: List[Dict]) -> Dict:
        if not events:
            return {"date": date, "total_events": 0}

        total_duration = sum(e.get("duration_seconds", 0) or 0 for e in events)

        # Count by type
        type_counts = defaultdict(int)
        cat_counts = defaultdict(int)
        all_tags = []

        focus_time = 0
        break_time = 0
        meeting_time = 0
        learning_time = 0
        health_time = 0

        for e in events:
            etype = e.get("event_type", "unknown")
            cat = e.get("category", "unknown")
            dur = e.get("duration_seconds", 0) or 0
            tags = e.get("tags", [])

            type_counts[etype] += 1
            cat_counts[cat] += 1
            all_tags.extend(tags)

            # Categorize time
            if etype in ["code", "deep_work", "focus"]:
                focus_time += dur
            elif etype in ["break", "rest"]:
                break_time += dur
            elif etype in ["meeting", "call"]:
                meeting_time += dur
            elif etype in ["learning", "study", "reading"]:
                learning_time += dur
            elif etype in ["exercise", "health", "meditation"]:
                health_time += dur

        # Top tags
        tag_counts = Counter(all_tags)
        top_tags = [{"tag": t, "count": c} for t, c in tag_counts.most_common(10)]

        # Productivity score (simple heuristic)
        work_events = sum(type_counts.get(t, 0) for t in ["code", "work", "deep_work", "meeting", "task"])
        total_events = len(events)
        productivity = min(100, (work_events / max(total_events, 1)) * 100) if total_events > 0 else 0

        summary = {
            "date": date,
            "total_events": total_events,
            "total_duration_seconds": total_duration,
            "event_types": dict(type_counts),
            "categories": dict(cat_counts),
            "top_tags": top_tags,
            "productivity_score": round(productivity, 1),
            "focus_time_seconds": focus_time,
            "break_time_seconds": break_time,
            "meeting_time_seconds": meeting_time,
            "learning_time_seconds": learning_time,
            "health_time_seconds": health_time,
            "highlights": self._extract_highlights(events),
            "challenges": [],
            "goals_progress": {}
        }

        # Save to DB
        self._save_summary(summary)
        return summary

    def _extract_highlights(self, events: List[Dict]) -> List[Dict]:
        """Extract key events as highlights."""
        highlights = []
        for e in events:
            if e.get("confidence", 1) > 0.8 and e.get("duration_seconds", 0) > 600:  # >10 min
                highlights.append({
                    "event_id": e["id"],
                    "title": e["title"],
                    "time": datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M"),
                    "duration_min": round(e["duration_seconds"] / 60, 1),
                    "type": e["event_type"]
                })
        return highlights[:5]  # Top 5

    def _save_summary(self, summary: Dict):
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_summaries (id, date, total_events, total_duration_seconds,
                                        event_types, categories, top_tags, productivity_score,
                                        focus_time_seconds, break_time_seconds, meeting_time_seconds,
                                        learning_time_seconds, health_time_seconds, highlights,
                                        challenges, goals_progress, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_events=excluded.total_events,
                total_duration_seconds=excluded.total_duration_seconds,
                event_types=excluded.event_types,
                categories=excluded.categories,
                top_tags=excluded.top_tags,
                productivity_score=excluded.productivity_score,
                focus_time_seconds=excluded.focus_time_seconds,
                break_time_seconds=excluded.break_time_seconds,
                meeting_time_seconds=excluded.meeting_time_seconds,
                learning_time_seconds=excluded.learning_time_seconds,
                health_time_seconds=excluded.health_time_seconds,
                highlights=excluded.highlights,
                challenges=excluded.challenges,
                goals_progress=excluded.goals_progress,
                updated_at=excluded.updated_at
        """, (f"sum_{summary['date']}", summary["date"], summary["total_events"],
              summary["total_duration_seconds"], json.dumps(summary["event_types"]),
              json.dumps(summary["categories"]), json.dumps(summary["top_tags"]),
              summary["productivity_score"], summary["focus_time_seconds"],
              summary["break_time_seconds"], summary["meeting_time_seconds"],
              summary["learning_time_seconds"], summary["health_time_seconds"],
              json.dumps(summary["highlights"]), json.dumps(summary["challenges"]),
              json.dumps(summary["goals_progress"]), time.time(), time.time()))
        conn.commit()
        conn.close()

    def _row_to_summary(self, row) -> Dict:
        return {
            "date": row[1], "total_events": row[2], "total_duration_seconds": row[3],
            "event_types": json.loads(row[4]) if row[4] else {},
            "categories": json.loads(row[5]) if row[5] else {},
            "top_tags": json.loads(row[6]) if row[6] else [],
            "productivity_score": row[7], "focus_time_seconds": row[8],
            "break_time_seconds": row[9], "meeting_time_seconds": row[10],
            "learning_time_seconds": row[11], "health_time_seconds": row[12],
            "highlights": json.loads(row[13]) if row[13] else [],
            "challenges": json.loads(row[14]) if row[14] else [],
            "goals_progress": json.loads(row[15]) if row[15] else {}
        }

    def get_week_summary(self, week_start: str) -> Dict:
        """Aggregate weekly summary."""
        dt = datetime.strptime(week_start, "%Y-%m-%d")
        summaries = []
        for i in range(7):
            day = (dt + timedelta(days=i)).strftime("%Y-%m-%d")
            s = self.generate_summary(day)
            summaries.append(s)

        return {
            "week_start": week_start,
            "total_events": sum(s.get("total_events", 0) for s in summaries),
            "total_duration_hours": sum(s.get("total_duration_seconds", 0) for s in summaries) / 3600,
            "avg_productivity": sum(s.get("productivity_score", 0) for s in summaries) / 7,
            "total_focus_hours": sum(s.get("focus_time_seconds", 0) for s in summaries) / 3600,
            "daily_summaries": summaries
        }

    def get_month_summary(self, year: int, month: int) -> Dict:
        """Monthly summary."""
        summaries = []
        for day in range(1, 32):
            try:
                date = f"{year}-{month:02d}-{day:02d}"
                s = self.generate_summary(date)
                if s.get("total_events", 0) > 0:
                    summaries.append(s)
            except:
                break

        return {
            "year": year, "month": month,
            "active_days": len(summaries),
            "total_events": sum(s.get("total_events", 0) for s in summaries),
            "total_hours": sum(s.get("total_duration_seconds", 0) for s in summaries) / 3600,
            "avg_productivity": sum(s.get("productivity_score", 0) for s in summaries) / max(len(summaries), 1)
        }


class HabitTracker:
    """Habit tracking with streaks and analytics."""

    def __init__(self):
        pass

    def create_habit(self, name: str, frequency: str = "daily",
                     target_count: int = 1, duration_minutes: int = None,
                     preferred_time: str = "", category: str = "",
                     description: str = "") -> str:
        habit_id = f"hab_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO habits (id, name, description, frequency, target_count,
                               duration_minutes, preferred_time, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (habit_id, name, description, frequency, target_count,
              duration_minutes, preferred_time, category, time.time(), time.time()))
        conn.commit()
        conn.close()
        return habit_id

    def complete_habit(self, habit_id: str, date: str = None,
                       count: int = 1, duration_minutes: int = None,
                       quality: float = None, notes: str = "") -> str:
        comp_id = f"hc_{int(time.time() * 1000) % 100000000:08d}"
        d = date or datetime.now().strftime("%Y-%m-%d")

        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO habit_completions (id, habit_id, date, completed_at,
                                          count, duration_minutes, quality_score, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(habit_id, date) DO UPDATE SET
                count=excluded.count, duration_minutes=excluded.duration_minutes,
                quality_score=excluded.quality_score, notes=excluded.notes
        """, (comp_id, habit_id, d, time.time(), count,
              duration_minutes, quality, notes, time.time()))
        conn.commit()

        # Update habit streak
        self._update_streak(habit_id)
        conn.close()
        return comp_id

    def _update_streak(self, habit_id: str):
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date FROM habit_completions WHERE habit_id = ? ORDER BY date DESC
        """, (habit_id,))
        dates = [r[0] for r in cursor.fetchall()]
        conn.close()

        if not dates:
            return

        # Calculate current streak
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        streak = 0
        check_date = today if today in dates else yesterday
        
        for d in dates:
            if d == check_date:
                streak += 1
                check_date = (datetime.strptime(check_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                break

        # Calculate longest streak
        longest = 0
        current = 0
        prev_date = None
        for d in reversed(dates):
            if prev_date:
                expected = (datetime.strptime(prev_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
                if d == expected:
                    current += 1
                else:
                    longest = max(longest, current)
                    current = 1
            else:
                current = 1
            prev_date = d
        longest = max(longest, current)

        total = len(dates)

        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE habits SET streak_current = ?, streak_longest = ?,
                             total_completions = ?, updated_at = ? WHERE id = ?
        """, (streak, longest, total, time.time(), habit_id))
        conn.commit()
        conn.close()

    def get_habit(self, habit_id: str) -> Optional[Dict]:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM habits WHERE id = ?", (habit_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "frequency": row[3], "target_count": row[4],
                "duration_minutes": row[5], "preferred_time": row[6],
                "category": row[7], "streak_current": row[8],
                "streak_longest": row[9], "total_completions": row[10],
                "is_active": bool(row[11]), "reminder_enabled": bool(row[12]),
                "reminder_time": row[13]
            }
        return None

    def list_habits(self, active_only: bool = True) -> List[Dict]:
        conn = get_tm_connection()
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM habits WHERE is_active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM habits ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "frequency": r[3],
             "streak": r[8], "longest": r[9], "total": r[10],
             "active": bool(r[11]), "category": r[7]}
            for r in rows
        ]

    def get_completion_heatmap(self, habit_id: str, year: int) -> Dict:
        """Get completion data for heatmap visualization."""
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, count FROM habit_completions 
            WHERE habit_id = ? AND date LIKE ?
        """, (habit_id, f"{year}-%"))
        rows = cursor.fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}

    def get_today_habits(self) -> List[Dict]:
        """Get habits due today with completion status."""
        today = datetime.now().strftime("%Y-%m-%d")
        habits = self.list_habits()
        
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT habit_id, count FROM habit_completions WHERE date = ?", (today,))
        completions = {r[0]: r[1] for r in cursor.fetchall()}
        conn.close()

        for h in habits:
            h["completed_today"] = h["id"] in completions
            h["count_today"] = completions.get(h["id"], 0)
        
        return habits


class GoalTracker:
    """Goal and milestone tracking."""

    def __init__(self):
        pass

    def create_goal(self, title: str, goal_type: str = "outcome",
                    category: str = "", target_date: float = None,
                    target_value: float = None, target_unit: str = "",
                    priority: int = 3, description: str = "") -> str:
        goal_id = f"goal_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO goals (id, title, description, goal_type, category,
                              target_date, target_value, target_unit,
                              priority, current_value, progress, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
        """, (goal_id, title, description, goal_type, category,
              target_date, target_value, target_unit,
              priority, time.time(), time.time()))
        conn.commit()
        conn.close()
        return goal_id

    def update_progress(self, goal_id: str, current_value: float) -> bool:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT target_value FROM goals WHERE id = ?", (goal_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False

        target = row[0] or 1
        progress = min(100, (current_value / target) * 100) if target > 0 else 0
        status = "completed" if progress >= 100 else "active"

        cursor.execute("""
            UPDATE goals SET current_value = ?, progress = ?, status = ?, updated_at = ?
            WHERE id = ?
        """, (current_value, progress, status, time.time(), goal_id))
        conn.commit()
        conn.close()
        return True

    def add_milestone(self, goal_id: str, title: str, target_date: float) -> bool:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT milestones FROM goals WHERE id = ?", (goal_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False

        milestones = json.loads(row[0]) if row[0] else []
        milestones.append({"title": title, "target_date": target_date, "completed": False})

        cursor.execute("UPDATE goals SET milestones = ?, updated_at = ? WHERE id = ?",
                      (json.dumps(milestones), time.time(), goal_id))
        conn.commit()
        conn.close()
        return True

    def get_goal(self, goal_id: str) -> Optional[Dict]:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "title": row[1], "description": row[2],
                "goal_type": row[3], "category": row[4], "target_date": row[5],
                "target_value": row[6], "target_unit": row[7],
                "current_value": row[8], "progress": row[9],
                "status": row[10], "priority": row[11],
                "milestones": json.loads(row[12]) if row[12] else [],
                "related_habits": json.loads(row[13]) if row[13] else []
            }
        return None

    def list_goals(self, status: str = None, category: str = None) -> List[Dict]:
        conn = get_tm_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM goals WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY priority, target_date"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "title": r[1], "category": r[4],
             "progress": r[9], "status": r[10], "priority": r[11],
             "target_date": r[5]}
            for r in rows
        ]


class MemoryAnchorStore:
    """Significant memory anchors for long-term recall."""

    def __init__(self):
        pass

    def create_anchor(self, anchor_type: str, title: str, timestamp: float = None,
                      description: str = "", significance: float = 5,
                      emotions: List[str] = None, people: List[str] = None,
                      location: str = "", lessons: str = "",
                      related_events: List[str] = None, tags: List[str] = None,
                      is_private: bool = True) -> str:
        anchor_id = f"anc_{int(time.time() * 1000) % 100000000:08d}"
        ts = timestamp or time.time()

        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO memory_anchors (id, anchor_type, title, description,
                                       timestamp, significance, emotions, people,
                                       location, lessons_learned, related_events,
                                       tags, is_private, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (anchor_id, anchor_type, title, description,
              ts, significance, json.dumps(emotions or []),
              json.dumps(people or []), location, lessons,
              json.dumps(related_events or []), json.dumps(tags or []),
              is_private, time.time()))
        conn.commit()
        conn.close()
        return anchor_id

    def get_anchors(self, anchor_type: str = None, limit: int = 50) -> List[Dict]:
        conn = get_tm_connection()
        cursor = conn.cursor()
        if anchor_type:
            cursor.execute("SELECT * FROM memory_anchors WHERE anchor_type = ? ORDER BY timestamp DESC LIMIT ?",
                          (anchor_type, limit))
        else:
            cursor.execute("SELECT * FROM memory_anchors ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "type": r[1], "title": r[2], "desc": r[3],
             "timestamp": r[4], "significance": r[5],
             "emotions": json.loads(r[6]) if r[6] else [],
             "people": json.loads(r[7]) if r[7] else [],
             "location": r[8], "lessons": r[9]}
            for r in rows
        ]

    def search_anchors(self, query: str) -> List[Dict]:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM memory_anchors 
            WHERE title LIKE ? OR description LIKE? OR lessons_learned LIKE ?
            ORDER BY significance DESC, timestamp DESC LIMIT 20
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "type": r[1], "title": r[2], "desc": r[3],
             "timestamp": r[4], "significance": r[5]}
            for r in rows
        ]


class NarrativeThreadManager:
    """Manages narrative threads across time."""

    def __init__(self, event_store: TimelineEventStore):
        self.event_store = event_store

    def create_thread(self, name: str, thread_type: str = "project",
                      description: str = "", themes: List[str] = None,
                      people: List[str] = None) -> str:
        thread_id = f"nt_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO narrative_threads (id, name, description, thread_type,
                                          themes, people, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """, (thread_id, name, description, thread_type,
              json.dumps(themes or []), json.dumps(people or []),
              time.time(), time.time()))
        conn.commit()
        conn.close()
        return thread_id

    def add_event_to_thread(self, thread_id: str, event_id: str) -> bool:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key_events FROM narrative_threads WHERE id = ?", (thread_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False

        events = json.loads(row[0]) if row[0] else []
        if event_id not in events:
            events.append(event_id)
            cursor.execute("UPDATE narrative_threads SET key_events = ?, updated_at = ? WHERE id = ?",
                          (json.dumps(events), time.time(), thread_id))
            conn.commit()
        conn.close()
        return True

    def get_thread(self, thread_id: str) -> Optional[Dict]:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM narrative_threads WHERE id = ?", (thread_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            # Columns: 0=id, 1=name, 2=description, 3=thread_type, 4=start_date, 5=end_date,
            # 6=status, 7=key_events, 8=themes, 9=people, 10=progress, 11=created_at, 12=updated_at
            event_ids = json.loads(row[7]) if row[7] and row[7].strip() else []
            events = [self.event_store.get_event(eid) for eid in event_ids]
            events = [e for e in events if e]
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "thread_type": row[3], "themes": json.loads(row[8]) if row[8] and row[8].strip() else [],
                "people": json.loads(row[9]) if row[9] and row[9].strip() else [],
                "events": events, "status": row[6], "progress": row[10]
            }
        return None

    def list_threads(self, status: str = "active") -> List[Dict]:
        conn = get_tm_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM narrative_threads WHERE status = ? ORDER BY updated_at DESC", (status,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "type": r[3], "status": r[6],
             "progress": r[10], "event_count": len(json.loads(r[7])) if r[7] and r[7].strip() else 0}
            for r in rows
        ]


# ===== TEMPORAL QUERIES =====

class TemporalQueryEngine:
    """Advanced temporal queries on timeline."""

    def __init__(self, event_store: TimelineEventStore):
        self.event_store = event_store

    def get_activity_heatmap(self, days: int = 30) -> Dict:
        """Get activity heatmap by hour of day."""
        end = time.time()
        start = end - (days * 86400)
        events = self.event_store.get_events(start_time=start, end_time=end, limit=10000)

        heatmap = defaultdict(lambda: defaultdict(int))  # day_of_week -> hour -> count
        for e in events:
            dt = datetime.fromtimestamp(e["timestamp"])
            dow = dt.weekday()  # 0=Monday
            hour = dt.hour
            heatmap[dow][hour] += 1

        return {str(dow): dict(hours) for dow, hours in heatmap.items()}

    def get_productivity_trend(self, days: int = 30) -> List[Dict]:
        """Daily productivity scores."""
        end = datetime.now()
        trend = []
        for i in range(days):
            date = (end - timedelta(days=i)).strftime("%Y-%m-%d")
            # Would use DailySummaryEngine in practice
            trend.append({"date": date, "productivity": 75})  # Placeholder
        return list(reversed(trend))

    def get_time_allocation(self, days: int = 7) -> Dict:
        """Time spent by category."""
        end = time.time()
        start = end - (days * 86400)
        events = self.event_store.get_events(start_time=start, end_time=end, limit=5000)

        allocation = defaultdict(float)
        for e in events:
            dur = e.get("duration_seconds", 0) or 0
            cat = e.get("category", "unknown")
            allocation[cat] += dur

        return {k: round(v / 3600, 1) for k, v in allocation.items()}

    def find_patterns(self, min_occurrences: int = 3) -> List[Dict]:
        """Find recurring patterns in timeline."""
        # Simplified: find events that happen at similar times
        events = self.event_store.get_events(limit=5000)
        
        # Group by hour and event type
        pattern_counts = defaultdict(int)
        for e in events:
            dt = datetime.fromtimestamp(e["timestamp"])
            key = (dt.hour, e.get("event_type", "unknown"))
            pattern_counts[key] += 1

        patterns = []
        for (hour, etype), count in pattern_counts.items():
            if count >= min_occurrences:
                patterns.append({
                    "hour": hour, "event_type": etype, "frequency": count,
                    "description": f"{etype} at {hour}:00 occurs {count} times"
                })
        return sorted(patterns, key=lambda x: x["frequency"], reverse=True)

    def correlate_events(self, event_type_a: str, event_type_b: str,
                         window_hours: int = 2) -> List[Dict]:
        """Find correlations between event types."""
        events = self.event_store.get_events(limit=5000)
        type_a = [e for e in events if e.get("event_type") == event_type_a]
        type_b = [e for e in events if e.get("event_type") == event_type_b]

        correlations = []
        for a in type_a:
            for b in type_b:
                diff = abs(a["timestamp"] - b["timestamp"])
                if diff <= window_hours * 3600:
                    correlations.append({
                        "event_a": a["id"], "event_b": b["id"],
                        "time_diff_minutes": round(diff / 60, 1),
                        "a_title": a["title"], "b_title": b["title"]
                    })
        return correlations


# ===== MODULE EXPORTS =====

event_store = TimelineEventStore()
daily_summary = DailySummaryEngine(event_store)
habit_tracker = HabitTracker()
goal_tracker = GoalTracker()
memory_anchors = MemoryAnchorStore()
narrative_threads = NarrativeThreadManager(event_store)
temporal_queries = TemporalQueryEngine(event_store)


def tm_debug() -> str:
    conn = get_tm_connection()
    cursor = conn.cursor()
    tables = ["timeline_events", "daily_summaries", "time_blocks", "life_metrics",
              "habits", "habit_completions", "goals", "memory_anchors", "narrative_threads"]
    output = "Timeline Memory Debug:\n"
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        output += f"  {t}: {count} records\n"
    conn.close()
    return output


def add_timeline_event(event_type: str, title: str, timestamp: float = None,
                       description: str = "", category: str = "", duration: float = None,
                       source: str = "manual", tags: List[str] = None,
                       metadata: Dict = None, session_id: str = "") -> str:
    return event_store.add_event(event_type, title, timestamp, description,
                                  category, duration, source, 1.0, tags, metadata, None, session_id)


def get_timeline_events(start: float = None, end: float = None,
                        event_type: str = None, category: str = None,
                        limit: int = 100) -> List[Dict]:
    return event_store.get_events(start_time=start, end_time=end,
                                   event_type=event_type, category=category, limit=limit)


def get_day_timeline(date: str) -> List[Dict]:
    return event_store.get_day_events(date)


def search_timeline(query: str, limit: int = 50) -> List[Dict]:
    return event_store.search_events(query, limit)


def get_daily_summary(date: str) -> Dict:
    return daily_summary.generate_summary(date)


def get_week_summary(week_start: str) -> Dict:
    return daily_summary.get_week_summary(week_start)


def get_month_summary(year: int, month: int) -> Dict:
    return daily_summary.get_month_summary(year, month)


def create_habit(name: str, frequency: str = "daily", **kwargs) -> str:
    return habit_tracker.create_habit(name, frequency, **kwargs)


def complete_habit(habit_id: str, date: str = None, **kwargs) -> str:
    return habit_tracker.complete_habit(habit_id, date, **kwargs)


def get_habits(active_only: bool = True) -> List[Dict]:
    return habit_tracker.list_habits(active_only)


def get_today_habits() -> List[Dict]:
    return habit_tracker.get_today_habits()


def create_goal(title: str, **kwargs) -> str:
    return goal_tracker.create_goal(title, **kwargs)


def update_goal_progress(goal_id: str, value: float) -> bool:
    return goal_tracker.update_progress(goal_id, value)


def get_goals(status: str = None) -> List[Dict]:
    return goal_tracker.list_goals(status)


def create_memory_anchor(anchor_type: str, title: str, **kwargs) -> str:
    return memory_anchors.create_anchor(anchor_type, title, **kwargs)


def get_memory_anchors(anchor_type: str = None) -> List[Dict]:
    return memory_anchors.get_anchors(anchor_type)


def create_narrative_thread(name: str, thread_type: str = "project", **kwargs) -> str:
    return narrative_threads.create_thread(name, thread_type, **kwargs)


def add_event_to_thread(thread_id: str, event_id: str) -> bool:
    return narrative_threads.add_event_to_thread(thread_id, event_id)


def get_narrative_thread(thread_id: str) -> Optional[Dict]:
    return narrative_threads.get_thread(thread_id)


def get_activity_heatmap(days: int = 30) -> Dict:
    return temporal_queries.get_activity_heatmap(days)


def get_time_allocation(days: int = 7) -> Dict:
    return temporal_queries.get_time_allocation(days)


def find_temporal_patterns(min_occurrences: int = 3) -> List[Dict]:
    return temporal_queries.find_patterns(min_occurrences)


def correlate_event_types(type_a: str, type_b: str, window_hours: int = 2) -> List[Dict]:
    return temporal_queries.correlate_events(type_a, type_b, window_hours)


if __name__ == "__main__":
    print("Timeline Memory Agent loaded.")
    print("Core: event_store, daily_summary, habit_tracker, goal_tracker")
    print("      memory_anchors, narrative_threads, temporal_queries")