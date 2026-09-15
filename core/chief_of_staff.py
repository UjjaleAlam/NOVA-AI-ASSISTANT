"""
Chief of Staff Agent - Phase 38
Daily priorities, time planning, progress reviews, executive reports,
strategic planning, decision assistance, reality checking, workload awareness,
blocker detection, priority management.
"""

import json
import time
import threading
import os
import sqlite3
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

DB_DIR = "database"
COS_DB = os.path.join(DB_DIR, "chief_of_staff.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_cos_connection():
    import sqlite3
    conn = sqlite3.connect(COS_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_cos_db():
    conn = get_cos_connection()
    cursor = conn.cursor()

    # Priority engine configuration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS priority_config (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            weights TEXT NOT NULL,  -- JSON: importance, urgency, goal_alignment, deadline, dependencies, effort, risk, impact
            is_default BOOLEAN DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Task priorities (computed)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_priorities (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            score REAL NOT NULL,
            breakdown TEXT,  -- JSON: score per factor
            rank INTEGER,
            computed_at REAL NOT NULL,
            config_id TEXT,
            FOREIGN KEY (config_id) REFERENCES priority_config(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_priorities_task ON task_priorities(task_id)
    """)

    # Daily plans
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_plans (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,  -- YYYY-MM-DD
            total_hours REAL DEFAULT 8,
            scheduled_tasks TEXT,  -- JSON array
            buffer_minutes INTEGER DEFAULT 60,
            focus_blocks TEXT,  -- JSON array
            meetings TEXT,  -- JSON array
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Executive reports
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS executive_reports (
            id TEXT PRIMARY KEY,
            report_type TEXT NOT NULL,  -- 'daily', 'weekly', 'monthly', 'quarterly', 'custom'
            period_start REAL NOT NULL,
            period_end REAL NOT NULL,
            content TEXT NOT NULL,
            metrics TEXT,  -- JSON
            insights TEXT,  -- JSON
            recommendations TEXT,  -- JSON
            generated_at REAL NOT NULL
        )
    """)

    # Strategic plans
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategic_plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            horizon TEXT,  -- 'quarterly', 'yearly', 'multi_year'
            objectives TEXT,  -- JSON array
            initiatives TEXT,  -- JSON array
            kpis TEXT,  -- JSON array
            status TEXT DEFAULT 'draft',  -- 'draft', 'active', 'completed', 'archived'
            owner TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Decisions log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions_log (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            context TEXT,
            options TEXT,  -- JSON array
            chosen_option TEXT,
            rationale TEXT,
            impact_areas TEXT,  -- JSON array
            confidence REAL,
            status TEXT DEFAULT 'pending',  -- 'pending', 'executed', 'deferred', 'rejected'
            decision_maker TEXT,
            created_at REAL NOT NULL,
            executed_at REAL
        )
    """)

    # Workload snapshots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workload_snapshots (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            active_tasks INTEGER,
            overdue_tasks INTEGER,
            avg_priority REAL,
            resource_utilization TEXT,  -- JSON
            team_capacity TEXT,  -- JSON if multi-user
            notes TEXT
        )
    """)

    conn.commit()
    conn.close()


init_cos_db()


# ============================================================
# PRIORITY ENGINE
# ============================================================

class PriorityFactor(Enum):
    IMPORTANCE = "importance"           # How important is this task (1-10)
    URGENCY = "urgency"                 # Time sensitivity (1-10)
    GOAL_ALIGNMENT = "goal_alignment"   # Alignment with strategic goals (0-1)
    DEADLINE = "deadline"               # Days until deadline (normalized)
    DEPENDENCIES = "dependencies"       # Number of blocking dependencies
    EFFORT = "effort"                   # Estimated effort hours
    RISK = "risk"                       # Risk level (1-10)
    IMPACT = "impact"                   # Expected impact (1-10)


@dataclass
class PriorityWeights:
    importance: float = 0.20
    urgency: float = 0.20
    goal_alignment: float = 0.15
    deadline: float = 0.15
    dependencies: float = 0.10
    effort: float = 0.05
    risk: float = 0.05
    impact: float = 0.10

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'PriorityWeights':
        return cls(**data)


@dataclass
class PriorityBreakdown:
    task_id: str
    total_score: float
    factors: Dict[str, float]
    raw_values: Dict[str, float]
    rank: int = 0


class PriorityEngine:
    """Calculates task priorities based on multiple factors."""

    def __init__(self, weights: PriorityWeights = None):
        self.weights = weights or PriorityWeights()
        self._load_default_config()

    def _load_default_config(self):
        """Load default priority configuration."""
        conn = get_cos_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM priority_config WHERE is_default = 1 LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            weights_data = json.loads(row[2])
            self.weights = PriorityWeights.from_dict(weights_data)

    def save_config(self, name: str = "default", is_default: bool = True):
        """Save current weights as configuration."""
        conn = get_cos_connection()
        cursor = conn.cursor()

        if is_default:
            cursor.execute("UPDATE priority_config SET is_default = 0 WHERE is_default = 1")

        config_id = f"cfg_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO priority_config (id, name, weights, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (config_id, name, json.dumps(self.weights.to_dict()), is_default, time.time(), time.time()))
        conn.commit()
        conn.close()

    def calculate_priority(self, task: Dict, context: Dict = None) -> PriorityBreakdown:
        """Calculate priority score for a single task."""
        context = context or {}
        goals = context.get("goals", [])
        all_tasks = context.get("all_tasks", [])

        # Extract raw values
        raw = {}

        # Importance (1-10)
        raw["importance"] = task.get("importance", task.get("priority", 5))
        if raw["importance"] > 10:
            raw["importance"] = 10

        # Urgency (1-10) - based on deadline proximity
        raw["urgency"] = self._calculate_urgency(task)

        # Goal alignment (0-1)
        raw["goal_alignment"] = self._calculate_goal_alignment(task, goals)

        # Deadline (normalized 0-1, closer = higher)
        raw["deadline"] = self._calculate_deadline_score(task)

        # Dependencies (0-1, fewer blocking = higher)
        raw["dependencies"] = self._calculate_dependencies(task, all_tasks)

        # Effort (0-1, less effort = higher for quick wins)
        raw["effort"] = self._calculate_effort_score(task)

        # Risk (1-10, lower risk = higher priority for stable work)
        raw["risk"] = task.get("risk", 5)

        # Impact (1-10)
        raw["impact"] = task.get("impact", task.get("expected_impact", 5))

        # Normalize and weight
        factors = {}
        for factor, weight in self.weights.to_dict().items():
            normalized = self._normalize_factor(factor, raw[factor])
            factors[factor] = normalized * weight

        total_score = sum(factors.values())

        return PriorityBreakdown(
            task_id=task.get("id", ""),
            total_score=total_score,
            factors=factors,
            raw_values=raw
        )

    def _calculate_urgency(self, task: Dict) -> float:
        """Calculate urgency based on deadline proximity."""
        due = task.get("due_date") or task.get("deadline")
        if not due:
            return 3.0  # Default medium-low urgency

        now = time.time()
        days_left = (due - now) / 86400

        if days_left <= 0:
            return 10.0
        elif days_left <= 1:
            return 9.0
        elif days_left <= 2:
            return 8.0
        elif days_left <= 3:
            return 7.0
        elif days_left <= 7:
            return 5.0
        elif days_left <= 14:
            return 3.0
        else:
            return 1.0

    def _calculate_goal_alignment(self, task: Dict, goals: List[Dict]) -> float:
        """Calculate how well task aligns with active goals."""
        if not goals:
            return 0.5

        task_tags = set(task.get("tags", []))
        task_project = task.get("project_id", "")

        max_alignment = 0.0
        for goal in goals:
            alignment = 0.0
            goal_tags = set(goal.get("tags", []))
            goal_project = goal.get("project_id", "")

            # Tag overlap
            if task_tags and goal_tags:
                overlap = len(task_tags & goal_tags) / len(task_tags | goal_tags)
                alignment += overlap * 0.5

            # Project match
            if task_project and task_project == goal_project:
                alignment += 0.5

            max_alignment = max(max_alignment, alignment)

        return max_alignment

    def _calculate_deadline_score(self, task: Dict) -> float:
        """Normalized deadline score (closer = higher)."""
        due = task.get("due_date") or task.get("deadline")
        if not due:
            return 0.2

        now = time.time()
        days_left = (due - now) / 86400

        if days_left <= 0:
            return 1.0
        elif days_left <= 1:
            return 0.9
        elif days_left <= 3:
            return 0.7
        elif days_left <= 7:
            return 0.5
        elif days_left <= 14:
            return 0.3
        else:
            return 0.1

    def _calculate_dependencies(self, task: Dict, all_tasks: List[Dict]) -> float:
        """Score based on how many tasks depend on this one."""
        task_id = task.get("id", "")
        if not task_id or not all_tasks:
            return 0.5

        dependents = sum(1 for t in all_tasks
                         if task_id in t.get("depends_on", []))

        # More dependents = higher priority (unblock others)
        if dependents >= 5:
            return 1.0
        elif dependents >= 3:
            return 0.8
        elif dependents >= 1:
            return 0.6
        else:
            return 0.4

    def _calculate_effort_score(self, task: Dict) -> float:
        """Quick wins get higher priority."""
        effort = task.get("estimated_hours", task.get("effort", 4))
        if effort <= 1:
            return 1.0
        elif effort <= 2:
            return 0.8
        elif effort <= 4:
            return 0.6
        elif effort <= 8:
            return 0.4
        else:
            return 0.2

    def _normalize_factor(self, factor: str, value: float) -> float:
        """Normalize factor to 0-1 range."""
        if factor in ["importance", "urgency", "risk", "impact"]:
            return value / 10.0
        return value  # Already 0-1

    def rank_tasks(self, tasks: List[Dict], context: Dict = None) -> List[Dict]:
        """Rank tasks by priority score."""
        breakdowns = []
        for task in tasks:
            bd = self.calculate_priority(task, context)
            breakdowns.append((task, bd))

        # Sort by score descending
        breakdowns.sort(key=lambda x: x[1].total_score, reverse=True)

        # Add rank
        ranked = []
        for rank, (task, bd) in enumerate(breakdowns, 1):
            task_copy = task.copy()
            task_copy["priority_score"] = bd.total_score
            task_copy["priority_breakdown"] = bd.factors
            task_copy["priority_rank"] = rank
            ranked.append(task_copy)

            # Persist
            self._persist_priority(task.get("id", ""), bd, self.weights)

        return ranked

    def _persist_priority(self, task_id: str, breakdown: PriorityBreakdown, weights: PriorityWeights):
        """Persist priority calculation."""
        if not task_id:
            return
        for attempt in range(3):
            try:
                conn = get_cos_connection()
                cursor = conn.cursor()
                priority_id = f"pri_{int(time.time() * 1000) % 100000000:08d}"
                cursor.execute("""
                    INSERT OR REPLACE INTO task_priorities (id, task_id, score, breakdown, rank, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (priority_id, task_id, breakdown.total_score,
                      json.dumps(breakdown.factors), breakdown.rank, time.time()))
                conn.commit()
                conn.close()
                return
            except sqlite3.OperationalError as e:
                if "readonly" in str(e).lower() or "locked" in str(e).lower():
                    time.sleep(0.01 * (attempt + 1))
                    continue
                raise


# ============================================================
# CHIEF OF STAFF AGENT
# ============================================================

class ChiefOfStaff:
    """Main Chief of Staff agent."""

    def __init__(self):
        self.priority_engine = PriorityEngine()
        self.running = False
        self.worker_thread = None

    def start(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

    def _worker_loop(self):
        while self.running:
            try:
                self._detect_blockers()
                self._monitor_workload()
                time.sleep(300)  # Every 5 minutes
            except Exception as e:
                print(f"Chief of Staff error: {e}")
                time.sleep(60)

    # ==========================================
    # PRIORITY MANAGEMENT
    # ==========================================

    def get_prioritized_tasks(self, tasks: List[Dict], context: Dict = None, limit: int = 20) -> List[Dict]:
        """Get tasks ranked by priority."""
        return self.priority_engine.rank_tasks(tasks, context)[:limit]

    def get_top_priorities(self, limit: int = 10) -> List[Dict]:
        """Get top priority tasks from queue."""
        from core.multi_agent import task_queue
        tasks = task_queue.get_tasks(status="pending")
        context = {"goals": self._get_active_goals(), "all_tasks": tasks}
        return self.get_prioritized_tasks(tasks, context, limit)

    def _get_active_goals(self) -> List[Dict]:
        try:
            from core.goal_awareness import get_active_goals_summary
            summary = get_active_goals_summary()
            return summary.get("goals", [])
        except:
            return []

    # ==========================================
    # DAILY PLANNING
    # ==========================================

    def create_daily_plan(self, date: str = None) -> Dict:
        """Create optimized daily plan."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        dt = datetime.strptime(date, "%Y-%m-%d")
        day_start = dt.replace(hour=8, minute=0).timestamp()
        day_end = dt.replace(hour=18, minute=0).timestamp()

        # Get pending tasks
        from core.multi_agent import task_queue

        pending = task_queue.get_tasks(status="pending")
        events = []

        # Try to get calendar events if available
        try:
            from core.context_engine import get_events
            events = get_events(day_start, day_end)
        except ImportError:
            events = []
        except Exception:
            events = []

        # Rank tasks
        context = {"goals": self._get_active_goals(), "all_tasks": pending}
        ranked = self.get_prioritized_tasks(pending, context)

        # Schedule into day
        scheduled = []
        remaining_hours = 8.0
        current_time = day_start

        # Add fixed events first
        fixed_events = []
        for event in events:
            if event.get("start_time") and event.get("end_time"):
                fixed_events.append({
                    "type": "meeting",
                    "title": event.get("title", "Meeting"),
                    "start": event["start_time"],
                    "end": event["end_time"],
                    "duration": (event["end_time"] - event["start_time"]) / 3600
                })
                remaining_hours -= (event["end_time"] - event["start_time"]) / 3600

        # Schedule tasks around events
        for task in ranked:
            if remaining_hours <= 0.5:
                break

            est_hours = task.get("estimated_hours", 1)
            if est_hours <= remaining_hours:
                # Find slot
                slot = self._find_time_slot(current_time, est_hours * 3600, fixed_events, day_end)
                if slot:
                    scheduled.append({
                        "task_id": task["id"],
                        "title": task.get("title", task.get("payload", {}).get("description", "Task")),
                        "start": slot,
                        "end": slot + est_hours * 3600,
                        "duration_hours": est_hours,
                        "priority": task.get("priority_score", 0)
                    })
                    current_time = slot + est_hours * 3600 + 900  # 15 min buffer
                    remaining_hours -= est_hours + 0.25

        # Add focus blocks
        focus_blocks = self._create_focus_blocks(scheduled, day_start, day_end)

        plan = {
            "date": date,
            "total_hours": 8.0,
            "scheduled_tasks": scheduled,
            "focus_blocks": focus_blocks,
            "meetings": fixed_events,
            "buffer_minutes": int(remaining_hours * 60),
            "created_at": time.time()
        }

        # Persist
        self._save_daily_plan(date, plan)
        return plan

    def _find_time_slot(self, start: float, duration: float, events: List[Dict], day_end: float) -> Optional[float]:
        """Find available time slot."""
        current = start
        for event in sorted(events, key=lambda x: x["start"]):
            if current + duration <= event["start"]:
                return current
            current = max(current, event["end"])

        if current + duration <= day_end:
            return current
        return None

    def _create_focus_blocks(self, scheduled: List[Dict], day_start: float, day_end: float) -> List[Dict]:
        """Create deep work focus blocks."""
        blocks = []
        current = day_start

        for task in scheduled:
            if current < task["start"] - 1800:  # 30 min gap
                gap = task["start"] - current
                if gap >= 3600:  # At least 1 hour
                    blocks.append({
                        "type": "deep_work",
                        "start": current,
                        "end": task["start"],
                        "duration_hours": gap / 3600
                    })
            current = task["end"] + 900  # 15 min buffer

        # End of day block
        if current < day_end - 3600:
            blocks.append({
                "type": "deep_work",
                "start": current,
                "end": day_end,
                "duration_hours": (day_end - current) / 3600
            })

        return blocks

    def _save_daily_plan(self, date: str, plan: Dict):
        conn = get_cos_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO daily_plans (id, date, total_hours, scheduled_tasks, buffer_minutes, focus_blocks, meetings, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"plan_{date}", date, plan["total_hours"],
              json.dumps(plan["scheduled_tasks"]), plan["buffer_minutes"],
              json.dumps(plan["focus_blocks"]), json.dumps(plan["meetings"]),
              time.time(), time.time()))
        conn.commit()
        conn.close()

    def get_daily_plan(self, date: str = None) -> Optional[Dict]:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = get_cos_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_plans WHERE date = ?", (date,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0], "date": row[1], "total_hours": row[2],
                "scheduled_tasks": json.loads(row[3]) if row[3] else [],
                "buffer_minutes": row[4],
                "focus_blocks": json.loads(row[5]) if row[5] else [],
                "meetings": json.loads(row[6]) if row[6] else [],
                "created_at": row[7], "updated_at": row[8]
            }
        return None

    # ==========================================
    # BRIEFINGS & REPORTS
    # ==========================================

    def generate_morning_briefing(self) -> str:
        """Generate executive morning briefing."""
        plan = self.get_daily_plan()
        top_priorities = self.get_top_priorities(5)

        briefing = f"Good morning! {datetime.now().strftime('%A, %B %d')}\n\n"

        if plan:
            briefing += f"[+] Today's Plan ({len(plan['scheduled_tasks'])} tasks, {plan['buffer_minutes']}min buffer)\n"
            for task in plan["scheduled_tasks"][:3]:
                start = datetime.fromtimestamp(task["start"]).strftime("%H:%M")
                end = datetime.fromtimestamp(task["end"]).strftime("%H:%M")
                briefing += f"  {start}-{end}: {task['title']}\n"

        briefing += f"\n[!] Top Priorities:\n"
        for i, task in enumerate(top_priorities, 1):
            briefing += f"  {i}. {task.get('title', task.get('payload', {}).get('description', 'Task'))}\n"

        # Add workload summary
        from core.multi_agent import orchestrator
        status = orchestrator.get_system_status()
        briefing += f"\n[E] Agent Status: {status['idle_agents']}/{status['total_agents']} idle\n"

        # Add goal progress
        goals = self._get_active_goals()
        if goals:
            avg_progress = sum(g.get("progress", 0) for g in goals) / len(goals)
            briefing += f"[+] Goal Progress: {avg_progress:.0f}% avg\n"

        return briefing

    def generate_evening_report(self) -> str:
        """Generate end-of-day report."""
        plan = self.get_daily_plan()

        report = f"Evening Report - {datetime.now().strftime('%A, %B %d')}\n\n"

        if plan:
            completed = sum(1 for t in plan["scheduled_tasks"]
                            if t.get("status") == "completed")
            total = len(plan["scheduled_tasks"])
            report += f"Tasks: {completed}/{total} completed\n"

            if completed < total:
                report += f"Remaining: {total - completed} tasks\n"

        # Add metrics
        from core.multi_agent import task_queue
        completed_today = task_queue.get_tasks(status="completed")
        report += f"Total Completed: {len(completed_today)}\n"

        return report

    def generate_weekly_report(self) -> Dict:
        """Generate weekly executive report."""
        end = time.time()
        start = end - 7 * 86400

        from core.multi_agent import task_queue
        tasks = task_queue.get_tasks()

        week_tasks = [t for t in tasks if t.get("created_at", 0) >= start]
        completed = [t for t in week_tasks if t.get("status") == "completed"]

        # By priority
        by_priority = {}
        for t in week_tasks:
            p = t.get("priority", 3)
            by_priority[p] = by_priority.get(p, 0) + 1

        # By type
        by_type = {}
        for t in week_tasks:
            typ = t.get("task_type", "unknown")
            by_type[typ] = by_type.get(typ, 0) + 1

        report = {
            "period": "weekly",
            "start": datetime.fromtimestamp(start).isoformat(),
            "end": datetime.fromtimestamp(end).isoformat(),
            "total_tasks": len(week_tasks),
            "completed": len(completed),
            "completion_rate": len(completed) / len(week_tasks) if week_tasks else 0,
            "by_priority": by_priority,
            "by_type": by_type,
            "generated_at": time.time()
        }

        # Save
        self._save_report(report)
        return report

    def _save_report(self, report: Dict):
        conn = get_cos_connection()
        cursor = conn.cursor()
        report_id = f"rpt_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO executive_reports (id, report_type, period_start, period_end, content, generated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (report_id, report.get("period", "weekly"),
              report.get("start", 0), report.get("end", 0),
              json.dumps(report), time.time()))
        conn.commit()
        conn.close()

    # ==========================================
    # BLOCKER DETECTION & WORKLOAD AWARENESS
    # ==========================================

    def _detect_blockers(self):
        """Detect and alert on blockers."""
        from core.multi_agent import task_queue

        # Stalled tasks
        in_progress = task_queue.get_tasks(status="in_progress")
        for task in in_progress:
            started = task.get("started_at", 0)
            if started and time.time() - started > 7200:  # 2 hours
                self._alert_blocker(task, "stalled", f"Task running >2hrs: {task.get('task_type')}")

        # Overdue tasks
        pending = task_queue.get_tasks(status="pending")
        for task in pending:
            due = task.get("due_date") or task.get("deadline")
            if due and due < time.time():
                days_overdue = (time.time() - due) / 86400
                if days_overdue > 1:
                    self._alert_blocker(task, "overdue", f"Overdue {days_overdue:.1f} days")

        # Dependency blockers
        pending = task_queue.get_tasks(status="pending")
        for task in pending:
            deps = task.get("depends_on", [])
            if deps:
                for dep in deps:
                    dep_task = task_queue.get_task_status(dep)
                    if dep_task and dep_task["status"] in ["failed", "cancelled"]:
                        self._alert_blocker(task, "dependency_failed", f"Dependency {dep} failed")

    def _alert_blocker(self, task: Dict, blocker_type: str, message: str):
        """Alert on blocker (could send notification)."""
        print(f"[BLOCKER] {blocker_type}: {message}")

        # Log to timeline
        try:
            from core.timeline_memory import event_store as timeline_memory
            timeline_memory.log_event(
                event_type="blocker",
                category="system",
                title=f"Blocker: {blocker_type}",
                description=message,
                tags=["blocker", blocker_type, task.get("id", "")]
            )
        except:
            pass

    def _monitor_workload(self):
        """Monitor system workload."""
        from core.multi_agent import task_queue, registry

        pending = len(task_queue.get_tasks(status="pending"))
        in_progress = len(task_queue.get_tasks(status="in_progress"))
        overdue = len(task_queue.get_overdue_tasks())

        agents = registry.get_all_agents()
        idle = len([a for a in agents if a["status"] == "idle"])
        busy = len([a for a in agents if a["status"] == "busy"])

        # Record snapshot
        conn = get_cos_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workload_snapshots (id, timestamp, active_tasks, overdue_tasks, avg_priority, resource_utilization, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (f"wl_{int(time.time())}", time.time(), in_progress, overdue, 0,
              json.dumps({"pending": pending, "in_progress": in_progress, "idle_agents": idle, "busy_agents": busy}),
              f"Workload: {pending} pending, {in_progress} active"))
        conn.commit()
        conn.close()

        # Alert if overloaded
        if pending > 50:
            print(f"[WORKLOAD] High pending queue: {pending} tasks")

    # ==========================================
    # DECISION SUPPORT
    # ==========================================

    def log_decision(self, title: str, context: str, options: List[Dict],
                     chosen: str, rationale: str, confidence: float = 0.8) -> str:
        """Log a decision for audit trail."""
        conn = get_cos_connection()
        cursor = conn.cursor()
        decision_id = f"dec_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO decisions_log (id, title, context, options, chosen_option, rationale, confidence, status, decision_maker, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'executed', 'chief_of_staff', ?)
        """, (decision_id, title, context, json.dumps(options), chosen, rationale, confidence, time.time()))
        conn.commit()
        conn.close()
        return decision_id

    def get_decision_history(self, limit: int = 20) -> List[Dict]:
        conn = get_cos_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM decisions_log ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "title": r[1], "context": r[2], "options": json.loads(r[3]) if r[3] else [],
             "chosen": r[4], "rationale": r[5], "confidence": r[6], "status": r[7],
             "maker": r[8], "created": r[9], "executed": r[10]}
            for r in rows
        ]

    # ==========================================
    # STRATEGIC PLANNING
    # ==========================================

    def create_strategic_plan(self, name: str, description: str, horizon: str,
                              objectives: List[Dict], initiatives: List[Dict],
                              kpis: List[Dict]) -> str:
        """Create a strategic plan."""
        conn = get_cos_connection()
        cursor = conn.cursor()
        plan_id = f"sp_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO strategic_plans (id, name, description, horizon, objectives, initiatives, kpis, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)
        """, (plan_id, name, description, horizon,
              json.dumps(objectives), json.dumps(initiatives), json.dumps(kpis),
              time.time(), time.time()))
        conn.commit()
        conn.close()
        return plan_id

    def get_strategic_plan(self, plan_id: str) -> Optional[Dict]:
        conn = get_cos_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM strategic_plans WHERE id = ?", (plan_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "horizon": row[3], "objectives": json.loads(row[4]) if row[4] else [],
                "initiatives": json.loads(row[5]) if row[5] else [],
                "kpis": json.loads(row[6]) if row[6] else [],
                "status": row[7], "owner": row[8],
                "created": row[9], "updated": row[10]
            }
        return None

    # ==========================================
    # VOICE COMMANDS
    # ==========================================

    def handle_command(self, command: str) -> Optional[str]:
        """Handle voice commands for Chief of Staff."""
        cmd = command.lower().strip()

        if cmd in ["morning briefing", "daily briefing", "brief me"]:
            return self.generate_morning_briefing()

        if cmd in ["evening report", "end of day report", "daily report"]:
            return self.generate_evening_report()

        if cmd in ["weekly report", "week report"]:
            report = self.generate_weekly_report()
            return f"Weekly Report: {report['completed']}/{report['total_tasks']} tasks completed ({report['completion_rate']:.0%})"

        if cmd in ["today's plan", "daily plan", "plan my day"]:
            plan = self.create_daily_plan()
            if plan:
                lines = [f"Daily Plan for {plan['date']}:"]
                for t in plan["scheduled_tasks"][:5]:
                    start = datetime.fromtimestamp(t["start"]).strftime("%H:%M")
                    lines.append(f"  {t['title']} at {datetime.fromtimestamp(t['start']).strftime('%H:%M')}")
                return "\n".join(lines)
            return "No plan created yet."

        if cmd.startswith("prioritize ") or cmd.startswith("rank tasks"):
            return self._handle_prioritize_command(cmd)

        if cmd in ["what's blocking", "blockers", "show blockers"]:
            return self._get_blocker_summary()

        if cmd in ["workload", "workload status", "system load"]:
            return self._get_workload_summary()

        if cmd.startswith("decide ") or cmd.startswith("log decision"):
            return "Use 'decide <title> | <option1> | <option2> | ... | chosen | rationale'"

        return None

    def _handle_prioritize_command(self, cmd: str) -> str:
        from core.multi_agent import task_queue
        tasks = task_queue.get_tasks(status="pending")
        ranked = self.get_prioritized_tasks(tasks, limit=10)
        lines = ["Top Priorities:"]
        for i, t in enumerate(ranked, 1):
            title = t.get("title", t.get("payload", {}).get("description", "Task"))
            lines.append(f"  {i}. {title} (score: {t.get('priority_score', 0):.2f})")
        return "\n".join(lines)

    def _get_blocker_summary(self) -> str:
        # This would check for blockers
        return "Blocker detection runs automatically. Use 'workload' for system status."

    def _get_workload_summary(self) -> str:
        from core.multi_agent import task_queue, registry

        pending = len(task_queue.get_tasks(status="pending"))
        in_progress = len(task_queue.get_tasks(status="in_progress"))
        overdue = len(task_queue.get_overdue_tasks())

        agents = registry.get_all_agents()
        idle = len([a for a in registry.agents.values() if a["status"] == "idle"])
        busy = len([a for a in registry.agents.values() if a["status"] == "busy"])

        return (f"Workload Summary:\n"
                f"  Pending: {pending}\n"
                f"  In Progress: {in_progress}\n"
                f"  Overdue: {overdue}\n"
                f"  Agents: {busy} busy, {len(registry.agents) - busy} idle")


# Global instance
chief_of_staff = ChiefOfStaff()


def start_chief_of_staff():
    chief_of_staff.start()


def stop_chief_of_staff():
    chief_of_staff.stop()


def get_chief_of_staff() -> ChiefOfStaff:
    return chief_of_staff


if __name__ == "__main__":
    print("Chief of Staff Agent - Phase 38")
    print("Features: Priority Engine, Daily Planning, Executive Reports, Blocker Detection, Decision Support")