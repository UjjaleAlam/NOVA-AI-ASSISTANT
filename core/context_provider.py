"""
Shared Context Provider - Phase 36 Integration
Builds and injects scoped context into tasks for all agents.
"""

import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

from core.context_engine import get_current_session, build_context_for_llm, get_project_context
from core.semantic_memory import search_memory
from core.multi_agent import registry
from core.search_manager import search_manager


@dataclass
class TaskContext:
    """Scoped context for a specific task."""
    session_id: str
    user_goal: str
    project_path: Optional[str] = None
    project_info: Optional[Dict] = None
    active_file: Optional[str] = None
    relevant_files: List[Dict] = field(default_factory=list)
    recent_tasks: List[Dict] = field(default_factory=list)
    relevant_memories: List[Dict] = field(default_factory=list)
    decisions: List[Dict] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    previous_results: List[Dict] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class ContextProvider:
    """Builds and provides scoped context for tasks."""

    def __init__(self, max_files: int = 10, max_memories: int = 5, max_history: int = 10):
        self.max_files = max_files
        self.max_memories = max_memories
        self.max_history = max_history

    def build_context(self, task_payload: Dict, task_type: str = "") -> TaskContext:
        """Build context for a task based on its payload and type."""
        session_id = get_current_session()
        user_goal = task_payload.get("goal") or task_payload.get("description") or task_payload.get("query", "")

        # Get project context
        project_path, project_info = self._get_project_context(task_payload)

        # Get active file
        active_file = task_payload.get("file_path") or task_payload.get("active_file")

        # Search relevant files
        relevant_files = self._search_relevant_files(user_goal, project_path) if user_goal else []

        # Get recent task history
        recent_tasks = self._get_recent_tasks(session_id)

        # Search relevant memories
        relevant_memories = self._search_relevant_memories(user_goal) if user_goal else []

        # Get decisions from context engine
        decisions = self._get_decisions(session_id, project_path)

        # Build constraints
        constraints = self._build_constraints(task_payload, project_info)

        # Get previous results for this session
        previous_results = self._get_previous_results(session_id, task_type=task_type)

        return TaskContext(
            session_id=session_id,
            user_goal=user_goal,
            project_path=project_path,
            project_info=project_info,
            active_file=active_file,
            relevant_files=relevant_files,
            recent_tasks=recent_tasks,
            relevant_memories=relevant_memories,
            decisions=decisions,
            constraints=constraints,
            previous_results=previous_results
        )

    def _get_project_context(self, task_payload: Dict) -> tuple:
        """Get current project path and info."""
        project_path = task_payload.get("project_path")
        if not project_path:
            # Try to get from context engine
            from core.context_engine import get_recent_projects
            projects = get_recent_projects(1)
            if projects:
                project_path = projects[0].get("project_path")

        project_info = None
        if project_path:
            project_info = get_project_context(project_path)
        return project_path, project_info

    def _search_relevant_files(self, query: str, project_path: str = None) -> List[Dict]:
        """Search for files relevant to the query."""
        try:
            results = search_manager.search(query, limit=self.max_files)
            # Filter by project path if provided
            if project_path:
                results = [r for r in results if r.get("path", "").startswith(project_path)]
            return results[:self.max_files]
        except Exception:
            return []

    def _get_recent_tasks(self, session_id: str) -> List[Dict]:
        """Get recent tasks from the session."""
        try:
            from core.context_engine import get_conversation_history
            history = get_conversation_history(session_id, limit=self.max_history)
            return [{"role": h["role"], "content": h["content"][:200]} for h in history]
        except Exception:
            return []

    def _search_relevant_memories(self, query: str) -> List[Dict]:
        """Search semantic memory for relevant facts."""
        try:
            results = search_memory(query, n_results=self.max_memories)
            return [{"text": r["text"], "distance": r.get("distance", 0)} for r in results]
        except Exception:
            return []

    def _get_decisions(self, session_id: str, project_path: str = None) -> List[Dict]:
        """Get recent decisions from context engine."""
        try:
            from core.context_engine import search_knowledge_facts
            results = search_knowledge_facts("decision", limit=5)
            return [{"fact_key": r["fact_key"], "fact_value": r["fact_value"]} for r in results]
        except Exception:
            return []

    def _build_constraints(self, task_payload: Dict, project_info: Dict = None) -> List[str]:
        """Build constraints from task payload and project info."""
        constraints = []

        # Explicit constraints from payload
        if "constraints" in task_payload:
            constraints.extend(task_payload["constraints"])

        # Project-based constraints
        if project_info:
            lang = project_info.get("language")
            if lang:
                constraints.append(f"Project language: {lang}")
            framework = project_info.get("framework")
            if framework:
                constraints.append(f"Project framework: {framework}")

        # Risk level constraints
        risk_level = task_payload.get("risk_level", "medium")
        if risk_level == "high":
            constraints.append("High risk - require user verification for destructive actions")
        elif risk_level == "critical":
            constraints.append("Critical risk - explicit user approval required")

        return constraints

    def _get_previous_results(self, session_id: str, task_type: str = "") -> List[Dict]:
        """Get previous task results for this session."""
        try:
            import sqlite3
            conn = sqlite3.connect("database/multi_agent.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, task_type, payload, result, completed_at
                FROM task_queue
                WHERE status = 'completed' AND created_at > ?
                ORDER BY completed_at DESC
                LIMIT ?
            """, (time.time() - 86400, self.max_history))  # Last 24 hours
            rows = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                results.append({
                    "task_id": row[0],
                    "task_type": row[1],
                    "payload": json.loads(row[2]) if row[2] else {},
                    "result": json.loads(row[3]) if row[3] else None,
                    "completed_at": row[4]
                })
            return results
        except Exception:
            return []

    def inject_into_payload(self, payload: Dict, context: TaskContext) -> Dict:
        """Inject context into task payload."""
        enriched = payload.copy()
        enriched["_context"] = {
            "session_id": context.session_id,
            "user_goal": context.user_goal,
            "project_path": context.project_path,
            "project_info": context.project_info,
            "active_file": context.active_file,
            "relevant_files": context.relevant_files,
            "recent_tasks": context.recent_tasks,
            "relevant_memories": context.relevant_memories,
            "decisions": context.decisions,
            "constraints": context.constraints,
            "previous_results": context.previous_results
        }
        return enriched


# Global context provider instance
context_provider = ContextProvider()


def get_task_context(task_payload: Dict, task_type: str = "") -> TaskContext:
    """Convenience function to build task context."""
    return context_provider.build_context(task_payload, task_type)


def inject_context(payload: Dict, task_type: str = "") -> Dict:
    """Convenience function to inject context into payload."""
    context = context_provider.build_context(payload, task_type)
    return context_provider.inject_into_payload(payload, context)


if __name__ == "__main__":
    # Test
    ctx = get_task_context({"goal": "Build a REST API", "project_path": "C:/project"})
    print("Context built:")
    print(f"  Session: {ctx.session_id}")
    print(f"  Goal: {ctx.user_goal}")
    print(f"  Project: {ctx.project_path}")
    print(f"  Relevant files: {len(ctx.relevant_files)}")
    print(f"  Memories: {len(ctx.relevant_memories)}")
    print(f"  Constraints: {ctx.constraints}")