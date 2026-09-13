"""
Digital Twin Agent - Phase 35 (continued)
Managers and core functionality.
"""

import os
import json
import time
import threading
import random
import statistics
import sqlite3
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path

DB_DIR = "database"
DT_DB = os.path.join(DB_DIR, "digital_twin.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_dt_connection():
    conn = sqlite3.connect(DT_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_dt_db():
    conn = get_dt_connection()
    cursor = conn.cursor()

    # Environment snapshots (periodic full state captures)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS environment_snapshots (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            applications TEXT,          -- JSON: running apps with window states
            files TEXT,                 -- JSON: recently accessed files
            clipboard TEXT,             -- JSON: clipboard content
            system_state TEXT,          -- JSON: CPU, memory, disk, network
            user_activity TEXT,         -- JSON: current activity context
            window_layout TEXT,         -- JSON: window positions/sizes
            active_window TEXT,         -- JSON: focused window info
            virtual_desktops TEXT,      -- JSON: virtual desktop states
            created_at REAL NOT NULL
        )
    """)

    # Activity timeline (continuous activity log)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_timeline (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            activity_type TEXT,         -- app_switch, file_open, file_save, web_visit, command, idle
            source_app TEXT,
            target_app TEXT,
            details TEXT,               -- JSON: specific details
            duration_ms INTEGER,        -- how long the activity lasted
            session_id TEXT,            -- groups related activities
            created_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_timeline(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_type ON activity_timeline(activity_type)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_session ON activity_timeline(session_id)
    """)

    # Session tracking (work sessions, breaks, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_sessions (
            id TEXT PRIMARY KEY,
            session_type TEXT,          -- work, break, meeting, deep_work, admin
            start_time REAL NOT NULL,
            end_time REAL,
            duration_minutes INTEGER,
            focus_score INTEGER,        -- 1-10 self-reported or inferred
            interruptions INTEGER,
            goals TEXT,                 -- JSON array
            outcomes TEXT,              -- JSON array
            tags TEXT,                  -- JSON array
            project_id TEXT,
            created_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_time ON work_sessions(start_time)
    """)

    # Project state (digital representation of project progress)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_states (
            id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            description TEXT,
            status TEXT,                -- planning, active, on_hold, completed, archived
            progress REAL DEFAULT 0,    -- 0-100
            start_date REAL,
            target_date REAL,
            last_activity REAL,
            files TEXT,                 -- JSON: associated files
            tasks TEXT,                 -- JSON: task IDs
            milestones TEXT,            -- JSON: milestone data
            metrics TEXT,               -- JSON: custom metrics
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Device/Peripheral state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_states (
            id TEXT PRIMARY KEY,
            device_type TEXT,           -- monitor, keyboard, mouse, headset, camera, microphone
            device_id TEXT,
            name TEXT,
            status TEXT,                -- connected, disconnected, active, inactive
            properties TEXT,            -- JSON: device-specific properties
            last_seen REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Network/Connectivity state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_state (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            interface TEXT,             -- wifi, ethernet, vpn, bluetooth
            ssid TEXT,
            signal_strength INTEGER,    -- 0-100
            ip_address TEXT,
            latency_ms INTEGER,
            bandwidth_mbps REAL,
            status TEXT,                -- connected, limited, disconnected
            created_at REAL NOT NULL
        )
    """)

    # User preferences/patterns (learned)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_patterns (
            id TEXT PRIMARY KEY,
            pattern_type TEXT,          -- app_usage, time_of_day, workflow, shortcut
            pattern_data TEXT,          -- JSON
            confidence REAL,            -- 0-1
            frequency INTEGER,          -- how often observed
            last_observed REAL,
            is_active BOOLEAN DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Context markers (bookmarks in the digital timeline)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS context_markers (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            label TEXT,
            description TEXT,
            context_type TEXT,          -- milestone, decision, idea, problem, solution
            related_entities TEXT,      -- JSON: task_ids, project_ids, file_paths
            tags TEXT,                  -- JSON array
            importance INTEGER DEFAULT 5, -- 1-10
            created_at REAL NOT NULL
        )
    """)

    # Synchronization state (for multi-device sync)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            id TEXT PRIMARY KEY,
            entity_type TEXT,           -- tasks, habits, notes, settings
            entity_id TEXT,
            operation TEXT,             -- create, update, delete
            payload TEXT,               -- JSON
            timestamp REAL NOT NULL,
            synced BOOLEAN DEFAULT 0,
            device_id TEXT,
            retry_count INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


init_dt_db()

# ============================================================
# SNAPSHOT MANAGER
# ============================================================

class SnapshotManager:
    """Manages periodic environment snapshots."""

    def __init__(self):
        self.capture_interval = 60  # seconds
        self.running = False
        self.worker_thread = None

    def capture_snapshot(self, session_id: str = None) -> str:
        """Capture a full environment snapshot."""
        snapshot_id = f"snap_{int(time.time() * 1000) % 100000000:08d}"
        timestamp = time.time()

        # Get running applications (simplified - would integrate with system_agent)
        applications = self._get_applications()

        # Get recent files
        files = self._get_recent_files()

        # Get clipboard (simplified)
        clipboard = self._get_clipboard()

        # Get system state
        system_state = self._get_system_state()

        # Get window layout (simplified)
        window_layout = self._get_window_layout()

        # Get active window
        active_window = self._get_active_window()

        # Get virtual desktops (simplified)
        virtual_desktops = self._get_virtual_desktops()

        # Determine user activity
        user_activity = self._determine_user_activity()

        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO environment_snapshots (id, timestamp, applications, files, clipboard,
                                              system_state, user_activity, window_layout,
                                              active_window, virtual_desktops, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (snapshot_id, timestamp,
              json.dumps(applications), json.dumps(files),
              json.dumps(clipboard), json.dumps(system_state),
              json.dumps(user_activity), json.dumps(window_layout),
              json.dumps(active_window), json.dumps(virtual_desktops),
              time.time()))
        conn.commit()
        conn.close()

        return snapshot_id

    def _get_applications(self) -> List[Dict]:
        """Get running applications."""
        try:
            import psutil
            apps = []
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cpu_percent', 'memory_info']):
                try:
                    info = proc.info
                    if info['name']:
                        apps.append({
                            "pid": info['pid'],
                            "name": info['name'],
                            "exe": info['exe'],
                            "cpu_percent": info['cpu_percent'] or 0,
                            "memory_mb": (info['memory_info'].rss / 1024 / 1024) if info['memory_info'] else 0
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return apps
        except:
            return []

    def _get_recent_files(self) -> List[Dict]:
        """Get recently accessed files."""
        try:
            from core.search_manager import search_manager
            recent = search_manager.search_recent(limit=20)
            return [{"path": r.get("path", ""), "name": r.get("name", ""), "modified": r.get("modified", 0)} for r in recent]
        except:
            return []

    def _get_clipboard(self) -> Dict:
        """Get clipboard content."""
        try:
            import pyperclip
            content = pyperclip.paste()
            return {"content": content[:500] if content else "", "timestamp": time.time()}
        except:
            return {"content": "", "timestamp": time.time()}

    def _get_system_state(self) -> Dict:
        """Get system resource state."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net = psutil.net_io_counters()
            return {
                "cpu_percent": cpu,
                "memory_percent": mem.percent,
                "memory_available_gb": mem.available / (1024**3),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024**3),
                "network_bytes_sent": net.bytes_sent,
                "network_bytes_recv": net.bytes_recv,
            }
        except:
            return {}

    def _get_window_layout(self) -> List[Dict]:
        """Get window layout."""
        try:
            import pygetwindow as gw
            windows = []
            for w in gw.getAllWindows():
                if w.visible and w.title:
                    windows.append({
                        "title": w.title,
                        "left": w.left, "top": w.top,
                        "width": w.width, "height": w.height,
                        "minimized": w.isMinimized,
                        "maximized": w.isMaximized
                    })
            return windows
        except:
            return []

    def _get_active_window(self) -> Dict:
        """Get active window info."""
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active:
                return {
                    "title": active.title,
                    "left": active.left, "top": active.top,
                    "width": active.width, "height": active.height
                }
        except:
            pass
        return {}

    def _get_virtual_desktops(self) -> List[Dict]:
        """Get virtual desktop info."""
        # Windows 10/11 virtual desktop detection would go here
        # Simplified for now
        return [{"index": 0, "name": "Desktop 1", "active": True}]

    def _determine_user_activity(self) -> str:
        """Determine current user activity level."""
        # Would check idle time, input activity, etc.
        return "active"  # active, idle, away

    def start(self, interval: int = 60):
        """Start periodic snapshot capture."""
        if self.running:
            return
        self.capture_interval = interval
        self.running = True
        self.worker_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

    def _capture_loop(self):
        while self.running:
            try:
                self.capture_snapshot()
            except Exception as e:
                print(f"Snapshot error: {e}")
            time.sleep(self.capture_interval)

    def get_snapshots(self, start: float = None, end: float = None, limit: int = 100) -> List[Dict]:
        """Get snapshots in time range."""
        conn = get_dt_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM environment_snapshots WHERE 1=1"
        params = []
        if start:
            query += " AND timestamp >= ?"
            params.append(start)
        if end:
            query += " AND timestamp <= ?"
            params.append(end)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "timestamp": r[1], "applications": json.loads(r[2]) if r[2] else [],
             "files": json.loads(r[3]) if r[3] else [], "clipboard": json.loads(r[4]) if r[4] else {},
             "system_state": json.loads(r[5]) if r[5] else {}, "user_activity": json.loads(r[6]) if r[6] else {},
             "window_layout": json.loads(r[7]) if r[7] else [], "active_window": json.loads(r[8]) if r[8] else {},
             "virtual_desktops": json.loads(r[9]) if r[9] else []}
            for r in rows
        ]


# ============================================================
# ACTIVITY MANAGER
# ============================================================

class ActivityManager:
    """Manages activity timeline logging."""

    def __init__(self):
        self.current_session_id = None

    def log_activity(self, activity_type: str, source_app: str = "",
                     target_app: str = "", details: Dict = None,
                     duration_ms: int = 0, session_id: str = None) -> str:
        """Log an activity event."""
        activity_id = f"act_{int(time.time() * 1000) % 100000000:08d}"
        session = session_id or self.current_session_id or f"sess_{int(time.time() * 1000) % 100000000:08d}"

        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_timeline (id, timestamp, activity_type, source_app,
                                          target_app, details, duration_ms, session_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (activity_id, time.time(), activity_type, source_app,
              target_app, json.dumps(details or {}), duration_ms, session, time.time()))
        conn.commit()
        conn.close()
        return activity_id

    def log_app_switch(self, from_app: str, to_app: str) -> str:
        """Log application switch."""
        return self.log_activity("app_switch", from_app, to_app,
                                 {"from": from_app, "to": to_app})

    def log_file_open(self, file_path: str, app: str) -> str:
        """Log file open."""
        return self.log_activity("file_open", app, "",
                                 {"file": file_path})

    def log_file_save(self, file_path: str, app: str) -> str:
        """Log file save."""
        return self.log_activity("file_save", app, "",
                                 {"file": file_path})

    def log_web_visit(self, url: str, browser: str) -> str:
        """Log web visit."""
        return self.log_activity("web_visit", browser, "",
                                 {"url": url})

    def log_command(self, command: str, terminal: str) -> str:
        """Log command execution."""
        return self.log_activity("command", terminal, "",
                                 {"command": command[:200]})

    def log_idle(self, duration_ms: int) -> str:
        """Log idle period."""
        return self.log_activity("idle", "", "",
                                 {"duration_ms": duration_ms}, duration_ms)

    def set_session(self, session_id: str = None):
        """Set current session."""
        self.current_session_id = session_id or f"sess_{int(time.time() * 1000) % 100000000:08d}"
        return self.current_session_id

    def get_activities(self, start: float = None, end: float = None,
                       activity_type: str = None, limit: int = 1000) -> List[Dict]:
        """Query activities."""
        conn = get_dt_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM activity_timeline WHERE 1=1"
        params = []
        if start:
            query += " AND timestamp >= ?"
            params.append(start)
        if end:
            query += " AND timestamp <= ?"
            params.append(end)
        if activity_type:
            query += " AND activity_type = ?"
            params.append(activity_type)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "timestamp": r[1], "activity_type": r[2],
             "source_app": r[3], "target_app": r[4],
             "details": json.loads(r[5]) if r[5] else {},
             "duration_ms": r[6], "session_id": r[7]}
            for r in rows
        ]

    def get_session_activities(self, session_id: str) -> List[Dict]:
        """Get all activities in a session."""
        return self.get_activities(session_id=session_id)


# ============================================================
# SESSION MANAGER
# ============================================================

class SessionManager:
    """Manages work sessions."""

    def __init__(self):
        pass

    def start_session(self, session_type: str = "work",
                      goals: List[str] = None,
                      project_id: str = None) -> str:
        """Start a work session."""
        session_id = f"sess_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO work_sessions (id, session_type, start_time,
                                      goals, project_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, session_type, time.time(),
              json.dumps(goals or []), project_id, time.time()))
        conn.commit()
        conn.close()
        return session_id

    def end_session(self, session_id: str,
                    outcomes: List[str] = None,
                    focus_score: int = None,
                    interruptions: int = 0) -> bool:
        """End a work session."""
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE work_sessions SET end_time = ?, duration_minutes = ?,
                                    outcomes = ?, focus_score = ?, interruptions = ?
            WHERE id = ?
        """, (time.time(), 0, json.dumps(outcomes or []), focus_score, interruptions, session_id))
        # Calculate duration
        cursor.execute("SELECT start_time FROM work_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            duration = int((time.time() - row[0]) / 60)
            cursor.execute("UPDATE work_sessions SET duration_minutes = ? WHERE id = ?", (duration, session_id))
        conn.commit()
        conn.close()
        return True

    def get_session(self, session_id: str) -> Optional[Dict]:
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM work_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "session_type": row[1], "start_time": row[1],
                "end_time": row[2], "duration_minutes": row[3],
                "focus_score": row[4], "interruptions": row[5],
                "goals": json.loads(row[6]) if row[6] else [],
                "outcomes": json.loads(row[7]) if row[7] else [],
                "tags": json.loads(row[8]) if row[8] else [],
                "project_id": row[9]
            }
        return None

    def get_sessions(self, days: int = 30) -> List[Dict]:
        conn = get_dt_connection()
        cursor = conn.cursor()
        start = time.time() - days * 86400
        cursor.execute("SELECT * FROM work_sessions WHERE start_time > ? ORDER BY start_time DESC", (start,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "type": r[1], "start": r[2], "end": r[3],
             "duration": r[3], "focus": r[4], "interruptions": r[5]}
            for r in rows
        ]


# ============================================================
# PROJECT STATE MANAGER
# ============================================================

class ProjectStateManager:
    """Manages digital project states."""

    def __init__(self):
        pass

    def create_project(self, name: str, description: str = "", **kwargs) -> str:
        proj_id = f"proj_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO project_states (id, project_name, description, status,
                                       progress, start_date, target_date,
                                       files, tasks, milestones, metrics,
                                       created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (proj_id, name, description, kwargs.get("status", "planning"),
              0.0, kwargs.get("start_date"), kwargs.get("target_date"),
              json.dumps(kwargs.get("files", [])), json.dumps(kwargs.get("tasks", [])),
              json.dumps(kwargs.get("milestones", [])), json.dumps(kwargs.get("metrics", {})),
              time.time(), time.time()))
        conn.commit()
        conn.close()
        return proj_id

    def update_progress(self, project_id: str, progress: float) -> bool:
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE project_states SET progress = ?, updated_at = ?, last_activity = ? WHERE id = ?",
                      (progress, time.time(), time.time(), project_id))
        conn.commit()
        conn.close()
        return True

    def get_project(self, project_id: str) -> Optional[Dict]:
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM project_states WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "status": row[3], "progress": row[4], "start_date": row[5],
                "target_date": row[6], "last_activity": row[7],
                "files": json.loads(row[8]) if row[8] else [],
                "tasks": json.loads(row[9]) if row[9] else [],
                "milestones": json.loads(row[10]) if row[10] else [],
                "metrics": json.loads(row[11]) if row[11] else {}
            }
        return None

    def list_projects(self) -> List[Dict]:
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM project_states ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "status": r[3], "progress": r[4]}
            for r in rows
        ]


# ============================================================
# PATTERN RECOGNIZER
# ============================================================

class PatternRecognizer:
    """Recognizes user behavior patterns."""

    def __init__(self):
        pass

    def analyze_app_usage(self, days: int = 30) -> Dict:
        """Analyze application usage patterns."""
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, applications FROM environment_snapshots
            WHERE timestamp > ? ORDER BY timestamp
        """, (time.time() - days * 86400,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {}

        app_usage = defaultdict(int)
        app_transitions = defaultdict(int)
        prev_app = None

        for row in rows:
            apps = json.loads(row[1]) if row[1] else []
            current_apps = [a["name"] for a in apps if a.get("name")]

            for app in current_apps:
                app_usage[app] += 1

            if prev_app and current_apps:
                for app in current_apps:
                    if app != prev_app:
                        app_transitions[f"{prev_app}->{app}"] += 1

            if current_apps:
                prev_app = current_apps[0]  # Assume first is active

        return {
            "app_usage": dict(app_usage),
            "transitions": dict(app_transitions),
            "total_snapshots": len(rows)
        }

    def detect_workflows(self, days: int = 7) -> List[Dict]:
        """Detect recurring workflows."""
        patterns = self.analyze_app_usage(days)
        transitions = patterns.get("transitions", {})

        workflows = []
        for transition, count in transitions.items():
            if count >= 3:  # At least 3 occurrences
                workflows.append({
                    "transition": transition,
                    "count": count,
                    "description": f"User switches {transition} {count} times"
                })

        return sorted(workflows, key=lambda x: x["count"], reverse=True)

    def detect_productive_hours(self, days: int = 30) -> Dict:
        """Find most productive hours."""
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, applications FROM environment_snapshots
            WHERE timestamp > ? ORDER BY timestamp
        """, (time.time() - days * 86400,))
        rows = cursor.fetchall()
        conn.close()

        hour_activity = defaultdict(int)
        for row in rows:
            dt = datetime.fromtimestamp(row[0])
            hour = dt.hour
            apps = json.loads(row[1]) if row[1] else []
            # Count as active if any "work" apps running
            work_apps = ["code", "visual studio", "pycharm", "terminal", "cmd", "powershell",
                        "chrome", "firefox", "edge", "word", "excel", "ppt"]
            for app in json.loads(row[1]) if row[1] else []:
                if any(w in app.get("name", "").lower() for w in work_apps):
                    hour_activity[hour] += 1
                    break

        total = sum(hour_activity.values())
        if total == 0:
            return {}

        return {h: round(c / total * 100, 1) for h, c in sorted(hour_activity.items())}


# ============================================================
# CONTEXT MARKER MANAGER
# ============================================================

class ContextMarkerManager:
    """Manages context markers (bookmarks in timeline)."""

    def __init__(self):
        pass

    def add_marker(self, label: str, description: str = "",
                   context_type: str = "milestone",
                   related_entities: List[str] = None,
                   tags: List[str] = None, importance: int = 5) -> str:
        marker_id = f"ctx_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO context_markers (id, timestamp, label, description,
                                        context_type, related_entities, tags, importance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (marker_id, time.time(), label, description,
              context_type, json.dumps(related_entities or []),
              json.dumps(tags or []), importance, time.time()))
        conn.commit()
        conn.close()
        return marker_id

    def get_markers(self, context_type: str = None, limit: int = 50) -> List[Dict]:
        conn = get_dt_connection()
        cursor = conn.cursor()
        if context_type:
            cursor.execute("SELECT * FROM context_markers WHERE context_type = ? ORDER BY timestamp DESC LIMIT ?",
                          (context_type, limit))
        else:
            cursor.execute("SELECT * FROM context_markers ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "timestamp": r[1], "label": r[2], "description": r[3],
             "context_type": r[4], "related_entities": json.loads(r[5]) if r[5] else [],
             "tags": json.loads(r[6]) if r[6] else [], "importance": r[7]}
            for r in rows
        ]


# ============================================================
# SYNC MANAGER
# ============================================================

class SyncManager:
    """Manages synchronization state for multi-device."""

    def __init__(self):
        pass

    def queue_sync(self, entity_type: str, entity_id: str,
                   operation: str, payload: Dict) -> str:
        sync_id = f"sync_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sync_state (id, entity_type, entity_id, operation,
                                   payload, timestamp, device_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sync_id, entity_type, entity_id, operation,
              json.dumps(payload), time.time(), self._get_device_id()))
        conn.commit()
        conn.close()
        return sync_id

    def _get_device_id(self) -> str:
        import socket
        return socket.gethostname()

    def get_pending_syncs(self, limit: int = 100) -> List[Dict]:
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sync_state WHERE synced = 0 ORDER BY timestamp LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "entity_type": r[1], "entity_id": r[2],
             "operation": r[3], "payload": json.loads(r[4]) if r[4] else {}}
            for r in rows
        ]

    def mark_synced(self, sync_id: str):
        conn = get_dt_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE sync_state SET synced = 1 WHERE id = ?", (sync_id,))
        conn.commit()
        conn.close()


# ============================================================
# DIGITAL TWIN ENGINE (Orchestrator)
# ============================================================

class DigitalTwinEngine:
    """Main orchestrator for Digital Twin."""

    def __init__(self):
        self.snapshots = SnapshotManager()
        self.activities = ActivityManager()
        self.sessions = SessionManager()
        self.projects = ProjectStateManager()
        self.patterns = PatternRecognizer()
        self.markers = ContextMarkerManager()
        self.sync = SyncManager()

    def get_dashboard(self) -> Dict:
        """Get digital twin dashboard."""
        return {
            "snapshots_today": len(self.snapshots.get_snapshots(
                start=datetime.now().replace(hour=0).timestamp())),
            "activities_today": len(self.activities.get_activities(
                start=datetime.now().replace(hour=0).timestamp())),
            "active_session": self.sessions.get_session(
                self.activities.current_session_id) if hasattr(self.activities, 'current_session_id') else None,
            "projects": len(self.projects.list_projects()),
            "patterns": len(self.patterns.detect_workflows()),
            "markers": len(self.markers.get_markers()),
            "pending_syncs": len(self.sync.get_pending_syncs()),
        }

    def reconstruct_workspace(self, timestamp: float = None) -> Dict:
        """Reconstruct workspace state at a given time."""
        ts = timestamp or time.time()
        snapshots = self.snapshots.get_snapshots(end=ts, limit=1)
        if not snapshots:
            return {}
        snap = snapshots[0]
        return {
            "timestamp": snap["timestamp"],
            "applications": snap["applications"],
            "active_window": snap["active_window"],
            "window_layout": snap["window_layout"],
            "system_state": snap["system_state"],
            "virtual_desktops": snap["virtual_desktops"]
        }

    def get_timeline(self, hours: int = 24) -> List[Dict]:
        """Get activity timeline."""
        start = time.time() - hours * 3600
        return self.activities.get_activities(start=start)

    def create_context_marker(self, label: str, description: str = '', **kwargs) -> str:
        return self.markers.add_marker(label, description, **kwargs)

    def get_productivity_report(self, days: int = 7) -> Dict:
        """Generate productivity report."""
        patterns = self.patterns.detect_workflows(7)
        productive_hours = self.patterns.detect_productive_hours(30)
        sessions = self.sessions.get_sessions(7)

        total_focus = sum(s.get("duration_minutes", 0) for s in sessions
                         if s.get("session_type") == "work" or s.get("session_type") == "deep_work")
        total_time = sum(s.get("duration_minutes", 0) for s in sessions)

        return {
            "period_days": 7,
            "total_sessions": len(sessions),
            "total_focus_minutes": total_focus,
            "total_time_minutes": total_time,
            "focus_ratio": round(total_focus / total_time * 100, 1) if total_time > 0 else 0,
            "workflows": patterns[:5],
            "productive_hours": productive_hours,
            "sessions_by_type": self._group_sessions_by_type(sessions)
        }

    def _group_sessions_by_type(self, sessions: List[Dict]) -> Dict:
        grouped = defaultdict(int)
        for s in sessions:
            grouped[s.get("session_type", "unknown")] += 1
        return dict(grouped)


# ============================================================
# MODULE EXPORTS
# ============================================================

snapshots = SnapshotManager()
activities = ActivityManager()
sessions = SessionManager()
projects = ProjectStateManager()
patterns = PatternRecognizer()
markers = ContextMarkerManager()
sync_mgr = SyncManager()
digital_twin = DigitalTwinEngine()


def dt_debug() -> str:
    conn = get_dt_connection()
    cursor = conn.cursor()
    tables = ["environment_snapshots", "activity_timeline", "work_sessions",
              "project_states", "device_states", "network_state",
              "user_patterns", "context_markers", "sync_state"]
    output = "Digital Twin Debug:\n"
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        output += f"  {t}: {count} records\n"
    conn.close()
    return output


def capture_snapshot(session_id: str = None) -> str:
    return snapshots.capture_snapshot(session_id)


def log_activity(activity_type: str, source_app: str = "",
                 target_app: str = "", details: Dict = None,
                 duration_ms: int = 0, session_id: str = None) -> str:
    return activities.log_activity(activity_type, source_app, target_app,
                                    details, duration_ms, session_id)


def start_session(session_type: str = "work", goals: List[str] = None,
                  project_id: str = None) -> str:
    return sessions.start_session(session_type, goals, project_id)


def end_session(session_id: str, outcomes: List[str] = None,
                focus_score: int = None, interruptions: int = 0) -> bool:
    return sessions.end_session(session_id, outcomes, focus_score, interruptions)


def get_activities(start: float = None, end: float = None,
                   activity_type: str = None, limit: int = 100) -> List[Dict]:
    return activities.get_activities(start, end, activity_type, limit)


def get_sessions(days: int = 30) -> List[Dict]:
    return sessions.get_sessions(days)


def create_project_state(name: str, description: str = "", **kwargs) -> str:
    return projects.create_project(name, description, **kwargs)


def get_project_state(project_id: str) -> Optional[Dict]:
    return projects.get_project(project_id)


def list_project_states() -> List[Dict]:
    return projects.list_projects()


def create_context_marker(label: str, description: str = '', **kwargs) -> str:
    return markers.add_marker(label, description, **kwargs)


def get_context_markers(context_type: str = None, limit: int = 50) -> List[Dict]:
    return markers.get_markers(context_type, limit)


def queue_sync(entity_type: str, entity_id: str,
               operation: str, payload: Dict) -> str:
    return sync_mgr.queue_sync(entity_type, entity_id, operation, payload)


def get_pending_syncs(limit: int = 100) -> List[Dict]:
    return sync_mgr.get_pending_syncs(limit)


def get_dashboard() -> Dict:
    return digital_twin.get_dashboard()


def reconstruct_workspace(timestamp: float = None) -> Dict:
    return digital_twin.reconstruct_workspace(timestamp)


def get_timeline(hours: int = 24) -> List[Dict]:
    return digital_twin.get_timeline(hours)


def get_productivity_report(days: int = 7) -> Dict:
    return digital_twin.get_productivity_report(days)


def get_workflow_patterns(days: int = 7) -> List[Dict]:
    return patterns.detect_workflows(days)


def get_productive_hours(days: int = 30) -> Dict:
    return patterns.detect_productive_hours(days)


if __name__ == "__main__":
    print("Digital Twin Agent loaded.")
    print("Core: SnapshotManager, ActivityManager, SessionManager")
    print("      ProjectStateManager, PatternRecognizer, ContextMarkerManager")
    print("      SyncManager, DigitalTwinEngine")