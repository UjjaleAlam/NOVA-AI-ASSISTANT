import os
import json
import time
import math
import random
import statistics
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path

DB_DIR = "database"
EA_DB = os.path.join(DB_DIR, "executive_assistant.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_ea_connection():
    import sqlite3
    conn = sqlite3.connect(EA_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_ea_db():
    conn = get_ea_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 3,
            category TEXT,
            project_id TEXT,
            parent_task_id TEXT,
            depth INTEGER DEFAULT 0,
            estimated_hours REAL,
            actual_hours REAL DEFAULT 0,
            progress REAL DEFAULT 0,
            due_date REAL,
            start_date REAL,
            completed_at REAL,
            depends_on TEXT,
            blocked_by TEXT,
            tags TEXT,
            context TEXT,
            energy_level INTEGER,
            time_of_day TEXT,
            location TEXT,
            delegated_to TEXT,
            delegated_at REAL,
            reminder_at REAL,
            recurrence TEXT,
            source TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES ea_projects(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 3,
            category TEXT,
            goal_id TEXT,
            start_date REAL,
            target_date REAL,
            completed_at REAL,
            budget REAL,
            spent REAL DEFAULT 0,
            tags TEXT,
            stakeholders TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_calendar (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            all_day BOOLEAN DEFAULT 0,
            event_type TEXT,
            status TEXT DEFAULT 'confirmed',
            location TEXT,
            attendees TEXT,
            meeting_link TEXT,
            recurrence TEXT,
            reminders TEXT,
            task_id TEXT,
            project_id TEXT,
            calendar_source TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_meetings (
            id TEXT PRIMARY KEY,
            calendar_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            attendees TEXT,
            organizer TEXT,
            location TEXT,
            meeting_link TEXT,
            agenda TEXT,
            notes TEXT,
            action_items TEXT,
            decisions TEXT,
            recording_path TEXT,
            transcript_path TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (calendar_id) REFERENCES ea_calendar(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_decisions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            context TEXT,
            options TEXT,
            chosen_option TEXT,
            rationale TEXT,
            decision_type TEXT,
            impact_scope TEXT,
            impact_level INTEGER,
            status TEXT DEFAULT 'pending',
            decided_at REAL,
            decided_by TEXT,
            review_date REAL,
            related_tasks TEXT,
            related_goals TEXT,
            confidence REAL,
            tags TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (goal_id) REFERENCES ea_goals(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_contacts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            role TEXT,
            organization TEXT,
            relationship TEXT,
            department TEXT,
            manager_id TEXT,
            preferred_contact TEXT,
            timezone TEXT,
            working_hours TEXT,
            notes TEXT,
            tags TEXT,
            last_contact REAL,
            contact_frequency TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_communications (
            id TEXT PRIMARY KEY,
            contact_id TEXT,
            direction TEXT,
            channel TEXT,
            subject TEXT,
            body TEXT,
            timestamp REAL NOT NULL,
            thread_id TEXT,
            related_task_id TEXT,
            related_meeting_id TEXT,
            attachments TEXT,
            sentiment TEXT,
            action_required BOOLEAN DEFAULT 0,
            action_taken TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (contact_id) REFERENCES ea_contacts(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_plans (
            id TEXT PRIMARY KEY,
            plan_type TEXT,
            period_start REAL NOT NULL,
            period_end REAL NOT NULL,
            objectives TEXT,
            priorities TEXT,
            time_blocks TEXT,
            focus_areas TEXT,
            success_criteria TEXT,
            review_notes TEXT,
            status TEXT DEFAULT 'draft',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_habits (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            frequency TEXT,
            target_count INTEGER DEFAULT 1,
            duration_minutes INTEGER,
            preferred_time TEXT,
            days_of_week TEXT,
            category TEXT,
            streak_current INTEGER DEFAULT 0,
            streak_longest INTEGER DEFAULT 0,
            total_completions INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            trigger TEXT,
            reward TEXT,
            difficulty INTEGER DEFAULT 3,
            accountability TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_habit_completions (
            id TEXT PRIMARY KEY,
            habit_id TEXT NOT NULL,
            date TEXT NOT NULL,
            completed_at REAL,
            count INTEGER DEFAULT 1,
            duration_minutes INTEGER,
            quality_score INTEGER,
            notes TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (habit_id) REFERENCES ea_habits(id)
        )
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_habit_date ON ea_habit_completions(habit_id, date)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_inbox (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            source TEXT,
            captured_at REAL NOT NULL,
            processed BOOLEAN DEFAULT 0,
            processed_at REAL,
            converted_to_task_id TEXT,
            converted_to_event_id TEXT,
            priority INTEGER DEFAULT 3,
            tags TEXT,
            created_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_focus_sessions (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            planned_duration INTEGER,
            actual_duration INTEGER,
            start_time REAL NOT NULL,
            end_time REAL,
            session_type TEXT,
            interruptions INTEGER DEFAULT 0,
            notes TEXT,
            productivity_score INTEGER,
            created_at REAL NOT NULL,
            FOREIGN KEY (task_id) REFERENCES ea_tasks(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_energy_logs (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            energy_level INTEGER,
            focus_level INTEGER,
            mood TEXT,
            activity TEXT,
            notes TEXT,
            created_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_delegations (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            delegated_to TEXT,
            delegated_at REAL NOT NULL,
            expected_completion REAL,
            actual_completion REAL,
            status TEXT DEFAULT 'pending',
            instructions TEXT,
            follow_up_date REAL,
            outcome TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ea_quick_capture (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            content_type TEXT,
            source TEXT,
            captured_at REAL NOT NULL,
            processed BOOLEAN DEFAULT 0,
            processed_at REAL,
            task_id TEXT,
            event_id TEXT,
            tags TEXT,
            created_at REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_ea_db()
class TaskManager:
    def __init__(self):
        pass

    def create_task(self, title: str, description: str = "", **kwargs) -> str:
        task_id = "task_{:08d}".format(int(time.time() * 1000000) % 100000000) + "_{:04d}".format(int(time.time() * 10000) % 10000) + "_{:04d}".format(random.randint(0, 9999))
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_tasks (id, title, description, status, priority, category,
                                  project_id, parent_task_id, depth, estimated_hours,
                                  actual_hours, progress, due_date, start_date, completed_at,
                                  depends_on, blocked_by, tags, context, energy_level,
                                  time_of_day, location, delegated_to, delegated_at,
                                  reminder_at, recurrence, source, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (task_id, title, description, kwargs.get("priority", 3),
              kwargs.get("category", "work"), kwargs.get("project_id"),
              kwargs.get("parent_task_id"), kwargs.get("depth", 0),
              kwargs.get("estimated_hours"), 0, 0,
              kwargs.get("due_date"), kwargs.get("start_date"), None,
              json.dumps(kwargs.get("depends_on", [])), json.dumps(kwargs.get("blocked_by", [])),
              json.dumps(kwargs.get("tags", [])), json.dumps(kwargs.get("context", {})),
              kwargs.get("energy_level", 2), kwargs.get("time_of_day", "anytime"),
              kwargs.get("location", "anywhere"), kwargs.get("delegated_to"), None,
              None, kwargs.get("recurrence"), kwargs.get("source", "manual"),
              time.time(), time.time()))
        conn.commit()
        conn.close()
        return task_id

    def get_task(self, task_id: str) -> Optional[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ea_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return self._row_to_task(row)
        return None

    def _row_to_task(self, row) -> Dict:
        return {
            "id": row[0], "title": row[1], "description": row[2], "status": row[3],
            "priority": row[4], "category": row[5], "project_id": row[6],
            "parent_task_id": row[7], "depth": row[8], "estimated_hours": row[9],
            "actual_hours": row[10], "progress": row[11], "due_date": row[12],
            "start_date": row[13], "completed_at": row[14],
            "depends_on": json.loads(row[15]) if row[15] else [],
            "blocked_by": json.loads(row[16]) if row[16] else [],
            "tags": json.loads(row[17]) if row[17] else [],
            "context": json.loads(row[18]) if row[18] else {},
            "energy_level": row[19], "time_of_day": row[20],
            "location": row[21], "delegated_to": row[22],
            "delegated_at": row[23], "reminder_at": row[24],
            "recurrence": row[25], "source": row[26],
            "created_at": row[27], "updated_at": row[28]
        }

    def update_task(self, task_id: str, **kwargs) -> bool:
        conn = get_ea_connection()
        cursor = conn.cursor()
        allowed = ["title", "description", "status", "priority", "category",
                   "project_id", "estimated_hours", "actual_hours", "progress",
                   "due_date", "start_date", "depends_on", "blocked_by",
                   "tags", "context", "energy_level", "time_of_day", "location",
                   "delegated_to", "recurrence", "reminder_at"]
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in allowed:
                updates.append(f"{k} = ?")
                params.append(json.dumps(v) if k in ["depends_on", "blocked_by", "tags", "context"] else v)
        if not updates:
            return False
        updates.append("updated_at = ?")
        params.append(time.time())
        params.append(task_id)
        cursor.execute("UPDATE ea_tasks SET {} WHERE id = ?".format(", ".join(updates)), params)
        conn.commit()
        conn.close()
        return True

    def get_tasks(self, status: str = None, category: str = None,
                  project_id: str = None, tag: str = None) -> List[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM ea_tasks WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if tag:
            query += " AND tags LIKE ?"
            params.append("%{}%".format(tag))
        query += " ORDER BY priority, due_date, created_at"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(r) for r in rows]

    def complete_task(self, task_id: str) -> bool:
        return self.update_task(task_id, status="completed", completed_at=time.time(), progress=100)

    def get_overdue_tasks(self) -> List[Dict]:
        now = time.time()
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ea_tasks WHERE due_date < ? AND status NOT IN ('completed', 'cancelled') ORDER BY due_date", (now,))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(r) for r in rows]

    def get_today_tasks(self) -> List[Dict]:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today_end = today_start + 86400
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ea_tasks 
            WHERE (due_date BETWEEN ? AND ? OR start_date BETWEEN ? AND ?)
            AND status NOT IN ('completed', 'cancelled')
            ORDER BY priority, due_date
        """, (today_start, today_end, today_start, today_end))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(r) for r in rows]


class ProjectManager:
    def __init__(self):
        pass

    def create_project(self, name: str, description: str = "", **kwargs) -> str:
        proj_id = "proj_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_projects (id, name, description, status, priority, category,
                                    goal_id, start_date, target_date, budget, tags, stakeholders,
                                    created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (proj_id, name, description, kwargs.get("priority", 3),
              kwargs.get("category"), kwargs.get("goal_id"),
              kwargs.get("start_date"), kwargs.get("target_date"),
              kwargs.get("budget"), json.dumps(kwargs.get("tags", [])),
              json.dumps(kwargs.get("stakeholders", [])), time.time(), time.time()))
        conn.commit()
        conn.close()
        return proj_id

    def get_project(self, proj_id: str) -> Optional[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ea_projects WHERE id = ?", (proj_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "status": row[3], "priority": row[4], "category": row[5],
                "goal_id": row[6], "start_date": row[7], "target_date": row[9],
                "completed_at": row[9], "budget": row[10], "spent": row[11],
                "tags": json.loads(row[12]) if row[12] else [],
                "stakeholders": json.loads(row[13]) if row[13] else [],
                "created_at": row[14], "updated_at": row[15]
            }
        return None

    def list_projects(self, status: str = None) -> List[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM ea_projects WHERE status = ? ORDER BY priority, target_date", (status,))
        else:
            cursor.execute("SELECT * FROM ea_projects ORDER BY priority, target_date")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "status": r[3], "priority": r[4],
             "category": r[5], "target_date": r[8], "budget": r[10], "spent": r[11]}
            for r in rows
        ]


class CalendarManager:
    def __init__(self):
        pass

    def create_event(self, title: str, start_time: float, end_time: float, **kwargs) -> str:
        event_id = "evt_{:08d}".format(int(time.time() * 1000000) % 100000000) + "_{:04d}".format(int(time.time() * 10000) % 10000) + "_{:04d}".format(random.randint(0, 9999))
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_calendar (id, title, description, start_time, end_time,
                                    all_day, event_type, status, location, attendees,
                                    meeting_link, recurrence, reminders, task_id,
                                    project_id, calendar_source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (event_id, title, kwargs.get("description", ""), start_time, end_time,
              kwargs.get("all_day", 0), kwargs.get("event_type", "meeting"),
              kwargs.get("status", "confirmed"), kwargs.get("location", ""),
              json.dumps(kwargs.get("attendees", [])), kwargs.get("meeting_link", ""),
              kwargs.get("recurrence", ""), json.dumps(kwargs.get("reminders", [])),
              kwargs.get("task_id"), kwargs.get("project_id"),
              kwargs.get("calendar_source", "local"), time.time(), time.time()))
        conn.commit()
        conn.close()
        return event_id

    def get_events(self, start: float, end: float) -> List[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ea_calendar WHERE start_time < ? AND end_time > ?
            ORDER BY start_time
        """, (end, start))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_event(r) for r in rows]

    def _row_to_event(self, row) -> Dict:
        return {
            "id": row[0], "title": row[1], "description": row[2],
            "start_time": row[3], "end_time": row[4], "all_day": bool(row[5]),
            "event_type": row[6], "status": row[7], "location": row[8],
            "attendees": json.loads(row[9]) if row[9] else [],
            "meeting_link": row[10], "recurrence": row[11],
            "reminders": json.loads(row[12]) if row[12] else [],
            "task_id": row[13], "project_id": row[14],
            "calendar_source": row[15], "created_at": row[16], "updated_at": row[17]
        }

    def get_today_events(self) -> List[Dict]:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today_end = today_start + 86400
        return self.get_events(today_start, today_end)

    def get_upcoming_meetings(self, hours: int = 24) -> List[Dict]:
        now = time.time()
        end = now + hours * 3600
        return self.get_events(now, end)


class DecisionManager:
    def __init__(self):
        pass

    def create_decision(self, title: str, description: str = "", **kwargs) -> str:
        dec_id = "dec_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_decisions (id, title, description, context, options,
                                     chosen_option, rationale, decision_type,
                                     impact_scope, impact_level, status, confidence,
                                     tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (dec_id, title, description, kwargs.get("context", ""),
              json.dumps(kwargs.get("options", [])), kwargs.get("chosen_option", ""),
              kwargs.get("rationale", ""), kwargs.get("decision_type", "tactical"),
              kwargs.get("impact_scope", "personal"), kwargs.get("impact_level", 2),
              kwargs.get("status", "pending"), kwargs.get("confidence", 0.8),
              json.dumps(kwargs.get("tags", [])), time.time(), time.time()))
        conn.commit()
        conn.close()
        return dec_id

    def decide(self, dec_id: str, chosen: str, rationale: str = "") -> bool:
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ea_decisions SET chosen_option = ?, rationale = ?,
                                   status = 'decided', decided_at = ?, updated_at = ?
            WHERE id = ?
        """, (chosen, rationale, time.time(), time.time(), dec_id))
        conn.commit()
        conn.close()
        return True

    def get_decision(self, dec_id: str) -> Optional[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ea_decisions WHERE id = ?", (dec_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "title": row[1], "description": row[2],
                "context": row[3], "options": json.loads(row[4]) if row[4] else [],
                "chosen_option": row[5], "rationale": row[6],
                "decision_type": row[6], "impact_scope": row[7],
                "impact_level": row[8], "status": row[9],
                "decided_at": row[10], "decided_by": row[11],
                "review_date": row[12], "related_tasks": json.loads(row[13]) if row[13] else [],
                "related_goals": json.loads(row[15]) if row[15] else [],
                "confidence": row[16], "tags": json.loads(row[16]) if row[16] else [],
                "created_at": row[17], "updated_at": row[18]
            }
        return None

    def list_decisions(self, status: str = None) -> List[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM ea_decisions WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM ea_decisions ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "title": r[1], "status": r[10], "type": r[7],
             "impact": r[9], "confidence": r[15]}
            for r in rows
        ]


class ContactManager:
    def __init__(self):
        pass

    def add_contact(self, name: str, **kwargs) -> str:
        contact_id = "contact_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_contacts (id, name, email, phone, role, organization,
                                    relationship, department, manager_id,
                                    preferred_contact, timezone, working_hours,
                                    notes, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (contact_id, name, kwargs.get("email", ""), kwargs.get("phone", ""),
              kwargs.get("role", ""), kwargs.get("organization", ""),
              kwargs.get("relationship", "colleague"), kwargs.get("department", ""),
              kwargs.get("manager_id"), kwargs.get("preferred_contact", "email"),
              kwargs.get("timezone", ""), json.dumps(kwargs.get("working_hours", {})),
              kwargs.get("notes", ""), json.dumps(kwargs.get("tags", [])),
              time.time(), time.time()))
        conn.commit()
        conn.close()
        return contact_id

    def get_contact(self, contact_id: str) -> Optional[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ea_contacts WHERE id = ?", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "email": row[2], "phone": row[3],
                "role": row[4], "organization": row[5], "relationship": row[6],
                "department": row[7], "manager_id": row[8],
                "preferred_contact": row[9], "timezone": row[10],
                "working_hours": json.loads(row[11]) if row[11] else {},
                "notes": row[12], "tags": json.loads(row[13]) if row[13] else [],
                "last_contact": row[14], "contact_frequency": row[15],
                "created_at": row[16], "updated_at": row[17]
            }
        return None


class Planner:
    def __init__(self):
        pass

    def create_daily_plan(self, date: str = None, **kwargs) -> str:
        plan_id = "plan_{:08d}".format(int(time.time() * 1000) % 100000000)
        if date:
            dt = datetime.strptime(date, "%Y-%m-%d")
        else:
            dt = datetime.now()
        period_start = dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        period_end = period_start + 86400

        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_plans (id, plan_type, period_start, period_end,
                                 objectives, priorities, time_blocks,
                                 focus_areas, success_criteria, status,
                                 created_at, updated_at)
            VALUES (?, 'daily', ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)
        """, (plan_id, period_start, period_end,
              json.dumps(kwargs.get("objectives", [])),
              json.dumps(kwargs.get("priorities", [])),
              json.dumps(kwargs.get("time_blocks", [])),
              json.dumps(kwargs.get("focus_areas", [])),
              json.dumps(kwargs.get("success_criteria", [])),
              time.time(), time.time()))
        conn.commit()
        conn.close()
        return plan_id


class InboxManager:
    def __init__(self):
        pass

    def capture(self, content: str, title: str = "", **kwargs) -> str:
        item_id = "inbox_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_inbox (id, title, description, source, captured_at,
                                 priority, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (item_id, title or content[:50], content, kwargs.get("source", "manual"), time.time(),
              kwargs.get("priority", 3), json.dumps(kwargs.get("tags", [])), time.time()))
        conn.commit()
        conn.close()
        return item_id

    def get_inbox(self, processed: bool = False) -> List[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ea_inbox WHERE processed = ? ORDER BY captured_at DESC", (1 if processed else 0,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "title": r[1], "description": r[2], "source": r[3],
             "captured_at": r[4], "processed": bool(r[5]), "processed_at": r[6],
             "task_id": r[7], "event_id": r[8], "priority": r[9],
             "tags": json.loads(r[10]) if r[10] else []}
            for r in rows
        ]

    def process_item(self, item_id: str, action: str, **kwargs) -> bool:
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE ea_inbox SET processed = 1, processed_at = ? WHERE id = ?",
                      (time.time(), item_id))
        conn.commit()
        conn.close()
        return True


class QuickCapture:
    def __init__(self):
        pass

    def capture(self, content: str, **kwargs) -> str:
        item_id = "qc_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_quick_capture (id, content, content_type, source,
                                         captured_at, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (item_id, content,
              kwargs.get("content_type", "text"), kwargs.get("source", "voice"),
              time.time(), json.dumps(kwargs.get("tags", [])), time.time()))
        conn.commit()
        conn.close()
        return item_id


class DelegationManager:
    def __init__(self):
        pass

    def delegate(self, task_id: str, delegated_to: str, **kwargs) -> str:
        del_id = "del_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_delegations (id, task_id, delegated_to, delegated_at,
                                       expected_completion, instructions,
                                       follow_up_date, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (del_id, task_id, delegated_to, time.time(),
              kwargs.get("expected_completion"), kwargs.get("instructions", ""),
              kwargs.get("follow_up_date"), time.time(), time.time()))
        
        # Update task
        cursor.execute("UPDATE ea_tasks SET delegated_to = ?, delegated_at = ? WHERE id = ?",
                      (delegated_to, time.time(), task_id))
        conn.commit()
        conn.close()
        return del_id

    def get_delegations(self, status: str = None) -> List[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM ea_delegations WHERE status = ? ORDER BY delegated_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM ea_delegations ORDER BY delegated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "task_id": r[1], "delegated_to": r[2],
             "status": r[7], "expected": r[4], "follow_up": r[6]}
            for r in rows
        ]


class FocusManager:
    def __init__(self):
        pass

    def start_session(self, task_id: str = None, duration: int = 25,
                      session_type: str = "pomodoro") -> str:
        session_id = "fs_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_focus_sessions (id, task_id, planned_duration,
                                          session_type, start_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, task_id, duration, session_type, time.time(), time.time()))
        conn.commit()
        conn.close()
        return session_id
    def end_session(self, session_id: str, **kwargs) -> bool:
        conn = get_ea_connection()
        cursor = conn.cursor()
        sql = (
            "UPDATE ea_focus_sessions SET end_time = ?, actual_duration = ?, "
            "interruptions = ?, notes = ?, productivity_score = ? "
            "WHERE id = ?"
        )
        params = (time.time(), kwargs.get("actual_duration"),
              kwargs.get("interruptions", 0), kwargs.get("notes", ""),
              kwargs.get("productivity_score"), session_id)
        cursor.execute(sql, params)
        conn.commit()
        conn.close()
        return True

    def get_sessions(self, task_id: str = None, days: int = 7) -> List[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        start = time.time() - days * 86400
        if task_id:
            cursor.execute("SELECT * FROM ea_focus_sessions WHERE task_id = ? AND start_time > ? ORDER BY start_time",
                          (task_id, start))
        else:
            cursor.execute("SELECT * FROM ea_focus_sessions WHERE start_time > ? ORDER BY start_time", (start,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "task_id": r[1], "planned": r[2], "actual": r[3],
             "type": r[4], "start": r[5], "end": r[6], "interruptions": r[7],
             "score": r[9]} for r in rows
        ]


class EnergyTracker:
    def __init__(self):
        pass

    def log_energy(self, energy: int, focus: int = None, mood: str = "",
                   activity: str = "", notes: str = "") -> str:
        log_id = "en_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_energy_logs (id, timestamp, energy_level, focus_level,
                                       mood, activity, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (log_id, time.time(), energy, focus, mood, activity, notes, time.time()))
        conn.commit()
        conn.close()
        return log_id

    def get_energy_trend(self, days: int = 7) -> Dict:
        conn = get_ea_connection()
        cursor = conn.cursor()
        start = time.time() - days * 86400
        cursor.execute("SELECT * FROM ea_energy_logs WHERE timestamp > ? ORDER BY timestamp", (start,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return {"data": [], "avg_energy": 0, "avg_focus": 0}
        
        energies = [r[2] for r in rows]
        focuses = [r[3] for r in rows if r[3]]
        return {
            "data": [{"timestamp": r[1], "energy": r[2], "focus": r[3], "mood": r[4]} for r in rows],
            "avg_energy": statistics.mean(energies),
            "avg_focus": statistics.mean(focuses) if focuses else 0,
            "trend": "up" if energies[-1] > energies[0] else "down" if energies[-1] < energies[0] else "stable"
        }


class HabitTracker:
    def __init__(self):
        pass

    def add_habit(self, name: str, **kwargs) -> str:
        habit_id = "habit_{:08d}".format(int(time.time() * 1000000) % 100000000) + "_{:04d}".format(int(time.time() * 10000) % 10000) + "_{:04d}".format(random.randint(0, 9999))
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_habits (id, name, description, frequency, target_count,
                                  duration_minutes, preferred_time, days_of_week,
                                  category, trigger, reward, difficulty, accountability,
                                  created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (habit_id, name, kwargs.get("description", ""),
              kwargs.get("frequency", "daily"), kwargs.get("target_count", 1),
              kwargs.get("duration_minutes"), kwargs.get("preferred_time", "morning"),
              json.dumps(kwargs.get("days_of_week", list(range(7)))),
              kwargs.get("category", "health"), kwargs.get("trigger", ""),
              kwargs.get("reward", ""), kwargs.get("difficulty", 3),
              kwargs.get("accountability", "none"), time.time(), time.time()))
        conn.commit()
        conn.close()
        return habit_id

    def complete_habit(self, habit_id: str, date: str = None, **kwargs) -> str:
        completion_id = "hc_{:08d}".format(int(time.time() * 1000) % 100000000)
        d = date or datetime.now().strftime("%Y-%m-%d")
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ea_habit_completions (id, habit_id, date, completed_at,
                                             count, duration_minutes, quality_score, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(habit_id, date) DO UPDATE SET
                count=excluded.count, duration_minutes=excluded.duration_minutes,
                quality_score=excluded.quality_score, notes=excluded.notes
        """, (completion_id, habit_id, d, time.time(),
              kwargs.get("count", 1), kwargs.get("duration_minutes"),
              kwargs.get("quality_score"), kwargs.get("notes", ""), time.time()))
        
        # Update streak
        cursor.execute("SELECT date FROM ea_habit_completions WHERE habit_id = ? ORDER BY date DESC", (habit_id,))
        dates = [r[0] for r in cursor.fetchall()]
        
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        check_date = today if today in dates else yesterday
        
        streak = 0
        for d in dates:
            if d == check_date:
                streak += 1
                check_date = (datetime.strptime(check_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                break
        
        # Longest streak
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
        
        cursor.execute("UPDATE ea_habits SET streak_current = ?, streak_longest = ?, total_completions = total_completions + 1, updated_at = ? WHERE id = ?",
                      (streak, longest, time.time(), habit_id))
        conn.commit()
        conn.close()
        return completion_id

    def get_habits(self, active_only: bool = True) -> List[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM ea_habits WHERE is_active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM ea_habits ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "frequency": r[3], "streak": r[8],
             "longest": r[9], "total": r[10], "category": r[8]}
            for r in rows
        ]

    def get_today_habits(self) -> List[Dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        habits = self.get_habits()
        
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT habit_id, count FROM ea_habit_completions WHERE date = ?", (today,))
        completions = {r[0]: r[1] for r in cursor.fetchall()}
        conn.close()

        for h in habits:
            h["completed_today"] = h["id"] in completions
            h["count_today"] = completions.get(h["id"], 0)
        return habits


# ===== EXECUTIVE ASSISTANT ENGINE =====

class ExecutiveAssistant:
    """High-level executive assistant coordinator."""

    def __init__(self):
        self.task_mgr = TaskManager()
        self.project_mgr = ProjectManager()
        self.calendar_mgr = CalendarManager()
        self.decision_mgr = DecisionManager()
        self.contact_mgr = ContactManager()
        self.planner = Planner()
        self.inbox_mgr = InboxManager()
        self.quick_capture = QuickCapture()
        self.delegation_mgr = DelegationManager()
        self.focus_mgr = FocusManager()
        self.energy_tracker = EnergyTracker()
        self.habit_tracker = HabitTracker()

    def get_dashboard(self) -> Dict:
        """Executive dashboard summary."""
        overdue = self.task_mgr.get_overdue_tasks()
        today_tasks = self.task_mgr.get_today_tasks()
        today_events = self.calendar_mgr.get_today_events()
        upcoming = self.calendar_mgr.get_upcoming_meetings(4)
        inbox_count = len(self.inbox_mgr.get_inbox())
        habits_today = self.habit_tracker.get_today_habits()
        energy = self.energy_tracker.get_energy_trend(7)
        delegations = self.delegation_mgr.get_delegations("pending")

        return {
            "overdue_tasks": len(overdue),
            "today_tasks": len(today_tasks),
            "today_events": len(today_events),
            "upcoming_meetings": len(upcoming),
            "inbox_count": inbox_count,
            "habits_due": len([h for h in habits_today if not h["completed_today"]]),
            "habits_done": len([h for h in habits_today if h["completed_today"]]),
            "energy_trend": energy.get("trend", "stable"),
            "avg_energy": energy.get("avg_energy", 0),
            "pending_delegations": len(delegations),
            "timestamp": time.time()
        }

    def get_prioritized_tasks(self, limit: int = 10) -> List[Dict]:
        """Get prioritized task list using multiple factors."""
        tasks = self.task_mgr.get_tasks(status="pending")
        
        scored = []
        for t in tasks:
            score = 0
            # Urgency
            if t.get("due_date"):
                days = (t["due_date"] - time.time()) / 86400
                if days < 0:
                    score += 100
                elif days < 1:
                    score += 50
                elif days < 3:
                    score += 25
                elif days < 7:
                    score += 10
            # Priority
            score += (6 - t.get("priority", 3)) * 10
            # Progress (less progress = higher priority)
            score += (100 - t.get("progress", 0)) * 0.1
            # Energy match (prefer tasks matching current energy)
            energy = 5  # Would get from energy tracker
            if t.get("energy_level", 2) == energy:
                score += 5
            scored.append({**t, "priority_score": score})
        
        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored[:limit]

    def suggest_schedule(self, date: str = None) -> Dict:
        """Suggest optimal schedule for a day."""
        if date:
            dt = datetime.strptime(date, "%Y-%m-%d")
        else:
            dt = datetime.now()
        
        tasks = self.task_mgr.get_tasks(status="pending")
        events = self.calendar_mgr.get_events(
            dt.replace(hour=0, minute=0).timestamp(),
            dt.replace(hour=23, minute=59).timestamp()
        )
        
        # Simple scheduling algorithm
        available_hours = 8
        scheduled = []
        remaining = available_hours * 60
        
        # Sort tasks by priority
        pending = [t for t in self.task_mgr.get_tasks(status="pending") if t.get("due_date")]
        pending.sort(key=lambda x: (x.get("due_date", 0), x.get("priority", 3)))
        
        for task in pending:
            if remaining <= 0:
                break
            est_min = int((task.get("estimated_hours", 1) or 1) * 60)
            if est_min <= remaining:
                scheduled.append({
                    "task_id": task["id"],
                    "title": task["title"],
                    "duration_min": est_min,
                    "priority": task["priority"]
                })
                remaining -= est_min
        
        return {
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "available_hours": available_hours,
            "scheduled_tasks": scheduled,
            "buffer_minutes": remaining,
            "events": events
        }

    def morning_briefing(self) -> str:
        """Generate morning briefing text."""
        dash = self.get_dashboard()
        briefing = "Good morning! Here's your briefing for {:%A, %B %d}:\n\n".format(datetime.now())
        
        if dash["overdue_tasks"]:
            briefing += "[WARNING] {} overdue tasks need attention\n".format(dash["overdue_tasks"])
        if dash["today_tasks"]:
            briefing += "[TASKS] {} tasks due today\n".format(dash["today_tasks"])
        if dash["today_events"]:
            briefing += "[EVENTS] {} events scheduled\n".format(dash["today_events"])
        if dash["upcoming_meetings"]:
            briefing += "[MEETINGS] {} meetings in next 4 hours\n".format(dash["upcoming_meetings"])
        if dash["inbox_count"]:
            briefing += "[INBOX] {} items in inbox\n".format(dash["inbox_count"])
        if dash["habits_due"]:
            briefing += "[HABITS] {} habits to complete\n".format(dash["habits_due"])
        
        briefing += "\n[ENERGY] Energy: {} ({:.0f}/10)\n".format(dash["energy_trend"], dash["avg_energy"])
        
        # Top priorities
        priorities = self.get_prioritized_tasks(3)
        if priorities:
            briefing += "\n[PRIORITY] Top priorities:"
            for i, t in enumerate(priorities, 1):
                briefing += "\n  {}. {} (due: {})".format(i, t["title"], datetime.fromtimestamp(t["due_date"]).strftime("%H:%M") if t.get("due_date") else "no due date")
        
        return briefing

    def evening_review(self) -> str:
        """Generate evening review."""
        return "Evening review - to be implemented"


# ===== MODULE EXPORTS =====

task_mgr = TaskManager()
project_mgr = ProjectManager()
calendar_mgr = CalendarManager()
decision_mgr = DecisionManager()
contact_mgr = ContactManager()
planner = Planner()
inbox_mgr = InboxManager()
quick_capture = QuickCapture()
delegation_mgr = DelegationManager()
focus_mgr = FocusManager()
energy_tracker = EnergyTracker()
habit_tracker = HabitTracker()
executive = ExecutiveAssistant()


def ea_debug() -> str:
    conn = get_ea_connection()
    cursor = conn.cursor()
    tables = ["ea_tasks", "ea_projects", "ea_calendar", "ea_meetings",
              "ea_decisions", "ea_contacts", "ea_communications", "ea_plans",
              "ea_habits", "ea_habit_completions", "ea_inbox", "ea_focus_sessions",
              "ea_energy_logs", "ea_delegations", "ea_quick_capture"]
    output = "Executive Assistant Debug:\n"
    for t in tables:
        cursor.execute("SELECT COUNT(*) FROM {}".format(t))
        count = cursor.fetchone()[0]
        output += "  {}: {} records\n".format(t, count)
    conn.close()
    return output


def create_task(title: str, description: str = "", **kwargs) -> str:
    return task_mgr.create_task(title, description, **kwargs)


def get_task(task_id: str) -> Optional[Dict]:
    return task_mgr.get_task(task_id)


def update_task(task_id: str, **kwargs) -> bool:
    return task_mgr.update_task(task_id, **kwargs)


def complete_task(task_id: str) -> bool:
    return task_mgr.complete_task(task_id)


def get_tasks(status: str = None, **kwargs) -> List[Dict]:
    return task_mgr.get_tasks(status, **kwargs)


def get_today_tasks() -> List[Dict]:
    return task_mgr.get_today_tasks()


def get_overdue_tasks() -> List[Dict]:
    return task_mgr.get_overdue_tasks()


def create_project(name: str, description: str = "", **kwargs) -> str:
    return project_mgr.create_project(name, description, **kwargs)


def get_project(proj_id: str) -> Optional[Dict]:
    return project_mgr.get_project(proj_id)


def list_projects(status: str = None) -> List[Dict]:
    return project_mgr.list_projects(status)


def create_event(title: str, start: float, end: float, **kwargs) -> str:
    return calendar_mgr.create_event(title, start, end, **kwargs)


def get_events(start: float, end: float) -> List[Dict]:
    return calendar_mgr.get_events(start, end)


def get_today_events() -> List[Dict]:
    return calendar_mgr.get_today_events()


def get_upcoming_meetings(hours: int = 24) -> List[Dict]:
    return calendar_mgr.get_upcoming_meetings(hours)


def create_decision(title: str, description: str = "", **kwargs) -> str:
    return decision_mgr.create_decision(title, description, **kwargs)


def make_decision(dec_id: str, chosen: str, rationale: str = "") -> bool:
    return decision_mgr.decide(dec_id, chosen, rationale)


def get_decision(dec_id: str) -> Optional[Dict]:
    return decision_mgr.get_decision(dec_id)


def add_contact(name: str, **kwargs) -> str:
    return contact_mgr.add_contact(name, **kwargs)


def get_contact(contact_id: str) -> Optional[Dict]:
    return contact_mgr.get_contact(contact_id)


def create_daily_plan(date: str = None, **kwargs) -> str:
    return planner.create_daily_plan(date, **kwargs)


def capture_inbox(content: str, title: str = "", **kwargs) -> str:
    return inbox_mgr.capture(content, title, **kwargs)


def get_inbox(processed: bool = False) -> List[Dict]:
    return inbox_mgr.get_inbox(processed)


def process_inbox_item(item_id: str, action: str, **kwargs) -> bool:
    return inbox_mgr.process_item(item_id, action, **kwargs)


def capture_quick(content: str, **kwargs) -> str:
    return quick_capture.capture(content, **kwargs)


def delegate_task(task_id: str, delegated_to: str, **kwargs) -> str:
    return delegation_mgr.delegate(task_id, delegated_to, **kwargs)


def get_delegations(status: str = None) -> List[Dict]:
    return delegation_mgr.get_delegations(status)


def start_focus_session(task_id: str = None, duration: int = 25,
                        session_type: str = "pomodoro") -> str:
    return focus_mgr.start_session(task_id, duration, session_type)


def end_focus_session(session_id: str, **kwargs) -> bool:
    return focus_mgr.end_session(session_id, **kwargs)


def log_energy(energy: int, focus: int = None, mood: str = "",
               activity: str = "", notes: str = "") -> str:
    return energy_tracker.log_energy(energy, focus, mood, activity, notes)


def get_energy_trend(days: int = 7) -> Dict:
    return energy_tracker.get_energy_trend(days)


def add_habit(name: str, **kwargs) -> str:
    return habit_tracker.add_habit(name, **kwargs)


def complete_habit(habit_id: str, date: str = None, **kwargs) -> str:
    return habit_tracker.complete_habit(habit_id, date, **kwargs)


def get_habits(active_only: bool = True) -> List[Dict]:
    return habit_tracker.get_habits(active_only)


def get_today_habits() -> List[Dict]:
    return habit_tracker.get_today_habits()


def get_dashboard() -> Dict:
    return executive.get_dashboard()


def get_prioritized_tasks(limit: int = 10) -> List[Dict]:
    return executive.get_prioritized_tasks(limit)


def suggest_schedule(date: str = None) -> Dict:
    return executive.suggest_schedule(date)


def morning_briefing() -> str:
    return executive.morning_briefing()


def evening_review() -> str:
    return executive.evening_review()


if __name__ == "__main__":
    print("Executive Assistant Agent loaded.")
    print("Core: TaskManager, ProjectManager, CalendarManager, DecisionManager")
    print("      ContactManager, Planner, InboxManager, QuickCapture")
    print("      DelegationManager, FocusManager, EnergyTracker, HabitTracker")
    print("      ExecutiveAssistant (orchestrator)")