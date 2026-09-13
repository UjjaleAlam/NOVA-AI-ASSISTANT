with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Prepend all the necessary imports and initialization code
imports = '''import os
import json
import time
import math
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
'''

# Find the first class definition
idx = content.find('class TaskManager:')
if idx != -1:
    new_content = imports + content[idx:]
    with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Added imports and init_ea_db')
else:
    print('Could not find TaskManager class')