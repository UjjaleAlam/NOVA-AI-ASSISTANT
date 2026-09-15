"""
NOVA OS - Phase 42
Personal AI Operating System - System Integration Layer
Brings all agents together into a cohesive, bootable, maintainable system.
"""

import json
import time
import os
import sys
import threading
import subprocess
import signal
import atexit
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path

DB_DIR = "database"
NOVA_DB = os.path.join(DB_DIR, "nova_os.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_nova_connection():
    import sqlite3
    conn = sqlite3.connect(NOVA_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_nova_db():
    conn = get_nova_connection()
    cursor = conn.cursor()

    # System configuration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT,
            category TEXT,
            is_sensitive BOOLEAN DEFAULT 0,
            updated_at REAL NOT NULL
        )
    """)

    # System state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at REAL NOT NULL
        )
    """)

    # Service registry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            module TEXT NOT NULL,
            class_name TEXT NOT NULL,
            config TEXT,
            enabled BOOLEAN DEFAULT 1,
            auto_start BOOLEAN DEFAULT 1,
            dependencies TEXT,  -- JSON array
            status TEXT DEFAULT 'stopped',  -- stopped, starting, running, failed
            pid INTEGER,
            started_at REAL,
            restart_count INTEGER DEFAULT 0,
            max_restarts INTEGER DEFAULT 3
        )
    """)

    # Health checks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_checks (
            id TEXT PRIMARY KEY,
            service_id TEXT,
            check_name TEXT,
            status TEXT,  -- healthy, degraded, unhealthy
            message TEXT,
            timestamp REAL NOT NULL,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    """)

    # System logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id TEXT PRIMARY KEY,
            level TEXT,  -- debug, info, warning, error, critical
            component TEXT,
            message TEXT,
            context TEXT,  -- JSON
            timestamp REAL NOT NULL
        )
    """)

    # Plugin/Extension registry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plugins (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT,
            author TEXT,
            description TEXT,
            entry_point TEXT,
            config TEXT,
            enabled BOOLEAN DEFAULT 1,
            auto_load BOOLEAN DEFAULT 1,
            dependencies TEXT,  -- JSON array
            installed_at REAL NOT NULL,
            updated_at REAL
        )
    """)

    # System metrics
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_metrics (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            cpu_percent REAL,
            memory_percent REAL,
            disk_percent REAL,
            gpu_percent REAL,
            gpu_memory_percent REAL,
            active_agents INTEGER,
            pending_tasks INTEGER,
            uptime_seconds REAL
        )
    """)

    # Default configuration
    defaults = [
        ("voice.enabled", "true", "Enable voice interface", "voice"),
        ("voice.wake_words", '["nova", "hey nova"]', "Wake words for voice activation", "voice"),
        ("voice.language", "en-US", "Speech recognition language", "voice"),
        ("tts.voice", "en-US-AndrewNeural", "Text-to-speech voice", "voice"),
        ("tts.rate", "1.0", "Speech rate", "voice"),
        ("stt.engine", "faster-whisper", "Speech-to-text engine", "voice"),
        ("stt.model", "base.en", "STT model size", "voice"),
        ("stt.device", "cuda", "STT device (cuda/cpu)", "voice"),
        ("agents.auto_start", "true", "Auto-start agents on boot", "agents"),
        ("agents.chief_of_staff.enabled", "true", "Enable Chief of Staff", "agents"),
        ("agents.engineering.enabled", "true", "Enable Engineering Agent", "agents"),
        ("agents.blender.enabled", "true", "Enable Blender Agent", "agents"),
        ("agents.animation.enabled", "true", "Enable Animation Agent", "agents"),
        ("agents.autonomous.enabled", "true", "Enable Autonomous Assistant", "agents"),
        ("system.tray_icon", "true", "Show system tray icon", "ui"),
        ("system.notifications", "true", "Enable desktop notifications", "ui"),
        ("system.auto_backup", "true", "Enable automatic backups", "system"),
        ("system.backup_interval", "86400", "Backup interval in seconds", "system"),
        ("system.log_level", "info", "Logging level (debug/info/warning/error)", "system"),
        ("system.max_log_size", "10485760", "Max log file size (10MB)", "system"),
        ("database.path", "database", "Database directory path", "database"),
        ("database.backup_enabled", "true", "Enable database backups", "database"),
    ]

    for key, value, desc, cat in defaults:
        cursor.execute("""
            INSERT OR IGNORE INTO system_config (key, value, description, category, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (key, value, desc, cat, time.time()))

    # Default services
    services = [
        ("core.multi_agent", "MultiAgentOrchestrator", "Orchestrator", '{"auto_start": true}', True, True, "[]"),
        ("core.chief_of_staff", "ChiefOfStaff", "Chief of Staff", '{"auto_start": true}', True, True, '["core.multi_agent"]'),
        ("core.engineering_agent", "EngineeringAgent", "Engineering Agent", '{"auto_start": true}', True, True, '["core.multi_agent"]'),
        ("core.blender_agent", "BlenderAgent", "Blender Agent", '{"auto_start": true}', True, True, '["core.multi_agent"]'),
        ("core.animation_agent", "AnimationAgent", "Animation Agent", '{"auto_start": true}', True, True, '["core.multi_agent"]'),
        ("core.autonomous_assistant", "AutonomousAssistant", "Autonomous Assistant", '{"auto_start": true}', True, True, '["core.chief_of_staff"]'),
        ("core.background_engine", "BackgroundEngine", "Background Task Engine", '{"auto_start": true}', True, True, '["core.multi_agent"]'),
    ]

    for module, class_name, name, config, enabled, auto_start, deps in services:
        cursor.execute("""
            INSERT OR IGNORE INTO services (id, name, module, class_name, config, enabled, auto_start, dependencies, status, restart_count, max_restarts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'stopped', 0, 3)
        """, (module, name, module, class_name, config, enabled, auto_start, deps))

    conn.commit()
    conn.close()


init_nova_db()


# ============================================================
# SYSTEM CONFIGURATION
# ============================================================

class SystemConfig:
    """Manage system configuration."""

    def __init__(self):
        self._cache = {}

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._cache:
            return self._cache[key]

        conn = get_nova_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        if row:
            value = row[0]
            # Try to parse as JSON
            try:
                value = json.loads(value)
            except:
                pass
            self._cache[key] = value
            return value
        return default

    def set(self, key: str, value: Any, description: str = "", category: str = "general") -> bool:
        conn = get_nova_connection()
        cursor = conn.cursor()
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            cursor.execute("""
                INSERT OR REPLACE INTO system_config (key, value, description, category, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (key, str(value), description, category, time.time()))
            conn.commit()
            self._cache[key] = value
            return True
        except Exception as e:
            print(f"Config set error: {e}")
            return False
        finally:
            conn.close()

    def get_all(self, category: str = None) -> Dict:
        conn = get_nova_connection()
        cursor = conn.cursor()
        if category:
            cursor.execute("SELECT key, value, description FROM system_config WHERE category = ?", (category,))
        else:
            cursor.execute("SELECT key, value, description FROM system_config")
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for key, value, desc in rows:
            try:
                result[key] = json.loads(value)
            except:
                result[key] = value
        return result


# ============================================================
# SERVICE MANAGER
# ============================================================

class ServiceManager:
    """Manage system services (agents, background tasks, etc.)."""

    def __init__(self):
        self.services: Dict[str, Dict] = {}
        self.running: Dict[str, Any] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self._load_services()

    def _load_services(self):
        conn = get_nova_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services WHERE enabled = 1")
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            self.services[row[0]] = {
                "id": row[0],
                "name": row[1],
                "module": row[2],
                "class_name": row[3],
                "config": json.loads(row[4]) if row[4] else {},
                "enabled": bool(row[5]),
                "auto_start": bool(row[6]),
                "dependencies": json.loads(row[7]) if row[7] else [],
                "status": row[8],
                "pid": row[9],
                "started_at": row[10],
                "restart_count": row[10],
                "max_restarts": row[11]
            }

    def start_service(self, service_id: str) -> bool:
        """Start a service by ID."""
        if service_id not in self.services:
            return False

        svc = self.services[service_id]
        if svc["status"] == "running":
            return True

        # Check dependencies
        for dep in svc["dependencies"]:
            if dep in self.services and self.services[dep]["status"] != "running":
                if not self.start_service(dep):
                    return False

        svc["status"] = "starting"
        self._persist_service(svc)

        try:
            # Import and instantiate
            module = __import__(svc["module"], fromlist=[svc["class_name"]])
            cls = getattr(module, svc["class_name"])
            
            # Check which config arguments the class accepts
            import inspect
            sig = inspect.signature(cls.__init__)
            accepted_params = set(sig.parameters.keys()) - {'self'}
            filtered_config = {k: v for k, v in svc["config"].items() if k in accepted_params}
            
            instance = cls(**filtered_config)

            if hasattr(instance, "start"):
                instance.start()

            svc["instance"] = instance
            svc["status"] = "running"
            svc["started_at"] = time.time()
            svc["pid"] = os.getpid()
            self._persist_service(svc)

            self.running[svc["id"]] = instance
            return True

        except Exception as e:
            svc["status"] = "failed"
            svc["error"] = str(e)
            self._persist_service(svc)
            return False

    def stop_service(self, service_id: str) -> bool:
        """Stop a service."""
        if service_id not in self.services:
            return False

        svc = self.services[service_id]
        if svc["status"] != "running":
            return True

        try:
            instance = svc.get("instance")
            if instance and hasattr(instance, "stop"):
                instance.stop()

            # Stop dependents first
            for sid, svc2 in self.services.items():
                if service_id in svc2.get("dependencies", []) and svc2["status"] == "running":
                    self.stop_service(sid)

            svc["status"] = "stopped"
            svc["instance"] = None
            self._persist_service(svc)

            if service_id in self.running:
                del self.running[service_id]

            return True

        except Exception as e:
            print(f"Stop service error: {e}")
            return False

    def restart_service(self, service_id: str) -> bool:
        """Restart a service."""
        self.stop_service(service_id)
        time.sleep(1)
        return self.start_service(service_id)

    def get_service_status(self, service_id: str) -> Optional[Dict]:
        if service_id in self.services:
            return self.services[service_id].copy()
        return None

    def get_all_status(self) -> Dict:
        return {sid: {"status": svc["status"], "name": svc["name"], "restart_count": svc["restart_count"]}
                for sid, svc in self.services.items()}

    def start_all(self):
        """Start all auto-start services in dependency order."""
        # Topological sort would be better, but for now just iterate
        for _ in range(len(self.services)):
            for sid, svc in self.services.items():
                if svc["auto_start"] and svc["status"] == "stopped":
                    self.start_service(sid)

    def stop_all(self):
        """Stop all running services."""
        for sid in list(self.services.keys()):
            if self.services[sid]["status"] == "running":
                self.stop_service(sid)

    def _persist_service(self, svc: Dict):
        conn = get_nova_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE services SET status = ?, pid = ?, started_at = ?, restart_count = ?
            WHERE id = ?
        """, (svc["status"], svc.get("pid", 0), svc.get("started_at", 0),
              svc.get("restart_count", 0), svc["id"]))
        conn.commit()
        conn.close()


# ============================================================
# HEALTH MONITOR
# ============================================================

class HealthMonitor:
    """Monitor system and service health."""

    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.running = False
        self.thread = None
        self._start_time = time.time()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def _monitor_loop(self):
        while self.running:
            try:
                self._check_services()
                self._check_system_resources()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                self._log_health("system", "monitor_error", f"Monitor error: {e}", "error")

    def _check_services(self):
        for sid, svc in self.service_manager.services.items():
            if svc["status"] == "running":
                instance = svc.get("instance")
                healthy = instance is not None

                # Try to call health check if available
                if hasattr(instance, "health_check"):
                    try:
                        healthy = instance.health_check()
                    except:
                        healthy = False

                status = "healthy" if healthy else "unhealthy"
                self._log_health(sid, "service_status", f"Service {status}", "info" if healthy else "warning")

                if not healthy and svc["restart_count"] < svc.get("max_restarts", 3):
                    self._log_health(sid, "restart", f"Restarting unhealthy service", "warning")
                    svc["restart_count"] = svc.get("restart_count", 0) + 1
                    self.service_manager.restart_service(sid)

    def _check_system_resources(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent

            # GPU
            gpu_percent = 0
            gpu_mem = 0
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_percent = gpus[0].load * 100
                    gpu_mem = gpus[0].memoryUtil * 100
            except:
                pass

            # Log metrics
            conn = get_nova_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_metrics (id, timestamp, cpu_percent, memory_percent, disk_percent,
                                            gpu_percent, gpu_memory_percent, active_agents, pending_tasks, uptime_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"met_{int(time.time() * 1000) % 100000000:08d}", time.time(),
                  cpu, mem, disk, gpu_percent, gpu_mem, 0, 0, time.time() - self._start_time))
            conn.commit()
            conn.close()

            # Alerts
            if cpu > 90:
                self._log_health("system", "high_cpu", f"CPU usage {cpu}%", "warning")
            if mem > 90:
                self._log_health("system", "high_memory", f"Memory usage {mem}%", "warning")
            if disk > 90:
                self._log_health("system", "high_disk", f"Disk usage {disk}%", "warning")

        except Exception as e:
            self._log_health("system", "resource_check_error", str(e), "error")

    def _log_health(self, service_id: str, check_name: str, message: str, level: str):
        conn = get_nova_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO health_checks (id, service_id, check_name, status, message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (f"hlth_{int(time.time() * 1000) % 100000000:08d}", service_id, check_name,
              "healthy" if level == "info" else ("degraded" if level == "warning" else "unhealthy"),
              message, time.time()))
        conn.commit()
        conn.close()

    def get_recent_health(self, limit: int = 50) -> List[Dict]:
        conn = get_nova_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM health_checks ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "service_id": r[1], "check": r[2], "status": r[3], "message": r[3], "timestamp": r[4]}
            for r in rows
        ]


# ============================================================
# PLUGIN MANAGER
# ============================================================

class PluginManager:
    """Manage plugins/extensions."""

    def __init__(self):
        self.plugins: Dict[str, Any] = {}
        self._load_plugins()

    def _load_plugins(self):
        conn = get_nova_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM plugins WHERE enabled = 1 AND auto_load = 1")
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            plugin_id = row[0]
            try:
                # Import plugin module
                module = __import__(row[5], fromlist=["Plugin"])
                plugin_class = getattr(module, "Plugin")
                instance = plugin_class(**json.loads(row[6]) if row[6] else {})
                self.plugins[row[0]] = instance
            except Exception as e:
                print(f"Failed to load plugin {row[1]}: {e}")

    def register_plugin(self, name: str, module: str, class_name: str = "Plugin",
                        config: Dict = None, description: str = "",
                        dependencies: List = None) -> str:
        plugin_id = f"plg_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_nova_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO plugins (id, name, version, author, description, entry_point,
                                 config, enabled, auto_load, dependencies, installed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
        """, (plugin_id, name, "1.0.0", "", description, module, json.dumps(config or {}),
              json.dumps(dependencies or []), time.time()))
        conn.commit()
        conn.close()
        return plugin_id

    def enable_plugin(self, plugin_id: str) -> bool:
        conn = get_nova_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE plugins SET enabled = 1 WHERE id = ?", (plugin_id,))
        conn.commit()
        conn.close()
        return True

    def disable_plugin(self, plugin_id: str) -> bool:
        conn = get_nova_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE plugins SET enabled = 0 WHERE id = ?", (plugin_id,))
        conn.commit()
        conn.close()
        return True


# ============================================================
# NOVA OS MAIN CLASS
# ============================================================

class NovaOS:
    """Main NOVA Operating System class."""

    def __init__(self):
        self.config = SystemConfig()
        self.service_manager = ServiceManager()
        self.health_monitor = HealthMonitor(self.service_manager)
        self.plugin_manager = PluginManager()
        self.running = False
        self._start_time = time.time()

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self.shutdown)

    def _signal_handler(self, signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)

    def boot(self) -> bool:
        """Boot the NOVA OS."""
        print("=" * 50)
        print("    NOVA AI OPERATING SYSTEM")
        print("    Personal AI Operating System")
        print("=" * 50)
        print(f"Booting NOVA OS v1.0...")
        print(f"Hardware: RTX 4060 8GB | 24GB RAM | i7-13650HX")
        print(f"OS: Windows 11")
        print("-" * 50)

        # Initialize core systems
        print("[1/5] Initializing configuration...")
        self._init_config()

        print("[2/5] Starting core services...")
        self.service_manager.start_all()

        print("[3/5] Starting health monitor...")
        self.health_monitor._start_time = time.time()
        self.health_monitor.start()

        print("[4/5] Loading plugins...")
        self._load_plugins()

        print("[5/5] Starting voice interface...")
        self._start_voice()

        self.running = True
        print("-" * 50)
        print("NOVA OS booted successfully!")
        print("Say 'Nova' to begin.")
        print("=" * 50)

        return True

    def _init_config(self):
        # Ensure directories exist
        os.makedirs("database", exist_ok=True)
        os.makedirs("renders", exist_ok=True)
        os.makedirs("backups", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

    def _load_plugins(self):
        # Plugin loading would go here
        pass

    def _start_voice(self):
        # Voice interface starts via MultiAgentOrchestrator
        pass

    def run(self):
        """Main run loop."""
        if not self.running:
            self.boot()

        print("NOVA OS running. Press Ctrl+C to shutdown.")
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        """Graceful shutdown."""
        if not self.running:
            return

        print("\nShutting down NOVA OS...")
        self.running = False

        # Stop health monitor
        self.health_monitor.stop()

        # Stop all services
        self.service_manager.stop_all()

        # Save state
        self._save_state()

        print("NOVA OS shutdown complete.")

    def _save_state(self):
        # Save any persistent state
        pass

    def get_status(self) -> Dict:
        """Get overall system status."""
        return {
            "running": self.running,
            "uptime": time.time() - self._start_time,
            "services": self.service_manager.get_all_status(),
            "health": self.health_monitor.get_recent_health(10),
            "config": self.config.get_all()
        }

    def get_system_info(self) -> Dict:
        """Get detailed system information."""
        import psutil
        return {
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent,
            "uptime": time.time() - self._start_time,
            "services": len(self.service_manager.services),
            "running_services": sum(1 for s in self.service_manager.services.values() if s["status"] == "running")
        }


# Global instance
nova_os = NovaOS()


def get_nova_os() -> NovaOS:
    return nova_os


def start_nova():
    """Start NOVA OS."""
    return nova_os.boot()


def shutdown_nova():
    nova_os.shutdown()


if __name__ == "__main__":
    print("NOVA OS - Phase 42")
    print("Personal AI Operating System")
    print("Integrates: Voice, Multi-Agent, Chief of Staff, Engineering, Blender, Animation, Autonomous")