"""
Interrupt System - Phase 18
Priority handling, context switching, and preemptive multitasking for Nova.
Fully local, no cloud dependencies.
"""

import threading
import time
import heapq
import uuid
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
from contextlib import contextmanager


class Priority(Enum):
    """Interrupt priority levels (higher = more urgent)."""
    BACKGROUND = 0      # Maintenance, sync, cleanup
    LOW = 10            # Non-urgent notifications
    NORMAL = 50         # Standard commands
    HIGH = 100          # User-facing responses
    CRITICAL = 200      # System alerts, errors
    EMERGENCY = 500     # Safety, security, immediate action


class InterruptState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class Interrupt:
    """Represents an interruptible task."""
    interrupt_id: str
    name: str
    priority: Priority
    handler: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict = field(default_factory=dict)
    state: InterruptState = InterruptState.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    context: Dict = field(default_factory=dict)
    can_preempt: bool = True
    can_be_preempted: bool = True
    max_runtime: float = 300.0  # 5 minutes default
    checkpoint_data: Any = None

    def __lt__(self, other):
        """For priority queue ordering (higher priority first)."""
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        return self.created_at < other.created_at


@dataclass
class ContextSnapshot:
    """Snapshot of execution context for switching."""
    snapshot_id: str
    interrupt_id: str
    timestamp: float
    local_vars: Dict = field(default_factory=dict)
    call_stack: List[str] = field(default_factory=list)
    execution_state: Dict = field(default_factory=dict)
    thread_id: int = 0


class InterruptManager:
    """Manages interruptible tasks with priority-based scheduling."""

    def __init__(self):
        self.queue: List[Interrupt] = []
        self.running: Optional[Interrupt] = None
        self.paused: Dict[str, Interrupt] = {}
        self.completed: Dict[str, Interrupt] = {}
        self.lock = threading.RLock()
        self.worker_thread: Optional[threading.Thread] = None
        self.running_flag = False
        self.preemption_enabled = True
        self.context_stack: List[ContextSnapshot] = []
        self.current_context: Dict = {}
        self.stats = {
            "total_interrupts": 0,
            "preemptions": 0,
            "context_switches": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }

    def submit(self, name: str, handler: Callable, priority: Priority = Priority.NORMAL,
               args: tuple = (), kwargs: Dict = None, context: Dict = None,
               can_preempt: bool = True, can_be_preempted: bool = True,
               max_runtime: float = 300.0) -> str:
        """Submit a new interruptible task."""
        interrupt = Interrupt(
            interrupt_id=str(uuid.uuid4())[:8],
            name=name,
            priority=priority,
            handler=handler,
            args=args,
            kwargs=kwargs or {},
            context=context or {},
            can_preempt=can_preempt,
            can_be_preempted=can_be_preempted,
            max_runtime=max_runtime
        )

        with self.lock:
            heapq.heappush(self.queue, interrupt)
            self.stats["total_interrupts"] += 1

        # Check for preemption
        self._check_preemption()

        return interrupt.interrupt_id

    def _check_preemption(self):
        """Check if current running task should be preempted."""
        if not self.preemption_enabled or not self.running:
            return

        with self.lock:
            if not self.queue:
                return

            next_task = self.queue[0]
            if (next_task.priority.value > self.running.priority.value and
                self.running.can_be_preempted and next_task.can_preempt):
                self._preempt_current(next_task)

    def _preempt_current(self, new_task: Interrupt):
        """Preempt the currently running task."""
        if not self.running:
            return

        # Save context
        snapshot = self._save_context(self.running.interrupt_id)
        self.context_stack.append(snapshot)

        # Pause current
        self.running.state = InterruptState.PAUSED
        self.paused[self.running.interrupt_id] = self.running

        # Start new task
        self.running = heapq.heappop(self.queue)
        self.running.state = InterruptState.RUNNING
        self.running.started_at = time.time()

        self.stats["preemptions"] += 1
        self.stats["context_switches"] += 1

        # Execute in background
        threading.Thread(target=self._execute_task, args=(self.running,), daemon=True).start()

    def _save_context(self, interrupt_id: str) -> ContextSnapshot:
        """Save execution context for an interrupt."""
        return ContextSnapshot(
            snapshot_id=str(uuid.uuid4())[:8],
            interrupt_id=interrupt_id,
            timestamp=time.time(),
            local_vars=dict(self.current_context),
            call_stack=[],  # Would need frame inspection for real call stack
            execution_state={"phase": "preempted"},
            thread_id=threading.get_ident()
        )

    def _restore_context(self, snapshot: ContextSnapshot):
        """Restore execution context."""
        self.current_context = dict(snapshot.local_vars)

    def _execute_task(self, interrupt: Interrupt):
        """Execute an interrupt task."""
        try:
            interrupt.result = interrupt.handler(*interrupt.args, **interrupt.kwargs)
            interrupt.state = InterruptState.COMPLETED
            interrupt.completed_at = time.time()
            self.stats["completed"] += 1
        except Exception as e:
            interrupt.error = str(e)
            interrupt.state = InterruptState.FAILED
            interrupt.completed_at = time.time()
            self.stats["failed"] += 1
        finally:
            with self.lock:
                self.completed[interrupt.interrupt_id] = interrupt
                if self.running and self.running.interrupt_id == interrupt.interrupt_id:
                    self.running = None
                    self._schedule_next()

    def _schedule_next(self):
        """Schedule the next task from queue."""
        with self.lock:
            # Resume paused task if higher priority than queue
            if self.paused:
                highest_paused = max(self.paused.values(), key=lambda i: i.priority.value)
                if not self.queue or highest_paused.priority.value >= self.queue[0].priority.value:
                    interrupt = self.paused.pop(highest_paused.interrupt_id)
                    interrupt.state = InterruptState.RUNNING
                    self.running = interrupt
                    self.stats["context_switches"] += 1
                    threading.Thread(target=self._execute_task, args=(interrupt,), daemon=True).start()
                    return

            # Otherwise take from queue
            if self.queue:
                interrupt = heapq.heappop(self.queue)
                interrupt.state = InterruptState.RUNNING
                interrupt.started_at = time.time()
                self.running = interrupt
                threading.Thread(target=self._execute_task, args=(interrupt,), daemon=True).start()

    def cancel(self, interrupt_id: str) -> bool:
        """Cancel a pending or paused interrupt."""
        with self.lock:
            # Check queue
            for i, interrupt in enumerate(self.queue):
                if interrupt.interrupt_id == interrupt_id:
                    interrupt.state = InterruptState.CANCELLED
                    self.queue.pop(i)
                    heapq.heapify(self.queue)
                    self.stats["cancelled"] += 1
                    return True

            # Check paused
            if interrupt_id in self.paused:
                interrupt = self.paused.pop(interrupt_id)
                interrupt.state = InterruptState.CANCELLED
                self.stats["cancelled"] += 1
                return True

            # Check running
            if self.running and self.running.interrupt_id == interrupt_id:
                if self.running.can_be_preempted:
                    self.running.state = InterruptState.CANCELLED
                    self.stats["cancelled"] += 1
                    self.running = None
                    self._schedule_next()
                    return True

        return False

    def pause(self, interrupt_id: str) -> bool:
        """Pause a running interrupt."""
        with self.lock:
            if self.running and self.running.interrupt_id == interrupt_id:
                if self.running.can_be_preempted:
                    snapshot = self._save_context(interrupt_id)
                    self.context_stack.append(snapshot)
                    self.running.state = InterruptState.PAUSED
                    self.paused[interrupt_id] = self.running
                    self.running = None
                    self._schedule_next()
                    return True
        return False

    def resume(self, interrupt_id: str) -> bool:
        """Resume a paused interrupt."""
        with self.lock:
            if interrupt_id in self.paused:
                interrupt = self.paused.pop(interrupt_id)
                interrupt.state = InterruptState.RUNNING
                # Preempt current if higher priority
                if self.running and interrupt.priority.value > self.running.priority.value:
                    self._preempt_current(interrupt)
                else:
                    # Queue it
                    heapq.heappush(self.queue, interrupt)
                return True
        return False

    def get_status(self, interrupt_id: str) -> Optional[Dict]:
        """Get status of an interrupt."""
        with self.lock:
            # Check running
            if self.running and self.running.interrupt_id == interrupt_id:
                return self._interrupt_to_dict(self.running)

            # Check queue
            for interrupt in self.queue:
                if interrupt.interrupt_id == interrupt_id:
                    return self._interrupt_to_dict(interrupt)

            # Check paused
            if interrupt_id in self.paused:
                return self._interrupt_to_dict(self.paused[interrupt_id])

            # Check completed
            if interrupt_id in self.completed:
                return self._interrupt_to_dict(self.completed[interrupt_id])

        return None

    def _interrupt_to_dict(self, interrupt: Interrupt) -> Dict:
        return {
            "interrupt_id": interrupt.interrupt_id,
            "name": interrupt.name,
            "priority": interrupt.priority.name,
            "state": interrupt.state.value,
            "created_at": interrupt.created_at,
            "started_at": interrupt.started_at,
            "completed_at": interrupt.completed_at,
            "runtime": (interrupt.completed_at or time.time()) - (interrupt.started_at or interrupt.created_at) if interrupt.started_at else 0,
            "result": str(interrupt.result)[:100] if interrupt.result else None,
            "error": interrupt.error
        }

    def list_interrupts(self, state: InterruptState = None) -> List[Dict]:
        """List all interrupts, optionally filtered by state."""
        with self.lock:
            results = []

            if self.running and (not state or self.running.state == state):
                results.append(self._interrupt_to_dict(self.running))

            for interrupt in self.queue:
                if not state or interrupt.state == state:
                    results.append(self._interrupt_to_dict(interrupt))

            for interrupt in self.paused.values():
                if not state or interrupt.state == state:
                    results.append(self._interrupt_to_dict(interrupt))

            for interrupt in list(self.completed.values())[-50:]:  # Last 50 completed
                if not state or interrupt.state == state:
                    results.append(self._interrupt_to_dict(interrupt))

            return results

    def get_stats(self) -> Dict:
        return dict(self.stats)

    def set_preemption(self, enabled: bool):
        self.preemption_enabled = enabled

    def clear_completed(self, older_than: float = 3600):
        """Clear completed interrupts older than specified seconds."""
        with self.lock:
            cutoff = time.time() - older_than
            to_remove = [
                k for k, v in self.completed.items()
                if v.completed_at and v.completed_at < cutoff
            ]
            for k in to_remove:
                del self.completed[k]

    def shutdown(self):
        """Shutdown the interrupt manager."""
        self.preemption_enabled = False
        with self.lock:
            # Cancel all pending
            for interrupt in self.queue:
                interrupt.state = InterruptState.CANCELLED
            self.queue.clear()

            # Cancel paused
            for interrupt in self.paused.values():
                interrupt.state = InterruptState.CANCELLED
            self.paused.clear()

            # Running task will complete naturally or be cancelled
            if self.running:
                self.running.can_be_preempted = True


# Global instance
interrupt_manager = InterruptManager()


# Convenience decorators
def interruptible(name: str = None, priority: Priority = Priority.NORMAL,
                  can_preempt: bool = True, can_be_preempted: bool = True):
    """Decorator to make a function interruptible."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            task_name = name or func.__name__
            interrupt_id = interrupt_manager.submit(
                task_name, func, priority=priority,
                args=args, kwargs=kwargs,
                can_preempt=can_preempt, can_be_preempted=can_be_preempted
            )
            return interrupt_id
        return wrapper
    return decorator


@contextmanager
def critical_section():
    """Context manager to disable preemption temporarily."""
    interrupt_manager.set_preemption(False)
    try:
        yield
    finally:
        interrupt_manager.set_preemption(True)


@contextmanager
def high_priority_section():
    """Context manager to run at high priority."""
    # This would require thread-local priority, simplified here
    yield


# Voice command integration
def interrupt_debug() -> str:
    """Debug interrupt system status."""
    stats = interrupt_manager.get_stats()
    running = interrupt_manager.list_interrupts(InterruptState.RUNNING)
    pending = interrupt_manager.list_interrupts(InterruptState.PENDING)
    paused = interrupt_manager.list_interrupts(InterruptState.PAUSED)

    output = f"Interrupt System Status:\n"
    output += f"  Preemption: {'Enabled' if interrupt_manager.preemption_enabled else 'Disabled'}\n"
    output += f"  Stats: {stats}\n"
    output += f"  Running: {len(running)}\n"
    for r in running:
        output += f"    {r['interrupt_id']}: {r['name']} ({r['priority']})\n"
    output += f"  Pending: {len(pending)}\n"
    for p in pending[:5]:
        output += f"    {p['interrupt_id']}: {p['name']} ({p['priority']})\n"
    output += f"  Paused: {len(paused)}\n"
    for p in paused:
        output += f"    {p['interrupt_id']}: {p['name']} ({p['priority']})\n"
    return output


# Example handlers for testing
def example_long_task(task_name: str, duration: float = 10.0):
    """Example long-running task that can be interrupted."""
    start = time.time()
    while time.time() - start < duration:
        time.sleep(0.1)
        # Check if cancelled (in real implementation, would check interrupt state)
    return f"{task_name} completed in {duration}s"


def example_critical_task():
    """Example critical task."""
    time.sleep(0.5)
    return "Critical task done"


if __name__ == "__main__":
    # Demo
    print("Interrupt System Demo")
    print("=" * 50)

    # Submit some tasks
    id1 = interrupt_manager.submit("Low priority task", example_long_task, Priority.LOW, args=("Task 1", 5.0))
    id2 = interrupt_manager.submit("Normal task", example_long_task, Priority.NORMAL, args=("Task 2", 3.0))
    id3 = interrupt_manager.submit("High priority task", example_critical_task, Priority.HIGH)

    print(f"Submitted: {id1}, {id2}, {id3}")

    time.sleep(1)
    print(interrupt_debug())

    time.sleep(3)
    print("\nAfter 3 seconds:")
    print(interrupt_debug())

    # Cleanup
    interrupt_manager.shutdown()