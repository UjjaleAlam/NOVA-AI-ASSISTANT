"""
Cybersecurity Agent - Phase 24
Security monitoring, threat detection, vulnerability scanning, log analysis.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import threading
import re
import hashlib
import subprocess
import ipaddress
import psutil
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

from core.context_engine import get_connection


DB_DIR = "database"
SECURITY_DB = os.path.join(DB_DIR, "cybersecurity.db")

os.makedirs(DB_DIR, exist_ok=True)


def init_security_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Threat intelligence
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS threat_intel (
            id TEXT PRIMARY KEY,
            indicator_type TEXT NOT NULL,  -- 'ip', 'domain', 'hash', 'url', 'cve'
            indicator_value TEXT NOT NULL,
            threat_type TEXT,  -- 'malware', 'phishing', 'botnet', 'exploit', 'suspicious'
            severity TEXT,  -- 'low', 'medium', 'high', 'critical'
            source TEXT,
            description TEXT,
            first_seen REAL NOT NULL,
            last_seen REAL NOT NULL,
            confidence REAL DEFAULT 0.5,
            tags TEXT  -- JSON array
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_threat_indicator
        ON threat_intel(indicator_type, indicator_value)
    """)

    # Security events/logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,  -- 'login', 'logout', 'failed_login', 'process', 'network', 'file', 'registry', 'privilege'
            severity TEXT,  -- 'info', 'low', 'medium', 'high', 'critical'
            source_ip TEXT,
            dest_ip TEXT,
            user TEXT,
            process_name TEXT,
            command_line TEXT,
            file_path TEXT,
            hash TEXT,
            description TEXT,
            raw_log TEXT,
            timestamp REAL NOT NULL,
            host TEXT,
            tags TEXT  -- JSON array
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_security_timestamp
        ON security_events(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_security_type
        ON security_events(event_type)
    """)

    # Vulnerability database
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vulnerabilities (
            id TEXT PRIMARY KEY,  -- CVE ID
            cve_id TEXT UNIQUE NOT NULL,
            title TEXT,
            description TEXT,
            severity TEXT,  -- 'low', 'medium', 'high', 'critical'
            cvss_score REAL,
            published_date REAL,
            modified_date REAL,
            affected_products TEXT,  -- JSON array
            refs TEXT,  -- JSON array
            exploit_available BOOLEAN DEFAULT 0,
            patch_available BOOLEAN DEFAULT 0
        )
    """)

    # Network connections
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_connections (
            id TEXT PRIMARY KEY,
            local_ip TEXT,
            local_port INTEGER,
            remote_ip TEXT,
            remote_port INTEGER,
            protocol TEXT,  -- 'tcp', 'udp'
            state TEXT,  -- 'established', 'listen', 'syn_sent', 'time_wait'
            pid INTEGER,
            process_name TEXT,
            direction TEXT,  -- 'inbound', 'outbound'
            bytes_sent INTEGER,
            bytes_recv INTEGER,
            timestamp REAL NOT NULL,
            risk_score REAL DEFAULT 0.0
        )
    """)

    # File integrity monitoring
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_integrity (
            id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            hash_algorithm TEXT,  -- 'sha256', 'sha1', 'md5'
            hash_value TEXT NOT NULL,
            size_bytes INTEGER,
            permissions TEXT,
            owner TEXT,
            modified_time REAL,
            created_time REAL,
            baseline_hash TEXT,
            status TEXT DEFAULT 'unchanged',  -- 'unchanged', 'modified', 'new', 'deleted'
            last_checked REAL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_path
        ON file_integrity(file_path)
    """)

    # Process execution monitoring
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS process_executions (
            id TEXT PRIMARY KEY,
            pid INTEGER,
            name TEXT,
            exe TEXT,
            cmdline TEXT,
            parent_pid INTEGER,
            user TEXT,
            start_time REAL,
            end_time REAL,
            cpu_time REAL,
            memory_mb REAL,
            exit_code INTEGER,
            suspicious BOOLEAN DEFAULT 0,
            mitre_techniques TEXT  -- JSON array of MITRE ATT&CK technique IDs
        )
    """)

    # Incident tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT,  -- 'low', 'medium', 'high', 'critical'
            status TEXT DEFAULT 'open',  -- 'open', 'investigating', 'contained', 'resolved', 'closed'
            assigned_to TEXT,
            detected_at REAL NOT NULL,
            updated_at REAL,
            resolved_at REAL,
            related_events TEXT,  -- JSON array of event IDs
            mitre_tactics TEXT,  -- JSON array
            mitre_techniques TEXT,  -- JSON array
            iocs TEXT,  -- JSON array of IOCs
            notes TEXT
        )
    """)

    # Threat hunting queries
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hunt_queries (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            query TEXT NOT NULL,  -- SQL or KQL-like query
            mitre_techniques TEXT,  -- JSON array
            schedule TEXT,  -- cron expression
            enabled BOOLEAN DEFAULT 1,
            last_run REAL,
            last_results TEXT  -- JSON
        )
    """)

    conn.commit()
    conn.close()


init_security_db()


@dataclass
class ThreatIntel:
    id: str
    indicator_type: str
    indicator_value: str
    threat_type: str
    severity: str
    source: str
    description: str
    first_seen: float
    last_seen: float
    confidence: float
    tags: List[str]


@dataclass
class SecurityEvent:
    id: str
    event_type: str
    severity: str
    source_ip: Optional[str]
    dest_ip: Optional[str]
    user: Optional[str]
    process_name: Optional[str]
    command_line: Optional[str]
    file_path: Optional[str]
    hash: Optional[str]
    description: str
    raw_log: str
    timestamp: float
    host: str
    tags: List[str]


@dataclass
class Vulnerability:
    id: str
    cve_id: str
    title: str
    description: str
    severity: str
    cvss_score: float
    published_date: float
    modified_date: float
    affected_products: List[str]
    refs: List[str]
    exploit_available: bool
    patch_available: bool


@dataclass
class NetworkConnection:
    id: str
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int
    protocol: str
    state: str
    pid: int
    process_name: str
    direction: str
    bytes_sent: int
    bytes_recv: int
    timestamp: float
    risk_score: float


class ThreatIntelligence:
    """Manages threat intelligence feeds and indicators."""

    def __init__(self):
        self.feeds = {
            "alienvault": "https://reputation.alienvault.com/reputation.data",
            "abuseipdb": "https://api.abuseipdb.com/api/v2/blacklist",
            "tor_exits": "https://check.torproject.org/torbulkexitlist",
            "spamhaus": "https://www.spamhaus.org/drop/drop.txt",
        }

    def add_indicator(self, indicator_type: str, value: str, threat_type: str = None,
                      severity: str = "medium", source: str = "manual",
                      description: str = "", confidence: float = 0.5, tags: List[str] = None) -> str:
        indicator_id = f"ti_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO threat_intel (id, indicator_type, indicator_value, threat_type, severity, source, description, first_seen, last_seen, confidence, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (indicator_id, indicator_type, value, threat_type, severity, source, description,
              time.time(), time.time(), confidence, json.dumps(tags or [])))
        conn.commit()
        conn.close()
        return indicator_id

    def check_indicator(self, indicator_type: str, value: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM threat_intel WHERE indicator_type = ? AND indicator_value = ?",
                       (indicator_type, value))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "type": row[1], "value": row[2],
                "threat_type": row[3], "severity": row[4], "source": row[5],
                "description": row[5], "confidence": row[9], "tags": json.loads(row[10]) if row[10] else []
            }
        return None

    def bulk_check(self, indicators: List[Dict]) -> List[Dict]:
        """Check multiple indicators at once."""
        results = []
        for ind in indicators:
            result = self.check_indicator(ind["type"], ind["value"])
            if result:
                results.append({**ind, "match": result})
        return results


class LogAnalyzer:
    """Analyzes security logs for anomalies and threats."""

    def __init__(self):
        self.rules = self._load_default_rules()

    def _load_default_rules(self) -> List[Dict]:
        return [
            {
                "id": "failed_ssh_bruteforce",
                "pattern": r"Failed password for .* from (\d+\.\d+\.\d+\.\d+)",
                "event_type": "failed_login",
                "severity": "high",
                "threshold": 5,  # 5 failures in window
                "window_seconds": 300
            },
            {
                "id": "sudo_usage",
                "pattern": r"sudo:.*COMMAND=(.*)",
                "event_type": "privilege_escalation",
                "severity": "medium",
                "threshold": 1,
                "window_seconds": 60
            },
            {
                "id": "suspicious_process",
                "pattern": r"(nc|netcat|ncat|socat|curl|wget)\s+.*(\d+\.\d+\.\d+\.\d+)",
                "event_type": "suspicious_process",
                "severity": "high",
                "threshold": 1,
                "window_seconds": 60
            },
            {
                "id": "web_shell",
                "pattern": r"(eval|exec|system|shell_exec|passthru|proc_open)\s*\(",
                "event_type": "web_shell",
                "severity": "critical",
                "threshold": 1,
                "window_seconds": 60
            },
            {
                "id": "sql_injection",
                "pattern": r"(union\s+select|or\s+1=1|';\s*--|union\s+all\s+select)",
                "event_type": "sql_injection",
                "severity": "high",
                "threshold": 1,
                "window_seconds": 60
            },
        ]

    def analyze_log_line(self, log_line: str, source: str = "unknown") -> List[SecurityEvent]:
        events = []
        for rule in self.rules:
            match = re.search(rule["pattern"], log_line, re.IGNORECASE)
            if match:
                event_id = f"evt_{int(time.time() * 1000) % 100000000:08d}"
                event = SecurityEvent(
                    id=event_id,
                    event_type=rule["event_type"],
                    severity=rule["severity"],
                    source_ip=match.group(1) if match.lastindex and match.lastindex >= 1 else None,
                    dest_ip=None,
                    user=None,
                    process_name=None,
                    command_line=log_line[:500],
                    file_path=None,
                    hash=None,
                    description=f"Matched rule: {rule['id']}",
                    raw_log=log_line[:1000],
                    timestamp=time.time(),
                    host=source,
                    tags=[rule["id"]]
                )
                self._store_event(event)
                events.append(event)
        return events

    def _store_event(self, event: SecurityEvent):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO security_events (id, event_type, severity, source_ip, dest_ip, user, process_name,
                                       command_line, file_path, hash, description, raw_log, timestamp, host, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (event.id, event.event_type, event.severity, event.source_ip, event.dest_ip,
              event.user, event.process_name, event.command_line, event.file_path,
              event.hash, event.description, event.raw_log, event.timestamp, event.host,
              json.dumps(event.tags)))
        conn.commit()
        conn.close()

    def analyze_log_file(self, file_path: str) -> List[SecurityEvent]:
        events = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    events.extend(self.analyze_log_line(line, file_path))
        except Exception as e:
            print(f"Error analyzing log file: {e}")
        return events


class NetworkMonitor:
    """Monitors network connections for suspicious activity."""

    def __init__(self):
        self.known_malicious_ips = set()
        self.load_threat_ips()

    def load_threat_ips(self):
        """Load known malicious IPs from threat intel."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT indicator_value FROM threat_intel WHERE indicator_type = 'ip'")
        rows = cursor.fetchall()
        conn.close()
        self.known_malicious_ips = {row[0] for row in rows}

    def scan_connections(self) -> List[NetworkConnection]:
        connections = []
        for conn in psutil.net_connections(kind='inet'):
            try:
                if conn.raddr:
                    remote_ip = conn.raddr.ip
                    remote_port = conn.raddr.port
                else:
                    remote_ip = ""
                    remote_port = 0

                local_ip = conn.laddr.ip if conn.laddr else ""
                local_port = conn.laddr.port if conn.laddr else 0

                risk_score = 0.0
                if remote_ip in self.known_malicious_ips:
                    risk_score = 1.0

                # Check for suspicious ports
                suspicious_ports = {22, 23, 3389, 445, 135, 139, 1433, 3306, 5432, 6379, 27017}
                if conn.raddr and conn.raddr.port in suspicious_ports:
                    risk_score = max(risk_score, 0.7)

                # Check for non-standard high ports
                if conn.raddr and conn.raddr.port > 10000:
                    risk_score = max(risk_score, 0.3)

                process_name = ""
                try:
                    if conn.pid:
                        proc = psutil.Process(conn.pid)
                        process_name = proc.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_name = ""

                conn_id = f"nc_{int(time.time() * 1000) % 100000000:08d}"
                conn_obj = NetworkConnection(
                    id=conn_id,
                    local_ip=local_ip,
                    local_port=local_port,
                    remote_ip=remote_ip,
                    remote_port=remote_port,
                    protocol="tcp" if conn.type == psutil.SOCK_STREAM else "udp",
                    state=conn.status,
                    pid=conn.pid or 0,
                    process_name=process_name,
                    direction="outbound" if conn.raddr else "inbound",
                    bytes_sent=0,  # Would need persistent tracking
                    bytes_recv=0,
                    timestamp=time.time(),
                    risk_score=risk_score
                )

                self._store_connection(conn_obj)
                connections.append(conn_obj)

            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                pass

        return connections

    def _store_connection(self, conn: NetworkConnection):
        conn_db = get_connection()
        cursor = conn_db.cursor()
        cursor.execute("""
            INSERT INTO network_connections (id, local_ip, local_port, remote_ip, remote_port,
                                           protocol, state, pid, process_name, direction,
                                           bytes_sent, bytes_recv, timestamp, risk_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (conn.id, conn.local_ip, conn.local_port, conn.remote_ip, conn.remote_port,
              conn.protocol, conn.state, conn.pid, conn.process_name, conn.direction,
              conn.bytes_sent, conn.bytes_recv, conn.timestamp, conn.risk_score))
        conn_db.commit()
        conn_db.close()


class FileIntegrityMonitor:
    """Monitors file system for unauthorized changes."""

    def __init__(self):
        self.baselines = {}
        self.monitored_paths = []

    def add_monitored_path(self, path: str, recursive: bool = True):
        """Add a path to monitor."""
        path_obj = Path(path)
        if path_obj.exists():
            self.monitored_paths.append({"path": str(path_obj), "recursive": recursive})
            self._create_baseline(path_obj, recursive)

    def _create_baseline(self, path: Path, recursive: bool):
        if path.is_file():
            self._hash_file(path)
        elif path.is_dir() and recursive:
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    self._hash_file(file_path)

    def _hash_file(self, file_path: Path, algorithm: str = "sha256") -> str:
        hasher = hashlib.new(algorithm)
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            hash_value = hasher.hexdigest()

            stat = file_path.stat()
            file_id = f"fim_{int(time.time() * 1000) % 100000000:08d}"

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO file_integrity (id, file_path, hash_algorithm, hash_value,
                                                     size_bytes, permissions, owner, modified_time,
                                                     created_time, baseline_hash, status, last_checked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_id, str(file_path), algorithm, hash_value, stat.st_size,
                  oct(stat.st_mode), stat.st_uid, stat.st_mtime, stat.st_ctime,
                  hash_value, "unchanged", time.time()))
            conn.commit()
            conn.close()

            self.baselines[str(file_path)] = hash_value
            return hash_value
        except Exception as e:
            print(f"Error hashing {file_path}: {e}")
            return ""

    def check_integrity(self) -> List[Dict]:
        """Check all monitored files for changes."""
        changes = []
        for entry in self.monitored_paths:
            path = Path(entry["path"])
            if path.is_file():
                changes.extend(self._check_file(path))
            elif path.is_dir() and entry["recursive"]:
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        changes.extend(self._check_file(file_path))
        return changes

    def _check_file(self, file_path: Path) -> List[Dict]:
        changes = []
        try:
            current_hash = self._hash_file(file_path)
            baseline = self.baselines.get(str(file_path))

            if not baseline:
                # New file
                changes.append({
                    "file": str(file_path),
                    "status": "new",
                    "hash": current_hash,
                    "timestamp": time.time()
                })
            elif current_hash != baseline:
                # Modified
                changes.append({
                    "file": str(file_path),
                    "status": "modified",
                    "old_hash": baseline,
                    "new_hash": current_hash,
                    "timestamp": time.time()
                })

                # Update database
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE file_integrity SET status = 'modified', baseline_hash = ?, last_checked = ?
                    WHERE file_path = ?
                """, (current_hash, time.time(), str(file_path)))
                conn.commit()
                conn.close()

            self.baselines[str(file_path)] = current_hash

        except Exception as e:
            print(f"Error checking {file_path}: {e}")

        return changes


class ProcessMonitor:
    """Monitors process execution for suspicious activity."""

    def __init__(self):
        self.mitre_techniques = {
            "T1059": "Command and Scripting Interpreter",
            "T1059.001": "PowerShell",
            "T1059.003": "Windows Command Shell",
            "T1059.004": "Unix Shell",
            "T1059.006": "Python",
            "T1027": "Obfuscated/Stored Files",
            "T1027.001": "Binary Padding",
            "T1027.003": "Steganography",
            "T1036": "Masquerading",
            "T1036.003": "Rename System Utilities",
            "T1055": "Process Injection",
            "T1055.001": "Dynamic-link Library Injection",
            "T1055.002": "Portable Executable Injection",
            "T1068": "Exploitation for Privilege Escalation",
            "T1068.001": "Local Privilege Escalation",
            "T1053": "Scheduled Task/Job",
            "T1053.005": "Scheduled Task",
            "T1053.006": "Systemd Timers",
        }

    def monitor_process(self, pid: int) -> Optional[Dict]:
        try:
            proc = psutil.Process(pid)
            info = {
                "pid": pid,
                "name": proc.name(),
                "exe": proc.exe(),
                "cmdline": proc.cmdline(),
                "parent_pid": proc.ppid(),
                "user": proc.username(),
                "start_time": proc.create_time(),
                "cpu_percent": proc.cpu_percent(),
                "memory_mb": proc.memory_info().rss / (1024**2),
                "status": proc.status(),
                "num_threads": proc.num_threads(),
            }

            # Check for suspicious patterns
            suspicious = False
            mitre_techniques = []

            cmdline = " ".join(proc.cmdline())
            cmdline_lower = cmdline.lower()

            # Check for suspicious patterns
            suspicious_patterns = {
                "T1059.001": [r"powershell.*-enc", r"powershell.*-e\b", r"iex\s*\("],
                "T1059.003": [r"cmd\.exe\s+/c", r"cmd\s+/c"],
                "T1059.004": [r"/bin/bash", r"/bin/sh", r"sh\s+-c"],
                "T1059.006": [r"python\s+-c", r"python\s+-c", r"perl\s+-e"],
                "T1027": [r"base64\s+-d", r"base64\s+-decode", r"certutil\s+-decode"],
                "T1036.003": [r"svchost\.exe", r"lsass\.exe", r"csrss\.exe"],
                "T1055": [r"CreateRemoteThread", r"WriteProcessMemory", r"VirtualAllocEx"],
                "T1068": [r"whoami\s*/priv", r"net\s+localgroup\s+administrators"],
                "T1053": [r"schtasks\s+/create", r"at\s+\d", r"systemctl\s+enable"],
            }

            for technique, patterns in suspicious_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, cmdline_lower):
                        suspicious = True
                        mitre_techniques.append(technique)

            # Check for suspicious file paths
            suspicious_paths = [r"temp", r"tmp", r"appdata", r"programdata", r"public", r"users\.*\desktop"]
            for path_pattern in suspicious_paths:
                if re.search(path_pattern, cmdline_lower):
                    suspicious = True

            return {
                "pid": pid,
                "name": proc.name(),
                "exe": proc.exe(),
                "cmdline": cmdline,
                "parent_pid": proc.ppid(),
                "user": proc.username(),
                "start_time": proc.create_time(),
                "cpu_percent": proc.cpu_percent(),
                "memory_mb": proc.memory_info().rss / (1024**2),
                "status": proc.status(),
                "suspicious": suspicious,
                "mitre_techniques": list(set(mitre_techniques))
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None


class VulnerabilityScanner:
    """Scans for known vulnerabilities."""

    def __init__(self):
        self.cve_database = {}

    def load_cve_database(self, cve_file: str = None):
        """Load CVE database from file or use built-in."""
        # Would load from NVD or local file
        pass

    def scan_installed_software(self) -> List[Dict]:
        """Scan installed software for known vulnerabilities."""
        vulnerabilities = []

        # Check Python packages
        try:
            import pkg_resources
            for dist in pkg_resources.working_set:
                vulns = self._check_package_vulnerabilities(dist.project_name, dist.version)
                vulnerabilities.extend(vulns)
        except Exception:
            pass

        # Check system packages (Linux)
        try:
            result = subprocess.run(["apt", "list", "--upgradable"], capture_output=True, text=True, timeout=30)
            # Parse output for security updates
        except Exception:
            pass

        return vulnerabilities

    def _check_package_vulnerabilities(self, package: str, version: str) -> List[Dict]:
        # Would query CVE database
        return []


class IncidentManager:
    """Manages security incidents."""

    def __init__(self):
        pass

    def create_incident(self, title: str, description: str, severity: str,
                        mitre_tactics: List[str] = None, mitre_techniques: List[str] = None,
                        iocs: List[Dict] = None) -> str:
        incident_id = f"inc_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO incidents (id, title, description, severity, status, detected_at, updated_at,
                                 mitre_tactics, mitre_techniques, iocs)
            VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
        """, (incident_id, title, description, severity, time.time(), time.time(),
              json.dumps(mitre_tactics or []), json.dumps(mitre_techniques or []), json.dumps(iocs or [])))
        conn.commit()
        conn.close()
        return incident_id

    def update_incident(self, incident_id: str, **kwargs) -> bool:
        allowed_fields = ["status", "description", "severity", "assigned_to", "mitre_tactics",
                          "mitre_techniques", "iocs", "notes"]
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        updates["updated_at"] = time.time()
        if kwargs.get("status") == "resolved":
            updates["resolved_at"] = time.time()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [incident_id]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE incidents SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return True

    def get_incident(self, incident_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "title": row[1], "description": row[2],
                "severity": row[2], "status": row[3], "assigned_to": row[4],
                "detected_at": row[5], "updated_at": row[6], "resolved_at": row[7],
                "mitre_tactics": json.loads(row[8]) if row[8] else [],
                "mitre_techniques": json.loads(row[9]) if row[9] else [],
                "iocs": json.loads(row[10]) if row[10] else [],
                "notes": row[11]
            }
        return None

    def list_incidents(self, status: str = None, limit: int = 50) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM incidents WHERE status = ? ORDER BY detected_at DESC LIMIT ?", (status, limit))
        else:
            cursor.execute("SELECT * FROM incidents ORDER BY detected_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "title": r[1], "description": r[2], "severity": r[2],
             "status": r[3], "assigned_to": r[4], "detected_at": r[5],
             "updated_at": r[6], "resolved_at": r[7]}
            for r in rows
        ]


class ThreatHunter:
    """Proactive threat hunting."""

    def __init__(self):
        self.queries = []

    def add_hunt_query(self, name: str, description: str, query: str,
                       mitre_techniques: List[str] = None, schedule: str = None) -> str:
        query_id = f"hq_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO hunt_queries (id, name, description, query, mitre_techniques, schedule, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (query_id, name, description, query,
              json.dumps(mitre_techniques or []), schedule, time.time()))
        conn.commit()
        conn.close()
        return query_id

    def run_hunt(self, query_id: str) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hunt_queries WHERE id = ?", (query_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"error": "Query not found"}

        query = row[3]
        try:
            # Execute the hunt query (SQL)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            result_id = f"hr_{int(time.time() * 1000) % 100000000:08d}"
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE hunt_queries SET last_run = ?, last_results = ? WHERE id = ?
            """, (time.time(), json.dumps([dict(r) for r in results]), query_id))
            conn.commit()
            conn.close()

            return {
                "query_id": query_id,
                "results_count": len(results),
                "results": [dict(r) for r in results[:100]]  # Limit to 100
            }
        except Exception as e:
            return {"error": str(e)}

    def get_scheduled_hunts(self) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hunt_queries WHERE enabled = 1 AND schedule IS NOT NULL")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "description": r[2], "schedule": r[5], "last_run": r[6]}
            for r in rows
        ]


class CybersecurityAgent:
    """Main cybersecurity agent coordinator."""

    def __init__(self):
        self.threat_intel = ThreatIntelligence()
        self.log_analyzer = LogAnalyzer()
        self.network_monitor = NetworkMonitor()
        self.file_integrity = FileIntegrityMonitor()
        self.process_monitor = ProcessMonitor()
        self.vuln_scanner = VulnerabilityScanner()
        self.incident_manager = IncidentManager()
        self.threat_hunter = ThreatHunter()
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
                self._monitor_cycle()
            except Exception as e:
                print(f"Cybersecurity monitor error: {e}")
            time.sleep(60)  # Run every minute

    def _monitor_cycle(self):
        # Scan network connections
        self.network_monitor.scan_connections()

        # Check file integrity
        changes = self.file_integrity.check_integrity()
        for change in changes:
            self._handle_file_change(change)

        # Monitor processes
        self._scan_processes()

        # Run scheduled threat hunts
        self._run_scheduled_hunts()

    def _handle_file_change(self, change: Dict):
        event_id = f"evt_{int(time.time() * 1000) % 100000000:08d}"
        event = SecurityEvent(
            id=event_id,
            event_type="file_integrity",
            severity="high" if change["status"] == "modified" else "medium",
            source_ip=None,
            dest_ip=None,
            user=None,
            process_name=None,
            command_line=None,
            file_path=change["file"],
            hash=change.get("new_hash") or change.get("hash"),
            description=f"File {change['status']}: {change['file']}",
            raw_log=json.dumps(change),
            timestamp=change.get("timestamp", time.time()),
            host=platform.node(),
            tags=["file_integrity", change["status"]]
        )
        self.log_analyzer._store_event(event)

    def _scan_processes(self):
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                result = self.process_monitor.monitor_process(proc.info['pid'])
                if result and result["suspicious"]:
                    self._handle_suspicious_process(result)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def _handle_suspicious_process(self, result: Dict):
        event_id = f"evt_{int(time.time() * 1000) % 100000000:08d}"
        event = SecurityEvent(
            id=event_id,
            event_type="suspicious_process",
            severity="high",
            source_ip=None,
            dest_ip=None,
            user=result.get("user"),
            process_name=result.get("name"),
            command_line=result.get("cmdline"),
            file_path=result.get("exe"),
            hash=None,
            description=f"Suspicious process detected: {result.get('name')} (PID: {result['pid']})",
            raw_log=json.dumps(result),
            timestamp=time.time(),
            host=platform.node(),
            tags=["suspicious_process"] + result.get("mitre_techniques", [])
        )
        self.log_analyzer._store_event(event)

    def _run_scheduled_hunts(self):
        hunts = self.threat_hunter.get_scheduled_hunts()
        for hunt in hunts:
            # Simple schedule check (would need croniter for production)
            self.threat_hunter.run_hunt(hunt["id"])

    def analyze_log(self, log_line: str, source: str = "unknown") -> List[SecurityEvent]:
        return self.log_analyzer.analyze_log_line(log_line, source)

    def analyze_log_file(self, file_path: str) -> List[SecurityEvent]:
        return self.log_analyzer.analyze_log_file(file_path)

    def scan_network(self) -> List[NetworkConnection]:
        return self.network_monitor.scan_connections()

    def check_file_integrity(self) -> List[Dict]:
        return self.file_integrity.check_integrity()

    def add_monitored_path(self, path: str, recursive: bool = True):
        self.file_integrity.add_monitored_path(path, recursive)

    def scan_processes(self) -> List[Dict]:
        suspicious = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                result = self.process_monitor.monitor_process(proc.info['pid'])
                if result and result["suspicious"]:
                    suspicious.append(result)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return suspicious

    def create_incident(self, title: str, description: str, severity: str,
                        mitre_tactics: List[str] = None, mitre_techniques: List[str] = None,
                        iocs: List[Dict] = None) -> str:
        return self.incident_manager.create_incident(title, description, severity, mitre_tactics, mitre_techniques, iocs)

    def get_incidents(self, status: str = None, limit: int = 50) -> List[Dict]:
        return self.incident_manager.list_incidents(status, limit)

    def update_incident(self, incident_id: str, **kwargs) -> bool:
        return self.incident_manager.update_incident(incident_id, **kwargs)

    def add_threat_indicator(self, indicator_type: str, value: str, threat_type: str = None,
                             severity: str = "medium", source: str = "manual",
                             description: str = "", confidence: float = 0.5) -> str:
        return self.threat_intel.add_indicator(indicator_type, value, threat_type, severity, source, description)

    def check_threat_indicator(self, indicator_type: str, value: str) -> Optional[Dict]:
        return self.threat_intel.check_indicator(indicator_type, value)

    def scan_vulnerabilities(self) -> List[Dict]:
        return self.vuln_scanner.scan_installed_software()

    def add_hunt_query(self, name: str, description: str, query: str,
                       mitre_techniques: List[str] = None, schedule: str = None) -> str:
        return self.threat_hunter.add_hunt_query(name, description, query, mitre_techniques, schedule)

    def run_hunt(self, query_id: str) -> Dict:
        return self.threat_hunter.run_hunt(query_id)

    def add_monitored_path(self, path: str, recursive: bool = True):
        self.file_integrity.add_monitored_path(path, recursive)

    def check_file_integrity(self) -> List[Dict]:
        return self.file_integrity.check_integrity()

    def get_incidents(self, status: str = None, limit: int = 50) -> List[Dict]:
        return self.incident_manager.list_incidents(status, limit)

    def get_recent_events(self, limit: int = 100, event_type: str = None) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        if event_type:
            cursor.execute("""
                SELECT * FROM security_events WHERE event_type = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (event_type, limit))
        else:
            cursor.execute("SELECT * FROM security_events ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "event_type": r[1], "severity": r[2], "source_ip": r[3],
             "dest_ip": r[4], "user": r[5], "process_name": r[6], "command_line": r[7],
             "file_path": r[8], "hash": r[9], "description": r[10], "raw_log": r[11],
             "timestamp": r[12], "host": r[13], "tags": json.loads(r[13]) if r[13] else []}
            for r in rows
        ]

    def get_network_connections(self, limit: int = 100) -> List[NetworkConnection]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM network_connections ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [NetworkConnection(id=r[0], local_ip=r[1], local_port=r[2], remote_ip=r[3],
                                  remote_port=r[4], protocol=r[5], state=r[6], pid=r[7],
                                  process_name=r[8], direction=r[9], bytes_sent=r[10],
                                  bytes_recv=r[11], timestamp=r[12], risk_score=r[13]) for r in rows]

    def get_threat_intel(self, indicator_type: str = None, limit: int = 100) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        if indicator_type:
            cursor.execute("SELECT * FROM threat_intel WHERE indicator_type = ? ORDER BY last_seen DESC LIMIT ?",
                           (indicator_type, limit))
        else:
            cursor.execute("SELECT * FROM threat_intel ORDER BY last_seen DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "type": r[1], "value": r[2], "threat_type": r[2],
             "severity": r[3], "source": r[4], "description": r[5],
             "first_seen": r[6], "last_seen": r[7], "confidence": r[8], "tags": json.loads(r[9]) if r[9] else []}
            for r in rows
        ]


# Global instance
cybersecurity_agent = CybersecurityAgent()


# Voice command integration
def cybersecurity_debug() -> str:
    """Debug cybersecurity agent status."""
    events = cybersecurity_agent.get_recent_events(5)
    connections = cybersecurity_agent.get_network_connections(5)
    incidents = cybersecurity_agent.get_incidents(limit=5)

    output = f"Cybersecurity Agent Status:\n"
    output += f"  Recent events: {len(events)}\n"
    output += f"  Network connections: {len(connections)}\n"
    output += f"  Active incidents: {len(incidents)}\n"
    return output


def cybersecurity_events(event_type: str = None, limit: int = 10) -> str:
    events = cybersecurity_agent.get_recent_events(limit, event_type)
    if not events:
        return "No recent security events."
    output = f"Recent Security Events ({len(events)}):\n"
    for e in events:
        dt = datetime.fromtimestamp(e['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        output += f"  [{dt}] {e['event_type']} ({e['severity']}): {e['description'][:80]}\n"
    return output


def cybersecurity_incidents(status: str = None, limit: int = 10) -> str:
    incidents = cybersecurity_agent.get_incidents(status, limit)
    if not incidents:
        return "No incidents."
    output = f"Incidents ({len(incidents)}):\n"
    for inc in incidents:
        output += f"  • {inc['title']} [{inc['severity']}] - {inc['status']}\n"
    return output


def cybersecurity_incident_create(title: str, description: str, severity: str) -> str:
    incident_id = cybersecurity_agent.create_incident(title, description, severity)
    return f"Created incident: {incident_id}"


def cybersecurity_incident_update(incident_id: str, **kwargs) -> str:
    if cybersecurity_agent.update_incident(incident_id, **kwargs):
        return f"Incident {incident_id} updated."
    return f"Failed to update incident {incident_id}."


def cybersecurity_network() -> str:
    connections = cybersecurity_agent.get_network_connections(10)
    if not connections:
        return "No network connections."
    output = f"Network Connections ({len(connections)}):\n"
    for c in connections:
        risk = "🔴" if c.risk_score > 0.7 else "🟡" if c.risk_score > 0.3 else "🟢"
        output += f"  {c.direction} {c.local_ip}:{c.local_port} -> {c.remote_ip}:{c.remote_port} [{c.protocol}] {c.state} {risk}\n"
    return output


def cybersecurity_integrity() -> str:
    changes = cybersecurity_agent.check_file_integrity()
    if not changes:
        return "File integrity OK - no changes detected."
    output = f"File Integrity Changes ({len(changes)}):\n"
    for c in changes[:10]:
        output += f"  • {c['file']}: {c['status']}\n"
    return output


def cybersecurity_add_path(path: str, recursive: str = "true") -> str:
    recursive_bool = recursive.lower() != "false"
    cybersecurity_agent.add_monitored_path(path, recursive_bool)
    return f"Added path to file integrity monitoring: {path}"


def cybersecurity_scan_network() -> str:
    connections = cybersecurity_agent.scan_network()
    if not connections:
        return "No network connections found."
    output = f"Network Scan ({len(connections)} connections):\n"
    for c in connections[:20]:
        risk = "🔴" if c.risk_score > 0.7 else "🟡" if c.risk_score > 0.3 else "🟢"
        output += f"  {risk} {c.direction} {c.local_ip}:{c.local_port} -> {c.remote_ip}:{c.remote_port} [{c.protocol}] {c.state}\n"
    return output


def cybersecurity_integrity_check() -> str:
    changes = cybersecurity_agent.check_file_integrity()
    if not changes:
        return "File integrity OK - no changes detected."
    output = f"File Integrity Changes ({len(changes)}):\n"
    for c in changes:
        output += f"  • {c['file']}: {c['status']}\n"
    return output


def cybersecurity_add_path_cmd(path: str, recursive: str = "true") -> str:
    recursive_bool = recursive.lower() != "false"
    cybersecurity_agent.add_monitored_path(path, recursive_bool)
    return f"Added path to file integrity monitoring: {path}"


def cybersecurity_scan_network() -> str:
    connections = cybersecurity_agent.scan_network()
    if not connections:
        return "No network connections found."
    output = f"Network Scan ({len(connections)} connections):\n"
    for c in connections[:20]:
        risk = "🔴" if c.risk_score > 0.7 else "🟡" if c.risk_score > 0.3 else "🟢"
        output += f"  {risk} {c.direction} {c.local_ip}:{c.local_port} -> {c.remote_ip}:{c.remote_port} [{c.protocol}] {c.state}\n"
    return output


def cybersecurity_processes() -> str:
    suspicious = cybersecurity_agent.scan_processes()
    if not suspicious:
        return "No suspicious processes detected."
    output = f"Suspicious Processes ({len(suspicious)}):\n"
    for p in suspicious[:10]:
        output += f"  • PID {p['pid']}: {p['name']} - {', '.join(p['mitre_techniques'])}\n"
    return output


def cybersecurity_incidents(status: str = None, limit: int = 10) -> str:
    incidents = cybersecurity_agent.get_incidents(status, limit)
    if not incidents:
        return "No incidents."
    output = f"Incidents ({len(incidents)}):\n"
    for inc in incidents:
        output += f"  • {inc['title']} [{inc['severity']}] - {inc['status']}\n"
    return output


def cybersecurity_incident_create(title: str, description: str, severity: str) -> str:
    incident_id = cybersecurity_agent.create_incident(title, description, severity)
    return f"Created incident: {incident_id}"


def cybersecurity_incident_update(incident_id: str, **kwargs) -> str:
    if cybersecurity_agent.update_incident(incident_id, **kwargs):
        return f"Incident {incident_id} updated."
    return f"Failed to update incident {incident_id}."


def cybersecurity_threat_intel(type: str = None, limit: int = 20) -> str:
    intel = cybersecurity_agent.get_threat_intel(type, limit)
    if not intel:
        return "No threat intelligence."
    output = f"Threat Intelligence ({len(intel)}):\n"
    for i in intel:
        output += f"  • {i['type']}: {i['value']} [{i['severity']}] ({i['source']})\n"
    return output


def cybersecurity_add_intel(indicator_type: str, value: str, threat_type: str = None,
                            severity: str = "medium", description: str = "") -> str:
    threat_id = cybersecurity_agent.add_threat_indicator(indicator_type, value, threat_type, severity, description=description)
    return f"Added threat indicator: {threat_id}"


def cybersecurity_check_intel(indicator_type: str, value: str) -> str:
    result = cybersecurity_agent.check_threat_indicator(indicator_type, value)
    if result:
        return f"MATCH: {result['type']}: {result['value']} - {result.get('threat_type', 'unknown')} [{result['severity']}]"
    return "No match found in threat intelligence."


def cybersecurity_scan_vulns() -> str:
    vulns = cybersecurity_agent.scan_vulnerabilities()
    if not vulns:
        return "No vulnerabilities found."
    output = f"Vulnerabilities ({len(vulns)}):\n"
    for v in vulns[:10]:
        output += f"  • {v.get('package', 'unknown')}: {v.get('cve', 'N/A')}\n"
    return output


def cybersecurity_add_hunt(name: str, description: str, query: str) -> str:
    hunt_id = cybersecurity_agent.add_hunt_query(name, description, query)
    return f"Created hunt query: {hunt_id}"


def cybersecurity_run_hunt(hunt_id: str) -> str:
    result = cybersecurity_agent.run_hunt(hunt_id)
    if "error" in result:
        return f"Hunt failed: {result['error']}"
    return f"Hunt completed: {result['results_count']} results found."


def cybersecurity_add_path(path: str, recursive: str = "true") -> str:
    recursive_bool = recursive.lower() != "false"
    cybersecurity_agent.add_monitored_path(path, recursive_bool)
    return f"Added path to file integrity monitoring: {path}"


def cybersecurity_integrity_check() -> str:
    changes = cybersecurity_agent.check_file_integrity()
    if not changes:
        return "File integrity OK - no changes detected."
    output = f"File Integrity Changes ({len(changes)}):\n"
    for c in changes[:10]:
        output += f"  • {c['file']}: {c['status']}\n"
    return output


def cybersecurity_incident_create(title: str, description: str, severity: str) -> str:
    incident_id = cybersecurity_agent.create_incident(title, description, severity)
    return f"Created incident: {incident_id}"


def cybersecurity_incident_update(incident_id: str, **kwargs) -> str:
    if cybersecurity_agent.update_incident(incident_id, **kwargs):
        return f"Incident {incident_id} updated."
    return f"Failed to update incident {incident_id}."

def cybersecurity_scan_network() -> str:
    connections = cybersecurity_agent.scan_network()
    if not connections:
        return "No network connections found."
    output = f"Network Scan ({len(connections)} connections):\n"
    for c in connections[:20]:
        risk = "🔴" if c.risk_score > 0.7 else "🟡" if c.risk_score > 0.3 else "🟢"
        output += f"  {risk} {c.direction} {c.local_ip}:{c.local_port} -> {c.remote_ip}:{c.remote_port} [{c.protocol}] {c.state}\n"
    return output


def cybersecurity_processes() -> str:
    suspicious = cybersecurity_agent.scan_processes()
    if not suspicious:
        return "No suspicious processes detected."
    output = f"Suspicious Processes ({len(suspicious)}):\n"
    for p in suspicious[:10]:
        output += f"  • PID {p['pid']}: {p['name']} - {', '.join(p['mitre_techniques'])}\n"
    return output


def cybersecurity_incidents(status: str = None, limit: int = 10) -> str:
    incidents = cybersecurity_agent.get_incidents(status, limit)
    if not incidents:
        return "No incidents."
    output = f"Incidents ({len(incidents)}):\n"
    for inc in incidents:
        output += f"  • {inc['title']} [{inc['severity']}] - {inc['status']}\n"
    return output


def cybersecurity_incident_create(title: str, description: str, severity: str) -> str:
    incident_id = cybersecurity_agent.create_incident(title, description, severity)
    return f"Created incident: {incident_id}"


def cybersecurity_incident_update(incident_id: str, **kwargs) -> str:
    if cybersecurity_agent.update_incident(incident_id, **kwargs):
        return f"Incident {incident_id} updated."
    return f"Failed to update incident {incident_id}."


if __name__ == "__main__":
    print("Cybersecurity Agent module loaded.")
    print("Available functions:")
    print("  cybersecurity_debug()")
    print("  cybersecurity_events(event_type, limit)")
    print("  cybersecurity_incidents(status, limit)")
    print("  cybersecurity_incident_create(title, description, severity)")
    print("  cybersecurity_incident_update(incident_id, **kwargs)")
    print("  cybersecurity_network()")
    print("  cybersecurity_integrity_check()")
    print("  cybersecurity_add_path(path, recursive)")
    print("  cybersecurity_scan_network()")
    print("  cybersecurity_processes()")
    print("  cybersecurity_incidents(status, limit)")
    print("  cybersecurity_incident_create(title, description, severity)")
    print("  cybersecurity_incident_update(incident_id, **kwargs)")
    print("  cybersecurity_threat_intel(type, limit)")
    print("  cybersecurity_add_intel(type, value, threat_type, severity, description)")
    print("  cybersecurity_check_intel(type, value)")
    print("  cybersecurity_scan_vulns()")
    print("  cybersecurity_add_hunt(name, description, query)")
    print("  cybersecurity_run_hunt(hunt_id)")
    print("  cybersecurity_add_path(path, recursive)")
    print("  cybersecurity_integrity_check()")
    print("  cybersecurity_incident_create(title, description, severity)")
    print("  cybersecurity_incident_update(incident_id, **kwargs)")
    print("  cybersecurity_scan_network()")
    print("  cybersecurity_processes()")
    print("  cybersecurity_incidents(status, limit)")
    print("  cybersecurity_incident_create(title, description, severity)")
    print("  cybersecurity_incident_update(incident_id, **kwargs)")