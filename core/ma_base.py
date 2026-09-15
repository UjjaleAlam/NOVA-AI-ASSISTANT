"""
Multi-Agent Base Components - Shared between multi_agent.py and specialist_adapters.py
Breaks circular import.
"""

import os
import json
import time
import threading
import queue
import random
import sqlite3
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path


DB_DIR = "database"
MA_DB = os.path.join(DB_DIR, "multi_agent.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_ma_connection():
    conn = sqlite3.connect(MA_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


# ============================================================
# MESSAGE TYPES & ENUMS
# ============================================================

class MessageType(Enum):
    """Standardized message types for agent communication."""
    TASK_ASSIGN = "task_assign"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    TASK_CANCEL = "task_cancel"
    TASK_DEPENDENCY = "task_dependency"
    RESOURCE_REQUEST = "resource_request"
    RESOURCE_RELEASE = "resource_release"
    AGENT_STATUS = "agent_status"
    CONTEXT_UPDATE = "context_update"
    QUERY = "query"
    RESPONSE = "response"
    EVENT = "event"
    HEARTBEAT = "heartbeat"


class TaskStatus(Enum):
    """Task status states."""
    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    WAITING = "waiting"
    WAITING_FOR_USER = "waiting_for_user"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================
# BASE AGENT CLASS
# ============================================================

class BaseAgent:
    """Base class for all agents."""

    def __init__(self, name: str, agent_type: str, capabilities: List[str],
                 max_concurrent_tasks: int = 1, config: Dict = None):
        self.agent_id = f"agent_{int(time.time() * 1000000) % 100000000:08d}_{int(time.time() * 10000) % 10000:04d}_{random.randint(0, 9999):04d}"
        self.name = name
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.max_concurrent_tasks = max_concurrent_tasks
        self.config = config or {}
        self.current_tasks: Dict[str, Dict] = {}
        self.running = False
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.message_handlers: Dict[str, Callable] = {}
        self.cancelled_tasks: Set[str] = set()
        self._progress_callbacks: List[Callable] = []

    def start(self):
        """Start the agent."""
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Stop the agent."""
        self.running = False
        # Cancel all current tasks
        for task_id in self.current_tasks:
            self.cancel_task(task_id)
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

    def cancel_task(self, task_id: str):
        """Cancel a running task."""
        self.cancelled_tasks.add(task_id)
        if task_id in self.current_tasks:
            self.current_tasks[task_id]["cancelled"] = True

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been cancelled."""
        return task_id in self.cancelled_tasks

    def report_progress(self, task_id: str, progress: float, message: str = "", 
                       artifacts: List[Dict] = None):
        """Report task progress."""
        if task_id in self.current_tasks:
            self.current_tasks[task_id]["progress"] = progress
            self.current_tasks[task_id]["progress_message"] = message
            if artifacts:
                self.current_tasks[task_id].setdefault("artifacts", []).extend(artifacts)
        
        # Send progress message to coordinator
        self.send_message(
            to_agent_id="coordinator",
            message_type=MessageType.TASK_PROGRESS.value,
            content={
                "task_id": task_id,
                "progress": progress,
                "message": message,
                "artifacts": artifacts or [],
                "agent_id": self.agent_id
            },
            correlation_id=task_id
        )

    def add_progress_callback(self, callback: Callable):
        """Add a callback for progress updates."""
        self._progress_callbacks.append(callback)

    def _worker_loop(self):
        """Main worker loop - pulls from shared task queue."""
        from core.multi_agent import task_queue
        while self.running:
            try:
                # Get next task from shared queue matching our capabilities
                task = task_queue.get_next_task(self.agent_id, self.capabilities)
                if task:
                    self._execute_task(task)
                else:
                    time.sleep(1)  # No tasks available, wait a bit
            except Exception as e:
                print(f"Agent {self.agent_id} error: {e}")

    def _execute_task(self, task: Dict):
        """Execute a single task with cancellation and progress support."""
        task_id = task["id"]
        # Get timeout from task (default 300 seconds = 5 minutes)
        timeout = task.get("timeout", 300.0)
        self.current_tasks[task_id] = {"task": task, "progress": 0.0, "cancelled": False, "start_time": time.time(), "timeout": timeout}
        registry.update_agent_status(self.agent_id, "busy", task_id)

        start_time = time.time()
        try:
            # Check for cancellation before execution
            if self.is_cancelled(task_id):
                raise Exception("Task cancelled")

            # Report initial progress
            self.report_progress(task_id, 0.1, "Starting task")

            # Execute with timeout monitoring
            result = self._execute_with_timeout(task, timeout)

            # Check for cancellation after execution
            if self.is_cancelled(task_id):
                raise Exception("Task cancelled after execution")

            duration = time.time() - start_time
            registry.record_metric(self.agent_id, tasks_completed=1,
                                   completion_time=duration, success=True, response_time=duration)
            self.report_progress(task_id, 1.0, "Task completed")
            self._complete_task(task_id, result)
        except Exception as e:
            duration = time.time() - start_time
            error_str = str(e).lower()
            if "cancelled" in error_str:
                self._cancel_task(task_id, str(e))
            else:
                # Timeouts and other errors are treated as failures (go to DLQ)
                registry.record_metric(self.agent_id, tasks_failed=1,
                                       completion_time=duration, success=False, response_time=duration)
                # Use TaskQueueManager to properly handle DLQ
                from core.multi_agent import task_queue
                task_queue.fail_task(task_id, str(e))

        self.cancelled_tasks.discard(task_id)
        del self.current_tasks[task_id]
        if not self.current_tasks:
            registry.update_agent_status(self.agent_id, "idle")

    def _execute_with_timeout(self, task: Dict, timeout: float) -> Any:
        """Execute task with timeout monitoring."""
        import threading
        import queue
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def worker():
            try:
                result = self.execute(task)
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        
        # Wait for completion or timeout
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            # Timeout occurred
            raise TimeoutError(f"Task timed out after {timeout} seconds")
        
        if not exception_queue.empty():
            raise exception_queue.get()
        
        return result_queue.get()

    def execute(self, task: Dict) -> Any:
        """Override in subclass to implement task execution."""
        raise NotImplementedError

    def _complete_task(self, task_id: str, result: Any):
        """Mark task as completed."""
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE task_queue SET status = 'completed', result = ?, completed_at = ?
            WHERE id = ?
        """, (json.dumps(result) if result else None, time.time(), task_id))
        conn.commit()
        conn.close()

    def _fail_task(self, task_id: str, error: str):
        """Mark task as failed."""
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT retry_count, max_retries FROM task_queue WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if row:
            retry_count, max_retries = row[0], row[1]
            if retry_count < max_retries:
                cursor.execute("UPDATE task_queue SET status = 'pending', error = ?, retry_count = retry_count + 1 WHERE id = ?",
                              (error, task_id))
            else:
                cursor.execute("UPDATE task_queue SET status = 'failed', error = ? WHERE id = ?",
                              (error, task_id))
            conn.commit()
        conn.close()

    def _cancel_task(self, task_id: str, reason: str):
        """Mark task as cancelled."""
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE task_queue SET status = 'cancelled', error = ? WHERE id = ?",
                      (reason, task_id))
        conn.commit()
        conn.close()
        self.report_progress(task_id, 0, f"Cancelled: {reason}")

    def send_message(self, to_agent_id: str, message_type: str, content: Dict,
                     correlation_id: str = None):
        """Send message to another agent."""
        msg_id = f"msg_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_messages (id, from_agent_id, to_agent_id, message_type,
                                       content, correlation_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (msg_id, self.agent_id, to_agent_id, message_type,
              json.dumps(content), correlation_id or str(random.uuid4()), time.time()))
        conn.commit()
        conn.close()

    def get_messages(self, unread_only: bool = True) -> List[Dict]:
        """Get messages for this agent."""
        conn = get_ma_connection()
        cursor = conn.cursor()
        if unread_only:
            cursor.execute("SELECT * FROM agent_messages WHERE to_agent_id = ? AND read = 0 ORDER BY timestamp",
                          (self.agent_id,))
        else:
            cursor.execute("SELECT * FROM agent_messages WHERE to_agent_id = ? ORDER BY timestamp DESC LIMIT 100",
                          (self.agent_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "from": r[1], "to": r[2], "type": r[3],
             "content": json.loads(r[4]) if r[4] else {}, "correlation_id": r[5],
             "timestamp": r[6], "read": bool(r[7])}
            for r in rows
        ]

    def register_handler(self, message_type: str, handler: Callable):
        """Register message handler."""
        self.message_handlers[message_type] = handler

    def process_messages(self):
        """Process incoming messages."""
        messages = self.get_messages(unread_only=True)
        for msg in messages:
            handler = self.message_handlers.get(msg["type"])
            if handler:
                try:
                    handler(msg)
                except Exception as e:
                    print(f"Handler error: {e}")
            # Mark as read
            conn = get_ma_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE agent_messages SET read = 1 WHERE id = ?", (msg["id"],))
            conn.commit()
            conn.close()


# ============================================================
# AGENT REGISTRY
# ============================================================

class AgentRegistry:
    """Registry and lifecycle management for agents."""

    def __init__(self):
        self.agents: Dict[str, 'BaseAgent'] = {}
        self.agent_info: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        # Resource limits (for RTX 4060 8GB, 24GB RAM, i7-13650HX)
        self.resource_limits = {
            "gpu_memory_mb": 7000,  # Leave 1GB for system
            "cpu_cores": 12,        # Logical cores
            "ram_mb": 20000         # Leave 4GB for system
        }
        self.current_resource_usage = {
            "gpu_memory_mb": 0,
            "cpu_cores": 0,
            "ram_mb": 0
        }

    def register_agent(self, agent: 'BaseAgent') -> str:
        """Register an agent."""
        with self.lock:
            agent_id = agent.agent_id
            self.agents[agent_id] = agent
            self.agent_info[agent_id] = {
                "name": agent.name,
                "type": agent.agent_type,
                "capabilities": agent.capabilities,
                "status": "idle",
                "max_concurrent": agent.max_concurrent_tasks,
                "current_task": None,
                "registered_at": time.time()
            }
            self._persist_agent_info(agent_id)
            return agent_id

    def unregister_agent(self, agent_id: str):
        """Unregister an agent."""
        with self.lock:
            if agent_id in self.agents:
                self.agents[agent_id].shutdown()
                del self.agents[agent_id]
            if agent_id in self.agent_info:
                del self.agent_info[agent_id]

    def get_agent(self, agent_id: str) -> Optional['BaseAgent']:
        with self.lock:
            return self.agents.get(agent_id)

    def get_available_agents(self, capability: str = None, max_load: float = 1.0) -> List[Dict]:
        """Get available agents matching criteria."""
        with self.lock:
            available = []
            for aid, info in self.agent_info.items():
                if info["status"] in ["idle", "busy"] and info.get("current_load", 0) < max_load:
                    if capability is None or capability in info.get("capabilities", []):
                        available.append({"agent_id": aid, **info})
            return available

    def update_agent_status(self, agent_id: str, status: str, current_task: str = None):
        """Update agent status."""
        with self.lock:
            if agent_id in self.agent_info:
                self.agent_info[agent_id]["status"] = status
                self.agent_info[agent_id]["current_task"] = current_task
                self.agent_info[agent_id]["last_heartbeat"] = time.time()
                self._persist_agent_info(agent_id)

    def update_agent_load(self, agent_id: str, load: float):
        """Update agent load factor (0-1)."""
        with self.lock:
            if agent_id in self.agent_info:
                self.agent_info[agent_id]["current_load"] = load
                self.agent_info[agent_id]["last_heartbeat"] = time.time()

    def _persist_agent_info(self, agent_id: str):
        """Persist agent info to database."""
        info = self.agent_info.get(agent_id)
        if not info:
            return
        for attempt in range(3):
            try:
                conn = get_ma_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO agents (id, name, agent_type, capabilities, status,
                                                  max_concurrent_tasks, current_task_id, configuration,
                                                  created_at, updated_at, last_heartbeat)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (agent_id, info["name"], info["type"], json.dumps(info["capabilities"]),
                      info["status"], info["max_concurrent"], info.get("current_task"),
                      json.dumps(info.get("config", {})), info.get("registered_at", time.time()),
                      time.time(), time.time()))
                conn.commit()
                conn.close()
                return
            except sqlite3.OperationalError as e:
                if "readonly" in str(e).lower() or "locked" in str(e).lower():
                    time.sleep(0.01 * (attempt + 1))
                    continue
                raise

    def get_all_agents(self) -> List[Dict]:
        with self.lock:
            return [{"agent_id": aid, **info} for aid, info in self.agent_info.items()]

    def record_metric(self, agent_id: str, tasks_completed: int = 0, tasks_failed: int = 0,
                      completion_time: float = 0, success: bool = True, response_time: float = 0):
        """Record agent performance metric."""
        conn = get_ma_connection()
        cursor = conn.cursor()
        metrics_id = f"met_{int(time.time() * 1000000) % 100000000:08d}_{random.randint(1000,9999)}"
        cursor.execute("""
            INSERT INTO agent_metrics (id, agent_id, timestamp, tasks_completed, tasks_failed,
                                      avg_completion_time, success_rate, avg_response_time, current_load)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (metrics_id, agent_id, time.time(),
              tasks_completed, tasks_failed, completion_time, 1.0 if success else 0.0, response_time, 0.5))
        conn.commit()
        conn.close()

    def allocate_resources(self, agent_id: str, resource_profile: Dict) -> bool:
        """Allocate resources for an agent task."""
        with self.lock:
            gpu = resource_profile.get("gpu_memory_mb", 0)
            cpu = resource_profile.get("cpu_cores", 0)
            ram = resource_profile.get("ram_mb", 0)
            
            if (self.current_resource_usage["gpu_memory_mb"] + gpu > self.resource_limits["gpu_memory_mb"] or
                self.current_resource_usage["cpu_cores"] + cpu > self.resource_limits["cpu_cores"] or
                self.current_resource_usage["ram_mb"] + ram > self.resource_limits["ram_mb"]):
                return False
            
            self.current_resource_usage["gpu_memory_mb"] += gpu
            self.current_resource_usage["cpu_cores"] += cpu
            self.current_resource_usage["ram_mb"] += ram
            
            if agent_id in self.agent_info:
                self.agent_info[agent_id]["allocated_resources"] = resource_profile
            return True

    def release_resources(self, agent_id: str):
        """Release resources allocated to an agent."""
        with self.lock:
            if agent_id in self.agent_info and "allocated_resources" in self.agent_info[agent_id]:
                resources = self.agent_info[agent_id]["allocated_resources"]
                self.current_resource_usage["gpu_memory_mb"] -= resources.get("gpu_memory_mb", 0)
                self.current_resource_usage["cpu_cores"] -= resources.get("cpu_cores", 0)
                self.current_resource_usage["ram_mb"] -= resources.get("ram_mb", 0)
                del self.agent_info[agent_id]["allocated_resources"]

    def get_resource_usage(self) -> Dict:
        """Get current resource usage."""
        with self.lock:
            return {
                "current": self.current_resource_usage.copy(),
                "limits": self.resource_limits.copy(),
                "available": {
                    "gpu_memory_mb": self.resource_limits["gpu_memory_mb"] - self.current_resource_usage["gpu_memory_mb"],
                    "cpu_cores": self.resource_limits["cpu_cores"] - self.current_resource_usage["cpu_cores"],
                    "ram_mb": self.resource_limits["ram_mb"] - self.current_resource_usage["ram_mb"]
                }
            }

    def can_allocate(self, resource_profile: Dict) -> bool:
        """Check if resources can be allocated without exceeding limits."""
        with self.lock:
            return (self.current_resource_usage["gpu_memory_mb"] + resource_profile.get("gpu_memory_mb", 0) <= self.resource_limits["gpu_memory_mb"] and
                    self.current_resource_usage["cpu_cores"] + resource_profile.get("cpu_cores", 0) <= self.resource_limits["cpu_cores"] and
                    self.current_resource_usage["ram_mb"] + resource_profile.get("ram_mb", 0) <= self.resource_limits["ram_mb"])


# Global registry instance
registry = AgentRegistry()


def init_ma_db():
    conn = get_ma_connection()
    cursor = conn.cursor()

    # Agent registry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            agent_type TEXT NOT NULL,
            capabilities TEXT,
            status TEXT DEFAULT 'idle',
            max_concurrent_tasks INTEGER DEFAULT 1,
            current_task_id TEXT,
            configuration TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            last_heartbeat REAL
        )
    """)

    # Task queue for agent coordination
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_queue (
            id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            priority INTEGER DEFAULT 3,
            status TEXT DEFAULT 'pending',
            assigned_agent_id TEXT,
            parent_task_id TEXT,
            depends_on TEXT,
            created_at REAL NOT NULL,
            assigned_at REAL,
            started_at REAL,
            completed_at REAL,
            result TEXT,
            error TEXT,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            timeout REAL DEFAULT 300.0
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_task_status ON task_queue(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_task_agent ON task_queue(assigned_agent_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_task_priority ON task_queue(priority, created_at)
    """)

    # Dead letter queue for failed tasks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dead_letter_queue (
            id TEXT PRIMARY KEY,
            original_task_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            priority INTEGER DEFAULT 3,
            assigned_agent_id TEXT,
            parent_task_id TEXT,
            depends_on TEXT,
            created_at REAL NOT NULL,
            assigned_at REAL,
            started_at REAL,
            completed_at REAL,
            result TEXT,
            error TEXT,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            timeout REAL DEFAULT 300.0,
            failed_at REAL NOT NULL,
            failure_reason TEXT,
            retry_history TEXT
        )
    """)

    # Agent communication / messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_messages (
            id TEXT PRIMARY KEY,
            from_agent_id TEXT,
            to_agent_id TEXT,
            message_type TEXT,
            content TEXT,
            correlation_id TEXT,
            timestamp REAL NOT NULL,
            read BOOLEAN DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_msg_to ON agent_messages(to_agent_id, read)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_msg_correlation ON agent_messages(correlation_id)
    """)

    # Workflow definitions (reusable agent workflows)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            steps TEXT,
            trigger_type TEXT,
            trigger_config TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Workflow executions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT DEFAULT 'running',
            current_step INTEGER DEFAULT 0,
            step_results TEXT,
            context TEXT,
            started_at REAL NOT NULL,
            completed_at REAL,
            error TEXT
        )
    """)

    # Agent performance metrics
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_metrics (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            tasks_completed INTEGER DEFAULT 0,
            tasks_failed INTEGER DEFAULT 0,
            avg_completion_time REAL,
            success_rate REAL,
            avg_response_time REAL,
            current_load REAL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metrics_agent ON agent_metrics(agent_id, timestamp)
    """)

    # Agent collaboration logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collaboration_logs (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            agents TEXT,
            interaction_type TEXT,
            details TEXT,
            timestamp REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_ma_db()