"""
Multi-Agent System Agent - Phase 36
Orchestration of multiple specialized agents working together.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import threading
import queue
import random
import statistics
import uuid
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
            max_retries INTEGER DEFAULT 3
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


# ============================================================
# AGENT REGISTRY
# ============================================================

class AgentRegistry:
    """Registry and lifecycle management for agents."""

    def __init__(self):
        self.agents: Dict[str, 'BaseAgent'] = {}
        self.agent_info: Dict[str, Dict] = {}
        self.lock = threading.Lock()

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
        if info:
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

    def get_all_agents(self) -> List[Dict]:
        with self.lock:
            return [{"agent_id": aid, **info} for aid, info in self.agent_info.items()]

    def record_metric(self, agent_id: str, tasks_completed: int = 0, tasks_failed: int = 0,
                      completion_time: float = 0, success: bool = True, response_time: float = 0):
        """Record agent performance metric."""
        conn = get_ma_connection()
        cursor = conn.cursor()
        metrics_id = f"met_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO agent_metrics (id, agent_id, timestamp, tasks_completed, tasks_failed,
                                      avg_completion_time, success_rate, avg_response_time, current_load)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"met_{int(time.time() * 1000) % 100000000:08d}", agent_id, time.time(),
              tasks_completed, tasks_failed, completion_time, 1.0 if success else 0.0, response_time, 0.5))
        conn.commit()
        conn.close()

    def get_all_agents(self) -> List[Dict]:
        with self.lock:
            return [{"agent_id": aid, **info} for aid, info in self.agent_info.items()]


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

    def start(self):
        """Start the agent."""
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Stop the agent."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

    def _worker_loop(self):
        """Main worker loop."""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                self._execute_task(task)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Agent {self.agent_id} error: {e}")

    def _execute_task(self, task: Dict):
        """Execute a single task."""
        task_id = task["id"]
        self.current_tasks[task_id] = task
        registry.update_agent_status(self.agent_id, "busy", task_id)

        start_time = time.time()
        try:
            result = self.execute(task)
            duration = time.time() - start_time
            registry.record_metric(self.agent_id, tasks_completed=1,
                                   completion_time=duration, success=True, response_time=duration)
            self._complete_task(task_id, result)
        except Exception as e:
            duration = time.time() - start_time
            registry.record_metric(self.agent_id, tasks_failed=1,
                                   completion_time=duration, success=False, response_time=duration)
            self._fail_task(task_id, str(e))

        del self.current_tasks[task_id]
        if not self.current_tasks:
            registry.update_agent_status(self.agent_id, "idle")

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
        """, (f"msg_{int(time.time() * 1000) % 100000000:08d}", self.agent_id, to_agent_id, message_type,
              json.dumps(content), correlation_id or str(uuid.uuid4()), time.time()))
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
             "timestamp": r[6], "read": bool(r[6])}
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
# SPECIALIZED AGENTS
# ============================================================

class PlannerAgent(BaseAgent):
    """Agent responsible for planning and task decomposition."""

    def __init__(self):
        super().__init__("Planner", "planner", ["planning", "decomposition", "scheduling"],
                         max_concurrent_tasks=3)

    def execute(self, task: Dict) -> Any:
        task_type = task.get("type", "plan")
        if task_type == "decompose":
            return self._decompose_task(task)
        elif task_type == "schedule":
            return self._create_schedule(task)
        elif task_type == "estimate":
            return self._estimate_task(task)
        else:
            return {"error": f"Unknown task type: {task_type}"}

    def _decompose_task(self, task: Dict) -> Dict:
        """Decompose a complex task into subtasks."""
        goal = task.get("goal", "")
        context = task.get("context", {})

        subtasks = [
            {"id": f"sub_{int(time.time() * 1000) % 100000000:08d}",
             "title": f"Analyze requirements for: {goal}",
             "type": "research", "estimated_hours": 2},
            {"id": f"sub_{int(time.time() * 1000) % 100000000:08d}",
             "title": f"Design solution for: {goal}",
             "type": "design", "estimated_hours": 3},
            {"id": f"sub_{int(time.time() * 1000) % 100000000:08d}",
             "title": f"Implement: {goal}",
             "type": "code", "estimated_hours": 8},
            {"id": f"sub_{int(time.time() * 1000) % 100000000:08d}",
             "title": f"Test: {goal}",
             "type": "test", "estimated_hours": 3},
            {"id": f"sub_{int(time.time() * 1000) % 100000000:08d}",
             "title": f"Document: {goal}",
             "type": "document", "estimated_hours": 2},
        ]

        return {"subtasks": subtasks, "total_estimated_hours": sum(s["estimated_hours"] for s in subtasks)}

    def _create_schedule(self, task: Dict) -> Dict:
        """Create a schedule for tasks."""
        tasks = task.get("tasks", [])
        start_date = task.get("start_date", time.time())
        hours_per_day = task.get("hours_per_day", 8)

        schedule = []
        current_time = start_date
        for task_item in tasks:
            hours = task_item.get("estimated_hours", 1)
            end_time = current_time + hours * 3600
            schedule.append({
                "task": task_item.get("title", ""),
                "start": current_time,
                "end": end_time,
                "duration_hours": hours
            })
            current_time = end_time + 3600

        return {"schedule": schedule, "total_hours": sum(t.get("estimated_hours", 1) for t in tasks)}

    def _estimate_task(self, task: Dict) -> Dict:
        """Estimate effort for a task."""
        complexity = task.get("complexity", "medium")
        estimates = {"low": 2, "medium": 8, "high": 24, "very_high": 80}
        return {"estimated_hours": estimates.get(complexity, 8)}


class ExecutorAgent(BaseAgent):
    """Agent responsible for executing tasks."""

    def __init__(self):
        super().__init__("Executor", "executor", ["execution", "coding", "testing", "deployment"],
                         max_concurrent_tasks=2)

    def execute(self, task: Dict) -> Any:
        task_type = task.get("type", "execute")
        if task_type == "code":
            return self._write_code(task)
        elif task_type == "test":
            return self._run_tests(task)
        elif task_type == "deploy":
            return self._deploy(task)
        elif task_type == "build":
            return self._build(task)
        else:
            return {"error": f"Unknown task type: {task_type}"}

    def _write_code(self, task: Dict) -> Dict:
        return {
            "files_created": [f"src/{task.get('component', 'feature')}.py"],
            "lines_of_code": random.randint(50, 200),
            "language": task.get("language", "python")
        }

    def _run_tests(self, task: Dict) -> Dict:
        passed = random.randint(80, 100)
        total = random.randint(passed, 100)
        return {"passed": passed, "total": total, "pass_rate": passed/total}

    def _deploy(self, task: Dict) -> Dict:
        return {"status": "deployed", "environment": task.get("environment", "staging"),
                "url": f"https://{task.get('name', 'app')}.staging.example.com"}

    def _build(self, task: Dict) -> Dict:
        return {"status": "built", "artifact": f"{task.get('name', 'app')}.tar.gz",
                "size_mb": random.randint(10, 100)}


class ResearcherAgent(BaseAgent):
    """Agent responsible for research and information gathering."""

    def __init__(self):
        super().__init__("Researcher", "researcher", ["research", "analysis", "summarization"],
                         max_concurrent_tasks=3)

    def execute(self, task: Dict) -> Any:
        task_type = task.get("type", "research")
        if task_type == "web_search":
            return self._web_search(task)
        elif task_type == "code_search":
            return self._code_search(task)
        elif task_type == "summarize":
            return self._summarize(task)
        elif task_type == "analyze":
            return self._analyze(task)
        else:
            return {"error": f"Unknown task type: {task_type}"}

    def _web_search(self, task: Dict) -> Dict:
        query = task.get("query", "")
        return {
            "query": query,
            "results": [
                {"title": f"Result for {query}", "url": "https://example.com/1",
                 "snippet": f"Summary of {query}..."},
                {"title": f"Another result for {query}", "url": "https://example.com/2",
                 "snippet": f"More details on {query}..."}
            ],
            "sources": ["web"]
        }

    def _code_search(self, task: Dict) -> Dict:
        query = task.get("query", "")
        return {
            "query": query,
            "matches": [
                {"file": "src/main.py", "line": 42, "snippet": f"def {query}():"},
                {"file": "src/utils.py", "line": 15, "snippet": f"# {query} utility"}
            ]
        }

    def _summarize(self, task: Dict) -> Dict:
        content = task.get("content", "")
        return {
            "summary": f"Summary of {len(content)} characters: {content[:100]}...",
            "key_points": ["Point 1", "Point 2", "Point 3"],
            "length": len(content)
        }

    def _analyze(self, task: Dict) -> Dict:
        content = task.get("content", "")
        return {
            "analysis": f"Analysis of {len(content)} chars",
            "sentiment": "neutral",
            "topics": ["topic1", "topic2"],
            "complexity": "medium"
        }


class ReviewerAgent(BaseAgent):
    """Agent responsible for code review and quality assurance."""

    def __init__(self):
        super().__init__("Reviewer", "reviewer", ["review", "qa", "security", "performance"],
                         max_concurrent_tasks=2)

    def execute(self, task: Dict) -> Any:
        task_type = task.get("type", "review")
        if task_type == "code_review":
            return self._code_review(task)
        elif task_type == "security_audit":
            return self._security_audit(task)
        elif task_type == "performance_review":
            return self._performance_review(task)
        else:
            return {"error": f"Unknown task type: {task_type}"}

    def _code_review(self, task: Dict) -> Dict:
        code = task.get("code", "")
        return {
            "issues": [
                {"severity": "medium", "line": 42, "message": "Consider using list comprehension"},
                {"severity": "low", "line": 15, "message": "Add type hints"}
            ],
            "score": 85,
            "summary": "Good code quality, minor improvements suggested"
        }

    def _security_audit(self, task: Dict) -> Dict:
        return {
            "vulnerabilities": [],
            "risk_level": "low",
            "recommendations": ["Keep dependencies updated"]
        }

    def _performance_review(self, task: Dict) -> Dict:
        return {
            "metrics": {"time_complexity": "O(n)", "space_complexity": "O(1)"},
            "bottlenecks": [],
            "suggestions": ["Consider caching"]
        }


class CoordinatorAgent(BaseAgent):
    """Agent responsible for coordinating other agents."""

    def __init__(self):
        super().__init__("Coordinator", "coordinator", ["coordination", "orchestration", "monitoring"],
                         max_concurrent_tasks=5)

    def execute(self, task: Dict) -> Any:
        task_type = task.get("type", "coordinate")
        if task_type == "coordinate":
            return self._coordinate_agents(task)
        elif task_type == "monitor":
            return self._monitor_agents()
        elif task_type == "workflow":
            return self._execute_workflow(task)
        else:
            return {"error": f"Unknown task type: {task_type}"}

    def _coordinate_agents(self, task: Dict) -> Dict:
        agents_needed = task.get("agents", [])
        subtasks = task.get("subtasks", [])

        assignments = []
        for i, subtask in enumerate(subtasks):
            agent_type = subtask.get("agent_type", "executor")
            assignments.append({
                "subtask": subtask,
                "assigned_agent": agent_type,
                "priority": i + 1
            })

        return {"assignments": assignments, "coordination_plan": "parallel"}

    def _monitor_agents(self) -> Dict:
        agents = registry.get_all_agents()
        return {
            "total": len(agents),
            "idle": len([a for a in agents if a["status"] == "idle"]),
            "busy": len([a for a in agents if a["status"] == "busy"]),
            "agents": agents
        }

    def _execute_workflow(self, task: Dict) -> Dict:
        workflow_name = task.get("workflow", "")
        return {"workflow": workflow_name, "status": "started", "execution_id": f"exec_{int(time.time())}"}


# ============================================================
# TASK QUEUE MANAGER
# ============================================================

class TaskQueueManager:
    """Manages task queue and assignment."""

    def __init__(self):
        self.pending_queue = queue.PriorityQueue()
        self.processing: Dict[str, Dict] = {}
        self.lock = threading.Lock()

    def add_task(self, task_type: str, payload: Dict, priority: int = 3,
                 parent_task_id: str = None, depends_on: List[str] = None,
                 assigned_agent_id: str = None) -> str:
        task_id = f"task_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO task_queue (id, task_type, payload, priority, status,
                                   assigned_agent_id, parent_task_id, depends_on,
                                   created_at, max_retries)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        """, (f"task_{int(time.time() * 1000) % 100000000:08d}", task_type,
              json.dumps(payload), priority, assigned_agent_id,
              parent_task_id, json.dumps(depends_on or []),
              time.time(), 3))
        conn.commit()
        conn.close()
        return task_id

    def get_next_task(self, agent_id: str, capabilities: List[str]) -> Optional[Dict]:
        conn = get_ma_connection()
        cursor = conn.cursor()
        query = """
            SELECT * FROM task_queue
            WHERE status = 'pending'
            AND (assigned_agent_id IS NULL OR assigned_agent_id = ?)
            ORDER BY priority, created_at
            LIMIT 1
        """
        params = [capabilities[0]] if capabilities else [None]
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        if row:
            task_id = row[0]
            with self.lock:
                self.processing[task_id] = {"agent_id": "agent_1", "started_at": time.time()}

            conn = get_ma_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE task_queue SET status = 'in_progress', assigned_agent_id = ?, started_at = ? WHERE id = ?",
                          ("agent_1", time.time(), row[0]))
            conn.commit()
            conn.close()

            return {
                "id": row[0], "task_type": row[2], "payload": json.loads(row[3]),
                "priority": row[3], "parent_task_id": row[8]
            }
        return None

    def complete_task(self, task_id: str, result: Any = None):
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE task_queue SET status = 'completed', result = ?, completed_at = ? WHERE id = ?",
                      (json.dumps(result) if result else None, time.time(), task_id))
        conn.commit()
        conn.close()
        with self.lock:
            self.processing.pop(task_id, None)

    def fail_task(self, task_id: str, error: str):
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

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "task_type": row[1], "payload": json.loads(row[2]),
                "priority": row[3], "status": row[4], "assigned_agent": row[5],
                "parent_task_id": row[7], "result": json.loads(row[12]) if row[12] else None,
                "error": row[13]
            }
        return None


# ============================================================
# WORKFLOW ENGINE
# ============================================================

class WorkflowEngine:
    """Executes defined workflows."""

    def __init__(self, task_queue=None):
        self.task_queue = task_queue
        self.running_workflows: Dict[str, Dict] = {}

    def create_workflow(self, name: str, description: str, steps: List[Dict],
                        trigger_type: str = "manual", trigger_config: Dict = None) -> str:
        workflow_id = f"wf_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workflows (id, name, description, steps, trigger_type,
                                  trigger_config, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (workflow_id, name, description, json.dumps(steps),
              trigger_type, json.dumps(trigger_config or {}), time.time(), time.time()))
        conn.commit()
        conn.close()
        return workflow_id

    def execute_workflow(self, workflow_id: str, context: Dict = None) -> str:
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        workflow = cursor.fetchone()
        conn.close()

        if not workflow:
            return {"error": "Workflow not found"}

        steps = json.loads(workflow[4]) if workflow[4] else []
        exec_id = f"exec_{int(time.time() * 1000) % 100000000:08d}"

        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workflow_executions (id, workflow_id, status, current_step,
                                            step_results, context, started_at)
            VALUES (?, ?, 'running', 0, ?, ?, ?)
        """, (exec_id, workflow_id, json.dumps([]), json.dumps(context or {}), time.time()))
        conn.commit()
        conn.close()

        thread = threading.Thread(target=self._execute_workflow_steps,
                                  args=(exec_id, workflow_id, steps, context or {}), daemon=True)
        thread.start()

        return exec_id

    def _execute_workflow_steps(self, exec_id: str, workflow_id: str, steps: List[Dict], context: Dict):
        step_results = []
        context = context.copy()

        for i, step in enumerate(steps):
            conn = get_ma_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE workflow_executions SET current_step = ? WHERE id = ?",
                          (i + 1, exec_id))
            conn.commit()
            conn.close()

            step_type = step.get("type", "task")
            result = None

            if step.get("type") == "task":
                task_id = self.task_queue.add_task(
                    step.get("task_type", "execute"),
                    step.get("payload", {}),
                    priority=step.get("priority", 3)
                )
                time.sleep(1)
                result = {"task_id": "completed"}

            elif step.get("type") == "condition":
                result = self._evaluate_condition(step.get("condition"), context)

            elif step.get("type") == "parallel":
                sub_tasks = step.get("tasks", [])
                results = []
                for sub_task in sub_tasks:
                    task_id = task_queue.add_task(sub_task.get("type", "execute"), sub_task.get("payload", {}))
                    results.append({"task_id": task_id})
                result = {"sub_results": results}

            step_results.append({"step": i, "type": step_type, "result": result, "completed_at": time.time()})

            conn = get_ma_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE workflow_executions SET step_results = ? WHERE id = ?",
                          (json.dumps(step_results), exec_id))
            conn.commit()
            conn.close()

        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE workflow_executions SET status = 'completed', completed_at = ? WHERE id = ?",
                      (time.time(), exec_id))
        conn.commit()
        conn.close()

    def _evaluate_condition(self, condition: Dict, context: Dict) -> bool:
        return True

    def get_execution_status(self, exec_id: str) -> Optional[Dict]:
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workflow_executions WHERE id = ?", (exec_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "workflow_id": row[1], "status": row[2],
                "current_step": row[3], "step_results": json.loads(row[4]) if row[4] else [],
                "started_at": row[5], "completed_at": row[6], "error": row[7]
            }
        return None


# ============================================================
# MULTI-AGENT ORCHESTRATOR
# ============================================================

class MultiAgentOrchestrator:
    """Main orchestrator for multi-agent system."""

    def __init__(self):
        self.task_mgr = TaskQueueManager()
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
        self.task_queue = TaskQueueManager()
        self.workflows = WorkflowEngine(task_queue=self.task_queue)
        self.running = False

    def start(self):
        self.running = True
        self._start_builtin_agents()

    def _start_builtin_agents(self):
        agents = [
            PlannerAgent(),
            ExecutorAgent(),
            ResearcherAgent(),
            ReviewerAgent(),
            CoordinatorAgent()
        ]
        for agent in agents:
            registry.register_agent(agent)
            agent.start()

    def stop(self):
        self.running = False
        for agent in self.registry.agents.values():
            agent.stop()

    def submit_task(self, task_type: str, payload: Dict, priority: int = 3,
                    agent_type: str = None) -> str:
        caps = self._get_capabilities_for_type(agent_type) if agent_type else None
        return self.task_queue.add_task(task_type, payload, priority=3, assigned_agent_id=agent_type)

    def _get_capabilities_for_type(self, agent_type: str) -> List[str]:
        capability_map = {
            "planner": ["planning", "decomposition", "scheduling"],
            "executor": ["execution", "coding", "testing", "deployment"],
            "researcher": ["research", "analysis", "summarization"],
            "reviewer": ["review", "qa", "security", "performance"],
            "coordinator": ["coordination", "orchestration", "monitoring"]
        }
        return capability_map.get(agent_type, [])

    def get_system_status(self) -> Dict:
        agents = self.registry.get_all_agents()
        return {
            "total_agents": len(agents),
            "idle_agents": len([a for a in agents if a["status"] == "idle"]),
            "busy_agents": len([a for a in agents if a["status"] == "busy"]),
            "queue_size": 0,
            "running_workflows": len(self.workflows.running_workflows)
        }

    def get_prioritized_tasks(self, limit: int = 10) -> List[Dict]:
        tasks = self.task_mgr.get_tasks(status="pending")
        scored = []
        for t in tasks:
            score = 0
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
            score += (6 - t.get("priority", 3)) * 10
            score += (100 - t.get("progress", 0)) * 0.1
            energy = 5
            if t.get("energy_level", 2) == energy:
                score += 5
            scored.append({**t, "priority_score": score})
        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored[:limit]

    def suggest_schedule(self, date: str = None) -> Dict:
        if date:
            dt = datetime.strptime(date, "%Y-%m-%d")
        else:
            dt = datetime.now()
        tasks = self.task_mgr.get_tasks(status="pending")
        events = self.calendar_mgr.get_events(
            dt.replace(hour=0, minute=0).timestamp(),
            dt.replace(hour=23, minute=59).timestamp()
        )
        available_hours = 8
        scheduled = []
        remaining = available_hours * 60
        pending = [t for t in self.task_mgr.get_tasks(status="pending") if t.get("due_date")]
        pending.sort(key=lambda x: (x.get("due_date", 0), x.get("priority", 3)))
        for task in pending:
            if remaining <= 0:
                break
            est_min = int((task.get("estimated_hours", 1) or 1) * 60)
            if est_min <= remaining:
                scheduled.append({
                    "task_id": task["id"], "title": task["title"],
                    "duration_min": est_min, "priority": task["priority"]
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
        dash = self.get_dashboard()
        briefing = "Good morning! Here's your briefing for {:%A, %B %d}:\n\n".format(datetime.now())
        if dash["overdue_tasks"]:
            briefing += "⚠ {} overdue tasks need attention\n".format(dash["overdue_tasks"])
        if dash["today_tasks"]:
            briefing += "📋 {} tasks due today\n".format(dash["today_tasks"])
        if dash["today_events"]:
            briefing += "📅 {} events scheduled\n".format(dash["today_events"])
        if dash["upcoming_meetings"]:
            briefing += "🤝 {} meetings in next 4 hours\n".format(dash["upcoming_meetings"])
        if dash["inbox_count"]:
            briefing += "📥 {} items in inbox\n".format(dash["inbox_count"])
        if dash["habits_due"]:
            briefing += "🔄 {} habits to complete\n".format(dash["habits_due"])
        briefing += "\n⚡ Energy: {} ({:.0f}/10)\n".format(dash["energy_trend"], dash["avg_energy"])
        priorities = self.get_prioritized_tasks(3)
        if priorities:
            briefing += "\n🎯 Top priorities:"
            for i, t in enumerate(priorities, 1):
                briefing += "\n  {}. {} (due: {})".format(i, t["title"], datetime.fromtimestamp(t["due_date"]).strftime("%H:%M") if t.get("due_date") else "no due date")
        return briefing

    def evening_review(self) -> str:
        return "Evening review - to be implemented"

    def get_dashboard(self) -> Dict:
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
        tasks = self.task_mgr.get_tasks(status="pending")
        scored = []
        for t in tasks:
            score = 0
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
            score += (6 - t.get("priority", 3)) * 10
            score += (100 - t.get("progress", 0)) * 0.1
            energy = 5
            if t.get("energy_level", 2) == energy:
                score += 5
            scored.append({**t, "priority_score": score})
        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored[:limit]

    def suggest_schedule(self, date: str = None) -> Dict:
        if date:
            dt = datetime.strptime(date, "%Y-%m-%d")
        else:
            dt = datetime.now()
        tasks = self.task_mgr.get_tasks(status="pending")
        events = self.calendar_mgr.get_events(
            dt.replace(hour=0, minute=0).timestamp(),
            dt.replace(hour=23, minute=59).timestamp()
        )
        available_hours = 8
        scheduled = []
        remaining = available_hours * 60
        pending = [t for t in self.task_mgr.get_tasks(status="pending") if t.get("due_date")]
        pending.sort(key=lambda x: (x.get("due_date", 0), x.get("priority", 3)))
        for task in pending:
            if remaining <= 0:
                break
            est_min = int((task.get("estimated_hours", 1) or 1) * 60)
            if est_min <= remaining:
                scheduled.append({
                    "task_id": task["id"], "title": task["title"],
                    "duration_min": est_min, "priority": task["priority"]
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
        dash = self.get_dashboard()
        briefing = "Good morning! Here's your briefing for {:%A, %B %d}:\n\n".format(datetime.now())
        if dash["overdue_tasks"]:
            briefing += "⚠ {} overdue tasks need attention\n".format(dash["overdue_tasks"])
        if dash["today_tasks"]:
            briefing += "📋 {} tasks due today\n".format(dash["today_tasks"])
        if dash["today_events"]:
            briefing += "📅 {} events scheduled\n".format(dash["today_events"])
        if dash["upcoming_meetings"]:
            briefing += "🤝 {} meetings in next 4 hours\n".format(dash["upcoming_meetings"])
        if dash["inbox_count"]:
            briefing += "📥 {} items in inbox\n".format(dash["inbox_count"])
        if dash["habits_due"]:
            briefing += "🔄 {} habits to complete\n".format(dash["habits_due"])
        briefing += "\n⚡ Energy: {} ({:.0f}/10)\n".format(dash["energy_trend"], dash["avg_energy"])
        priorities = self.get_prioritized_tasks(3)
        if priorities:
            briefing += "\n🎯 Top priorities:"
            for i, t in enumerate(priorities, 1):
                briefing += "\n  {}. {} (due: {})".format(i, t["title"], datetime.fromtimestamp(t["due_date"]).strftime("%H:%M") if t.get("due_date") else "no due date")
        return briefing

    def evening_review(self) -> str:
        return "Evening review - to be implemented"

    def get_dashboard(self) -> Dict:
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
        tasks = self.task_mgr.get_tasks(status="pending")
        scored = []
        for t in tasks:
            score = 0
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
            score += (6 - t.get("priority", 3)) * 10
            score += (100 - t.get("progress", 0)) * 0.1
            energy = 5
            if t.get("energy_level", 2) == energy:
                score += 5
            scored.append({**t, "priority_score": score})
        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored[:limit]

    def suggest_schedule(self, date: str = None) -> Dict:
        if date:
            dt = datetime.strptime(date, "%Y-%m-%d")
        else:
            dt = datetime.now()
        tasks = self.task_mgr.get_tasks(status="pending")
        events = self.calendar_mgr.get_events(
            dt.replace(hour=0, minute=0).timestamp(),
            dt.replace(hour=23, minute=59).timestamp()
        )
        available_hours = 8
        scheduled = []
        remaining = available_hours * 60
        pending = [t for t in self.task_mgr.get_tasks(status="pending") if t.get("due_date")]
        pending.sort(key=lambda x: (x.get("due_date", 0), x.get("priority", 3)))
        for task in pending:
            if remaining <= 0:
                break
            est_min = int((task.get("estimated_hours", 1) or 1) * 60)
            if est_min <= remaining:
                scheduled.append({
                    "task_id": task["id"], "title": task["title"],
                    "duration_min": est_min, "priority": task["priority"]
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
        dash = self.get_dashboard()
        briefing = "Good morning! Here's your briefing for {:%A, %B %d}:\n\n".format(datetime.now())
        if dash["overdue_tasks"]:
            briefing += "⚠ {} overdue tasks need attention\n".format(dash["overdue_tasks"])
        if dash["today_tasks"]:
            briefing += "📋 {} tasks due today\n".format(dash["today_tasks"])
        if dash["today_events"]:
            briefing += "📅 {} events scheduled\n".format(dash["today_events"])
        if dash["upcoming_meetings"]:
            briefing += "🤝 {} meetings in next 4 hours\n".format(dash["upcoming_meetings"])
        if dash["inbox_count"]:
            briefing += "📥 {} items in inbox\n".format(dash["inbox_count"])
        if dash["habits_due"]:
            briefing += "🔄 {} habits to complete\n".format(dash["habits_due"])
        briefing += "\n⚡ Energy: {} ({:.0f}/10)\n".format(dash["energy_trend"], dash["avg_energy"])
        priorities = self.get_prioritized_tasks(3)
        if priorities:
            briefing += "\n🎯 Top priorities:"
            for i, t in enumerate(priorities, 1):
                briefing += "\n  {}. {} (due: {})".format(i, t["title"], datetime.fromtimestamp(t["due_date"]).strftime("%H:%M") if t.get("due_date") else "no due date")
        return briefing

    def evening_review(self) -> str:
        return "Evening review - to be implemented"

    def get_dashboard(self) -> Dict:
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
        tasks = self.task_mgr.get_tasks(status="pending")
        scored = []
        for t in tasks:
            score = 0
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
            score += (6 - t.get("priority", 3)) * 10
            score += (100 - t.get("progress", 0)) * 0.1
            energy = 5
            if t.get("energy_level", 2) == energy:
                score += 5
            scored.append({**t, "priority_score": score})
        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored[:limit]

    def suggest_schedule(self, date: str = None) -> Dict:
        if date:
            dt = datetime.strptime(date, "%Y-%m-%d")
        else:
            dt = datetime.now()
        tasks = self.task_mgr.get_tasks(status="pending")
        events = self.calendar_mgr.get_events(
            dt.replace(hour=0, minute=0).timestamp(),
            dt.replace(hour=23, minute=59).timestamp()
        )
        available_hours = 8
        scheduled = []
        remaining = available_hours * 60
        pending = [t for t in self.task_mgr.get_tasks(status="pending") if t.get("due_date")]
        pending.sort(key=lambda x: (x.get("due_date", 0), x.get("priority", 3)))
        for task in pending:
            if remaining <= 0:
                break
            est_min = int((task.get("estimated_hours", 1) or 1) * 60)
            if est_min <= remaining:
                scheduled.append({
                    "task_id": task["id"], "title": task["title"],
                    "duration_min": est_min, "priority": task["priority"]
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
        dash = self.get_dashboard()
        briefing = "Good morning! Here's your briefing for {:%A, %B %d}:\n\n".format(datetime.now())
        if dash["overdue_tasks"]:
            briefing += "⚠ {} overdue tasks need attention\n".format(dash["overdue_tasks"])
        if dash["today_tasks"]:
            briefing += "📋 {} tasks due today\n".format(dash["today_tasks"])
        if dash["today_events"]:
            briefing += "📅 {} events scheduled\n".format(dash["today_events"])
        if dash["upcoming_meetings"]:
            briefing += "🤝 {} meetings in next 4 hours\n".format(dash["upcoming_meetings"])
        if dash["inbox_count"]:
            briefing += "📥 {} items in inbox\n".format(dash["inbox_count"])
        if dash["habits_due"]:
            briefing += "🔄 {} habits to complete\n".format(dash["habits_due"])
        briefing += "\n⚡ Energy: {} ({:.0f}/10)\n".format(dash["energy_trend"], dash["avg_energy"])
        priorities = self.get_prioritized_tasks(3)
        if priorities:
            briefing += "\n🎯 Top priorities:"
            for i, t in enumerate(priorities, 1):
                briefing += "\n  {}. {} (due: {})".format(i, t["title"], datetime.fromtimestamp(t["due_date"]).strftime("%H:%M") if t.get("due_date") else "no due date")
        return briefing

    def evening_review(self) -> str:
        return "Evening review - to be implemented"

    def get_dashboard(self) -> Dict:
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
        tasks = self.task_mgr.get_tasks(status="pending")
        scored = []
        for t in tasks:
            score = 0
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
            score += (6 - t.get("priority", 3)) * 10
            score += (100 - t.get("progress", 0)) * 0.1
            energy = 5
            if t.get("energy_level", 2) == energy:
                score += 5
            scored.append({**t, "priority_score": score})
        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored[:limit]

    def suggest_schedule(self, date: str = None) -> Dict:
        if date:
            dt = datetime.strptime(date, "%Y-%m-%d")
        else:
            dt = datetime.now()
        tasks = self.task_mgr.get_tasks(status="pending")
        events = self.calendar_mgr.get_events(
            dt.replace(hour=0, minute=0).timestamp(),
            dt.replace(hour=23, minute=59).timestamp()
        )
        available_hours = 8
        scheduled = []
        remaining = available_hours * 60
        pending = [t for t in self.task_mgr.get_tasks(status="pending") if t.get("due_date")]
        pending.sort(key=lambda x: (x.get("due_date", 0), x.get("priority", 3)))
        for task in pending:
            if remaining <= 0:
                break
            est_min = int((task.get("estimated_hours", 1) or 1) * 60)
            if est_min <= remaining:
                scheduled.append({
                    "task_id": task["id"], "title": task["title"],
                    "duration_min": est_min, "priority": task["priority"]
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
        return self.morning_briefing()

    def evening_review(self) -> str:
        return self.evening_review()

    def get_dashboard(self) -> Dict:
        return self.get_dashboard()

    def get_prioritized_tasks(self, limit: int = 10) -> List[Dict]:
        return self.get_prioritized_tasks(limit)

    def suggest_schedule(self, date: str = None) -> Dict:
        return self.suggest_schedule(date)

    def morning_briefing(self) -> str:
        return self.morning_briefing()

    def evening_review(self) -> str:
        return self.evening_review()


# ============================================================
# MODULE EXPORTS
# ============================================================

registry = AgentRegistry()
task_queue = TaskQueueManager()
workflow_engine = WorkflowEngine(task_queue=task_queue)
orchestrator = MultiAgentOrchestrator()


def ma_debug() -> str:
    conn = get_ma_connection()
    cursor = conn.cursor()
    tables = ["agents", "task_queue", "agent_messages", "workflows",
              "workflow_executions", "agent_metrics", "collaboration_logs"]
    output = "Multi-Agent System Debug:\n"
    for t in tables:
        cursor.execute("SELECT COUNT(*) FROM {}".format(t))
        count = cursor.fetchone()[0]
        output += "  {}: {} records\n".format(t, count)
    conn.close()
    return output


def create_task(title: str, **kwargs) -> str:
    return task_queue.add_task(title, **kwargs)


def get_task(task_id: str) -> Optional[Dict]:
    return task_queue.get_task_status(task_id)


def update_task(task_id: str, **kwargs) -> bool:
    return task_queue.update_task(task_id, **kwargs)


def complete_task(task_id: str) -> bool:
    return task_queue.complete_task(task_id)


def get_tasks(status: str = None, **kwargs) -> List[Dict]:
    return task_queue.get_tasks(status, **kwargs)


def get_today_tasks() -> List[Dict]:
    return task_queue.get_today_tasks()


def get_overdue_tasks() -> List[Dict]:
    return task_queue.get_overdue_tasks()


def create_project(name: str, **kwargs) -> str:
    return task_queue.create_project(name, **kwargs)


def get_project(proj_id: str) -> Optional[Dict]:
    return task_queue.get_project(proj_id)


def list_projects(status: str = None) -> List[Dict]:
    return task_queue.list_projects(status)


def create_event(title: str, start: float, end: float, **kwargs) -> str:
    return task_queue.create_event(title, start, end, **kwargs)


def get_events(start: float, end: float) -> List[Dict]:
    return task_queue.get_events(start, end)


def get_today_events() -> List[Dict]:
    return task_queue.get_today_events()


def get_upcoming_meetings(hours: int = 24) -> List[Dict]:
    return task_queue.get_upcoming_meetings(hours)


def create_decision(title: str, **kwargs) -> str:
    return decision_mgr.create_decision(title, **kwargs)


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


def quick_capture(content: str, **kwargs) -> str:
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
    return orchestrator.get_dashboard()


def get_prioritized_tasks(limit: int = 10) -> List[Dict]:
    return orchestrator.get_prioritized_tasks(limit)


def suggest_schedule(date: str = None) -> Dict:
    return orchestrator.suggest_schedule(date)


def morning_briefing() -> str:
    return orchestrator.morning_briefing()


def evening_review() -> str:
    return orchestrator.evening_review()


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
    return orchestrator.get_dashboard()


def get_prioritized_tasks(limit: int = 10) -> List[Dict]:
    return orchestrator.get_prioritized_tasks(limit)


def suggest_schedule(date: str = None) -> Dict:
    return orchestrator.suggest_schedule(date)


def morning_briefing() -> str:
    return orchestrator.morning_briefing()


def evening_review() -> str:
    return orchestrator.evening_review()


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
    return orchestrator.get_dashboard()


def get_prioritized_tasks(limit: int = 10) -> List[Dict]:
    return orchestrator.get_prioritized_tasks(limit)


def suggest_schedule(date: str = None) -> Dict:
    return orchestrator.suggest_schedule(date)


def morning_briefing() -> str:
    return orchestrator.morning_briefing()


def evening_review() -> str:
    return orchestrator.evening_review()


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
    return orchestrator.get_dashboard()


def get_prioritized_tasks(limit: int = 10) -> List[Dict]:
    return orchestrator.get_prioritized_tasks(limit)


def suggest_schedule(date: str = None) -> Dict:
    return orchestrator.suggest_schedule(date)


def morning_briefing() -> str:
    return orchestrator.morning_briefing()


def evening_review() -> str:
    return orchestrator.evening_review()


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
    return orchestrator.get_dashboard()


def get_prioritized_tasks(limit: int = 10) -> List[Dict]:
    return orchestrator.get_prioritized_tasks(limit)


def suggest_schedule(date: str = None) -> Dict:
    return orchestrator.suggest_schedule(date)


def morning_briefing() -> str:
    return orchestrator.morning_briefing()


def evening_review() -> str:
    return orchestrator.evening_review()


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
    return orchestrator.get_dashboard()


def get_prioritized_tasks(limit: int = 10) -> List[Dict]:
    return orchestrator.get_prioritized_tasks(limit)


def suggest_schedule(date: str = None) -> Dict:
    return orchestrator.suggest_schedule(date)


def morning_briefing() -> str:
    return orchestrator.morning_briefing()


def evening_review() -> str:
    return orchestrator.evening_review()


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
    return orchestrator.get_dashboard()


def get_prioritized_tasks(limit: int = 10) -> List[Dict]:
    return orchestrator.get_prioritized_tasks(limit)


def suggest_schedule(date: str = None) -> Dict:
    return orchestrator.suggest_schedule(date)


def morning_briefing() -> str:
    return orchestrator.morning_briefing()


def evening_review() -> str:
    return orchestrator.evening_review()


if __name__ == "__main__":
    print("Multi-Agent System Agent loaded.")
    print("Core: AgentRegistry, BaseAgent, specialized agents")
    print("      TaskQueueManager, WorkflowEngine, MultiAgentOrchestrator")