"""
Background Task Engine - Phase 37 Foundation
Persistent background queue, scheduled/recurring jobs, resumability.
"""

import os
import json
import time
import threading
import queue
import sqlite3
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

import croniter

from core.ma_base import get_ma_connection, registry


DB_DIR = "database"
BG_DB = os.path.join(DB_DIR, "background_tasks.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_bg_connection():
    conn = sqlite3.connect(BG_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_bg_db():
    conn = get_bg_connection()
    cursor = conn.cursor()

    # Background job definitions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bg_jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            job_type TEXT NOT NULL,           -- 'scheduled', 'recurring', 'one_time', 'event_driven'
            task_type TEXT NOT NULL,          -- The task_type to execute
            payload TEXT NOT NULL,            -- JSON payload for the task
            schedule TEXT,                    -- Cron expression or interval
            next_run REAL,                    -- Unix timestamp of next run
            last_run REAL,                    -- Unix timestamp of last run
            priority INTEGER DEFAULT 3,
            status TEXT DEFAULT 'active',     -- 'active', 'paused', 'completed', 'failed', 'deleted'
            max_runs INTEGER,                 -- Max runs for recurring (None = infinite)
            run_count INTEGER DEFAULT 0,
            timeout INTEGER DEFAULT 300,      -- Max runtime in seconds
            retry_on_failure BOOLEAN DEFAULT 1,
            max_retries INTEGER DEFAULT 3,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_bg_jobs_next_run ON bg_jobs(next_run, status)
    """)

    # Job execution history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bg_job_runs (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            task_id TEXT,                     -- Link to task_queue task
            status TEXT NOT NULL,             -- 'started', 'completed', 'failed', 'timeout'
            started_at REAL NOT NULL,
            completed_at REAL,
            result TEXT,
            error TEXT,
            retry_count INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_bg_runs_job ON bg_job_runs(job_id, started_at)
    """)

    # Event triggers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bg_triggers (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            event_type TEXT NOT NULL,         -- 'file_change', 'system_event', 'time', 'manual', 'webhook'
            event_config TEXT,                -- JSON config for the trigger
            is_active BOOLEAN DEFAULT 1,
            created_at REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_bg_db()


class BackgroundTaskEngine:
    """Manages background jobs, scheduling, and recurring tasks."""

    def __init__(self):
        self.running = False
        self.worker_thread = None
        self.scheduler_thread = None
        self.job_queue = queue.PriorityQueue()
        self._load_active_jobs()

    def _load_active_jobs(self):
        """Load active jobs from database into memory."""
        conn = get_bg_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM bg_jobs 
            WHERE status = 'active' AND next_run IS NOT NULL
            ORDER BY next_run
        """)
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            job = {
                "id": row[0], "name": row[1], "job_type": row[2],
                "task_type": row[3], "payload": json.loads(row[4]) if row[4] else {},
                "schedule": row[5], "next_run": row[6], "last_run": row[7],
                "priority": row[8], "status": row[9], "max_runs": row[10],
                "run_count": row[11], "timeout": row[12], "retry_on_failure": bool(row[13]),
                "max_retries": row[14]
            }
            self._schedule_job(job)

    def _schedule_job(self, job: Dict):
        """Add job to scheduler queue."""
        if job["next_run"]:
            self.job_queue.put((job["next_run"], job["priority"], job["id"], job))

    def start(self):
        """Start the background task engine."""
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()

    def stop(self):
        """Stop the background task engine."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

    def _worker_loop(self):
        """Execute background jobs."""
        from core.multi_agent import task_queue
        while self.running:
            try:
                # Get next job from queue
                next_run, priority, job_id, job = self.job_queue.get(timeout=1)
                now = time.time()
                
                if next_run > now:
                    # Not time yet, put back
                    self.job_queue.put((next_run, priority, job_id, job))
                    time.sleep(0.5)
                    continue

                # Execute the job
                self._execute_job(job)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Background worker error: {e}")

    def _scheduler_loop(self):
        """Update next_run times for recurring jobs."""
        while self.running:
            try:
                self._update_recurring_jobs()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                print(f"Scheduler error: {e}")

    def _update_recurring_jobs(self):
        """Update next_run for recurring jobs that have completed."""
        conn = get_bg_connection()
        cursor = conn.cursor()
        now = time.time()
        
        # Find jobs that need rescheduling
        cursor.execute("""
            SELECT * FROM bg_jobs 
            WHERE status = 'active' 
            AND job_type IN ('recurring', 'scheduled')
            AND next_run IS NOT NULL
            AND next_run <= ?
        """, (now,))
        
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            job_id = row[0]
            schedule = row[5]
            max_runs = row[10]
            run_count = row[11]
            job_type = row[2]

            if max_runs and run_count >= max_runs:
                # Job completed its run limit
                self._deactivate_job(job_id)
                continue

            next_run = self._calculate_next_run(schedule, now)
            if next_run:
                conn = get_bg_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE bg_jobs SET next_run = ?, run_count = run_count + 1, updated_at = ?
                    WHERE id = ?
                """, (next_run, now, job_id))
                conn.commit()
                conn.close()
                
                # Reload job into queue
                self._reload_job(job_id)

    def _calculate_next_run(self, schedule: str, from_time: float) -> Optional[float]:
        """Calculate next run time from cron expression or interval."""
        if not schedule:
            return None
        
        try:
            # Try as cron expression
            cron = croniter.croniter(schedule, datetime.fromtimestamp(from_time))
            return cron.get_next(float)
        except:
            try:
                # Try as interval in seconds
                interval = int(schedule)
                return from_time + interval
            except:
                return None

    def _execute_job(self, job: Dict):
        """Execute a background job by creating a task."""
        from core.multi_agent import task_queue
        
        job_id = job["id"]
        conn = get_bg_connection()
        cursor = conn.cursor()
        
        # Record run start
        run_id = f"run_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO bg_job_runs (id, job_id, status, started_at)
            VALUES (?, ?, 'started', ?)
        """, (run_id, job_id, time.time()))
        conn.commit()
        conn.close()

        # Create task in main queue
        try:
            task_id = task_queue.add_task(
                job["task_type"],
                job["payload"],
                priority=job.get("priority", 3)
            )
            
            # Link task to job run
            conn = get_bg_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE bg_job_runs SET task_id = ? WHERE id = ?", (task_id, run_id))
            conn.commit()
            conn.close()

            # Wait for task completion (with timeout)
            timeout = job.get("timeout", 300)
            start_time = time.time()
            while time.time() - start_time < timeout:
                task_status = task_queue.get_task_status(task_id)
                if task_status and task_status["status"] in ["completed", "failed", "cancelled"]:
                    # Update job run
                    conn = get_bg_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE bg_job_runs SET status = ?, completed_at = ?, result = ?, error = ?
                        WHERE id = ?
                    """, (
                        task_status["status"],
                        time.time(),
                        json.dumps(task_status.get("result")) if task_status.get("result") else None,
                        task_status.get("error"),
                        run_id
                    ))
                    conn.commit()
                    conn.close()
                    
                    # Handle retry logic
                    if task_status["status"] == "failed" and job.get("retry_on_failure"):
                        self._handle_job_retry(job, run_id, task_status.get("error"))
                    break
                time.sleep(1)
            else:
                # Timeout
                conn = get_bg_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE bg_job_runs SET status = 'timeout', completed_at = ? WHERE id = ?",
                              (time.time(), run_id))
                conn.commit()
                conn.close()
                
        except Exception as e:
            conn = get_bg_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE bg_job_runs SET status = 'failed', completed_at = ?, error = ? WHERE id = ?",
                          (time.time(), str(e), run_id))
            conn.commit()
            conn.close()

    def _handle_job_retry(self, job: Dict, run_id: str, error: str):
        """Handle job retry logic."""
        retry_count = 0
        conn = get_bg_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bg_job_runs WHERE job_id = ? AND status = 'failed'", (job["id"],))
        retry_count = cursor.fetchone()[0]
        conn.close()

        if retry_count < job.get("max_retries", 3):
            # Reschedule with delay
            delay = min(60 * (2 ** retry_count), 3600)  # Exponential backoff, max 1 hour
            next_run = time.time() + delay
            
            conn = get_bg_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE bg_jobs SET next_run = ?, updated_at = ? WHERE id = ?",
                          (next_run, time.time(), job["id"]))
            conn.commit()
            conn.close()
        else:
            self._deactivate_job(job["id"])

    def _deactivate_job(self, job_id: str):
        """Mark job as completed/deactivated."""
        conn = get_bg_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE bg_jobs SET status = 'completed', updated_at = ? WHERE id = ?",
                      (time.time(), job_id))
        conn.commit()
        conn.close()

    def _reload_job(self, job_id: str):
        """Reload a job from database into queue."""
        conn = get_bg_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bg_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row[9] == 'active':
            job = {
                "id": row[0], "name": row[1], "job_type": row[2],
                "task_type": row[3], "payload": json.loads(row[4]) if row[4] else {},
                "schedule": row[5], "next_run": row[6], "last_run": row[7],
                "priority": row[8], "status": row[9], "max_runs": row[10],
                "run_count": row[11], "timeout": row[12], "retry_on_failure": bool(row[13]),
                "max_retries": row[14]
            }
            self._schedule_job(job)

    # Public API
    def create_job(self, name: str, task_type: str, payload: Dict,
                   schedule: str = None, job_type: str = "one_time",
                   priority: int = 3, timeout: int = 300,
                   max_runs: int = None, retry_on_failure: bool = True,
                   max_retries: int = 3) -> str:
        """Create a new background job."""
        job_id = f"job_{int(time.time() * 1000) % 100000000:08d}"
        now = time.time()

        if job_type in ("recurring", "scheduled") and schedule:
            next_run = self._calculate_next_run(schedule, now)
        else:
            next_run = now if job_type == "one_time" else None

        conn = get_bg_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bg_jobs (id, name, job_type, task_type, payload, schedule,
                                next_run, priority, status, max_runs, timeout,
                                retry_on_failure, max_retries, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, 1, ?, ?, ?)
        """, (job_id, name, job_type, task_type, json.dumps(payload), schedule,
              next_run, priority, max_runs, timeout, max_retries, now, now))
        conn.commit()
        conn.close()

        if next_run:
            job = {
                "id": job_id, "name": name, "job_type": job_type,
                "task_type": task_type, "payload": payload,
                "schedule": schedule, "next_run": next_run, "priority": priority,
                "max_runs": max_runs, "timeout": timeout, "retry_on_failure": retry_on_failure,
                "max_retries": max_retries
            }
            self._schedule_job(job)

        return job_id

    def pause_job(self, job_id: str) -> bool:
        """Pause a background job."""
        conn = get_bg_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE bg_jobs SET status = 'paused', updated_at = ? WHERE id = ?",
                      (time.time(), job_id))
        conn.commit()
        conn.close()
        return True

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        conn = get_bg_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE bg_jobs SET status = 'active', updated_at = ? WHERE id = ?",
                      (time.time(), job_id))
        conn.commit()
        conn.close()
        
        # Reload into queue
        self._reload_job(job_id)
        return True

    def delete_job(self, job_id: str) -> bool:
        """Delete a background job."""
        conn = get_bg_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE bg_jobs SET status = 'deleted', updated_at = ? WHERE id = ?",
                      (time.time(), job_id))
        conn.commit()
        conn.close()
        return True

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job status and recent runs."""
        conn = get_bg_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bg_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None

        job = {
            "id": row[0], "name": row[1], "job_type": row[2],
            "task_type": row[3], "payload": json.loads(row[4]) if row[4] else {},
            "schedule": row[5], "next_run": row[6], "last_run": row[7],
            "priority": row[8], "status": row[9], "max_runs": row[10],
            "run_count": row[11], "timeout": row[12], "retry_on_failure": bool(row[13]),
            "max_retries": row[14], "created_at": row[15], "updated_at": row[16]
        }

        # Get recent runs
        cursor.execute("""
            SELECT * FROM bg_job_runs WHERE job_id = ? ORDER BY started_at DESC LIMIT 10
        """, (job_id,))
        runs = cursor.fetchall()
        conn.close()

        job["recent_runs"] = [
            {"id": r[0], "job_id": r[1], "task_id": r[2], "status": r[3],
             "started_at": r[4], "completed_at": r[5], "result": json.loads(r[6]) if r[6] else None,
             "error": r[7], "retry_count": r[8]}
            for r in runs
        ]

        return job

    def list_jobs(self, status: str = None) -> List[Dict]:
        """List all background jobs."""
        conn = get_bg_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM bg_jobs WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM bg_jobs ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()

        return [
            {"id": r[0], "name": r[1], "job_type": r[2], "task_type": r[3],
             "schedule": r[5], "next_run": r[6], "status": r[9], "run_count": r[11]}
            for r in rows
        ]


# Global instance
bg_engine = BackgroundTaskEngine()


def start_background_engine():
    """Start the global background task engine."""
    bg_engine.start()


def stop_background_engine():
    """Stop the global background task engine."""
    bg_engine.stop()


# Convenience functions
def schedule_job(name: str, task_type: str, payload: Dict, schedule: str = None,
                 job_type: str = "one_time", **kwargs) -> str:
    """Schedule a background job."""
    return bg_engine.create_job(name, task_type, payload, schedule, job_type, **kwargs)


def pause_job(job_id: str) -> bool:
    return bg_engine.pause_job(job_id)


def resume_job(job_id: str) -> bool:
    return bg_engine.resume_job(job_id)


def delete_job(job_id: str) -> bool:
    return bg_engine.delete_job(job_id)


def get_job(job_id: str) -> Optional[Dict]:
    return bg_engine.get_job_status(job_id)


def list_jobs(status: str = None) -> List[Dict]:
    return bg_engine.list_jobs(status)


if __name__ == "__main__":
    print("Background Task Engine loaded.")
    print("Features: scheduled, recurring, one-time jobs with cron/interval support")
    print("Features: retry logic, timeout handling, job persistence")