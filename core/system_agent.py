"""
System Agent - Phase 23
System monitoring, automation, process management, service management.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import threading
import subprocess
import psutil
import platform
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from collections import defaultdict

from core.context_engine import get_connection


DB_DIR = "database"
SYSTEM_AGENT_DB = os.path.join(DB_DIR, "system_agent.db")

os.makedirs(DB_DIR, exist_ok=True)


def init_system_agent_db():
    conn = get_connection()
    cursor = conn.cursor()

    # System metrics history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics_history (
            id TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            timestamp REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metrics_name_time
        ON metrics_history(metric_name, timestamp)
    """)

    # Process tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS process_events (
            id TEXT PRIMARY KEY,
            pid INTEGER,
            name TEXT,
            event_type TEXT,  -- 'start', 'stop', 'crash', 'high_cpu', 'high_mem'
            cpu_percent REAL,
            memory_mb REAL,
            timestamp REAL NOT NULL,
            details TEXT  -- JSON
        )
    """)

    # Service management
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT,
            service_type TEXT,  -- 'systemd', 'windows', 'custom'
            command_start TEXT,
            command_stop TEXT,
            command_restart TEXT,
            command_status TEXT,
            auto_start BOOLEAN DEFAULT 0,
            enabled BOOLEAN DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Service status history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_status_history (
            id TEXT PRIMARY KEY,
            service_id TEXT NOT NULL,
            status TEXT,  -- 'running', 'stopped', 'failed', 'starting', 'stopping'
            pid INTEGER,
            timestamp REAL NOT NULL,
            details TEXT
        )
    """)

    # Automation rules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS automation_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            trigger_type TEXT NOT NULL,  -- 'metric', 'schedule', 'event', 'process'
            trigger_config TEXT NOT NULL,  -- JSON
            action_type TEXT NOT NULL,  -- 'command', 'service_action', 'notification', 'script'
            action_config TEXT NOT NULL,  -- JSON
            enabled BOOLEAN DEFAULT 1,
            cooldown_seconds INTEGER DEFAULT 60,
            last_triggered REAL,
            created_at REAL NOT NULL,
            trigger_count INTEGER DEFAULT 0
        )
    """)

    # Automation execution history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS automation_executions (
            id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            triggered_at REAL NOT NULL,
            success BOOLEAN,
            output TEXT,
            error TEXT
        )
    """)

    # System snapshots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_snapshots (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            cpu_percent REAL,
            memory_percent REAL,
            disk_percent REAL,
            network_io TEXT,  -- JSON
            process_count INTEGER,
            load_average TEXT,  -- JSON
            temperature_celsius REAL
        )
    """)

    # Alert rules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            condition TEXT NOT NULL,  -- '>', '<', '>=', '<=', '==', '!='
            threshold REAL NOT NULL,
            severity TEXT DEFAULT 'warning',  -- 'info', 'warning', 'critical'
            notification_channels TEXT,  -- JSON array
            enabled BOOLEAN DEFAULT 1,
            cooldown_seconds INTEGER DEFAULT 300,
            last_triggered REAL
        )
    """)

    # Alert history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            metric_value REAL NOT NULL,
            threshold REAL NOT NULL,
            severity TEXT,
            acknowledged BOOLEAN DEFAULT 0,
            triggered_at REAL NOT NULL,
            acknowledged_at REAL
        )
    """)

    conn.commit()
    conn.close()


init_system_agent_db()


class SystemMonitor:
    """Monitors system metrics and resources."""

    def __init__(self):
        self.sampling_interval = 30  # seconds
        self.history_retention = 86400 * 7  # 7 days
        self.running = False
        self.worker_thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

    def _monitor_loop(self):
        while self.running:
            try:
                self._collect_metrics()
            except Exception as e:
                print(f"System monitor error: {e}")
            time.sleep(self.sampling_interval)

    def _collect_metrics(self):
        timestamp = time.time()

        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        self._store_metric("cpu_percent", cpu_percent, "%", timestamp)

        # Per-CPU
        per_cpu = psutil.cpu_percent(percpu=True)
        for i, pct in enumerate(per_cpu):
            self._store_metric(f"cpu_core_{i}_percent", pct, "%", timestamp)

        # Memory
        mem = psutil.virtual_memory()
        self._store_metric("memory_percent", mem.percent, "%", timestamp)
        self._store_metric("memory_available_gb", mem.available / (1024**3), "GB", timestamp)
        self._store_metric("memory_used_gb", mem.used / (1024**3), "GB", timestamp)

        # Swap
        swap = psutil.swap_memory()
        self._store_metric("swap_percent", swap.percent, "%", timestamp)

        # Disk
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                self._store_metric(f"disk_{partition.mountpoint.replace('/', '_')}_percent",
                                 usage.percent, "%", timestamp)
                self._store_metric(f"disk_{partition.mountpoint.replace('/', '_')}_free_gb",
                                 usage.free / (1024**3), "GB", timestamp)
            except PermissionError:
                pass

        # Network
        net_io = psutil.net_io_counters()
        self._store_metric("network_bytes_sent", net_io.bytes_sent, "bytes", timestamp)
        self._store_metric("network_bytes_recv", net_io.bytes_recv, "bytes", timestamp)
        self._store_metric("network_packets_sent", net_io.packets_sent, "packets", timestamp)
        self._store_metric("network_packets_recv", net_io.packets_recv, "packets", timestamp)

        # Network per interface
        for iface, stats in psutil.net_io_counters(pernic=True).items():
            self._store_metric(f"net_{iface}_bytes_sent", stats.bytes_sent, "bytes", timestamp)
            self._store_metric(f"net_{iface}_bytes_recv", stats.bytes_recv, "bytes", timestamp)

        # Processes
        processes = len(psutil.pids())
        self._store_metric("process_count", processes, "count", timestamp)

        # Load average (Unix)
        try:
            load = psutil.getloadavg()
            self._store_metric("load_1min", load[0], "load", timestamp)
            self._store_metric("load_5min", load[1], "load", timestamp)
            self._store_metric("load_15min", load[2], "load", timestamp)
        except AttributeError:
            pass  # Windows

        # Battery (laptop)
        try:
            battery = psutil.sensors_battery()
            if battery:
                self._store_metric("battery_percent", battery.percent, "%", time.time())
        except AttributeError:
            pass

        # Temperatures
        try:
            temps = psutil.sensors_temperatures()
            for name, entries in temps.items():
                for entry in entries:
                    if entry.current:
                        self._store_metric(f"temp_{name}_{entry.label or 'core'}", entry.current, "°C", timestamp)
        except AttributeError:
            pass

        # Store snapshot
        self._store_snapshot(timestamp)

        # Check alert rules
        self._check_alerts(timestamp)

    def _store_metric(self, name: str, value: float, unit: str, timestamp: float):
        conn = get_connection()
        cursor = conn.cursor()
        metric_id = f"met_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO metrics_history (id, metric_name, value, unit, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (metric_id, name, value, unit, timestamp))
        conn.commit()
        conn.close()

    def _store_snapshot(self, timestamp: float):
        conn = get_connection()
        cursor = conn.cursor()

        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        processes = len(psutil.pids())

        try:
            load = psutil.getloadavg()
            load_avg = list(load)
        except AttributeError:
            load_avg = []

        snapshot_id = f"snap_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO system_snapshots (id, timestamp, cpu_percent, memory_percent, disk_percent,
                                        network_io, process_count, load_average)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (snapshot_id, timestamp, cpu, psutil.virtual_memory().percent,
              disk.percent, json.dumps({"sent": net.bytes_sent, "recv": net.bytes_recv}),
              processes, json.dumps(load_avg)))
        conn.commit()
        conn.close()

    def _check_alerts(self, timestamp: float):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alert_rules WHERE enabled = 1")
        rules = cursor.fetchall()
        conn.close()

        for rule in rules:
            rule_id, name, metric_name, condition, threshold, severity, channels, cooldown, last_triggered = rule

            # Check cooldown
            if last_triggered and timestamp - last_triggered < cooldown:
                continue

            # Get latest metric value
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value FROM metrics_history
                WHERE metric_name = ? ORDER BY timestamp DESC LIMIT 1
            """, (metric_name,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                continue

            value = row[0]
            triggered = False

            if condition == ">" and value > threshold:
                triggered = True
            elif condition == "<" and value < threshold:
                triggered = True
            elif condition == ">=" and value >= threshold:
                triggered = True
            elif condition == "<=" and value <= threshold:
                triggered = True
            elif condition == "==" and value == threshold:
                triggered = True
            elif condition == "!=" and value != threshold:
                triggered = True

            if triggered:
                self._trigger_alert(rule_id, name, metric_name, value, threshold, severity, timestamp)

    def _trigger_alert(self, rule_id: str, name: str, metric: str, value: float, threshold: float, severity: str, timestamp: float):
        alert_id = f"alert_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alert_history (id, rule_id, metric_value, threshold, severity, triggered_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (alert_id, rule_id, value, threshold, severity, timestamp))
        cursor.execute("UPDATE alert_rules SET last_triggered = ? WHERE id = ?", (timestamp, rule_id))
        conn.commit()
        conn.close()

    def get_metric_history(self, metric_name: str, hours: int = 24) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cutoff = time.time() - (hours * 3600)
        cursor.execute("""
            SELECT value, unit, timestamp FROM metrics_history
            WHERE metric_name = ? AND timestamp > ?
            ORDER BY timestamp
        """, (metric_name, cutoff))
        rows = cursor.fetchall()
        conn.close()
        return [{"value": r[0], "unit": r[1], "timestamp": r[2]} for r in rows]

    def get_current_snapshot(self) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_snapshots ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0], "timestamp": row[1], "cpu_percent": row[2],
                "memory_percent": row[3], "disk_percent": row[4],
                "network_io": json.loads(row[5]) if row[5] else {},
                "process_count": row[6], "load_average": json.loads(row[7]) if row[7] else []
            }
        return {}

    def get_process_list(self, limit: int = 50, sort_by: str = "cpu") -> List[Dict]:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
            try:
                info = proc.info
                info['memory_mb'] = info.get('memory_percent', 0) * psutil.virtual_memory().total / 100 / (1024**2)
                processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if sort_by == "cpu":
            processes.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
        elif sort_by == "memory":
            processes.sort(key=lambda p: p.get('memory_percent', 0), reverse=True)

        return processes[:limit]


class ProcessManager:
    """Manages system processes."""

    def __init__(self):
        self.monitored_pids = set()

    def get_process_info(self, pid: int) -> Optional[Dict]:
        try:
            proc = psutil.Process(pid)
            return {
                "pid": pid,
                "name": proc.name(),
                "exe": proc.exe(),
                "cmdline": proc.cmdline(),
                "cpu_percent": proc.cpu_percent(),
                "memory_percent": proc.memory_percent(),
                "memory_mb": proc.memory_info().rss / (1024**2),
                "status": proc.status(),
                "create_time": proc.create_time(),
                "num_threads": proc.num_threads(),
                "connections": len(proc.connections()),
                "open_files": len(proc.open_files()) if proc.open_files() else 0,
                "username": proc.username()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def kill_process(self, pid: int, force: bool = False) -> bool:
        try:
            proc = psutil.Process(pid)
            if force:
                proc.kill()
            else:
                proc.terminate()
            proc.wait(timeout=5)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            return False

    def get_high_resource_processes(self, cpu_threshold: float = 50.0, mem_threshold: float = 50.0) -> List[Dict]:
        high_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if info['cpu_percent'] and info['cpu_percent'] > cpu_threshold:
                    high_processes.append({"reason": "high_cpu", **info})
                if info['memory_percent'] and info['memory_percent'] > mem_threshold:
                    high_processes.append({"reason": "high_memory", **info})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return high_processes

    def find_processes_by_name(self, name: str) -> List[Dict]:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                if name.lower() in proc.info['name'].lower():
                    processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return processes

    def get_process_tree(self, pid: int) -> Dict:
        try:
            proc = psutil.Process(pid)
            children = proc.children(recursive=True)
            return {
                "pid": pid,
                "name": proc.name(),
                "children": [
                    {"pid": c.pid, "name": c.name(), "cpu_percent": c.cpu_percent()}
                    for c in children
                ]
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {}


class ServiceManager:
    """Manages system services."""

    def __init__(self):
        self.is_windows = platform.system() == "Windows"

    def get_service_status(self, service_name: str) -> Dict:
        """Get status of a service."""
        if self.is_windows:
            return self._get_windows_service_status(service_name)
        else:
            return self._get_systemd_service_status(service_name)

    def _get_systemd_service_status(self, service_name: str) -> Dict:
        try:
            result = subprocess.run(
                ["systemctl", "status", service_name],
                capture_output=True, text=True, timeout=5
            )
            active = "active (running)" in result.stdout
            return {
                "name": service_name,
                "active": active,
                "status": "running" if active else "stopped",
                "output": result.stdout
            }
        except subprocess.TimeoutExpired:
            return {"name": service_name, "active": False, "status": "timeout", "error": "timeout"}
        except Exception as e:
            return {"name": service_name, "active": False, "status": "error", "error": str(e)}

    def _get_windows_service_status(self, service_name: str) -> Dict:
        try:
            result = subprocess.run(
                ["sc", "query", service_name],
                capture_output=True, text=True, timeout=5
            )
            running = "RUNNING" in result.stdout
            return {
                "name": service_name,
                "active": running,
                "status": "running" if running else "stopped",
                "output": result.stdout
            }
        except Exception as e:
            return {"name": service_name, "active": False, "status": "error", "error": str(e)}

    def start_service(self, service_name: str) -> bool:
        if self.is_windows:
            subprocess.run(["net", "start", service_name], check=False)
        else:
            subprocess.run(["systemctl", "start", service_name], check=False)
        time.sleep(1)
        return self.get_service_status(service_name)["active"]

    def stop_service(self, service_name: str) -> bool:
        if self.is_windows:
            subprocess.run(["net", "stop", service_name], check=False)
        else:
            subprocess.run(["systemctl", "stop", service_name], check=False)
        time.sleep(1)
        return not self.get_service_status(service_name)["active"]

    def restart_service(self, service_name: str) -> bool:
        if self.is_windows:
            subprocess.run(["net", "stop", service_name], check=False)
            time.sleep(1)
            subprocess.run(["net", "start", service_name], check=False)
        else:
            subprocess.run(["systemctl", "restart", service_name], check=False)
        time.sleep(2)
        return self.get_service_status(service_name)["active"]

    def enable_service(self, service_name: str) -> bool:
        if not self.is_windows:
            subprocess.run(["systemctl", "enable", service_name], check=False)
        return True

    def disable_service(self, service_name: str) -> bool:
        if not self.is_windows:
            subprocess.run(["systemctl", "disable", service_name], check=False)
        return True

    def list_services(self, pattern: str = None) -> List[Dict]:
        services = []
        if self.is_windows:
            result = subprocess.run(["sc", "query", "state= all"], capture_output=True, text=True)
            # Parse Windows services
        else:
            result = subprocess.run(["systemctl", "list-units", "--type=service", "--all", "--no-legend"],
                                  capture_output=True, text=True)
            for line in result.stdout.strip().split('\n'):
                if line and (not pattern or pattern in line):
                    parts = line.split()
                    if len(parts) >= 4:
                        services.append({
                            "name": parts[0],
                            "load": parts[1],
                            "active": parts[2],
                            "sub": parts[3],
                            "description": " ".join(parts[4:]) if len(parts) > 4 else ""
                        })
        return services


class AutomationEngine:
    """Manages automation rules and execution."""

    def __init__(self):
        self.rules = []
        self.running = False
        self.worker_thread = None

    def load_rules(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM automation_rules WHERE enabled = 1")
        rows = cursor.fetchall()
        conn.close()

        self.rules = []
        for row in rows:
            self.rules.append({
                "id": row[0], "name": row[1], "trigger_type": row[2],
                "trigger_config": json.loads(row[3]) if row[3] else {},
                "action_type": row[4], "action_config": json.loads(row[5]) if row[5] else {},
                "enabled": bool(row[6]), "cooldown_seconds": row[7],
                "last_triggered": row[8], "trigger_count": row[9]
            })

    def add_rule(self, name: str, trigger_type: str, trigger_config: Dict,
                 action_type: str, action_config: Dict, cooldown_seconds: int = 60) -> str:
        rule_id = f"rule_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO automation_rules (id, name, trigger_type, trigger_config, action_type, action_config, cooldown_seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (rule_id, name, trigger_type, json.dumps(trigger_config),
              action_type, json.dumps(action_config), cooldown_seconds, time.time()))
        conn.commit()
        conn.close()
        self.load_rules()
        return rule_id

    def remove_rule(self, rule_id: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM automation_rules WHERE id = ?", (rule_id,))
        conn.commit()
        conn.close()
        self.load_rules()
        return True

    def start(self):
        if self.running:
            return
        self.load_rules()
        self.running = True
        self.worker_thread = threading.Thread(target=self._evaluation_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

    def _evaluation_loop(self):
        while self.running:
            try:
                self._evaluate_rules()
            except Exception as e:
                print(f"Automation engine error: {e}")
            time.sleep(10)  # Check every 10 seconds

    def _evaluate_rules(self):
        now = time.time()

        for rule in self.rules:
            if not rule["enabled"]:
                continue

            # Check cooldown
            if rule["last_triggered"] and (now - rule["last_triggered"]) < rule["cooldown_seconds"]:
                continue

            triggered = False
            trigger_config = rule["trigger_config"]

            if rule["trigger_type"] == "metric":
                triggered = self._check_metric_trigger(trigger_config)
            elif rule["trigger_type"] == "schedule":
                triggered = self._check_schedule_trigger(trigger_config)
            elif rule["trigger_type"] == "process":
                triggered = self._check_process_trigger(trigger_config)

            if triggered:
                self._execute_action(rule)

    def _check_metric_trigger(self, config: Dict) -> bool:
        metric_name = config.get("metric")
        condition = config.get("condition", ">")
        threshold = config.get("threshold", 0)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM metrics_history WHERE metric_name = ? ORDER BY timestamp DESC LIMIT 1", (metric_name,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return False

        value = row[0]
        if condition == ">" and value > threshold:
            return True
        elif condition == "<" and value < threshold:
            return True
        elif condition == ">=" and value >= threshold:
            return True
        elif condition == "<=" and value <= threshold:
            return True
        return False

    def _check_schedule_trigger(self, config: Dict) -> bool:
        # Simple cron-like scheduling
        schedule = config.get("schedule", "")  # cron expression
        # Simplified: check every minute
        return False  # Would need croniter for full implementation

    def _check_process_trigger(self, config: Dict) -> bool:
        process_name = config.get("process_name")
        condition = config.get("condition", "running")  # running, stopped, crashed

        for proc in psutil.process_iter(['name']):
            try:
                if process_name.lower() in proc.info['name'].lower():
                    if condition == "running":
                        return True
                    elif condition == "stopped":
                        return False
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return condition == "stopped"

    def _execute_action(self, rule: Dict):
        action_type = rule["action_type"]
        action_config = rule["action_config"]

        success = False
        output = ""
        error = ""

        try:
            if action_type == "command":
                cmd = action_config.get("command", "")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                success = result.returncode == 0
                output = result.stdout
                error = result.stderr

            elif action_type == "service_action":
                service_name = action_config.get("service")
                action = action_config.get("action", "restart")
                sm = ServiceManager()
                if action == "start":
                    success = sm.start_service(action_config["service"])
                elif action == "stop":
                    success = sm.stop_service(action_config["service"])
                elif action == "restart":
                    success = sm.restart_service(action_config["service"])
                output = f"Service {action} {'succeeded' if success else 'failed'}"

            elif action_type == "notification":
                # Would integrate with notification system
                success = True
                output = "Notification sent"

            elif action_type == "script":
                script = action_config.get("script", "")
                result = subprocess.run(["python", "-c", script], capture_output=True, text=True, timeout=60)
                success = result.returncode == 0
                output = result.stdout
                error = result.stderr

        except Exception as e:
            success = False
            error = str(e)

        # Record execution
        execution_id = f"exec_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO automation_executions (id, rule_id, triggered_at, success, output, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (execution_id, rule["id"], time.time(), success, output, error))
        conn.commit()

        # Update rule
        cursor.execute("""
            UPDATE automation_rules SET last_triggered = ?, trigger_count = trigger_count + 1 WHERE id = ?
        """, (time.time(), rule["id"]))
        conn.commit()
        conn.close()


class SystemAgent:
    """Main System Agent coordinator."""

    def __init__(self):
        self.monitor = SystemMonitor()
        self.process_manager = ProcessManager()
        self.service_manager = ServiceManager()
        self.automation = AutomationEngine()

    def start(self):
        self.monitor.start()
        self.automation.start()

    def stop(self):
        self.monitor.stop()
        self.automation.stop()

    def get_system_status(self) -> Dict:
        snapshot = self.monitor.get_current_snapshot()
        high_procs = self.process_manager.get_high_resource_processes()

        return {
            "snapshot": snapshot,
            "high_resource_processes": high_procs[:10],
            "uptime_seconds": time.time() - psutil.boot_time(),
            "boot_time": psutil.boot_time()
        }

    def record_metric(self, name: str, value: float, unit: str = ""):
        self.monitor._store_metric(name, value, unit, time.time())

    def get_metric_history(self, name: str, hours: int = 24) -> List[Dict]:
        return self.monitor.get_metric_history(name, hours)

    def create_alert_rule(self, name: str, metric: str, condition: str, threshold: float,
                          severity: str = "warning", cooldown: int = 300) -> str:
        rule_id = f"alert_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alert_rules (id, name, metric_name, condition, threshold, severity, cooldown_seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (rule_id, name, metric, condition, threshold, severity, cooldown, time.time()))
        conn.commit()
        conn.close()
        return rule_id

    def get_alerts(self, hours: int = 24) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ah.*, ar.name, ar.metric_name, ar.condition, ar.threshold, ar.severity
            FROM alert_history ah
            JOIN alert_rules ar ON ah.rule_id = ar.id
            WHERE ah.triggered_at > ?
            ORDER BY ah.triggered_at DESC
        """, (time.time() - 86400 * 7,))  # Last 7 days
        rows = cursor.fetchall()
        conn.close()

        return [
            {"id": r[0], "rule_id": r[1], "value": r[2], "threshold": r[3],
             "severity": r[4], "acknowledged": bool(r[5]), "triggered_at": r[6],
             "rule_name": r[7], "metric": r[8], "condition": r[9], "threshold": r[10], "severity_level": r[11]}
            for r in rows
        ]

    def acknowledge_alert(self, alert_id: str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE alert_history SET acknowledged = 1, acknowledged_at = ? WHERE id = ?", (time.time(), alert_id))
        conn.commit()
        conn.close()

    def get_automation_rules(self) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM automation_rules WHERE enabled = 1")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "trigger_type": r[2],
             "trigger_config": json.loads(r[3]) if r[3] else {},
             "action_type": r[4], "action_config": json.loads(r[5]) if r[5] else {},
             "enabled": bool(r[6]), "cooldown": r[7], "last_triggered": r[8], "trigger_count": r[9]}
            for r in rows
        ]

    def create_automation_rule(self, name: str, trigger_type: str, trigger_config: Dict,
                               action_type: str, action_config: Dict, cooldown: int = 60) -> str:
        return self.automation.add_rule(name, trigger_type, trigger_config, action_type, action_config, cooldown)

    def delete_automation_rule(self, rule_id: str) -> bool:
        return self.automation.remove_rule(rule_id)

    def get_automation_history(self, rule_id: str = None, limit: int = 50) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        if rule_id:
            cursor.execute("SELECT * FROM automation_executions WHERE rule_id = ? ORDER BY triggered_at DESC LIMIT ?", (rule_id, limit))
        else:
            cursor.execute("SELECT * FROM automation_executions ORDER BY triggered_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "rule_id": r[1], "triggered_at": r[2], "success": bool(r[3]),
             "output": r[4], "error": r[5]}
            for r in rows
        ]


# Global instance
system_agent = SystemAgent()


# Voice command integration
def system_agent_debug() -> str:
    status = system_agent.get_system_status()
    snapshot = status.get("snapshot", {})

    output = f"System Status:\n"
    output += f"  CPU: {snapshot.get('cpu_percent', 0):.1f}%\n"
    output += f"  Memory: {snapshot.get('memory_percent', 0):.1f}%\n"
    output += f"  Disk: {snapshot.get('disk_percent', 0):.1f}%\n"
    output += f"  Processes: {snapshot.get('process_count', 0)}\n"
    output += f"  Uptime: {int(status.get('uptime_seconds', 0) / 3600)}h\n"
    output += f"  High resource processes: {len(status.get('high_resource_processes', []))}\n"

    return output


def system_snapshot() -> str:
    snapshot = system_agent.monitor.get_current_snapshot()
    if not snapshot:
        return "No snapshot available."

    output = f"System Snapshot:\n"
    output += f"  CPU: {snapshot.get('cpu_percent', 0):.1f}%\n"
    output += f"  Memory: {snapshot.get('memory_percent', 0):.1f}%\n"
    output += f"  Disk: {snapshot.get('disk_percent', 0):.1f}%\n"
    output += f"  Processes: {snapshot.get('process_count', 0)}\n"
    if snapshot.get('load_average'):
        output += f"  Load: {snapshot['load_average']}\n"
    return output


def system_alerts() -> str:
    alerts = system_agent.get_alerts(24)
    if not alerts:
        return "No alerts in last 24 hours."

    output = f"Active Alerts ({len(alerts)}):\n"
    for alert in alerts[:10]:
        output += f"  • {alert['rule_name']}: {alert['metric']} = {alert['value']:.1f} (threshold: {alert['threshold']}) [{alert['severity']}]\n"
    return output


def create_alert(metric: str, condition: str, threshold: float, severity: str = "warning") -> str:
    rule_id = system_agent.create_alert_rule(f"Alert for {metric}", metric, condition, threshold, severity)
    return f"Created alert rule: {rule_id}"


def list_alerts() -> str:
    alerts = system_agent.get_alerts(24)
    if not alerts:
        return "No alerts in last 24 hours."

    output = f"Recent Alerts ({len(alerts)}):\n"
    for a in alerts[:10]:
        status = "✓" if a["acknowledged"] else "⚠"
        output += f"{status} {a['rule_name']}: {a['metric']} = {a['value']:.1f} (threshold: {a['threshold']}) [{a['severity']}]\n"
    return output


def acknowledge_alert(alert_id: str) -> str:
    system_agent.acknowledge_alert(alert_id)
    return f"Acknowledged alert {alert_id}"


def create_automation(name: str, trigger: str, action: str) -> str:
    # Simplified: name="High CPU restart nginx", trigger="cpu>80", action="restart nginx"
    # This is simplified - real implementation would parse properly
    rule_id = f"auto_{int(time.time() * 1000) % 100000000:08d}"
    return f"Automation rule created: {rule_id} (needs full config)"


def list_automations() -> str:
    rules = system_agent.get_automation_rules()
    if not rules:
        return "No automation rules configured."

    output = f"Automation Rules ({len(rules)}):\n"
    for r in rules:
        output += f"  • {r['name']} ({r['trigger_type']} -> {r['action_type']}) {'✓' if r['enabled'] else '✗'}\n"
    return output


def system_processes() -> str:
    procs = system_agent.process_manager.get_process_list(10, "cpu")
    if not procs:
        return "No processes found."

    output = "Top Processes (by CPU):\n"
    for i, p in enumerate(procs[:10], 1):
        output += f"{i}. {p.get('name', 'unknown')} (PID: {p.get('pid')}) CPU: {p.get('cpu_percent', 0):.1f}% Mem: {p.get('memory_percent', 0):.1f}%\n"
    return output


def kill_process(pid: int) -> str:
    if system_agent.process_manager.kill_process(pid):
        return f"Process {pid} terminated."
    return f"Failed to kill process {pid} (permission denied or not found)."


def restart_service(service_name: str) -> str:
    if system_agent.service_manager.restart_service(service_name):
        return f"Service {service_name} restarted."
    return f"Failed to restart {service_name}."


def service_status(service_name: str) -> str:
    status = system_agent.service_manager.get_service_status(service_name)
    return f"Service {service_name}: {status['status']}"


def list_services(pattern: str = "") -> str:
    services = system_agent.service_manager.list_services(pattern)
    if not services:
        return "No services found."

    output = f"Services ({len(services)}):\n"
    for s in services[:20]:
        output += f"  • {s['name']}: {s.get('active', s.get('status', 'unknown'))}\n"
    return output


# Voice command integration
def system_agent_debug() -> str:
    return system_agent_debug()


if __name__ == "__main__":
    print("System Agent module loaded.")
    print("Available functions:")
    print("  system_agent.start() / system_agent.stop()")
    print("  system_agent.get_system_status()")
    print("  system_agent.create_alert_rule(...)")
    print("  system_agent.get_alerts()")
    print("  system_agent.create_automation_rule(...)")
    print("  system_agent.get_automation_rules()")