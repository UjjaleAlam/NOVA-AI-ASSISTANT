"""
Workspace Reconstruction Agent - Phase 30
Reconstructs user workspace state: open apps, windows, files, browser tabs, terminal sessions.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import hashlib
import subprocess
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False

DB_DIR = "database"
WR_DB = os.path.join(DB_DIR, "workspace_reconstruction.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_wr_connection():
    import sqlite3
    conn = sqlite3.connect(WR_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_wr_db():
    conn = get_wr_connection()
    cursor = conn.cursor()

    # Workspace snapshots (full state captures)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspace_snapshots (
            id TEXT PRIMARY KEY,
            name TEXT,                    -- user-defined name
            description TEXT,
            timestamp REAL NOT NULL,
            session_id TEXT,
            is_auto BOOLEAN DEFAULT 0,   -- auto-captured vs manual
            apps TEXT,                    -- JSON array of app states
            windows TEXT,                 -- JSON array of window states
            browser_tabs TEXT,            -- JSON array of browser tabs
            terminal_sessions TEXT,       -- JSON array of terminal sessions
            open_files TEXT,              -- JSON array of open files
            virtual_desktops TEXT,        -- JSON array of virtual desktops
            screen_layout TEXT,           -- JSON: monitor arrangement
            metadata TEXT,                -- JSON
            created_at REAL NOT NULL
        )
    """)

    # Application states
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_states (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            app_name TEXT NOT NULL,
            exe_path TEXT,
            pid INTEGER,
            window_title TEXT,
            window_rect TEXT,             -- JSON: x, y, width, height
            is_minimized BOOLEAN,
            is_maximized BOOLEAN,
            is_active BOOLEAN,
            cpu_percent REAL,
            memory_mb REAL,
            command_line TEXT,
            working_directory TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES workspace_snapshots(id)
        )
    """)

    # Window states
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS window_states (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            app_name TEXT,
            window_title TEXT,
            window_class TEXT,
            rect TEXT,                    -- JSON: x, y, width, height
            z_order INTEGER,
            is_visible BOOLEAN,
            is_minimized BOOLEAN,
            is_maximized BOOLEAN,
            monitor_index INTEGER,
            created_at REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES workspace_snapshots(id)
        )
    """)

    # Browser tabs (from supported browsers)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS browser_tabs (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            browser TEXT NOT NULL,        -- chrome, firefox, edge, brave
            window_id TEXT,
            tab_index INTEGER,
            url TEXT,
            title TEXT,
            favicon_url TEXT,
            is_active BOOLEAN,
            is_pinned BOOLEAN,
            is_muted BOOLEAN,
            created_at REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES workspace_snapshots(id)
        )
    """)

    # Terminal sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS terminal_sessions (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            terminal_app TEXT,            -- cmd, powershell, wsl, gitbash, terminal
            shell TEXT,                   -- cmd, powershell, bash, zsh
            working_directory TEXT,
            command_history TEXT,         -- JSON array
            current_command TEXT,
            pid INTEGER,
            window_title TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES workspace_snapshots(id)
        )
    """)

    # Open files (from applications)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS open_files (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            app_name TEXT,
            file_path TEXT,
            file_name TEXT,
            line_number INTEGER,
            column_number INTEGER,
            is_modified BOOLEAN,
            encoding TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES workspace_snapshots(id)
        )
    """)

    # Virtual desktops
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS virtual_desktops (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            desktop_index INTEGER,
            desktop_name TEXT,
            wallpaper_path TEXT,
            active_window_ids TEXT,       -- JSON array of window IDs
            created_at REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES workspace_snapshots(id)
        )
    """)

    # Screen/monitor layout
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screen_layouts (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            monitor_count INTEGER,
            monitors TEXT,                -- JSON array: x, y, width, height, scale, primary
            arrangement TEXT,             -- 'horizontal', 'vertical', 'custom'
            created_at REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES workspace_snapshots(id)
        )
    """)

    # Workspace templates (reusable configurations)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspace_templates (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            category TEXT,                -- 'development', 'research', 'meeting', 'creative'
            apps TEXT,                    -- JSON array: app configs to launch
            layout TEXT,                  -- JSON: window positions
            tags TEXT,                    -- JSON array
            is_default BOOLEAN DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Restoration jobs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restoration_jobs (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            template_id TEXT,
            status TEXT DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'partial'
            started_at REAL,
            completed_at REAL,
            apps_launched INTEGER DEFAULT 0,
            apps_failed INTEGER DEFAULT 0,
            windows_restored INTEGER DEFAULT 0,
            errors TEXT,                  -- JSON array
            created_at REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES workspace_snapshots(id)
        )
    """)

    conn.commit()
    conn.close()


init_wr_db()


@dataclass
class AppState:
    app_name: str
    exe_path: str
    pid: int
    window_title: str
    window_rect: Dict
    is_minimized: bool
    is_maximized: bool
    is_active: bool
    cpu_percent: float
    memory_mb: float
    command_line: str
    working_directory: str


class WorkspaceCapture:
    """Captures complete workspace state."""

    def __init__(self):
        pass

    def capture_full_workspace(self, name: str = "", description: str = "",
                               session_id: str = "", is_auto: bool = False) -> str:
        """Capture complete workspace snapshot."""
        snapshot_id = f"ws_{int(time.time() * 1000) % 100000000:08d}"
        timestamp = time.time()

        # Capture all components
        apps = self._capture_apps()
        windows = self._capture_windows()
        browser_tabs = self._capture_browser_tabs()
        terminal_sessions = self._capture_terminal_sessions()
        open_files = self._capture_open_files()
        virtual_desktops = self._capture_virtual_desktops()
        screen_layout = self._capture_screen_layout()

        conn = get_wr_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workspace_snapshots (id, name, description, timestamp,
                                            session_id, is_auto, apps, windows,
                                            browser_tabs, terminal_sessions,
                                            open_files, virtual_desktops,
                                            screen_layout, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (snapshot_id, name, description, timestamp, session_id, is_auto,
              json.dumps(apps), json.dumps(windows), json.dumps(browser_tabs),
              json.dumps(terminal_sessions), json.dumps(open_files),
              json.dumps(virtual_desktops), json.dumps(screen_layout),
              json.dumps({}), time.time()))
        conn.commit()
        conn.close()

        return snapshot_id

    def _capture_apps(self) -> List[Dict]:
        """Capture running applications with window info."""
        apps = []

        if not PSUTIL_AVAILABLE:
            return apps

        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'cwd', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                if not info['name']:
                    continue

                # Skip system processes
                if info['name'].lower() in ['system', 'registry', 'smss.exe', 'csrss.exe', 'wininit.exe', 'services.exe', 'lsass.exe']:
                    continue

                app_data = {
                    "app_name": info['name'],
                    "exe_path": info['exe'] or "",
                    "pid": info['pid'],
                    "command_line": " ".join(info['cmdline']) if info['cmdline'] else "",
                    "working_directory": info['cwd'] or "",
                    "cpu_percent": info['cpu_percent'] or 0,
                    "memory_mb": (info['memory_info'].rss / (1024*1024)) if info['memory_info'] else 0,
                    "window_title": "",
                    "window_rect": {"x": 0, "y": 0, "width": 0, "height": 0},
                    "is_minimized": False,
                    "is_maximized": False,
                    "is_active": False
                }

                # Try to get window info
                if PYGETWINDOW_AVAILABLE:
                    try:
                        windows = gw.getWindowsWithTitle(info['name'])
                        if windows:
                            w = windows[0]
                            app_data["window_title"] = w.title
                            app_data["window_rect"] = {"x": w.left, "y": w.top, "width": w.width, "height": w.height}
                            app_data["is_minimized"] = w.isMinimized
                            app_data["is_maximized"] = w.isMaximized
                            app_data["is_active"] = w.isActive
                    except:
                        pass

                apps.append(app_data)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return apps

    def _capture_windows(self) -> List[Dict]:
        """Capture all visible windows."""
        windows = []

        if not PYGETWINDOW_AVAILABLE:
            return windows

        try:
            all_windows = gw.getAllWindows()
            for i, w in enumerate(all_windows):
                if not w.title or not w.visible:
                    continue

                windows.append({
                    "window_title": w.title,
                    "app_name": self._get_app_name_from_window(w),
                    "window_class": "",
                    "rect": {"x": w.left, "y": w.top, "width": w.width, "height": w.height},
                    "z_order": i,
                    "is_visible": w.visible,
                    "is_minimized": w.isMinimized,
                    "is_maximized": w.isMaximized,
                    "monitor_index": 0  # Would need multi-monitor detection
                })
        except:
            pass

        return windows

    def _get_app_name_from_window(self, window) -> str:
        """Extract app name from window."""
        try:
            # Try to get process name from window
            import win32process
            import win32gui
            hwnd = window._hWnd
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            return proc.name()
        except:
            return "Unknown"

    def _capture_browser_tabs(self) -> List[Dict]:
        """Capture browser tabs from supported browsers."""
        tabs = []

        # Try to read browser tab data from various sources
        # Chrome/Edge: read from profile directory
        # Firefox: read from sessionstore.jsonlz4

        browser_paths = {
            "chrome": [
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Sessions"),
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Current Session")
            ],
            "edge": [
                os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\Sessions"),
                os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\Current Session")
            ],
            "firefox": [
                os.path.expanduser(r"~\AppData\Roaming\Mozilla\Firefox\Profiles")
            ],
            "brave": [
                os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Sessions")
            ]
        }

        # This is a simplified implementation - real implementation would parse
        # browser session files (SNSS format for Chrome/Edge, sessionstore for Firefox)
        # For now, return empty - would need browser-specific parsers

        return tabs

    def _capture_terminal_sessions(self) -> List[Dict]:
        """Capture active terminal sessions."""
        sessions = []

        if not PSUTIL_AVAILABLE:
            return sessions

        terminal_apps = ['cmd.exe', 'powershell.exe', 'pwsh.exe', 'wsl.exe', 'bash.exe', 
                         'mintty.exe', 'conhost.exe', 'wt.exe', 'terminal.exe']

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
            try:
                info = proc.info
                if info['name'].lower() in terminal_apps:
                    sessions.append({
                        "terminal_app": info['name'],
                        "shell": self._detect_shell(info['cmdline']),
                        "working_directory": info['cwd'] or "",
                        "command_history": [],
                        "current_command": " ".join(info['cmdline']) if info['cmdline'] else "",
                        "pid": info['pid'],
                        "window_title": ""
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return sessions

    def _detect_shell(self, cmdline: List[str]) -> str:
        if not cmdline:
            return "unknown"
        cmd = " ".join(cmdline).lower()
        if 'powershell' in cmd or 'pwsh' in cmd:
            return 'powershell'
        elif 'wsl' in cmd:
            return 'wsl'
        elif 'bash' in cmd:
            return 'bash'
        elif 'zsh' in cmd:
            return 'zsh'
        elif 'cmd' in cmd:
            return 'cmd'
        return 'unknown'

    def _capture_open_files(self) -> List[Dict]:
        """Capture files open in applications."""
        files = []

        # This would require hooking into applications or parsing recent files
        # For now, use system agent's recent files
        try:
            from core.search_manager import search_manager
            recent = search_manager.search_recent(limit=50)
            for f in recent:
                files.append({
                    "app_name": "system",
                    "file_path": f.get('path', ''),
                    "file_name": f.get('name', ''),
                    "line_number": None,
                    "column_number": None,
                    "is_modified": False,
                    "encoding": "utf-8"
                })
        except:
            pass

        return files

    def _capture_virtual_desktops(self) -> List[Dict]:
        """Capture virtual desktop info (Windows 10/11)."""
        desktops = []

        # Windows virtual desktop API is not easily accessible from Python
        # Would need COM interface or Windows SDK
        # Return placeholder
        return desktops

    def _capture_screen_layout(self) -> Dict:
        """Capture monitor arrangement."""
        if not PSUTIL_AVAILABLE:
            return {"monitor_count": 0, "monitors": [], "arrangement": "unknown"}

        try:
            monitors = []
            # Get display info using win32api or similar
            # Simplified for now
            return {
                "monitor_count": 1,
                "monitors": [{"x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1.0, "primary": True}],
                "arrangement": "horizontal"
            }
        except:
            return {"monitor_count": 0, "monitors": [], "arrangement": "unknown"}


class WorkspaceRestorer:
    """Restores workspace from snapshot or template."""

    def __init__(self):
        pass

    def restore_from_snapshot(self, snapshot_id: str, options: Dict = None) -> str:
        """Restore workspace from a snapshot."""
        job_id = f"restore_{int(time.time() * 1000) % 100000000:08d}"
        options = options or {}

        conn = get_wr_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workspace_snapshots WHERE id = ?", (snapshot_id,))
        snapshot = cursor.fetchone()
        conn.close()

        if not snapshot:
            return {"error": "Snapshot not found", "job_id": job_id}

        # Create restoration job
        conn = get_wr_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO restoration_jobs (id, snapshot_id, template_id, status, started_at, created_at)
            VALUES (?, ?, ?, 'running', ?, ?)
        """, (job_id, snapshot_id, options.get('template_id'), time.time(), time.time()))
        conn.commit()
        conn.close()

        # Run restoration in background
        thread = threading.Thread(target=self._run_restoration, args=(job_id, snapshot, options))
        thread.daemon = True
        thread.start()

        return job_id

    def _run_restoration(self, job_id: str, snapshot: tuple, options: Dict):
        """Background restoration worker."""
        try:
            apps = json.loads(snapshot[6]) if snapshot[6] else []
            windows = json.loads(snapshot[7]) if snapshot[7] else []
            browser_tabs = json.loads(snapshot[8]) if snapshot[8] else []
            terminals = json.loads(snapshot[9]) if snapshot[9] else []

            apps_launched = 0
            apps_failed = 0
            windows_restored = 0
            errors = []

            # Only launch apps that have valid exe_path and are known applications
            # Limit to first 10 to avoid launching too many
            known_apps = ['code', 'chrome', 'firefox', 'edge', 'terminal', 'wt', 'cmd', 'powershell', 'notepad', 'vim', 'code.exe']
            
            for app in apps[:10]:  # Limit to 10 apps
                app_name = app.get('app_name', '').lower()
                exe_path = app.get('exe_path', '')
                
                # Only try to launch known applications
                if any(known in app_name for known in known_apps):
                    try:
                        if exe_path and os.path.exists(exe_path):
                            subprocess.Popen([exe_path], cwd=app.get('working_directory', ''))
                            apps_launched += 1
                        else:
                            apps_failed += 1
                            errors.append(f"App not found: {app.get('app_name')}")
                    except Exception as e:
                        apps_failed += 1
                        errors.append(f"Failed to launch {app.get('app_name')}: {str(e)}")

            # Restore window positions (simplified)
            # Would need pygetwindow to move/resize windows

            # Update job status
            conn = get_wr_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE restoration_jobs SET status = 'completed', completed_at = ?,
                                           apps_launched = ?, apps_failed = ?,
                                           windows_restored = ?, errors = ?
                WHERE id = ?
            """, (time.time(), apps_launched, apps_failed, windows_restored, json.dumps(errors), job_id))
            conn.commit()
            conn.close()

        except Exception as e:
            conn = get_wr_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE restoration_jobs SET status = 'failed', completed_at = ?, errors = ? WHERE id = ?",
                          (time.time(), json.dumps([str(e)]), job_id))
            conn.commit()
            conn.close()

    def restore_from_template(self, template_id: str, options: Dict = None) -> str:
        """Restore workspace from a template."""
        # Similar to snapshot restoration but uses template
        return self.restore_from_snapshot("", {"template_id": template_id})


class TemplateManager:
    """Manages workspace templates."""

    def __init__(self):
        pass

    def create_template(self, name: str, description: str = "", category: str = "",
                        apps: List[Dict] = None, layout: Dict = None,
                        tags: List[str] = None, is_default: bool = False) -> str:
        # Check if template with this name exists
        conn = get_wr_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM workspace_templates WHERE name = ?", (name,))
        existing = cursor.fetchone()
        if existing:
            template_id = existing[0]
            # Update existing
            cursor.execute("""
                UPDATE workspace_templates SET description = ?, category = ?,
                                            apps = ?, layout = ?, tags = ?,
                                            is_default = ?, updated_at = ?
                WHERE id = ?
            """, (description, category, json.dumps(apps or []), json.dumps(layout or {}),
                  json.dumps(tags or []), is_default, time.time(), template_id))
            conn.commit()
            conn.close()
            return template_id

        template_id = f"tpl_{int(time.time() * 1000) % 100000000:08d}"
        cursor.execute("""
            INSERT INTO workspace_templates (id, name, description, category,
                                            apps, layout, tags, is_default,
                                            created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (template_id, name, description, category,
              json.dumps(apps or []), json.dumps(layout or {}),
              json.dumps(tags or []), is_default, time.time(), time.time()))
        conn.commit()
        conn.close()
        return template_id

    def create_template_from_snapshot(self, snapshot_id: str, name: str,
                                      description: str = "", category: str = "") -> str:
        """Create template from existing snapshot."""
        conn = get_wr_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workspace_snapshots WHERE id = ?", (snapshot_id,))
        snapshot = cursor.fetchone()
        conn.close()

        if not snapshot:
            return ""

        apps = json.loads(snapshot[6]) if snapshot[6] else []
        layout = {"windows": json.loads(snapshot[7]) if snapshot[7] else []}

        return self.create_template(name, description, category, apps, layout)

    def get_template(self, template_id: str) -> Optional[Dict]:
        conn = get_wr_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workspace_templates WHERE id = ?", (template_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "description": row[2],
                "category": row[3], "apps": json.loads(row[4]) if row[4] else [],
                "layout": json.loads(row[5]) if row[5] else {},
                "tags": json.loads(row[6]) if row[6] else [],
                "is_default": bool(row[7]), "created_at": row[8], "updated_at": row[9]
            }
        return None

    def list_templates(self, category: str = None) -> List[Dict]:
        conn = get_wr_connection()
        cursor = conn.cursor()
        if category:
            cursor.execute("SELECT * FROM workspace_templates WHERE category = ? ORDER BY name", (category,))
        else:
            cursor.execute("SELECT * FROM workspace_templates ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "description": r[2], "category": r[3],
             "is_default": bool(r[7])}
            for r in rows
        ]

    def delete_template(self, template_id: str) -> bool:
        conn = get_wr_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workspace_templates WHERE id = ?", (template_id,))
        conn.commit()
        conn.close()
        return True


# Pre-built templates
DEFAULT_TEMPLATES = {
    "development": {
        "name": "Development Environment",
        "description": "VS Code, terminal, browser for web development",
        "category": "development",
        "apps": [
            {"app_name": "code", "exe_path": "code", "working_directory": "~/projects"},
            {"app_name": "terminal", "exe_path": "wt.exe", "working_directory": "~/projects"},
            {"app_name": "browser", "exe_path": "chrome", "url": "http://localhost:3000"}
        ],
        "layout": {
            "windows": [
                {"app_name": "code", "rect": {"x": 0, "y": 0, "width": 1200, "height": 1080}},
                {"app_name": "terminal", "rect": {"x": 1200, "y": 0, "width": 720, "height": 540}},
                {"app_name": "browser", "rect": {"x": 1200, "y": 540, "width": 720, "height": 540}}
            ]
        },
        "tags": ["coding", "web", "fullstack"]
    },
    "research": {
        "name": "Research Workspace",
        "description": "Browser, note-taking, document viewer",
        "category": "research",
        "apps": [
            {"app_name": "browser", "exe_path": "chrome", "url": "https://scholar.google.com"},
            {"app_name": "notes", "exe_path": "code", "working_directory": "~/research/notes"},
            {"app_name": "pdf_viewer", "exe_path": "sumatrapdf.exe"}
        ],
        "layout": {
            "windows": [
                {"app_name": "browser", "rect": {"x": 0, "y": 0, "width": 1200, "height": 1080}},
                {"app_name": "notes", "rect": {"x": 1200, "y": 0, "width": 720, "height": 1080}}
            ]
        },
        "tags": ["research", "reading", "writing"]
    },
    "meeting": {
        "name": "Meeting Setup",
        "description": "Video conferencing, notes, calendar",
        "category": "meeting",
        "apps": [
            {"app_name": "teams", "exe_path": "teams.exe"},
            {"app_name": "notes", "exe_path": "notepad.exe"},
            {"app_name": "calendar", "exe_path": "outlook.exe"}
        ],
        "layout": {},
        "tags": ["meeting", "video-call", "calendar"]
    }
}


def create_default_templates():
    """Create default workspace templates."""
    tm = TemplateManager()
    for key, tpl in DEFAULT_TEMPLATES.items():
        try:
            existing = tm.list_templates()
            if not any(t['name'] == tpl['name'] for t in existing):
                tm.create_template(
                    tpl['name'], tpl['description'], tpl['category'],
                    tpl['apps'], tpl['layout'], tpl['tags']
                )
        except:
            pass


# Module-level functions
capture = WorkspaceCapture()
restorer = WorkspaceRestorer()
template_mgr = TemplateManager()


def wr_debug() -> str:
    conn = get_wr_connection()
    cursor = conn.cursor()
    tables = ["workspace_snapshots", "app_states", "window_states", "browser_tabs",
              "terminal_sessions", "open_files", "virtual_desktops", "screen_layouts",
              "workspace_templates", "restoration_jobs"]
    output = "Workspace Reconstruction Debug:\n"
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        output += f"  {t}: {count} records\n"
    conn.close()
    return output


def capture_workspace(name: str = "", description: str = "", session_id: str = "") -> str:
    return capture.capture_full_workspace(name, description, session_id)


def auto_capture_workspace() -> str:
    return capture.capture_full_workspace("Auto-capture", "Automatic workspace capture", is_auto=True)


def get_snapshot(snapshot_id: str) -> Optional[Dict]:
    conn = get_wr_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workspace_snapshots WHERE id = ?", (snapshot_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "name": row[1], "description": row[2],
            "timestamp": row[3], "session_id": row[4], "is_auto": bool(row[5]),
            "apps": json.loads(row[6]) if row[6] else [],
            "windows": json.loads(row[7]) if row[7] else [],
            "browser_tabs": json.loads(row[8]) if row[8] else [],
            "terminal_sessions": json.loads(row[9]) if row[9] else [],
            "open_files": json.loads(row[10]) if row[10] else [],
            "virtual_desktops": json.loads(row[11]) if row[11] else [],
            "screen_layout": json.loads(row[11]) if row[11] else {},
        }
    return None


def list_snapshots(limit: int = 20, auto_only: bool = False) -> List[Dict]:
    conn = get_wr_connection()
    cursor = conn.cursor()
    if auto_only:
        cursor.execute("SELECT * FROM workspace_snapshots WHERE is_auto = 1 ORDER BY timestamp DESC LIMIT ?", (limit,))
    else:
        cursor.execute("SELECT * FROM workspace_snapshots ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "description": r[2], "timestamp": r[3],
         "is_auto": bool(r[5]), "apps_count": len(json.loads(r[6])) if r[6] else 0}
        for r in rows
    ]


def restore_workspace(snapshot_id: str, options: Dict = None) -> str:
    return restorer.restore_from_snapshot(snapshot_id, options)


def get_restoration_status(job_id: str) -> Dict:
    conn = get_wr_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM restoration_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "snapshot_id": row[1], "template_id": row[2],
            "status": row[3], "started_at": row[4], "completed_at": row[5],
            "apps_launched": row[6], "apps_failed": row[7],
            "windows_restored": row[8], "errors": json.loads(row[9]) if row[9] else []
        }
    return {}


def create_template(name: str, description: str = "", category: str = "",
                    apps: List[Dict] = None, layout: Dict = None,
                    tags: List[str] = None) -> str:
    return template_mgr.create_template(name, description, category, apps, layout, tags)


def create_template_from_snapshot(snapshot_id: str, name: str, description: str = "", category: str = "") -> str:
    return template_mgr.create_template_from_snapshot(snapshot_id, name, description, category)


def get_template(template_id: str) -> Optional[Dict]:
    return template_mgr.get_template(template_id)


def list_templates(category: str = None) -> List[Dict]:
    return template_mgr.list_templates(category)


def delete_template(template_id: str) -> bool:
    return template_mgr.delete_template(template_id)


def create_default_workspace_templates():
    create_default_templates()


if __name__ == "__main__":
    print("Workspace Reconstruction Agent loaded.")
    print("Functions:")
    print("  capture_workspace(name, description)")
    print("  auto_capture_workspace()")
    print("  get_snapshot(id)")
    print("  list_snapshots(limit)")
    print("  restore_workspace(snapshot_id)")
    print("  create_template(name, apps, layout)")
    print("  list_templates(category)")
    create_default_workspace_templates()