"""
Continuous Awareness Agent - Phase 29
Continuous monitoring, background awareness, proactive intelligence.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import threading
import hashlib
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from collections import defaultdict, deque, Counter
from enum import Enum
from pathlib import Path
import psutil

from core.context_engine import get_connection
from core.system_agent import system_agent
from core.personal_context import personal_context

DB_DIR = "database"
CA_DB = os.path.join(DB_DIR, "continuous_awareness.db")
SNAPSHOT_DIR = os.path.join(DB_DIR, "awareness_snapshots")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def get_ca_connection():
    import sqlite3
    conn = sqlite3.connect(CA_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_ca_db():
    conn = get_ca_connection()
    cursor = conn.cursor()

    # Context snapshots (metadata only - full data stored in JSON files)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS context_snapshots (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            active_window TEXT,
            active_app TEXT,
            user_presence TEXT,    -- 'active', 'idle', 'away', 'sleep'
            session_id TEXT,
            snapshot_file TEXT,    -- path to JSON file with full snapshot data
            file_size_bytes INTEGER,
            created_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshots_session_time
        ON context_snapshots(session_id, timestamp)
    """)

    # User activity events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,  -- 'keystroke', 'mouse_click', 'window_switch', 'app_launch', 'file_open'
            timestamp REAL NOT NULL,
            details TEXT,              -- JSON: key, window, app, path, etc.
            session_id TEXT,
            created_at REAL NOT NULL
        )
    """)

    # Idle/active periods
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presence_periods (
            id TEXT PRIMARY KEY,
            start_time REAL NOT NULL,
            end_time REAL,
            period_type TEXT NOT NULL,  -- 'active', 'idle', 'away', 'sleep'
            duration_seconds REAL,
            trigger TEXT,               -- what caused the transition
            session_id TEXT,
            created_at REAL NOT NULL
        )
    """)

    # Proactive suggestions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proactive_suggestions (
            id TEXT PRIMARY KEY,
            suggestion_type TEXT NOT NULL,  -- 'break', 'task_switch', 'automation', 'info', 'health'
            title TEXT NOT NULL,
            description TEXT,
            priority INTEGER DEFAULT 3,    -- 1=high, 2=medium, 3=low
            context TEXT,                  -- JSON: what triggered this
            status TEXT DEFAULT 'pending', -- 'pending', 'shown', 'accepted', 'dismissed', 'expired'
            shown_at REAL,
            responded_at REAL,
            expires_at REAL,
            created_at REAL NOT NULL
        )
    """)

    # Pattern recognitions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recognized_patterns (
            id TEXT PRIMARY KEY,
            pattern_type TEXT NOT NULL,   -- 'daily_routine', 'app_sequence', 'work_hours', 'break_pattern'
            description TEXT,
            confidence REAL,
            frequency INTEGER,
            last_seen REAL,
            pattern_data TEXT,            -- JSON
            is_active BOOLEAN DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Anomaly detections
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id TEXT PRIMARY KEY,
            anomaly_type TEXT NOT NULL,   -- 'resource_spike', 'unusual_app', 'time_anomaly', 'pattern_break'
            severity TEXT,                -- 'low', 'medium', 'high', 'critical'
            description TEXT,
            details TEXT,                 -- JSON
            acknowledged BOOLEAN DEFAULT 0,
            created_at REAL NOT NULL
        )
    """)

    # User goals/intentions (inferred)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inferred_goals (
            id TEXT PRIMARY KEY,
            goal_description TEXT NOT NULL,
            confidence REAL,
            evidence TEXT,                -- JSON: supporting observations
            status TEXT DEFAULT 'active', -- 'active', 'completed', 'abandoned', 'superseded'
            started_at REAL,
            completed_at REAL,
            related_tasks TEXT,           -- JSON array of task IDs
            created_at REAL NOT NULL
        )
    """)

    # Contextual insights
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insights (
            id TEXT PRIMARY KEY,
            insight_type TEXT NOT NULL,   -- 'productivity', 'health', 'workflow', 'resource', 'security'
            title TEXT NOT NULL,
            description TEXT,
            actionable BOOLEAN DEFAULT 1,
            suggested_actions TEXT,       -- JSON array
            confidence REAL,
            source_data TEXT,             -- JSON
            status TEXT DEFAULT 'new',    -- 'new', 'viewed', 'acted_on', 'dismissed'
            created_at REAL NOT NULL
        )
    """)

    # Awareness sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS awareness_sessions (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            started_at REAL NOT NULL,
            ended_at REAL,
            total_active_time REAL,
            total_idle_time REAL,
            window_switches INTEGER,
            apps_used TEXT,               -- JSON array
            files_accessed TEXT,          -- JSON array
            suggestions_generated INTEGER,
            suggestions_accepted INTEGER,
            insights_generated INTEGER,
            anomalies_detected INTEGER,
            created_at REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_ca_db()


class ActivityMonitor:
    """Monitors user activity (keystrokes, mouse, window focus)."""

    def __init__(self):
        self.running = False
        self.worker_thread = None
        self.last_activity = time.time()
        self.idle_threshold = 60  # seconds
        self.current_session_id = None
        self.presence_period_id = None
        self.is_idle = False
        self.last_window = None
        self.window_switch_count = 0

    def start(self, session_id: str = None):
        if self.running:
            return
        self.current_session_id = session_id or f"sess_{int(time.time() * 1000) % 100000000:08d}"
        self.running = True
        self.worker_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.worker_thread.start()
        self._start_presence_period('active', 'session_start')

    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        if self.presence_period_id:
            self._end_presence_period()

    def _monitor_loop(self):
        while self.running:
            try:
                self._check_activity()
                self._check_window_focus()
                self._capture_context_snapshot()
            except Exception as e:
                print(f"Activity monitor error: {e}")
            time.sleep(5)  # Check every 5 seconds

    def _check_activity(self):
        # Check for recent activity via system metrics
        # In a full implementation, would hook into OS events
        # For now, use system agent's process info as proxy
        try:
            # Simple heuristic: if any process has high CPU, user might be active
            high_procs = system_agent.process_manager.get_high_resource_processes(10.0, 10.0)
            if high_procs:
                self._record_activity()
        except:
            pass

    def _check_window_focus(self):
        # Would use pygetwindow or similar to detect active window
        # Placeholder for window tracking
        pass

    def _record_activity(self):
        now = time.time()
        if now - self.last_activity > self.idle_threshold:
            # Transition from idle to active
            self._end_presence_period()
            self._start_presence_period('active', 'activity_detected')
        self.last_activity = now

    def _start_presence_period(self, period_type: str, trigger: str):
        period_id = f"pres_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO presence_periods (id, start_time, period_type, trigger, session_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (period_id, time.time(), period_type, trigger, self.current_session_id, time.time()))
        conn.commit()
        conn.close()
        self.presence_period_id = period_id
        self.is_idle = (period_type == 'idle')

    def _end_presence_period(self):
        if self.presence_period_id:
            end_time = time.time()
            conn = get_ca_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE presence_periods SET end_time = ?, duration_seconds = ?
                WHERE id = ?
            """, (end_time, end_time - time.time(), self.presence_period_id))
            conn.commit()
            conn.close()
            self.presence_period_id = None

    def _capture_context_snapshot(self):
        snapshot_id = f"ctx_{int(time.time() * 1000) % 100000000:08d}"
        timestamp = time.time()
        
        # Get system state
        sys_status = system_agent.get_system_status()
        snapshot = sys_status.get('snapshot', {})
        
        # Determine user presence
        idle_time = time.time() - self.last_activity
        if idle_time > 300:
            presence = 'away'
        elif idle_time > self.idle_threshold:
            presence = 'idle'
        else:
            presence = 'active'
        
        # Build full snapshot data
        full_snapshot = {
            "id": snapshot_id,
            "timestamp": timestamp,
            "active_window": "",
            "active_app": "",
            "screen_activity": {},
            "system_state": snapshot,
            "user_presence": presence,
            "session_id": self.current_session_id,
            "metadata": {}
        }
        
        # Save to JSON file
        snapshot_file = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.json")
        with open(snapshot_file, 'w') as f:
            json.dump(full_snapshot, f, separators=(',', ':'))
        file_size = os.path.getsize(snapshot_file)
        
        # Save metadata to database
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO context_snapshots (id, timestamp, active_window, active_app,
                                          user_presence, session_id, snapshot_file,
                                          file_size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (snapshot_id, timestamp, "", "", presence, self.current_session_id,
              snapshot_file, file_size, time.time()))
        conn.commit()
        conn.close()

    def get_snapshot_data(self, snapshot_id: str) -> Optional[Dict]:
        """Load full snapshot data from JSON file."""
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT snapshot_file FROM context_snapshots WHERE id = ?", (snapshot_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] and os.path.exists(row[0]):
            with open(row[0], 'r') as f:
                return json.load(f)
        return None

    def get_session_stats(self) -> Dict:
        return {
            "session_id": self.current_session_id,
            "idle_time": time.time() - self.last_activity,
            "is_idle": self.is_idle,
            "window_switches": self.window_switch_count
        }


class PatternRecognizer:
    """Recognizes patterns in user behavior."""

    def __init__(self):
        self.pattern_cache = {}

    def analyze_activity_patterns(self, hours: int = 24) -> List[Dict]:
        """Analyze recent activity for patterns."""
        conn = get_ca_connection()
        cursor = conn.cursor()
        
        cutoff = time.time() - (hours * 3600)
        cursor.execute("""
            SELECT * FROM activity_events 
            WHERE timestamp > ? ORDER BY timestamp
        """, (cutoff,))
        events = cursor.fetchall()
        conn.close()

        if not events:
            return []

        patterns = []

        # App usage sequence pattern
        app_sequence = [e[3] for e in events if e[2] == 'app_launch']  # details.app
        if len(app_sequence) > 3:
            seq_pattern = self._find_repeating_sequences(app_sequence)
            if seq_pattern:
                patterns.append({
                    "type": "app_sequence",
                    "description": f"Repeated app sequence: {' -> '.join(seq_pattern[:3])}",
                    "confidence": 0.8,
                    "frequency": len(app_sequence),
                    "data": {"sequence": seq_pattern}
                })

        # Time-based patterns (hourly activity)
        hourly_activity = defaultdict(int)
        for e in events:
            hour = datetime.fromtimestamp(e[4]).hour  # timestamp
            hourly_activity[hour] += 1

        peak_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)[:3]
        if peak_hours:
            patterns.append({
                "type": "work_hours",
                "description": f"Most active hours: {', '.join(f'{h}:00' for h, _ in peak_hours)}",
                "confidence": 0.9,
                "frequency": sum(hourly_activity.values()),
                "data": {"hourly_distribution": dict(hourly_activity)}
            })

        # Idle patterns
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM presence_periods 
            WHERE start_time > ? AND period_type = 'idle' ORDER BY start_time
        """, (cutoff,))
        idle_periods = cursor.fetchall()
        conn.close()

        if idle_periods:
            idle_hours = defaultdict(int)
            for p in idle_periods:
                hour = datetime.fromtimestamp(p[1]).hour
                idle_hours[hour] += 1
            
            if idle_hours:
                patterns.append({
                    "type": "break_pattern",
                    "description": f"Regular breaks at hours: {', '.join(f'{h}:00' for h in sorted(idle_hours.keys())[:3])}",
                    "confidence": 0.7,
                    "frequency": len(idle_periods),
                    "data": {"idle_by_hour": dict(idle_hours)}
                })

        return patterns

    def _find_repeating_sequences(self, sequence: List[str], min_length: int = 3) -> List[str]:
        """Find repeating subsequences."""
        if len(sequence) < min_length * 2:
            return []

        # Simple n-gram frequency
        ngrams = defaultdict(int)
        for i in range(len(sequence) - min_length + 1):
            ngram = tuple(sequence[i:i+min_length])
            ngrams[ngram] += 1

        # Return most frequent
        sorted_ngrams = sorted(ngrams.items(), key=lambda x: x[1], reverse=True)
        if sorted_ngrams and sorted_ngrams[0][1] >= 2:
            return list(sorted_ngrams[0][0])
        return []

    def store_pattern(self, pattern_type: str, description: str, confidence: float,
                      frequency: int, pattern_data: Dict) -> str:
        pattern_id = f"pat_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recognized_patterns (id, pattern_type, description, confidence,
                                            frequency, last_seen, pattern_data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pattern_id, pattern_type, description, confidence, frequency,
              time.time(), json.dumps(pattern_data), time.time(), time.time()))
        conn.commit()
        conn.close()
        return pattern_id

    def get_patterns(self, pattern_type: str = None, active_only: bool = True) -> List[Dict]:
        conn = get_ca_connection()
        cursor = conn.cursor()
        if pattern_type:
            cursor.execute("SELECT * FROM recognized_patterns WHERE pattern_type = ? AND is_active = ? ORDER BY confidence DESC",
                          (pattern_type, active_only))
        else:
            cursor.execute("SELECT * FROM recognized_patterns WHERE is_active = ? ORDER BY confidence DESC", (active_only,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "pattern_type": r[1], "description": r[2], "confidence": r[3],
             "frequency": r[4], "last_seen": r[5], "pattern_data": json.loads(r[6]) if r[6] else {}}
            for r in rows
        ]


class AnomalyDetector:
    """Detects anomalies in system and user behavior."""

    def __init__(self):
        self.baselines = {}
        self.update_interval = 3600  # 1 hour
        self.last_update = 0

    def check_system_anomalies(self) -> List[Dict]:
        anomalies = []
        snapshot = system_agent.monitor.get_current_snapshot()
        if not snapshot:
            return anomalies

        cpu = snapshot.get('cpu_percent', 0)
        memory = snapshot.get('memory_percent', 0)
        disk = snapshot.get('disk_percent', 0)

        # Resource spike detection
        if cpu > 90:
            anomalies.append(self._create_anomaly('resource_spike', 'high',
                f"CPU usage critical: {cpu:.1f}%", {"metric": "cpu", "value": cpu}))
        elif cpu > 80:
            anomalies.append(self._create_anomaly('resource_spike', 'medium',
                f"CPU usage high: {cpu:.1f}%", {"metric": "cpu", "value": cpu}))

        if memory > 90:
            anomalies.append(self._create_anomaly('resource_spike', 'high',
                f"Memory usage critical: {memory:.1f}%", {"metric": "memory", "value": memory}))
        elif memory > 85:
            anomalies.append(self._create_anomaly('resource_spike', 'medium',
                f"Memory usage high: {memory:.1f}%", {"metric": "memory", "value": memory}))

        if disk > 95:
            anomalies.append(self._create_anomaly('resource_spike', 'critical',
                f"Disk space critical: {disk:.1f}%", {"metric": "disk", "value": disk}))
        elif disk > 90:
            anomalies.append(self._create_anomaly('resource_spike', 'high',
                f"Disk space low: {disk:.1f}%", {"metric": "disk", "value": disk}))

        # Process anomalies
        high_procs = system_agent.process_manager.get_high_resource_processes(80.0, 80.0)
        for proc in high_procs:
            anomalies.append(self._create_anomaly('resource_spike', 'medium',
                f"Process {proc.get('name')} using high resources",
                {"pid": proc.get('pid'), "cpu": proc.get('cpu_percent'), "mem": proc.get('memory_percent')}))

        return anomalies

    def check_behavioral_anomalies(self, hours: int = 24) -> List[Dict]:
        """Check for behavioral anomalies."""
        anomalies = []

        # Get recent activity
        conn = get_ca_connection()
        cursor = conn.cursor()
        cutoff = time.time() - (hours * 3600)
        cursor.execute("""
            SELECT * FROM activity_events WHERE timestamp > ? ORDER BY timestamp
        """, (cutoff,))
        events = cursor.fetchall()
        conn.close()

        if not events:
            return anomalies

        # Check for unusual app usage
        app_counts = Counter(e[3] for e in events if e[2] == 'app_launch' and e[3])
        if app_counts:
            # Get historical baseline
            baseline = self._get_app_baseline()
            for app, count in app_counts.items():
                expected = baseline.get(app, 0)
                if expected > 0 and count > expected * 3:  # 3x normal
                    anomalies.append(self._create_anomaly('unusual_app', 'medium',
                        f"Unusual activity in {app}: {count}x normal",
                        {"app": app, "count": count, "baseline": expected}))

        # Time-based anomalies (activity at unusual hours)
        hour_counts = defaultdict(int)
        for e in events:
            hour = datetime.fromtimestamp(e[2]).hour  # e[2] is timestamp
            hour_counts[hour] += 1

        # Check against typical work hours
        typical_hours = set(range(9, 18))  # 9am-5pm
        for hour, count in hour_counts.items():
            if hour not in typical_hours and count > 10:  # Significant off-hours activity
                anomalies.append(self._create_anomaly('time_anomaly', 'low',
                    f"Unusual activity at {hour}:00 ({count} events)",
                    {"hour": hour, "event_count": count}))

        return anomalies

    def _get_app_baseline(self) -> Dict[str, float]:
        """Get historical app usage baseline."""
        conn = get_ca_connection()
        cursor = conn.cursor()
        # Last 7 days
        cutoff = time.time() - (7 * 86400)
        cursor.execute("""
            SELECT json_extract(details, '$.app') as app, COUNT(*) as cnt
            FROM activity_events 
            WHERE timestamp > ? AND event_type = 'app_launch'
            GROUP BY app
        """, (cutoff,))
        rows = cursor.fetchall()
        conn.close()
        return {r[0]: r[1] / 7 for r in rows if r[0]}  # Daily average

    def _create_anomaly(self, anomaly_type: str, severity: str, description: str, details: Dict) -> Dict:
        anomaly_id = f"anom_{int(time.time() * 1000000) % 100000000:08d}_{os.urandom(4).hex()}"
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO anomalies (id, anomaly_type, severity, description, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (anomaly_id, anomaly_type, severity, description, json.dumps(details), time.time()))
        conn.commit()
        conn.close()
        return {"id": anomaly_id, "type": anomaly_type, "severity": severity,
                "description": description, "details": details, "created_at": time.time()}


class ProactiveSuggestionEngine:
    """Generates proactive suggestions based on context."""

    def __init__(self):
        self.suggestion_cooldowns = defaultdict(float)
        self.min_cooldown = 1800  # 30 minutes between similar suggestions

    def generate_suggestions(self, context: Dict = None) -> List[Dict]:
        suggestions = []
        now = time.time()

        # Health/break suggestions
        suggestions.extend(self._health_suggestions(now))

        # Productivity suggestions
        suggestions.extend(self._productivity_suggestions(now))

        # Resource suggestions
        suggestions.extend(self._resource_suggestions(now))

        # Automation suggestions
        suggestions.extend(self._automation_suggestions(now))

        # Filter by cooldown
        filtered = []
        for s in suggestions:
            key = f"{s['type']}:{s['title'][:30]}"
            if now - self.suggestion_cooldowns.get(key, 0) > self.min_cooldown:
                filtered.append(s)
                self.suggestion_cooldowns[key] = now

        return filtered[:5]  # Max 5 suggestions

    def _health_suggestions(self, now: float) -> List[Dict]:
        suggestions = []
        
        # Check idle time
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT start_time, period_type FROM presence_periods
            WHERE period_type = 'active' AND start_time > ?
            ORDER BY start_time DESC LIMIT 1
        """, (now - 7200,))  # Last 2 hours
        row = cursor.fetchone()
        conn.close()

        if row:
            active_duration = now - row[0]
            if active_duration > 7200:  # 2 hours
                suggestions.append({
                    "type": "health",
                    "title": "Take a break",
                    "description": f"You've been active for {active_duration/60:.0f} minutes. Consider a 5-10 minute break.",
                    "priority": 2,
                    "context": {"active_duration_minutes": active_duration/60},
                    "expires_at": now + 3600
                })
            elif active_duration > 3600:  # 1 hour
                suggestions.append({
                    "type": "health",
                    "title": "Stretch break",
                    "description": "You've been working for over an hour. Time to stretch!",
                    "priority": 3,
                    "context": {"active_duration_minutes": active_duration/60},
                    "expires_at": now + 1800
                })

        # Check for late night work
        hour = datetime.now().hour
        if hour >= 22 or hour <= 5:
            suggestions.append({
                "type": "health",
                "title": "Late night work detected",
                "description": f"It's {hour}:00. Consider wrapping up for better sleep.",
                "priority": 2,
                "context": {"hour": hour},
                "expires_at": now + 3600
            })

        return suggestions

    def _productivity_suggestions(self, now: float) -> List[Dict]:
        suggestions = []
        
        # Check context switches
        conn = get_ca_connection()
        cursor = conn.cursor()
        cutoff = now - 3600  # Last hour
        cursor.execute("""
            SELECT COUNT(*) FROM activity_events 
            WHERE timestamp > ? AND event_type = 'window_switch'
        """, (cutoff,))
        switches = cursor.fetchone()[0]
        conn.close()

        if switches > 20:
            suggestions.append({
                "type": "productivity",
                "title": "High context switching",
                "description": f"{switches} window switches in the last hour. Consider focusing on one task.",
                "priority": 2,
                "context": {"switches_per_hour": switches},
                "expires_at": now + 1800
            })

        # Check for long-running tasks without breaks
        cursor = get_ca_connection().cursor()
        cursor.execute("""
            SELECT * FROM awareness_sessions WHERE started_at > ? ORDER BY started_at DESC LIMIT 1
        """, (now - 86400,))
        session = cursor.fetchone()
        get_ca_connection().close()

        if session and session[5]:  # total_active_time
            if session[5] > 14400:  # 4 hours
                suggestions.append({
                    "type": "productivity",
                    "title": "Long work session",
                    "description": "You've been active for 4+ hours. Consider a longer break.",
                    "priority": 2,
                    "context": {"active_hours": session[5]/3600},
                    "expires_at": now + 3600
                })

        return suggestions

    def _resource_suggestions(self, now: float) -> List[Dict]:
        suggestions = []
        snapshot = system_agent.monitor.get_current_snapshot()
        if not snapshot:
            return suggestions

        cpu = snapshot.get('cpu_percent', 0)
        memory = snapshot.get('memory_percent', 0)
        disk = snapshot.get('disk_percent', 0)

        if cpu > 85:
            suggestions.append({
                "type": "resource",
                "title": "High CPU usage",
                "description": f"CPU at {cpu:.0f}%. Consider closing unused applications.",
                "priority": 1,
                "context": {"cpu_percent": cpu},
                "expires_at": now + 600
            })

        if memory > 85:
            suggestions.append({
                "type": "resource",
                "title": "High memory usage",
                "description": f"Memory at {memory:.0f}%. Consider closing browser tabs or apps.",
                "priority": 1,
                "context": {"memory_percent": memory},
                "expires_at": now + 600
            })

        if disk > 90:
            suggestions.append({
                "type": "resource",
                "title": "Low disk space",
                "description": f"Disk at {disk:.0f}%. Clean up temporary files or move data.",
                "priority": 1,
                "context": {"disk_percent": disk},
                "expires_at": now + 3600
            })

        return suggestions

    def _automation_suggestions(self, now: float) -> List[Dict]:
        suggestions = []
        
        # Check for repetitive tasks
        patterns = PatternRecognizer().get_patterns('app_sequence')
        for p in patterns[:2]:
            suggestions.append({
                "type": "automation",
                "title": f"Automate: {p['description'][:50]}",
                "description": "This sequence repeats frequently. Could be automated.",
                "priority": 3,
                "context": {"pattern_id": p['id'], "data": p['data']},
                "expires_at": now + 86400
            })

        return suggestions

    def create_suggestion(self, suggestion_type: str, title: str, description: str,
                          priority: int = 3, context: Dict = None, expires_in: int = 3600) -> str:
        suggestion_id = f"sugg_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO proactive_suggestions (id, suggestion_type, title, description,
                                              priority, context, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (suggestion_id, suggestion_type, title, description, priority,
              json.dumps(context or {}), time.time() + expires_in, time.time()))
        conn.commit()
        conn.close()
        return suggestion_id

    def get_pending_suggestions(self, limit: int = 10) -> List[Dict]:
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM proactive_suggestions 
            WHERE status = 'pending' AND expires_at > ?
            ORDER BY priority, created_at DESC LIMIT ?
        """, (time.time(), limit))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "type": r[1], "title": r[2], "description": r[3],
             "priority": r[4], "context": json.loads(r[5]) if r[5] else {},
             "status": r[6], "expires_at": r[9], "created_at": r[10]}
            for r in rows
        ]

    def dismiss_suggestion(self, suggestion_id: str):
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE proactive_suggestions SET status = 'dismissed', responded_at = ? WHERE id = ?",
                      (time.time(), suggestion_id))
        conn.commit()
        conn.close()

    def accept_suggestion(self, suggestion_id: str):
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE proactive_suggestions SET status = 'accepted', responded_at = ? WHERE id = ?",
                      (time.time(), suggestion_id))
        conn.commit()
        conn.close()


class InsightGenerator:
    """Generates actionable insights from collected data."""

    def __init__(self):
        pass

    def generate_insights(self) -> List[Dict]:
        insights = []
        now = time.time()

        # Productivity insights
        insights.extend(self._productivity_insights(now))

        # Health insights
        insights.extend(self._health_insights(now))

        # Resource insights
        insights.extend(self._resource_insights(now))

        # Workflow insights
        insights.extend(self._workflow_insights(now))

        return insights

    def _productivity_insights(self, now: float) -> List[Dict]:
        insights = []
        cutoff = now - 86400  # Last 24 hours

        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM activity_events WHERE timestamp > ? ORDER BY timestamp
        """, (cutoff,))
        events = cursor.fetchall()
        conn.close()

        if not events:
            return insights

        # App focus time
        app_durations = defaultdict(float)
        last_event = None
        for e in events:
            if last_event and e[4] > last_event[4]:  # timestamp
                duration = e[4] - last_event[4]
                app = e[3]  # details.app
                if app:
                    app_durations[app] += duration
            last_event = e

        if app_durations:
            top_app = max(app_durations.items(), key=lambda x: x[1])
            total_time = sum(app_durations.values())
            pct = top_app[1] / total_time * 100

            if pct > 60:
                insights.append({
                    "type": "productivity",
                    "title": f"Deep focus on {top_app[0]}",
                    "description": f"Spent {pct:.0f}% of active time in {top_app[0]} ({top_app[1]/60:.0f} min).",
                    "actionable": True,
                    "suggested_actions": ["Continue focus", "Schedule break"],
                    "confidence": 0.85,
                    "source_data": {"app_durations": dict(app_durations)}
                })

        return insights

    def _health_insights(self, now: float) -> List[Dict]:
        insights = []
        cutoff = now - 86400

        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT start_time, end_time, period_type, duration_seconds
            FROM presence_periods 
            WHERE start_time > ? ORDER BY start_time
        """, (cutoff,))
        periods = cursor.fetchall()
        conn.close()

        active_periods = [p for p in periods if p[2] == 'active' and p[3]]
        idle_periods = [p for p in periods if p[2] == 'idle' and p[3]]

        if active_periods:
            total_active = sum(p[3] for p in active_periods)
            avg_session = total_active / len(active_periods) / 60  # minutes
            max_session = max(p[3] for p in active_periods) / 60

            if max_session > 120:
                insights.append({
                    "type": "health",
                    "title": "Long continuous work sessions",
                    "description": f"Longest session: {max_session:.0f} min. Average: {avg_session:.0f} min. Consider more frequent breaks.",
                    "actionable": True,
                    "suggested_actions": ["Enable break reminders", "Use Pomodoro technique"],
                    "confidence": 0.9,
                    "source_data": {"max_session_min": max_session, "avg_session_min": avg_session}
                })

        return insights

    def _resource_insights(self, now: float) -> List[Dict]:
        insights = []

        # Get metric trends
        cpu_history = system_agent.monitor.get_metric_history('cpu_percent', 24)
        mem_history = system_agent.monitor.get_metric_history('memory_percent', 24)

        if cpu_history:
            avg_cpu = sum(h['value'] for h in cpu_history) / len(cpu_history)
            max_cpu = max(h['value'] for h in cpu_history)
            
            if avg_cpu > 50:
                insights.append({
                    "type": "resource",
                    "title": "Consistently high CPU usage",
                    "description": f"24h average CPU: {avg_cpu:.0f}% (peak: {max_cpu:.0f}%). Consider optimizing workloads.",
                    "actionable": True,
                    "suggested_actions": ["Identify resource-heavy processes", "Schedule heavy tasks off-peak"],
                    "confidence": 0.8,
                    "source_data": {"avg_cpu": avg_cpu, "max_cpu": max_cpu, "samples": len(cpu_history)}
                })

        if mem_history:
            avg_mem = sum(h['value'] for h in mem_history) / len(mem_history)
            if avg_mem > 70:
                insights.append({
                    "type": "resource",
                    "title": "High memory pressure",
                    "description": f"24h average memory: {avg_mem:.0f}%. May impact performance.",
                    "actionable": True,
                    "suggested_actions": ["Close unused apps", "Increase swap", "Add RAM"],
                    "confidence": 0.8,
                    "source_data": {"avg_memory": avg_mem, "samples": len(mem_history)}
                })

        return insights

    def _workflow_insights(self, now: float) -> List[Dict]:
        insights = []
        
        # Check for automation opportunities
        patterns = PatternRecognizer().get_patterns('app_sequence')
        for p in patterns[:3]:
            if p['confidence'] > 0.7 and p['frequency'] > 5:
                insights.append({
                    "type": "workflow",
                    "title": f"Automation opportunity: {p['pattern_type']}",
                    "description": f"Pattern '{p['description']}' occurs {p['frequency']} times. Could save time with automation.",
                    "actionable": True,
                    "suggested_actions": ["Create automation rule", "Build script", "Use macros"],
                    "confidence": p['confidence'],
                    "source_data": p['data']
                })

        return insights

    def store_insight(self, insight_type: str, title: str, description: str,
                      actionable: bool = True, suggested_actions: List[str] = None,
                      confidence: float = 0.8, source_data: Dict = None) -> str:
        insight_id = f"ins_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO insights (id, insight_type, title, description, actionable,
                                 suggested_actions, confidence, source_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (insight_id, insight_type, title, description, actionable,
              json.dumps(suggested_actions or []), confidence, json.dumps(source_data or {}), time.time()))
        conn.commit()
        conn.close()
        return insight_id

    def get_insights(self, insight_type: str = None, status: str = 'new', limit: int = 20) -> List[Dict]:
        conn = get_ca_connection()
        cursor = conn.cursor()
        if insight_type:
            cursor.execute("SELECT * FROM insights WHERE insight_type = ? AND status = ? ORDER BY created_at DESC LIMIT ?",
                          (insight_type, status, limit))
        else:
            cursor.execute("SELECT * FROM insights WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "insight_type": r[1], "title": r[2], "description": r[3],
             "actionable": bool(r[4]), "suggested_actions": json.loads(r[5]) if r[5] else [],
             "confidence": r[6], "source_data": json.loads(r[7]) if r[7] else {},
             "status": r[8], "created_at": r[9]}
            for r in rows
        ]


class AwarenessSessionManager:
    """Manages awareness sessions and daily summaries."""

    def __init__(self):
        self.current_session = None

    def start_session(self, session_id: str = None) -> str:
        sid = session_id or f"aw_{int(time.time() * 1000) % 100000000:08d}"
        self.current_session = {
            "id": sid,
            "started_at": time.time(),
            "window_switches": 0,
            "apps_used": set(),
            "files_accessed": set(),
            "suggestions_generated": 0,
            "suggestions_accepted": 0,
            "insights_generated": 0,
            "anomalies_detected": 0
        }
        return sid

    def end_session(self) -> Dict:
        if not self.current_session:
            return {}

        session = self.current_session
        session["ended_at"] = time.time()
        session["total_active_time"] = session["ended_at"] - session["started_at"]
        # Estimate idle time from presence periods
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SUM(duration_seconds) FROM presence_periods
            WHERE session_id = ? AND period_type = 'idle'
        """, (session["id"],))
        idle_row = cursor.fetchone()
        session["total_idle_time"] = idle_row[0] if idle_row and idle_row[0] else 0
        conn.close()

        # Save session
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO awareness_sessions (id, session_id, started_at, ended_at,
                                           total_active_time, total_idle_time, window_switches,
                                           apps_used, files_accessed, suggestions_generated,
                                           suggestions_accepted, insights_generated, anomalies_detected, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"aws_{int(time.time() * 1000) % 100000000:08d}", session["id"],
              session["started_at"], session["ended_at"], session["total_active_time"],
              session["total_idle_time"], session["window_switches"],
              json.dumps(list(session["apps_used"])), json.dumps(list(session["files_accessed"])),
              session["suggestions_generated"], session["suggestions_accepted"],
              session["insights_generated"], session["anomalies_detected"], time.time()))
        conn.commit()
        conn.close()

        result = session.copy()
        session["apps_used"] = list(session["apps_used"])
        session["files_accessed"] = list(session["files_accessed"])
        self.current_session = None
        return result

    def record_app_use(self, app_name: str):
        if self.current_session:
            self.current_session["apps_used"].add(app_name)

    def record_file_access(self, file_path: str):
        if self.current_session:
            self.current_session["files_accessed"].add(file_path)

    def record_window_switch(self):
        if self.current_session:
            self.current_session["window_switches"] += 1

    def record_suggestion(self, accepted: bool = False):
        if self.current_session:
            self.current_session["suggestions_generated"] += 1
            if accepted:
                self.current_session["suggestions_accepted"] += 1

    def record_insight(self):
        if self.current_session:
            self.current_session["insights_generated"] += 1

    def record_anomaly(self):
        if self.current_session:
            self.current_session["anomalies_detected"] += 1

    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM awareness_sessions ORDER BY started_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "session_id": r[1], "started_at": r[2], "ended_at": r[3],
             "active_time": r[4], "idle_time": r[5], "switches": r[6],
             "apps": json.loads(r[7]) if r[7] else [], "files": json.loads(r[8]) if r[8] else [],
             "suggestions_gen": r[9], "suggestions_acc": r[10],
             "insights": r[11], "anomalies": r[12]}
            for r in rows
        ]

    def get_daily_summary(self, date: float = None) -> Dict:
        """Get summary for a specific day."""
        if date is None:
            date = time.time()
        day_start = datetime.fromtimestamp(date).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        day_end = day_start + 86400

        sessions = self.get_recent_sessions(50)
        day_sessions = [s for s in sessions if day_start <= s["started_at"] < day_end]

        if not day_sessions:
            return {"date": day_start, "sessions": 0}

        total_active = sum(s["active_time"] for s in day_sessions)
        total_idle = sum(s["idle_time"] for s in day_sessions)
        total_switches = sum(s["switches"] for s in day_sessions)
        all_apps = set()
        for s in day_sessions:
            all_apps.update(s["apps"])

        return {
            "date": day_start,
            "sessions": len(day_sessions),
            "total_active_hours": total_active / 3600,
            "total_idle_hours": total_idle / 3600,
            "window_switches": total_switches,
            "unique_apps": len(all_apps),
            "apps_used": list(all_apps)
        }


# Global instances
activity_monitor = ActivityMonitor()
pattern_recognizer = PatternRecognizer()
anomaly_detector = AnomalyDetector()
suggestion_engine = ProactiveSuggestionEngine()
insight_generator = InsightGenerator()
session_manager = AwarenessSessionManager()


def ca_debug() -> str:
    conn = get_ca_connection()
    cursor = conn.cursor()
    tables = ["context_snapshots", "activity_events", "presence_periods",
              "proactive_suggestions", "recognized_patterns", "anomalies",
              "inferred_goals", "insights", "awareness_sessions"]
    output = "Continuous Awareness Debug:\n"
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        output += f"  {t}: {count} records\n"
    
    # Snapshot storage info
    snapshot_count = 0
    total_size = 0
    if os.path.exists(SNAPSHOT_DIR):
        for f in os.listdir(SNAPSHOT_DIR):
            if f.endswith('.json'):
                snapshot_count += 1
                total_size += os.path.getsize(os.path.join(SNAPSHOT_DIR, f))
    output += f"\nSnapshot Storage:\n"
    output += f"  JSON files: {snapshot_count}\n"
    output += f"  Total size: {total_size / 1024:.1f} KB\n"
    output += f"  Directory: {SNAPSHOT_DIR}\n"
    
    conn.close()
    return output


def cleanup_old_snapshots(days_to_keep: int = 7) -> Dict:
    """Delete snapshot JSON files older than specified days, keep metadata in DB."""
    cutoff = time.time() - (days_to_keep * 86400)
    deleted = 0
    freed_bytes = 0
    
    conn = get_ca_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, snapshot_file FROM context_snapshots 
        WHERE timestamp < ? AND snapshot_file IS NOT NULL
    """, (cutoff,))
    rows = cursor.fetchall()
    conn.close()
    
    for snap_id, snap_file in rows:
        if snap_file and os.path.exists(snap_file):
            size = os.path.getsize(snap_file)
            os.remove(snap_file)
            deleted += 1
            freed_bytes += size
        
        # Update DB to clear file reference
        conn = get_ca_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE context_snapshots SET snapshot_file = NULL, file_size_bytes = 0 WHERE id = ?", (snap_id,))
        conn.commit()
        conn.close()
    
    return {"deleted": deleted, "freed_mb": freed_bytes / (1024*1024)}


def get_snapshot_data(snapshot_id: str) -> Optional[Dict]:
    """Load full snapshot data from JSON file."""
    conn = get_ca_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT snapshot_file FROM context_snapshots WHERE id = ?", (snapshot_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0] and os.path.exists(row[0]):
        with open(row[0], 'r') as f:
            return json.load(f)
    return None


def get_snapshots_for_session(session_id: str, limit: int = 100) -> List[Dict]:
    """Get snapshot metadata for a session."""
    conn = get_ca_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, active_window, active_app, user_presence, snapshot_file, file_size_bytes
        FROM context_snapshots WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "timestamp": r[1], "active_window": r[2], "active_app": r[3],
         "user_presence": r[4], "snapshot_file": r[5], "file_size_bytes": r[6]}
        for r in rows
    ]


# Global instances
activity_monitor = ActivityMonitor()
pattern_recognizer = PatternRecognizer()
anomaly_detector = AnomalyDetector()
suggestion_engine = ProactiveSuggestionEngine()
insight_generator = InsightGenerator()
session_manager = AwarenessSessionManager()


def start_awareness(session_id: str = None) -> str:
    activity_monitor.start(session_id)
    session_manager.start_session(session_id)
    return f"Continuous awareness started (session: {session_id or 'auto'})"


def stop_awareness() -> Dict:
    activity_monitor.stop()
    return session_manager.end_session()


def get_awareness_status() -> Dict:
    return {
        "monitor": activity_monitor.get_session_stats(),
        "session": session_manager.current_session,
        "pending_suggestions": len(suggestion_engine.get_pending_suggestions()),
        "unacknowledged_anomalies": len([a for a in anomaly_detector.check_system_anomalies()]),
        "new_insights": len(insight_generator.get_insights(status='new'))
    }


def get_proactive_suggestions() -> List[Dict]:
    return suggestion_engine.generate_suggestions()


def get_insights(insight_type: str = None) -> List[Dict]:
    return insight_generator.get_insights(insight_type)


def get_anomalies() -> List[Dict]:
    sys_anoms = anomaly_detector.check_system_anomalies()
    behav_anoms = anomaly_detector.check_behavioral_anomalies()
    return sys_anoms + behav_anoms


def get_patterns(pattern_type: str = None) -> List[Dict]:
    return pattern_recognizer.get_patterns(pattern_type)


def get_daily_summary(date: float = None) -> Dict:
    return session_manager.get_daily_summary(date)


def get_recent_sessions(limit: int = 10) -> List[Dict]:
    return session_manager.get_recent_sessions(limit)


def dismiss_suggestion(suggestion_id: str):
    suggestion_engine.dismiss_suggestion(suggestion_id)
    return f"Dismissed suggestion {suggestion_id}"


def accept_suggestion(suggestion_id: str):
    suggestion_engine.accept_suggestion(suggestion_id)
    session_manager.record_suggestion(accepted=True)
    return f"Accepted suggestion {suggestion_id}"


def record_activity(event_type: str, details: Dict):
    event_id = f"evt_{int(time.time() * 1000) % 100000000:08d}"
    conn = get_ca_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO activity_events (id, event_type, timestamp, details, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (event_id, event_type, time.time(), json.dumps(details),
          session_manager.current_session["id"] if session_manager.current_session else "",
          time.time()))
    conn.commit()
    conn.close()


def record_window_switch():
    session_manager.record_window_switch()
    record_activity("window_switch", {"timestamp": time.time()})


def record_app_launch(app_name: str):
    session_manager.record_app_use(app_name)
    record_activity("app_launch", {"app": app_name, "timestamp": time.time()})


def record_file_open(file_path: str):
    session_manager.record_file_access(file_path)
    record_activity("file_open", {"path": file_path, "timestamp": time.time()})