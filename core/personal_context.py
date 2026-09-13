"""
Personal Context Engine - Phase 14
User behavior learning, preference inference, and adaptive personalization.
Fully local, no cloud, privacy-preserving.
"""

import json
import time
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

from core.context_engine import get_connection, get_current_session


DB_DIR = "database"
CONTEXT_DB = os.path.join(DB_DIR, "personal_context.db")

os.makedirs(DB_DIR, exist_ok=True)


def init_personal_context_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Command history with context
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            command TEXT NOT NULL,
            normalized_command TEXT,
            intent TEXT,
            entities TEXT,  -- JSON
            response_time REAL,
            success BOOLEAN,
            timestamp REAL NOT NULL,
            context_snapshot TEXT  -- JSON of relevant context
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_cmd_session_time
        ON command_history(session_id, timestamp)
    """)

    # User preferences (learned)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            source TEXT,  -- 'explicit', 'inferred', 'behavioral'
            evidence TEXT,  -- JSON
            created REAL NOT NULL,
            last_updated REAL NOT NULL
        )
    """)

    # Usage patterns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,  -- 'time', 'sequence', 'frequency', 'context'
            pattern_data TEXT NOT NULL,  -- JSON
            frequency INTEGER DEFAULT 1,
            confidence REAL DEFAULT 0.5,
            first_seen REAL NOT NULL,
            last_seen REAL NOT NULL
        )
    """)

    # Habits and routines
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            trigger TEXT,  -- JSON: time, command, context
            actions TEXT NOT NULL,  -- JSON array of commands
            frequency INTEGER DEFAULT 0,
            strength REAL DEFAULT 0.0,  -- 0-1
            active BOOLEAN DEFAULT 1,
            created REAL NOT NULL,
            last_triggered REAL
        )
    """)

    # Proactive suggestions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suggestion_type TEXT NOT NULL,  -- 'command', 'workflow', 'setting', 'reminder'
            content TEXT NOT NULL,
            context TEXT,  -- JSON
            priority INTEGER DEFAULT 0,
            shown BOOLEAN DEFAULT 0,
            accepted BOOLEAN DEFAULT 0,
            created REAL NOT NULL,
            expires REAL
        )
    """)

    # User profile
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            confidence REAL DEFAULT 1.0,
            source TEXT DEFAULT 'explicit',
            updated REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_personal_context_db()


@dataclass
class CommandRecord:
    command: str
    normalized_command: str
    intent: str
    entities: Dict
    response_time: float
    success: bool
    timestamp: float
    context_snapshot: Dict


@dataclass
class LearnedPreference:
    key: str
    value: Any
    confidence: float
    source: str
    evidence: Dict


class PersonalContextEngine:
    def __init__(self):
        self.session_id = get_current_session()
        self.command_buffer = []
        self.max_buffer = 50

    # ==========================================
    # COMMAND TRACKING
    # ==========================================

    def record_command(self, record: CommandRecord):
        """Record a command execution for learning."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO command_history
            (session_id, command, normalized_command, intent, entities,
             response_time, success, timestamp, context_snapshot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.session_id,
            record.command,
            record.normalized_command,
            record.intent,
            json.dumps(record.entities),
            record.response_time,
            record.success,
            record.timestamp,
            json.dumps(record.context_snapshot)
        ))
        conn.commit()
        conn.close()

        # Add to buffer for pattern detection
        self.command_buffer.append(record)
        if len(self.command_buffer) > self.max_buffer:
            self.command_buffer.pop(0)

        # Trigger pattern analysis periodically
        if len(self.command_buffer) % 10 == 0:
            self._analyze_patterns()

    def get_recent_commands(self, limit: int = 20) -> List[CommandRecord]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT command, normalized_command, intent, entities,
                   response_time, success, timestamp, context_snapshot
            FROM command_history
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (self.session_id, limit))
        rows = cursor.fetchall()
        conn.close()

        return [
            CommandRecord(
                command=r[0],
                normalized_command=r[1],
                intent=r[2],
                entities=json.loads(r[3]) if r[3] else {},
                response_time=r[4],
                success=bool(r[5]),
                timestamp=r[6],
                context_snapshot=json.loads(r[7]) if r[7] else {}
            )
            for r in rows
        ]

    # ==========================================
    # PREFERENCE LEARNING
    # ==========================================

    def learn_preference(self, key: str, value: Any, confidence: float = 0.7,
                         source: str = "inferred", evidence: Dict = None):
        """Learn or update a user preference."""
        conn = get_connection()
        cursor = conn.cursor()
        now = time.time()
        cursor.execute("""
            INSERT INTO learned_preferences (key, value, confidence, source, evidence, created, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                confidence=CASE WHEN excluded.confidence > learned_preferences.confidence
                    THEN excluded.confidence ELSE learned_preferences.confidence END,
                source=excluded.source,
                evidence=excluded.evidence,
                last_updated=excluded.last_updated
        """, (
            key,
            json.dumps(value),
            confidence,
            source,
            json.dumps(evidence or {}),
            now,
            now
        ))
        conn.commit()
        conn.close()

    def get_preference(self, key: str, default=None) -> Any:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value, confidence FROM learned_preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            val = json.loads(row[0])
            # Could filter by confidence threshold here
            return val
        return default

    def get_all_preferences(self, min_confidence: float = 0.0) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT key, value, confidence, source FROM learned_preferences
            WHERE confidence >= ?
        """, (min_confidence,))
        rows = cursor.fetchall()
        conn.close()
        return {r[0]: {"value": json.loads(r[1]), "confidence": r[2], "source": r[3]} for r in rows}

    # ==========================================
    # PATTERN ANALYSIS
    # ==========================================

    def _analyze_patterns(self):
        """Analyze command buffer for patterns."""
        if len(self.command_buffer) < 5:
            return

        # Time-based patterns
        self._detect_time_patterns()

        # Command sequences
        self._detect_sequence_patterns()

        # Frequency patterns
        self._detect_frequency_patterns()

        # Context patterns
        self._detect_context_patterns()

    def _detect_time_patterns(self):
        """Detect time-of-day usage patterns."""
        hour_counts = Counter()
        for cmd in self.command_buffer:
            dt = datetime.fromtimestamp(cmd.timestamp)
            hour_counts[dt.hour] += 1

        # Find peak hours
        if hour_counts:
            peak_hour = hour_counts.most_common(1)[0][0]
            self.learn_preference(
                "peak_usage_hour",
                peak_hour,
                confidence=0.6,
                source="behavioral",
                evidence={"hour_distribution": dict(hour_counts)}
            )

    def _detect_sequence_patterns(self):
        """Detect common command sequences (n-grams)."""
        commands = [cmd.normalized_command or cmd.command for cmd in self.command_buffer]

        # Look for bigrams and trigrams
        for n in [2, 3]:
            sequences = Counter()
            for i in range(len(commands) - n + 1):
                seq = tuple(commands[i:i+n])
                sequences[seq] += 1

            for seq, count in sequences.most_common(3):
                if count >= 2:  # At least twice
                    key = f"sequence_{n}gram_{'_'.join(seq)}"
                    self.learn_preference(
                        key,
                        {"sequence": list(seq), "count": count},
                        confidence=min(0.5 + count * 0.1, 0.9),
                        source="behavioral",
                        evidence={"count": count, "n": n}
                    )

    def _detect_frequency_patterns(self):
        """Detect frequently used commands."""
        cmd_counts = Counter(cmd.normalized_command or cmd.command for cmd in self.command_buffer)

        for cmd, count in cmd_counts.most_common(5):
            if count >= 3:
                self.learn_preference(
                    f"frequent_command_{cmd}",
                    {"command": cmd, "count": count},
                    confidence=min(0.4 + count * 0.05, 0.85),
                    source="behavioral",
                    evidence={"count": count}
                )

    def _detect_context_patterns(self):
        """Detect context-dependent command patterns."""
        # Group by context (e.g., project, time, active app)
        context_groups = defaultdict(list)
        for cmd in self.command_buffer:
            ctx_key = json.dumps(cmd.context_snapshot, sort_keys=True)[:100]
            context_groups[ctx_key].append(cmd.normalized_command or cmd.command)

        for ctx, cmds in context_groups.items():
            if len(cmds) >= 3:
                cmd_counts = Counter(cmds)
                top_cmd = cmd_counts.most_common(1)[0]
                self.learn_preference(
                    f"context_command_{hash(ctx) % 10000}",
                    {"context": ctx, "command": top_cmd[0], "count": top_cmd[1]},
                    confidence=0.5,
                    source="behavioral",
                    evidence={"context": ctx, "commands": dict(cmd_counts)}
                )

    # ==========================================
    # HABIT DETECTION
    # ==========================================

    def detect_habits(self) -> List[Dict]:
        """Detect recurring habits from command history."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT command, normalized_command, timestamp
            FROM command_history
            WHERE session_id = ?
            ORDER BY timestamp
        """, (self.session_id,))
        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 10:
            return []

        # Simple habit detection: commands at similar times
        habits = []
        time_buckets = defaultdict(list)

        for cmd, norm_cmd, ts in rows:
            dt = datetime.fromtimestamp(ts)
            bucket = f"{dt.weekday()}_{dt.hour}"  # Day of week + hour
            time_buckets[bucket].append(norm_cmd or cmd)

        for bucket, cmds in time_buckets.items():
            if len(cmds) >= 3:
                cmd_counts = Counter(cmds)
                top_cmd, count = cmd_counts.most_common(1)[0]
                if count >= 2:
                    habits.append({
                        "name": f"Habit: {top_cmd} on {bucket}",
                        "trigger": {"time_bucket": bucket},
                        "action": top_cmd,
                        "frequency": count,
                        "strength": min(count / 10.0, 1.0)
                    })

        return habits

    def save_habit(self, habit: Dict):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO habits (name, trigger, actions, frequency, strength, active, created, last_triggered)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            habit["name"],
            json.dumps(habit["trigger"]),
            json.dumps([habit["action"]]),
            habit["frequency"],
            habit["strength"],
            time.time(),
            time.time()
        ))
        conn.commit()
        conn.close()

    # ==========================================
    # PROACTIVE SUGGESTIONS
    # ==========================================

    def generate_suggestions(self, current_context: Dict = None) -> List[Dict]:
        """Generate proactive suggestions based on learned patterns."""
        suggestions = []
        prefs = self.get_all_preferences(min_confidence=0.5)
        now = time.time()
        current_hour = datetime.now().hour

        # Time-based suggestions
        if "peak_usage_hour" in prefs:
            peak = prefs["peak_usage_hour"]["value"]
            if isinstance(peak, int) and abs(current_hour - peak) <= 1:
                suggestions.append({
                    "type": "workflow",
                    "content": f"You're typically active now. Want to continue your {prefs.get('frequent_command_', {}).get('value', {}).get('command', 'work')}?",
                    "priority": 5,
                    "context": {"hour": current_hour, "peak_hour": peak}
                })

        # Frequent command suggestions
        for key, pref in prefs.items():
            if key.startswith("frequent_command_") and pref["confidence"] > 0.6:
                cmd = pref["value"].get("command", "")
                if cmd and current_context:
                    # Check if context matches
                    suggestions.append({
                        "type": "command",
                        "content": f"Quick action: {cmd}",
                        "priority": int(pref["confidence"] * 10),
                        "context": {"suggested_command": cmd}
                    })

        # Sequence suggestions
        for key, pref in prefs.items():
            if key.startswith("sequence_") and pref["confidence"] > 0.6:
                seq = pref["value"].get("sequence", [])
                if len(seq) >= 2 and current_context:
                    last_cmd = current_context.get("last_command")
                    if last_cmd and last_cmd == seq[0]:
                        suggestions.append({
                            "type": "workflow",
                            "content": f"Next step might be: {seq[1]}",
                            "priority": int(pref["confidence"] * 8),
                            "context": {"sequence": seq, "position": 1}
                        })

        # Store suggestions
        conn = get_connection()
        cursor = conn.cursor()
        for s in suggestions:
            cursor.execute("""
                INSERT INTO suggestions (suggestion_type, content, context, priority, created, expires)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                s["type"],
                s["content"],
                json.dumps(s.get("context", {})),
                s["priority"],
                now,
                now + 3600  # Expire in 1 hour
            ))
        conn.commit()
        conn.close()

        return suggestions[:5]  # Top 5

    def get_pending_suggestions(self, limit: int = 5) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        now = time.time()
        cursor.execute("""
            SELECT id, suggestion_type, content, context, priority, created
            FROM suggestions
            WHERE shown = 0 AND (expires IS NULL OR expires > ?)
            ORDER BY priority DESC, created DESC
            LIMIT ?
        """, (now, limit))
        rows = cursor.fetchall()
        conn.close()

        return [
            {"id": r[0], "type": r[1], "content": r[2],
             "context": json.loads(r[3]) if r[3] else {},
             "priority": r[4], "created": r[5]}
            for r in rows
        ]

    def mark_suggestion_shown(self, suggestion_id: int):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE suggestions SET shown = 1 WHERE id = ?", (suggestion_id,))
        conn.commit()
        conn.close()

    def mark_suggestion_accepted(self, suggestion_id: int):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE suggestions SET accepted = 1, shown = 1 WHERE id = ?", (suggestion_id,))
        conn.commit()
        conn.close()

    # ==========================================
    # USER PROFILE
    # ==========================================

    def set_profile(self, key: str, value: Any, category: str = "general", confidence: float = 1.0):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_profile (key, value, category, confidence, source, updated)
            VALUES (?, ?, ?, ?, 'explicit', ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                category=excluded.category,
                confidence=excluded.confidence,
                updated=excluded.updated
        """, (key, json.dumps(value), category, confidence, time.time()))
        conn.commit()
        conn.close()

    def get_profile(self, key: str, default=None) -> Any:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM user_profile WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return json.loads(row[0]) if row else default

    # ==========================================
    # ADAPTIVE RESPONSES
    # ==========================================

    def get_adaptive_config(self) -> Dict:
        """Get configuration adapted to user preferences."""
        prefs = self.get_all_preferences(min_confidence=0.5)
        profile = {}

        # Language/style preferences
        if "preferred_style" in prefs:
            profile["writing_style"] = prefs["preferred_style"]["value"]
        if "preferred_language" in prefs:
            profile["coding_language"] = prefs["preferred_language"]["value"]

        # Verbosity
        if "verbosity" in prefs:
            profile["verbosity"] = prefs["verbosity"]["value"]

        # Default model
        if "preferred_model" in prefs:
            profile["default_model"] = prefs["preferred_model"]["value"]

        # UI preferences
        if "theme" in prefs:
            profile["theme"] = prefs["theme"]["value"]

        return profile

    # ==========================================
    # EXPORT/IMPORT
    # ==========================================

    def export_context(self, file_path: str = None) -> str:
        """Export personal context for backup."""
        file_path = file_path or f"personal_context_{int(time.time())}.json"

        data = {
            "preferences": self.get_all_preferences(),
            "profile": {},
            "habits": self.detect_habits(),
            "exported_at": time.time()
        }

        # Get profile
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, category, confidence FROM user_profile")
        for row in cursor.fetchall():
            data["profile"][row[0]] = {"value": json.loads(row[1]), "category": row[2], "confidence": row[3]}
        conn.close()

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

        return file_path

    def import_context(self, file_path: str) -> bool:
        """Import personal context from backup."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Import preferences
            for key, pref in data.get("preferences", {}).items():
                self.learn_preference(key, pref["value"], pref["confidence"], pref["source"], pref.get("evidence"))

            # Import profile
            for key, prof in data.get("profile", {}).items():
                self.set_profile(key, prof["value"], prof["category"], prof["confidence"])

            return True
        except Exception:
            return False


# Global instance
personal_context = PersonalContextEngine()


# Convenience functions
def record_command(command: str, normalized: str, intent: str, entities: Dict,
                   response_time: float, success: bool, context: Dict = None):
    personal_context.record_command(CommandRecord(
        command=command,
        normalized_command=normalized,
        intent=intent,
        entities=entities,
        response_time=response_time,
        success=success,
        timestamp=time.time(),
        context_snapshot=context or {}
    ))

def get_suggestions(context: Dict = None) -> List[Dict]:
    return personal_context.generate_suggestions(context)

def get_user_preferences(min_confidence: float = 0.5) -> Dict:
    return personal_context.get_all_preferences(min_confidence)

def set_user_preference(key: str, value: Any, confidence: float = 1.0, source: str = "explicit"):
    personal_context.learn_preference(key, value, confidence, source)

def get_adaptive_config() -> Dict:
    return personal_context.get_adaptive_config()

def export_personal_context(file_path: str = None) -> str:
    return personal_context.export_context(file_path)

def import_personal_context(file_path: str) -> bool:
    return personal_context.import_context(file_path)


if __name__ == "__main__":
    # Test
    engine = PersonalContextEngine()

    # Simulate some commands
    test_commands = [
        ("create file test.py", "create file test.py", "file_create", {"name": "test.py"}, 0.5, True),
        ("open file test.py", "open file test.py", "file_open", {"name": "test.py"}, 0.3, True),
        ("run code test.py", "run code test.py", "code_run", {"file": "test.py"}, 1.2, True),
        ("create file test.py", "create file test.py", "file_create", {"name": "test.py"}, 0.4, True),
        ("open file test.py", "open file test.py", "file_open", {"name": "test.py"}, 0.2, True),
    ]

    for cmd, norm, intent, entities, rt, success in test_commands:
        engine.record_command(CommandRecord(
            command=cmd, normalized_command=norm, intent=intent,
            entities=entities, response_time=rt, success=success,
            timestamp=time.time(), context_snapshot={}
        ))

    time.sleep(0.1)  # Let pattern analysis run

    print("Preferences:", engine.get_all_preferences(0.5))
    print("Habits:", engine.detect_habits())
    print("Suggestions:", engine.generate_suggestions({"last_command": "create file test.py"}))
    print("Adaptive config:", engine.get_adaptive_config())