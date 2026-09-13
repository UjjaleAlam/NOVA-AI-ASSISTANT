"""
Passive Mentor - Phase 22
Background learning, pattern recognition, proactive guidance.
Learns continuously from user behavior without explicit requests.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import threading
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from core.context_engine import get_connection, get_current_session
from core.personal_context import personal_context
from core.second_brain import knowledge_graph
from brain import ask_nova


DB_DIR = "database"
MENTOR_DB = os.path.join(DB_DIR, "passive_mentor.db")

os.makedirs(DB_DIR, exist_ok=True)


def init_mentor_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Observed patterns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS observed_patterns (
            id TEXT PRIMARY KEY,
            pattern_type TEXT NOT NULL,  -- 'workflow', 'timing', 'tool_usage', 'error', 'preference'
            pattern_data TEXT NOT NULL,  -- JSON
            confidence REAL DEFAULT 0.0,
            occurrences INTEGER DEFAULT 1,
            first_seen REAL NOT NULL,
            last_seen REAL NOT NULL,
            is_actionable BOOLEAN DEFAULT 0
        )
    """)

    # Proactive suggestions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proactive_suggestions (
            id TEXT PRIMARY KEY,
            trigger_type TEXT NOT NULL,  -- 'pattern', 'time', 'context', 'anomaly'
            suggestion_text TEXT NOT NULL,
            context TEXT,  -- JSON
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',  -- 'pending', 'shown', 'accepted', 'dismissed'
            created_at REAL NOT NULL,
            shown_at REAL,
            resolved_at REAL
        )
    """)

    # Learning insights
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_insights (
            id TEXT PRIMARY KEY,
            insight_type TEXT NOT NULL,  -- 'workflow_optimization', 'tool_discovery', 'skill_gap', 'best_practice'
            title TEXT NOT NULL,
            description TEXT,
            evidence TEXT,  -- JSON
            confidence REAL DEFAULT 0.0,
            action_items TEXT,  -- JSON
            created_at REAL NOT NULL,
            acknowledged_at REAL
        )
    """)

    # User behavior baseline
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS behavior_baseline (
            id TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,
            baseline_value REAL NOT NULL,
            current_value REAL,
            deviation REAL,
            last_updated REAL NOT NULL
        )
    """)

    # Anomaly detection
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id TEXT PRIMARY KEY,
            anomaly_type TEXT NOT NULL,
            description TEXT,
            severity TEXT,  -- 'low', 'medium', 'high'
            context TEXT,  -- JSON
            detected_at REAL NOT NULL,
            resolved_at REAL,
            is_false_positive BOOLEAN DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


init_mentor_db()


@dataclass
class ObservedPattern:
    id: str
    pattern_type: str
    pattern_data: Dict
    confidence: float
    occurrences: int
    first_seen: float
    last_seen: float
    is_actionable: bool


@dataclass
class ProactiveSuggestion:
    id: str
    trigger_type: str
    suggestion_text: str
    context: Dict
    priority: int
    status: str
    created_at: float
    shown_at: Optional[float]
    resolved_at: Optional[float]


class PatternRecognizer:
    """Recognizes patterns from user behavior."""

    def __init__(self):
        self.min_occurrences = 3
        self.confidence_threshold = 0.6

    def analyze_command_sequence(self, commands: List[Dict]) -> List[ObservedPattern]:
        """Analyze sequence of commands for patterns."""
        patterns = []

        if len(commands) < self.min_occurrences:
            return patterns

        # Workflow patterns (command sequences)
        workflows = self._extract_workflows(commands)
        for workflow in workflows:
            pattern = self._create_pattern("workflow", workflow)
            if pattern:
                patterns.append(pattern)

        # Tool usage patterns
        tool_patterns = self._extract_tool_patterns(commands)
        for tp in tool_patterns:
            pattern = self._create_pattern("tool_usage", tp)
            if pattern:
                patterns.append(pattern)

        # Timing patterns
        timing_patterns = self._extract_timing_patterns(commands)
        for tp in timing_patterns:
            pattern = self._create_pattern("timing", tp)
            if pattern:
                patterns.append(pattern)

        return patterns

    def _extract_workflows(self, commands: List[Dict]) -> List[Dict]:
        """Extract recurring command sequences (n-grams)."""
        workflows = defaultdict(int)
        sequence = [cmd.get("normalized", cmd.get("command", "")) for cmd in commands]

        # Extract 2-grams and 3-grams
        for n in [2, 3]:
            for i in range(len(sequence) - n + 1):
                ngram = tuple(sequence[i:i+n])
                workflows[ngram] += 1

        return [{"sequence": list(k), "count": v} for k, v in workflows.items() if v >= 2]

    def _extract_tool_patterns(self, commands: List[Dict]) -> List[Dict]:
        """Extract tool/command usage patterns."""
        tool_usage = Counter()
        tool_sequences = defaultdict(list)

        for cmd in commands:
            intent = cmd.get("intent", "unknown")
            tool_usage[intent] += 1

        # Find tools often used together
        tools = [cmd.get("intent", "") for cmd in commands]
        pairs = Counter()
        for i in range(len(tools) - 1):
            pair = tuple(sorted([tools[i], tools[i+1]]))
            pairs[pair] += 1

        return [
            {"tools": list(k), "count": v}
            for k, v in pairs.items() if v >= 2
        ]

    def _extract_timing_patterns(self, commands: List[Dict]) -> List[Dict]:
        """Extract temporal usage patterns."""
        hour_usage = Counter()
        day_usage = Counter()

        for cmd in commands:
            ts = cmd.get("timestamp", 0)
            if ts:
                dt = datetime.fromtimestamp(ts)
                hour_usage[dt.hour] += 1
                day_usage[dt.weekday()] += 1

        patterns = []
        if hour_usage:
            peak_hour = hour_usage.most_common(1)[0]
            patterns.append({
                "type": "peak_hour",
                "hour": peak_hour[0],
                "count": peak_hour[1]
            })
        if day_usage:
            peak_day = day_usage.most_common(1)[0]
            patterns.append({
                "type": "peak_day",
                "day": peak_day[0],
                "count": peak_day[1]
            })
        return patterns

    def _create_pattern(self, pattern_type: str, data: Dict) -> Optional[ObservedPattern]:
        """Create pattern object from analyzed data."""
        if not data or data.get("count", 0) < self.min_occurrences:
            return None

        pattern_id = f"pat_{int(time.time() * 1000) % 100000000:08d}"
        return ObservedPattern(
            id=pattern_id,
            pattern_type=pattern_type,
            pattern_data=data,
            confidence=min(data.get("count", 1) / 10.0, 1.0),
            occurrences=data.get("count", 1),
            first_seen=time.time(),
            last_seen=time.time(),
            is_actionable=data.get("count", 1) >= 5
        )


class ProactiveGuidance:
    """Generates proactive suggestions based on patterns and context."""

    def __init__(self):
        self.suggestion_cooldown = 300  # 5 minutes between suggestions

    def generate_suggestions(self, context: Dict) -> List[ProactiveSuggestion]:
        """Generate proactive suggestions based on current context."""
        suggestions = []

        # Get recent patterns
        patterns = self._get_recent_patterns()

        # Pattern-based suggestions
        for pattern in patterns:
            if pattern.is_actionable and pattern.confidence > 0.7:
                suggestion = self._create_pattern_suggestion(pattern)
                if suggestion:
                    suggestions.append(suggestion)

        # Time-based suggestions
        time_suggestions = self._generate_time_based_suggestions(context)
        suggestions.extend(time_suggestions)

        # Context-based suggestions
        context_suggestions = self._generate_context_suggestions(context)
        suggestions.extend(context_suggestions)

        # Anomaly-based suggestions
        anomaly_suggestions = self._generate_anomaly_suggestions()
        suggestions.extend(anomaly_suggestions)

        # Sort by priority
        suggestions.sort(key=lambda s: s.priority, reverse=True)
        return suggestions[:5]  # Top 5

    def _get_recent_patterns(self) -> List[ObservedPattern]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM observed_patterns
            WHERE is_actionable = 1 AND confidence > 0.6
            ORDER BY last_seen DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()

        return [
            ObservedPattern(
                id=r[0], pattern_type=r[1], pattern_data=json.loads(r[2]),
                confidence=r[3], occurrences=r[4], first_seen=r[5],
                last_seen=r[6], is_actionable=bool(r[7])
            )
            for r in rows
        ]

    def _create_pattern_suggestion(self, pattern: ObservedPattern) -> Optional[ProactiveSuggestion]:
        """Create suggestion from actionable pattern."""
        suggestion_text = ""

        if pattern.pattern_type == "workflow":
            seq = pattern.pattern_data.get("sequence", [])
            if seq:
                suggestion_text = f"You often run: {' → '.join(seq)}. Want me to create a shortcut?"

        elif pattern.pattern_type == "tool_usage":
            tools = pattern.pattern_data.get("tools", [])
            if tools:
                suggestion_text = f"You often use {' and '.join(tools)} together. Consider a script?"

        elif pattern.pattern_type == "timing":
            pdata = pattern.pattern_data
            if pdata.get("type") == "peak_hour":
                suggestion_text = f"You're most active at {pdata['hour']}:00. Schedule focused work?"

        if not suggestion_text:
            return None

        return ProactiveSuggestion(
            id=f"sug_{int(time.time() * 1000) % 100000000:08d}",
            trigger_type="pattern",
            suggestion_text=suggestion_text,
            context={"pattern_id": pattern.id},
            priority=int(pattern.confidence * 10),
            status="pending",
            created_at=time.time(),
            shown_at=None,
            resolved_at=None
        )

    def _generate_time_based_suggestions(self, context: Dict) -> List[ProactiveSuggestion]:
        suggestions = []
        now = datetime.now()
        hour = now.hour

        # Morning suggestions
        if 6 <= hour <= 9:
            suggestions.append(ProactiveSuggestion(
                id=f"sug_{int(time.time() * 1000) % 100000000:08d}",
                trigger_type="time",
                suggestion_text="Good morning! Want to review today's tasks?",
                context={"time_of_day": "morning"},
                priority=5,
                status="pending",
                created_at=time.time(),
                shown_at=None,
                resolved_at=None
            ))

        # End of day
        if 17 <= hour <= 19:
            suggestions.append(ProactiveSuggestion(
                id=f"sug_{int(time.time() * 1000) % 100000000:08d}",
                trigger_type="time",
                suggestion_text="End of day approaching. Want to review progress?",
                context={"time_of_day": "evening"},
                priority=5,
                status="pending",
                created_at=time.time(),
                shown_at=None,
                resolved_at=None
            ))

        return suggestions

    def _generate_context_suggestions(self, context: Dict) -> List[ProactiveSuggestion]:
        suggestions = []

        # Project-based
        current_project = context.get("current_project")
        if current_project:
            suggestions.append(ProactiveSuggestion(
                id=f"sug_{int(time.time() * 1000) % 100000000:08d}",
                trigger_type="context",
                suggestion_text=f"Working on {current_project}. Need help with anything?",
                context={"project": current_project},
                priority=4,
                status="pending",
                created_at=time.time(),
                shown_at=None,
                resolved_at=None
            ))

        return suggestions

    def _generate_anomaly_suggestions(self) -> List[ProactiveSuggestion]:
        suggestions = []
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM anomalies
            WHERE resolved_at IS NULL AND is_false_positive = 0
            ORDER BY severity DESC, detected_at DESC
            LIMIT 5
        """)
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            suggestions.append(ProactiveSuggestion(
                id=f"sug_{int(time.time() * 1000) % 100000000:08d}",
                trigger_type="anomaly",
                suggestion_text=f"Detected: {row[2]}. Need investigation?",
                context={"anomaly_id": row[0], "severity": row[4]},
                priority=8 if row[4] == "high" else 5,
                status="pending",
                created_at=time.time(),
                shown_at=None,
                resolved_at=None
            ))

        return suggestions


class InsightGenerator:
    """Generates learning insights from accumulated data."""

    def __init__(self):
        pass

    def generate_insights(self) -> List[Dict]:
        insights = []

        # Workflow optimization insights
        insights.extend(self._analyze_workflow_efficiency())

        # Tool discovery insights
        insights.extend(self._analyze_tool_usage())

        # Skill gap insights
        insights.extend(self._identify_skill_gaps())

        # Best practice insights
        insights.extend(self._identify_best_practices())

        return insights

    def _analyze_workflow_efficiency(self) -> List[Dict]:
        insights = []
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT pattern_data, confidence, occurrences
            FROM observed_patterns
            WHERE pattern_type = 'workflow' AND occurrences >= 5
        """)
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            data = json.loads(row[0])
            seq = data.get("sequence", [])
            if len(seq) >= 3:
                insights.append({
                    "type": "workflow_optimization",
                    "title": f"Frequent workflow: {' → '.join(seq[:3])}...",
                    "description": f"This {len(seq)}-step workflow occurs {row[2]} times. Consider automation.",
                    "evidence": {"sequence": seq, "count": row[2]},
                    "confidence": row[1],
                    "actions": ["Create script", "Add alias", "Use macro"]
                })

        return insights

    def _analyze_tool_usage(self) -> List[Dict]:
        insights = []
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT pattern_data, confidence
            FROM observed_patterns
            WHERE pattern_type = 'tool_usage' AND confidence > 0.7
        """)
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            data = json.loads(row[0])
            tools = data.get("tools", [])
            if len(tools) >= 2:
                insights.append({
                    "type": "tool_discovery",
                    "title": f"Tool combo: {' + '.join(tools)}",
                    "description": f"You frequently use {' and '.join(tools)} together.",
                    "evidence": {"tools": tools, "count": data.get("count", 0)},
                    "confidence": row[1],
                    "actions": ["Create wrapper script", "Add to PATH", "Create alias"]
                })

        return insights

    def _identify_skill_gaps(self) -> List[Dict]:
        insights = []
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name, category, difficulty FROM topics
            WHERE id NOT IN (SELECT topic_id FROM user_progress WHERE status IN ('mastered', 'completed'))
            ORDER BY
                CASE difficulty WHEN 'beginner' THEN 0 WHEN 'intermediate' THEN 1 WHEN 'advanced' THEN 2 ELSE 3 END
            LIMIT 5
        """)
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            insights.append({
                "type": "skill_gap",
                "title": f"Learn {row[0]}",
                "description": f"Recommended {row[1]} topic at {row[2]} level.",
                "evidence": {"topic": row[0], "category": row[1], "difficulty": row[2]},
                "confidence": 0.8,
                "actions": ["Start tutorial", "Add to learning path", "Schedule time"]
            })

        return insights

    def _identify_best_practices(self) -> List[Dict]:
        insights = []

        # Check for common patterns that indicate best practices
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM observed_patterns
            WHERE pattern_type IN ('workflow', 'tool_usage')
            AND is_actionable = 1
            AND occurrences >= 10
        """)
        rows = cursor.fetchall()
        conn.close()

        if rows:
            insights.append({
                "type": "best_practice",
                "title": "Established workflows detected",
                "description": f"You have {len(rows)} well-established patterns. Consider documenting them.",
                "evidence": {"pattern_count": len(rows)},
                "confidence": 0.9,
                "actions": ["Document workflows", "Share with team", "Create templates"]
            })

        return insights


class AnomalyDetector:
    """Detects anomalies in user behavior."""

    def __init__(self):
        self.baselines = {}

    def update_baseline(self, metric_name: str, value: float):
        """Update baseline for a metric."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO behavior_baseline (id, metric_name, baseline_value, current_value, deviation, last_updated)
            VALUES (?, ?, ?, ?, 0, ?)
            ON CONFLICT(id) DO UPDATE SET
                baseline_value = (baseline_value + excluded.baseline_value) / 2,
                current_value = excluded.current_value,
                deviation = ABS(excluded.current_value - baseline_value) / baseline_value,
                last_updated = excluded.last_updated
        """, (f"baseline_{metric_name}", metric_name, value, value, time.time()))
        conn.commit()
        conn.close()

    def check_anomaly(self, metric_name: str, value: float, threshold: float = 2.0) -> Optional[Dict]:
        """Check if value is anomalous."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT baseline_value FROM behavior_baseline WHERE metric_name = ?", (metric_name,))
        row = cursor.fetchone()
        conn.close()

        if not row or row[0] == 0:
            return None

        baseline = row[0]
        deviation = abs(value - baseline) / baseline if baseline else 0

        if deviation > threshold:
            severity = "high" if deviation > 3.0 else "medium" if deviation > 2.0 else "low"
            anomaly_id = f"anom_{int(time.time() * 1000) % 100000000:08d}"

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO anomalies (id, anomaly_type, description, severity, context, detected_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (anomaly_id, "metric_deviation",
                  f"{metric_name} deviated {deviation:.1%} from baseline",
                  severity, json.dumps({"metric": metric_name, "value": value, "baseline": baseline}),
                  time.time()))
            conn.commit()
            conn.close()

            return {"id": anomaly_id, "metric": metric_name, "deviation": deviation, "severity": severity}
        return None

    def get_unresolved_anomalies(self) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM anomalies WHERE resolved_at IS NULL AND is_false_positive = 0
            ORDER BY severity DESC, detected_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "type": r[1], "description": r[2], "severity": r[3],
             "context": json.loads(r[4]) if r[4] else {}, "detected_at": r[5]}
            for r in rows
        ]


class PassiveMentor:
    """Main passive mentor coordinator."""

    def __init__(self):
        self.pattern_recognizer = PatternRecognizer()
        self.proactive_guidance = ProactiveGuidance()
        self.insight_generator = InsightGenerator()
        self.anomaly_detector = AnomalyDetector()
        self.running = False
        self.worker_thread = None

    def start(self):
        """Start background mentor processes."""
        if self.running:
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._background_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

    def _background_loop(self):
        while self.running:
            try:
                self._process_cycle()
            except Exception as e:
                print(f"Mentor background error: {e}")
            time.sleep(60)  # Run every minute

    def _process_cycle(self):
        # Update behavior baselines
        self._update_baselines()

        # Detect anomalies
        self._check_anomalies()

        # Generate proactive suggestions
        self._generate_suggestions()

        # Generate insights periodically
        if int(time.time()) % 3600 == 0:  # Every hour
            self._generate_insights()

    def _update_baselines(self):
        # Update command frequency baseline
        conn = get_connection()
        cursor = get_connection().cursor()
        cursor.execute("SELECT COUNT(*) FROM command_history WHERE timestamp > ?", (time.time() - 3600,))
        cmd_count = cursor.fetchone()[0]
        conn.close()

        self.anomaly_detector.update_baseline("commands_per_hour", cmd_count)

    def _check_anomalies(self):
        # Check for unusual patterns
        conn = get_connection()
        cursor = get_connection().cursor()
        cursor.execute("SELECT COUNT(*) FROM command_history WHERE timestamp > ?", (time.time() - 3600,))
        cmd_count = cursor.fetchone()[0]
        conn.close()

        self.anomaly_detector.check_anomaly("commands_per_hour", cmd_count)

    def _generate_suggestions(self):
        context = self._get_current_context()
        suggestions = self.proactive_guidance.generate_suggestions(context)

        for suggestion in suggestions:
            self._store_suggestion(suggestion)

    def _generate_insights(self):
        insights = self.insight_generator.generate_insights()
        for insight in insights:
            self._store_insight(insight)

    def _get_current_context(self) -> Dict:
        return {
            "current_project": self._get_current_project(),
            "time_of_day": datetime.now().hour,
            "recent_commands": self._get_recent_commands(10)
        }

    def _get_current_project(self) -> Optional[str]:
        # Would integrate with project_awareness
        return None

    def _get_recent_commands(self, limit: int) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT command, normalized_command, intent, timestamp
            FROM command_history
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"command": r[0], "normalized": r[1], "intent": r[2], "timestamp": r[3]}
            for r in rows
        ]

    def _store_suggestion(self, suggestion: ProactiveSuggestion):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO proactive_suggestions (id, trigger_type, suggestion_text, context, priority, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (suggestion.id, suggestion.trigger_type, suggestion.suggestion_text,
              json.dumps(suggestion.context), suggestion.priority, suggestion.status, suggestion.created_at))
        conn.commit()
        conn.close()

    def _store_insight(self, insight: Dict):
        insight_id = f"ins_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO learning_insights (id, insight_type, title, description, evidence, confidence, action_items, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (insight_id, insight["type"], insight["title"], insight["description"],
              json.dumps(insight.get("evidence", {})), insight["confidence"],
              json.dumps(insight.get("actions", [])), time.time()))
        conn.commit()
        conn.close()

    def record_command(self, command: str, normalized: str, intent: str, timestamp: float = None):
        """Record a command for pattern analysis."""
        timestamp = timestamp or time.time()
        session_id = get_current_session()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO command_history (session_id, command, normalized_command, intent, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, command, normalized, intent, timestamp))
        conn.commit()
        conn.close()

        # Trigger pattern analysis
        self._analyze_recent_commands()

    def _analyze_recent_commands(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT command, normalized_command, intent, timestamp
            FROM command_history
            ORDER BY timestamp DESC LIMIT 50
        """)
        rows = cursor.fetchall()
        conn.close()

        commands = [
            {"command": r[0], "normalized": r[1], "intent": r[2], "timestamp": r[3]}
            for r in rows
        ]

        patterns = self.pattern_recognizer.analyze_command_sequence(commands)
        for pattern in patterns:
            self._store_pattern(pattern)

    def _store_pattern(self, pattern: ObservedPattern):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO observed_patterns (id, pattern_type, pattern_data, confidence, occurrences, first_seen, last_seen, is_actionable)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (pattern.id, pattern.pattern_type, json.dumps(pattern.pattern_data),
              pattern.confidence, pattern.occurrences, pattern.first_seen, pattern.last_seen, pattern.is_actionable))
        conn.commit()
        conn.close()

    def get_pending_suggestions(self, limit: int = 5) -> List[ProactiveSuggestion]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM proactive_suggestions
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [
            ProactiveSuggestion(
                id=r[0], trigger_type=r[1], suggestion_text=r[2],
                context=json.loads(r[3]) if r[3] else {},
                priority=r[4], status=r[5], created_at=r[6],
                shown_at=r[7], resolved_at=r[8]
            )
            for r in rows
        ]

    def mark_suggestion_shown(self, suggestion_id: str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE proactive_suggestions SET status = 'shown', shown_at = ? WHERE id = ?", (time.time(), suggestion_id))
        conn.commit()
        conn.close()

    def mark_suggestion_accepted(self, suggestion_id: str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE proactive_suggestions SET status = 'accepted', resolved_at = ? WHERE id = ?", (time.time(), suggestion_id))
        conn.commit()
        conn.close()

    def mark_suggestion_dismissed(self, suggestion_id: str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE proactive_suggestions SET status = 'dismissed', resolved_at = ? WHERE id = ?", (time.time(), suggestion_id))
        conn.commit()
        conn.close()

    def get_insights(self, limit: int = 20) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM learning_insights ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "type": r[1], "title": r[2], "description": r[3],
             "evidence": json.loads(r[4]) if r[4] else {},
             "confidence": r[5], "actions": json.loads(r[6]) if r[6] else [],
             "created_at": r[7], "acknowledged_at": r[7]}
            for r in rows
        ]

    def get_anomalies(self) -> List[Dict]:
        return self.anomaly_detector.get_unresolved_anomalies()

    def resolve_anomaly(self, anomaly_id: str, is_false_positive: bool = False):
        conn = get_connection()
        cursor = conn.cursor()
        if is_false_positive:
            cursor.execute("UPDATE anomalies SET is_false_positive = 1, resolved_at = ? WHERE id = ?", (time.time(), anomaly_id))
        else:
            cursor.execute("UPDATE anomalies SET resolved_at = ? WHERE id = ?", (time.time(), anomaly_id))
        conn.commit()
        conn.close()


# Global instance
passive_mentor = PassiveMentor()


# Voice command integration
def mentor_debug() -> str:
    suggestions = passive_mentor.get_pending_suggestions(5)
    insights = passive_mentor.get_insights(5)
    anomalies = passive_mentor.get_anomalies()

    output = f"Passive Mentor Status:\n"
    output += f"Pending suggestions: {len(suggestions)}\n"
    output += f"Recent insights: {len(insights)}\n"
    output += f"Active anomalies: {len(anomalies)}\n"

    if suggestions:
        output += "\nTop suggestions:\n"
        for s in suggestions[:3]:
            output += f"  • {s.suggestion_text} (priority: {s.priority})\n"

    if anomalies:
        output += "\nActive anomalies:\n"
        for a in anomalies[:3]:
            output += f"  • {a['description']} ({a['severity']})\n"

    return output


def mentor_suggestions() -> str:
    suggestions = passive_mentor.get_pending_suggestions(5)
    if not suggestions:
        return "No pending suggestions."
    output = "Proactive suggestions:\n"
    for i, s in enumerate(suggestions, 1):
        output += f"{i}. {s.suggestion_text} (priority: {s.priority})\n"
    return output


def mentor_insights() -> str:
    insights = passive_mentor.get_insights(5)
    if not insights:
        return "No insights yet."
    output = "Learning insights:\n"
    for i, ins in enumerate(insights, 1):
        output += f"{i}. {ins['title']}: {ins['description'][:100]}...\n"
    return output


def mentor_anomalies() -> str:
    anomalies = passive_mentor.get_anomalies()
    if not anomalies:
        return "No active anomalies."
    output = "Active anomalies:\n"
    for a in anomalies:
        output += f"• {a['description']} ({a['severity']})\n"
    return output


if __name__ == "__main__":
    print("Passive Mentor module loaded.")
    print("Available functions:")
    print("  mentor.start() / mentor.stop()")
    print("  mentor.record_command(command, normalized, intent)")
    print("  mentor.get_pending_suggestions()")
    print("  mentor.get_insights()")
    print("  mentor.get_anomalies()")
    print("  mentor.resolve_anomaly(id)")
    print("  mentor_debug() / mentor_suggestions() / mentor_insights() / mentor_anomalies()")