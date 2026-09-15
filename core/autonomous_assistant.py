"""
Autonomous Assistant - Phase 37
Daily briefings, goal tracking, background monitoring, scheduled tasks,
automatic backup, long-running tasks, task resumption, background coordination.
"""

import json
import time
import threading
import os
import shutil
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from core.multi_agent import orchestrator, registry, task_queue, create_task, get_dashboard, morning_briefing, suggest_schedule
from core.context_engine import get_current_session, build_context_for_llm, get_recent_projects, get_active_tasks
from core.semantic_memory import search_memory, add_memory
from core.background_engine import bg_engine, schedule_job, list_jobs
from core.timeline_memory import event_store as timeline_memory
from core.personal_context import personal_context


class AutonomousMode(Enum):
    PASSIVE = "passive"          # Only respond to user
    REACTIVE = "reactive"        # Respond + react to events
    PROACTIVE = "proactive"      # Suggest actions, monitor
    AUTONOMOUS = "autonomous"    # Full autonomy within bounds


@dataclass
class AutonomousConfig:
    mode: AutonomousMode = AutonomousMode.PROACTIVE
    briefing_enabled: bool = True
    briefing_time: str = "08:00"  # Morning briefing time
    evening_review_enabled: bool = True
    evening_review_time: str = "20:00"
    goal_check_interval: int = 3600  # Check goals every hour
    backup_enabled: bool = True
    backup_interval: int = 86400  # Daily backup
    backup_paths: List[str] = field(default_factory=lambda: ["database", "memory.json"])
    monitoring_enabled: bool = True
    auto_accept_low_risk: bool = True
    notification_threshold: str = "important"  # "all", "important", "critical"


class AutonomousAssistant:
    """Main autonomous assistant coordinator."""

    def __init__(self, config: AutonomousConfig = None):
        self.config = config or AutonomousConfig()
        self.running = False
        self.worker_thread = None
        self.last_briefing = 0
        self.last_evening_review = 0
        self.last_goal_check = 0
        self.last_backup = 0
        self.session_id = get_current_session()
        self._load_state()

    def _load_state(self):
        """Load persistent state."""
        try:
            from core.context_engine import get_preference
            briefing = get_preference("autonomous_last_briefing", 0)
            evening = get_preference("autonomous_last_evening", 0)
            backup = get_preference("autonomous_last_backup", 0)
            self.last_briefing = briefing
            self.last_evening_review = evening
            self.last_backup = backup
        except:
            pass

    def _save_state(self):
        """Save persistent state."""
        try:
            from core.context_engine import set_preference
            set_preference("autonomous_last_briefing", self.last_briefing)
            set_preference("autonomous_last_evening", self.last_evening_review)
            set_preference("autonomous_last_backup", self.last_backup)
        except:
            pass

    def start(self):
        """Start the autonomous assistant."""
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        # Start background engine if not running
        if not bg_engine.running:
            bg_engine.start()
        
        # Schedule daily jobs
        self._schedule_daily_jobs()

    def stop(self):
        """Stop the autonomous assistant."""
        self.running = False
        self._save_state()
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

    def _worker_loop(self):
        """Main autonomous loop."""
        while self.running:
            try:
                now = time.time()
                current_time = datetime.now()

                # Morning briefing
                if self.config.briefing_enabled and self._should_brief(current_time):
                    self._run_morning_briefing()
                    self.last_briefing = now
                    self._save_state()

                # Evening review
                if self.config.evening_review_enabled and self._should_evening_review(current_time):
                    self._run_evening_review()
                    self.last_evening_review = now
                    self._save_state()

                # Goal check
                if now - self.last_goal_check >= self.config.goal_check_interval:
                    self._check_goals()
                    self.last_goal_check = now
                    self._save_state()

                # Backup
                if self.config.backup_enabled and now - self.last_backup >= self.config.backup_interval:
                    self._run_backup()
                    self.last_backup = now
                    self._save_state()

                # Monitor system
                if self.config.monitoring_enabled:
                    self._monitor_system()

                # Process proactive suggestions
                self._process_suggestions()

                time.sleep(60)  # Check every minute

            except Exception as e:
                print(f"Autonomous assistant error: {e}")
                time.sleep(60)

    def _should_brief(self, current_time: datetime) -> bool:
        """Check if it's time for morning briefing."""
        if self.last_briefing == 0:
            return True
        last_brief = datetime.fromtimestamp(self.last_briefing)
        brief_hour, brief_min = map(int, self.config.briefing_time.split(":"))
        target = current_time.replace(hour=brief_hour, minute=brief_min, second=0, microsecond=0)
        return current_time >= target and last_brief < target

    def _should_evening_review(self, current_time: datetime) -> bool:
        """Check if it's time for evening review."""
        if self.last_evening_review == 0:
            return True
        last_evening = datetime.fromtimestamp(self.last_evening_review)
        review_hour, review_min = map(int, self.config.evening_review_time.split(":"))
        target = current_time.replace(hour=review_hour, minute=review_min, second=0, microsecond=0)
        return current_time >= target and last_evening < target

    def _schedule_daily_jobs(self):
        """Schedule recurring daily jobs."""
        # Morning briefing job
        schedule_job(
            name="Morning Briefing",
            task_type="autonomous_briefing",
            payload={"type": "morning"},
            schedule=self.config.briefing_time,
            job_type="recurring",
            priority=1
        )

        # Evening review job
        schedule_job(
            name="Evening Review",
            task_type="autonomous_briefing",
            payload={"type": "evening"},
            schedule=self.config.evening_review_time,
            job_type="recurring",
            priority=1
        )

        # Goal check job (hourly)
        schedule_job(
            name="Goal Check",
            task_type="autonomous_goal_check",
            payload={},
            schedule="3600",  # Every hour
            job_type="recurring",
            priority=3
        )

        # Backup job (daily)
        if self.config.backup_enabled:
            schedule_job(
                name="System Backup",
                task_type="autonomous_backup",
                payload={},
                schedule="86400",  # Daily
                job_type="recurring",
                priority=2
            )

    def _run_morning_briefing(self):
        """Run morning briefing."""
        try:
            briefing = morning_briefing()
            print("\n" + "="*50)
            print("MORNING BRIEFING - " + datetime.now().strftime("%A, %B %d"))
            print("="*50)
            print(briefing)
            print("="*50 + "\n")

            # Speak briefing if voice is available
            from core.signal_bus import signal_bus
            signal_bus.speak.emit(briefing[:500])  # Truncate for voice

            # Log to timeline
            try:
                timeline_memory.log_event(
                    event_type="briefing",
                    category="system",
                    title="Morning Briefing",
                    description=briefing[:200],
                    tags=["briefing", "morning", "autonomous"]
                )
            except:
                pass

        except Exception as e:
            print(f"Morning briefing error: {e}")

    def _run_evening_review(self):
        """Run evening review."""
        try:
            from core.multi_agent import evening_review
            review = evening_review()
            print("\n" + "="*50)
            print("EVENING REVIEW - " + datetime.now().strftime("%A, %B %d"))
            print("="*50)
            print(review)
            print("="*50 + "\n")

            # Log to timeline
            try:
                timeline_memory.log_event(
                    event_type="review",
                    category="system",
                    title="Evening Review",
                    description=review[:200],
                    tags=["review", "evening", "autonomous"]
                )
            except:
                pass

        except Exception as e:
            print(f"Evening review error: {e}")

    def _check_goals(self):
        """Check goal progress and alert on blockers."""
        try:
            from core.goal_awareness import get_active_goals_summary, get_goal
            summary = get_active_goals_summary()
            goals = summary.get("goals", [])
            
            for goal in goals:
                progress = goal.get("progress", 0)
                if progress < 10 and goal.get("target_date"):
                    days_left = (goal["target_date"] - time.time()) / 86400
                    if days_left < 7:
                        self._notify(
                            f"Goal '{goal['title']}' is at {progress:.0f}% with {days_left:.0f} days left",
                            level="warning"
                        )

        except Exception as e:
            print(f"Goal check error: {e}")

    def _run_backup(self):
        """Run system backup."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = Path("backups") / f"backup_{datetime.now().strftime('%Y%m%d')}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            for path in self.config.backup_paths:
                src = Path(path)
                if src.exists():
                    dst = backup_dir / src.name
                    if src.is_dir():
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)

            print(f"Backup completed: {backup_dir}")
            self._notify(f"System backup completed: {backup_dir.name}", level="info")

        except Exception as e:
            print(f"Backup error: {e}")
            self._notify(f"Backup failed: {e}", level="critical")

    def _monitor_system(self):
        """Monitor system health and activity."""
        try:
            # Check system resources
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent

            if cpu > 90 or mem > 90 or disk > 90:
                self._notify(
                    f"High resource usage: CPU={cpu}%, MEM={mem}%, DISK={disk}%",
                    level="warning"
                )

            # Check for stalled tasks
            tasks = task_queue.get_tasks(status="in_progress")
            for task in tasks:
                started = task.get("started_at", 0)
                if started and time.time() - started > 1800:  # 30 minutes
                    self._notify(
                        f"Task {task['id']} running for >30 min: {task.get('task_type')}",
                        level="info"
                    )

        except Exception as e:
            print(f"Monitor error: {e}")

    def _process_suggestions(self):
        """Process proactive suggestions from personal context."""
        try:
            suggestions = personal_context.get_suggestions(limit=3)
            for s in suggestions:
                if s.get("priority", 0) >= 7:
                    self._notify(
                        f"Suggestion: {s.get('content', '')}",
                        level="info"
                    )
        except:
            pass

    def _notify(self, message: str, level: str = "info"):
        """Send notification based on threshold."""
        thresholds = {"all": 0, "important": 1, "critical": 2}
        current = thresholds.get(self.config.notification_threshold, 1)
        msg_level = {"info": 0, "warning": 1, "critical": 2}.get(level, 0)

        if msg_level >= current:
            from core.signal_bus import signal_bus
            signal_bus.speak.emit(f"{level.upper()}: {message}")
            
            # Log to timeline
            try:
                timeline_memory.log_event(
                    event_type="notification",
                    category="system",
                    title=f"Autonomous: {level}",
                    description=message,
                    tags=["notification", level, "autonomous"]
                )
            except:
                pass

    def get_status(self) -> Dict:
        """Get autonomous assistant status."""
        return {
            "running": self.running,
            "mode": self.config.mode.value,
            "last_briefing": datetime.fromtimestamp(self.last_briefing).isoformat() if self.last_briefing else None,
            "last_evening_review": datetime.fromtimestamp(self.last_evening_review).isoformat() if self.last_evening_review else None,
            "last_backup": datetime.fromtimestamp(self.last_backup).isoformat() if self.last_backup else None,
            "config": {
                "mode": self.config.mode.value,
                "briefing_enabled": self.config.briefing_enabled,
                "briefing_time": self.config.briefing_time,
                "evening_review_enabled": self.config.evening_review_enabled,
                "backup_enabled": self.config.backup_enabled,
                "monitoring_enabled": self.config.monitoring_enabled
            }
        }

    def set_mode(self, mode: AutonomousMode):
        """Change autonomy mode."""
        self.config.mode = mode
        if mode == AutonomousMode.PASSIVE:
            self.config.monitoring_enabled = False
            self.config.briefing_enabled = False
        elif mode == AutonomousMode.REACTIVE:
            self.config.monitoring_enabled = True
            self.config.briefing_enabled = True
        elif mode == AutonomousMode.PROACTIVE:
            self.config.monitoring_enabled = True
            self.config.briefing_enabled = True
        elif mode == AutonomousMode.AUTONOMOUS:
            self.config.monitoring_enabled = True
            self.config.briefing_enabled = True
            self.config.auto_accept_low_risk = True


# Global instance
autonomous_assistant = AutonomousAssistant()


def start_autonomous(config: AutonomousConfig = None):
    """Start the autonomous assistant."""
    global autonomous_assistant
    if config:
        autonomous_assistant = AutonomousAssistant(config)
    autonomous_assistant.start()


def stop_autonomous():
    """Stop the autonomous assistant."""
    autonomous_assistant.stop()


def get_autonomous_status() -> Dict:
    return autonomous_assistant.get_status()


def set_autonomy_mode(mode: AutonomousMode):
    autonomous_assistant.set_mode(mode)


if __name__ == "__main__":
    print("Autonomous Assistant - Phase 37")
    print("Features: daily briefings, goal tracking, monitoring, backup, autonomous operation")