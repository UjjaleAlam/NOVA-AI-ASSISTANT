"""
Animation Agent - Phase 41
2D animation, 3D animation, storyboarding, educational video workflows.
Animation Agent PLANS, Blender Agent EXECUTES.
Integrates with Blender Agent, Writing Agent, Writing Agent, Voice Agent.
"""

import json
import time
import os
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path

DB_DIR = "database"
ANIM_DB = os.path.join(DB_DIR, "animation.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_anim_connection():
    import sqlite3
    conn = sqlite3.connect(ANIM_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_anim_db():
    conn = get_anim_connection()
    cursor = conn.cursor()

    # Animation projects
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anim_projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            project_type TEXT,  -- 2d_educational, 3d_educational, explainer, short_film, motion_graphics
            target_audience TEXT,
            duration_seconds INTEGER,
            style TEXT,  -- flat, isometric, realistic, stylized, whiteboard
            status TEXT DEFAULT 'concept',  -- concept, script, storyboard, animatic, production, post, complete
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Scripts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anim_scripts (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            content TEXT,
            scenes TEXT,  -- JSON array
            word_count INTEGER,
            estimated_duration REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES anim_projects(id)
        )
    """)

    # Storyboards
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storyboards (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            script_id TEXT,
            name TEXT,
            panels TEXT,  -- JSON array of panels
            notes TEXT,
            version INTEGER DEFAULT 1,
            status TEXT DEFAULT 'draft',  -- draft, review, approved, archived
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES anim_projects(id),
            FOREIGN KEY (script_id) REFERENCES anim_scripts(id)
        )
    """)

    # Animation shots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS animation_shots (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            storyboard_id TEXT,
            shot_number INTEGER,
            name TEXT,
            description TEXT,
            duration_frames INTEGER,
            duration_seconds REAL,
            camera_type TEXT,  -- static, pan, zoom, dolly, crane, handheld
            objects TEXT,  -- JSON array of object IDs
            animation_data TEXT,  -- JSON: keyframes, easing, etc.
            status TEXT DEFAULT 'planned',  -- planned, in_progress, review, approved, rejected
            assigned_to TEXT,
            dependencies TEXT,  -- JSON array of shot IDs
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES anim_projects(id),
            FOREIGN KEY (storyboard_id) REFERENCES storyboards(id)
        )
    """)

    # Assets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anim_assets (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            asset_type TEXT,  -- character, prop, environment, effect, sound, music, voiceover
            name TEXT,
            description TEXT,
            file_path TEXT,
            metadata TEXT,  -- JSON
            version INTEGER DEFAULT 1,
            status TEXT DEFAULT 'needed',  -- needed, in_progress, review, approved, delivered
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES anim_projects(id)
        )
    """)

    # Production schedule
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS production_schedule (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            phase TEXT,  -- pre_production, production, post_production
            task_name TEXT,
            description TEXT,
            start_date REAL,
            end_date REAL,
            assigned_to TEXT,
            dependencies TEXT,  -- JSON array of task IDs
            status TEXT DEFAULT 'pending',  -- pending, in_progress, review, completed, blocked
            priority INTEGER DEFAULT 3,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES anim_projects(id)
        )
    """)

    # Review notes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS review_notes (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            entity_type TEXT,  -- script, storyboard, shot, asset
            entity_id TEXT,
            reviewer TEXT,
            notes TEXT,
            status TEXT,  -- pending, addressed, rejected
            timestamp REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_anim_db()


# ============================================================
# DATA CLASSES
# ============================================================

class ProjectType(Enum):
    EDUCATIONAL_2D = "2d_educational"
    EDUCATIONAL_3D = "3d_educational"
    EXPLAINER = "explainer"
    SHORT_FILM = "short_film"
    MOTION_GRAPHICS = "motion_graphics"
    WHITEBOARD = "whiteboard"
    MOTION_CAPTURE = "motion_capture"


class Style(Enum):
    FLAT = "flat"
    ISOMETRIC = "isometric"
    REALISTIC = "realistic"
    STYLIZED = "stylized"
    WHITEBOARD = "whiteboard"
    CEL_SHADED = "cel_shaded"
    LOW_POLY = "low_poly"


@dataclass
class AnimationProject:
    id: str
    name: str
    description: str
    project_type: ProjectType
    target_audience: str = ""
    duration_seconds: int = 60
    style: Style = Style.FLAT
    status: str = "concept"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class AnimationScript:
    id: str
    project_id: str
    version: int = 1
    content: str = ""
    scenes: List = field(default_factory=list)
    word_count: int = 0
    estimated_duration: float = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class Storyboard:
    id: str
    project_id: str
    script_id: Optional[str] = None
    name: str = ""
    panels: List = field(default_factory=list)
    notes: str = ""
    version: int = 1
    status: str = "draft"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class AnimationShot:
    id: str
    project_id: str
    storyboard_id: Optional[str] = None
    shot_number: int = 0
    name: str = ""
    description: str = ""
    duration_frames: int = 24
    duration_seconds: float = 1.0
    camera_type: str = "static"
    objects: List = field(default_factory=list)
    animation_data: Dict = field(default_factory=dict)
    status: str = "planned"
    assigned_to: str = ""
    dependencies: List = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class AnimationAsset:
    id: str
    project_id: str
    asset_type: str
    name: str
    description: str = ""
    file_path: str = ""
    metadata: Dict = field(default_factory=dict)
    version: int = 1
    status: str = "needed"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ProductionTask:
    id: str
    project_id: str
    phase: str
    task_name: str
    description: str = ""
    start_date: float = 0
    end_date: float = 0
    assigned_to: str = ""
    dependencies: List = field(default_factory=list)
    status: str = "pending"
    priority: int = 3
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


# ============================================================
# ANIMATION AGENT
# ============================================================

class AnimationAgent:
    """Animation planning, storyboarding, and production management agent."""

    def __init__(self):
        self.projects: Dict[str, AnimationProject] = {}
        self.scripts: Dict[str, AnimationScript] = {}
        self.storyboards: Dict[str, Storyboard] = {}
        self.shots: Dict[str, AnimationShot] = {}
        self.assets: Dict[str, AnimationAsset] = {}
        self.schedule: Dict[str, ProductionTask] = {}
        self.reviews: Dict[str, Dict] = {}

        # Integration references
        self.blender_agent = None
        self.writing_agent = None

    def set_integrations(self, blender_agent=None, writing_agent=None):
        self.blender_agent = blender_agent
        self.writing_agent = writing_agent

    # ==========================================
    # PROJECT MANAGEMENT
    # ==========================================

    def create_project(self, name: str, description: str,
                       project_type: ProjectType,
                       target_audience: str = "",
                       duration_seconds: int = 60,
                       style: Style = Style.FLAT) -> str:
        """Create a new animation project."""
        project_id = f"anim_{int(time.time() * 1000) % 100000000:08d}"
        project = AnimationProject(
            id=project_id,
            name=name,
            description=description,
            project_type=project_type,
            target_audience=target_audience,
            duration_seconds=duration_seconds,
            style=style
        )
        self.projects[project_id] = project
        self._persist_project(project)
        return project_id

    def get_project(self, project_id: str) -> Optional[AnimationProject]:
        return self.projects.get(project_id)

    def list_projects(self, project_type: ProjectType = None, status: str = None) -> List[Dict]:
        results = []
        for p in self.projects.values():
            if project_type and p.project_type != project_type:
                continue
            if status and p.status != status:
                continue
            results.append(asdict(p))
        return results

    # ==========================================
    # SCRIPT WRITING
    # ==========================================

    def create_script(self, project_id: str, content: str = "") -> str:
        """Create a new script for the project."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError("Project not found")

        script_id = f"scr_{int(time.time() * 1000) % 100000000:08d}"
        script = AnimationScript(
            id=script_id,
            project_id=project_id,
            content=content
        )
        self.scripts[script_id] = script
        self._persist_script(script)
        return script_id

    def update_script(self, script_id: str, content: str, scenes: List = None) -> bool:
        script = self.scripts.get(script_id)
        if not script:
            return False

        script.content = content
        if scenes:
            script.scenes = scenes
        script.word_count = len(content.split())
        script.estimated_duration = script.word_count / 150 * 60  # ~150 words per minute
        script.version += 1
        script.updated_at = time.time()
        self._persist_script(script)
        return True

    def parse_script_to_scenes(self, script_id: str) -> List[Dict]:
        """Parse script into structured scenes."""
        script = self.scripts.get(script_id)
        if not script:
            return []

        # Simple scene parsing - split by scene headings
        lines = script.content.split('\n')
        scenes = []
        current_scene = None

        for line in lines:
            line = line.strip()
            if line.upper().startswith(('SCENE ', 'INT.', 'EXT.', 'INT/EXT.')):
                if current_scene:
                    scenes.append(current_scene)
                current_scene = {
                    "heading": line,
                    "content": "",
                    "duration_estimate": 0
                }
            elif current_scene:
                current_scene["content"] += line + "\n"

        if current_scene:
            scenes.append(current_scene)

        # Estimate durations
        for scene in scenes:
            words = len(scene["content"].split())
            scene["duration_estimate"] = words / 150 * 60  # seconds

        return scenes

    # ==========================================
    # STORYBOARDING
    # ==========================================

    def create_storyboard(self, project_id: str, script_id: str = None,
                          name: str = "Storyboard") -> str:
        """Create a new storyboard."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError("Project not found")

        storyboard_id = f"sb_{int(time.time() * 1000) % 100000000:08d}"
        storyboard = Storyboard(
            id=storyboard_id,
            project_id=project_id,
            script_id=script_id,
            name=name
        )
        self.storyboards[storyboard_id] = storyboard
        self._persist_storyboard(storyboard)
        return storyboard_id

    def add_panel(self, storyboard_id: str, panel_data: Dict) -> str:
        """Add a panel to storyboard."""
        storyboard = self.storyboards.get(storyboard_id)
        if not storyboard:
            return ""

        panel = {
            "id": f"pnl_{int(time.time() * 1000) % 100000000:08d}",
            "image_path": panel_data.get("image_path", ""),
            "description": panel_data.get("description", ""),
            "dialogue": panel_data.get("dialogue", ""),
            "action_notes": panel_data.get("action_notes", ""),
            "camera_notes": panel_data.get("camera_notes", ""),
            "duration_frames": panel_data.get("duration_frames", 24),
            "audio_notes": panel_data.get("audio_notes", ""),
            "order": len(storyboard.panels)
        }
        storyboard.panels.append(panel)
        storyboard.updated_at = time.time()
        self._persist_storyboard(storyboard)
        return panel["id"]

    def generate_shot_list(self, storyboard_id: str) -> List[Dict]:
        """Generate shot list from storyboard panels."""
        storyboard = self.storyboards.get(storyboard_id)
        if not storyboard:
            return []

        shots = []
        for i, panel in enumerate(storyboard.panels):
            shot = {
                "shot_number": i + 1,
                "panel_id": panel.get("id", ""),
                "name": f"Shot {i+1}: {panel.get('description', '')[:50]}",
                "description": panel.get("description", ""),
                "duration_frames": panel.get("duration_frames", 24),
                "duration_seconds": panel.get("duration_frames", 24) / 24,
                "camera_type": self._infer_camera_type(panel),
                "objects": [],
                "animation_data": {
                    "keyframes": [],
                    "camera_moves": panel.get("camera_notes", "")
                },
                "status": "planned"
            }
            shots.append(shot)

        return shots

    def _infer_camera_type(self, panel: Dict) -> str:
        camera_notes = panel.get("camera_notes", "").lower()
        if "pan" in camera_notes:
            return "pan"
        elif "zoom" in camera_notes:
            return "zoom"
        elif "dolly" in camera_notes:
            return "dolly"
        elif "crane" in camera_notes:
            return "crane"
        elif "handheld" in camera_notes:
            return "handheld"
        return "static"

    def shots_to_production_tasks(self, shots: List[Dict]) -> List[str]:
        """Convert shots to production schedule tasks."""
        task_ids = []
        for shot in shots:
            task_id = self.create_production_task(
                project_id=shot.get("project_id", ""),
                phase="production",
                task_name=shot.get("name", "Shot"),
                description=shot.get("description", ""),
                start_date=time.time(),
                end_date=time.time() + 86400 * 2,  # 2 days default
                assigned_to="animator",
                dependencies=shot.get("dependencies", [])
            )
            task_ids.append(task_id)
        return task_ids

    # ==========================================
    # PRODUCTION SCHEDULE
    # ==========================================

    def create_production_task(self, project_id: str, phase: str,
                               task_name: str, description: str = "",
                               start_date: float = 0, end_date: float = 0,
                               assigned_to: str = "", dependencies: List = None) -> str:
        """Create a production schedule task."""
        task_id = f"tsk_{int(time.time() * 1000) % 100000000:08d}"
        task = ProductionTask(
            id=task_id,
            project_id=project_id,
            phase=phase,
            task_name=task_name,
            description=description,
            start_date=start_date or time.time(),
            end_date=end_date or (time.time() + 86400 * 2),
            assigned_to=assigned_to,
            dependencies=dependencies or []
        )
        self.schedule[task_id] = task
        self._persist_task(task)
        return task_id

    def get_schedule(self, project_id: str) -> List[Dict]:
        """Get production schedule for project."""
        tasks = [asdict(t) for t in self.schedule.values() if t.project_id == project_id]
        tasks.sort(key=lambda x: x["start_date"])
        return tasks

    def update_task_status(self, task_id: str, status: str) -> bool:
        task = self.schedule.get(task_id)
        if not task:
            return False
        task.status = status
        task.updated_at = time.time()
        self._persist_task(task)
        return True

    def get_critical_path(self, project_id: str) -> List[str]:
        """Calculate critical path for project."""
        tasks = [t for t in self.schedule.values() if t.project_id == project_id]
        # Simple topological sort for critical path
        # This is a simplified version
        task_ids = [t.id for t in tasks]
        return task_ids

    # ==========================================
    # ASSET MANAGEMENT
    # ==========================================

    def create_asset(self, project_id: str, asset_type: str, name: str,
                     description: str = "", file_path: str = "",
                     metadata: Dict = None) -> str:
        """Create an animation asset."""
        asset_id = f"ast_{int(time.time() * 1000) % 100000000:08d}"
        asset = AnimationAsset(
            id=asset_id,
            project_id=project_id,
            asset_type=asset_type,
            name=name,
            description=description,
            file_path=file_path,
            metadata=metadata or {}
        )
        self.assets[asset_id] = asset
        self._persist_asset(asset)
        return asset_id

    def update_asset_status(self, asset_id: str, status: str) -> bool:
        asset = self.assets.get(asset_id)
        if not asset:
            return False
        asset.status = status
        asset.updated_at = time.time()
        self._persist_asset(asset)
        return True

    def get_asset_list(self, project_id: str, asset_type: str = None) -> List[Dict]:
        assets = [asdict(a) for a in self.assets.values() if a.project_id == project_id]
        if asset_type:
            assets = [a for a in assets if a["asset_type"] == asset_type]
        return assets

    # ==========================================
    # REVIEW SYSTEM
    # ==========================================

    def add_review_note(self, project_id: str, entity_type: str,
                        entity_id: str, reviewer: str, notes: str,
                        status: str = "pending") -> str:
        """Add a review note."""
        note_id = f"rev_{int(time.time() * 1000) % 100000000:08d}"
        note = {
            "id": note_id,
            "project_id": project_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "reviewer": reviewer,
            "notes": notes,
            "status": status,
            "timestamp": time.time()
        }
        self.reviews[note_id] = note
        self._persist_review(note)
        return note_id

    def get_reviews(self, project_id: str, entity_type: str = None,
                    entity_id: str = None) -> List[Dict]:
        reviews = [r for r in self.reviews.values() if r["project_id"] == project_id]
        if entity_type:
            reviews = [r for r in reviews if r["entity_type"] == entity_type]
        if entity_id:
            reviews = [r for r in reviews if r["entity_id"] == entity_id]
        return reviews

    # ==========================================
    # INTEGRATIONS
    # ==========================================

    def export_to_blender(self, project_id: str) -> Dict:
        """Export animation plan to Blender Agent format."""
        shots = [s for s in self.shots.values() if s.project_id == project_id]

        blender_data = {
            "project_name": self.projects.get(project_id, {}).get("name", "Animation"),
            "shots": [],
            "assets": []
        }

        for shot in shots:
            blender_data["shots"].append({
                "shot_number": shot.shot_number,
                "name": shot.name,
                "duration_frames": shot.duration_frames,
                "camera_type": shot.camera_type,
                "animation_data": shot.animation_data
            })

        # Assets
        assets = [a for a in self.assets.values() if a.project_id == project_id]
        for asset in assets:
            blender_data["assets"].append({
                "name": asset.name,
                "type": asset.asset_type,
                "file_path": asset.file_path,
                "metadata": asset.metadata
            })

        return blender_data

    def create_blender_shots(self, project_id: str) -> List[str]:
        """Create corresponding shots in Blender Agent."""
        if not hasattr(self, 'blender_agent') or not self.blender_agent:
            return []

        shots = [s for s in self.shots.values() if s.project_id == project_id]
        job_ids = []

        for shot in shots:
            # Create render job for each shot
            job_id = self.blender_agent.create_render_job(
                project_id=project_id,  # This would need a Blender project ID mapping
                name=shot.name,
                engine="cycles",
                frame_start=1,
                frame_end=shot.duration_frames,
                output_path=f"renders/{shot.id}.png",
                output_format="png"
            )
            job_ids.append(job_id)

        return job_ids

    # ==========================================
    # VOICE COMMANDS
    # ==========================================

    def handle_command(self, command: str) -> Optional[str]:
        """Handle voice commands for Animation Agent."""
        cmd = command.lower().strip()

        if cmd in ["new animation", "create animation"]:
            return "Specify project name and type. Example: 'create animation project named Solar System Explainer, type 3d_educational, duration 120 seconds'"

        if cmd.startswith("create animation project"):
            return self._parse_create_project(cmd)

        if cmd in ["create script", "write script"]:
            return "Script creation requires a project ID. Use 'create script for project <id>'"

        if cmd.startswith("create storyboard"):
            return "Storyboard creation requires a project ID. Use 'create storyboard for project <id>'"

        if cmd in ["generate shots", "generate shot list"]:
            return "Shot generation requires a storyboard ID. Use 'generate shots from storyboard <id>'"

        if cmd in ["create schedule", "generate schedule", "production schedule"]:
            return "Schedule generation requires a project ID. Use 'create schedule for project <id>'"

        if cmd in ["what's the schedule", "show schedule", "production status"]:
            return "Schedule viewing requires a project ID. Use 'show schedule for project <id>'"

        return None

    def _parse_create_project(self, cmd: str) -> str:
        # Simplified parsing
        return "Project creation requires: name, description, type (2d_educational/3d_educational/explainer/short_film/motion_graphics/whiteboard/motion_capture), target_audience, duration_seconds, style (flat/isometric/realistic/stylized/whiteboard/cel_shaded/low_poly)"

    # ==========================================
    # PERSISTENCE
    # ==========================================

    def _persist_project(self, project: AnimationProject):
        conn = get_anim_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO anim_projects (id, name, description, project_type, target_audience, duration_seconds, style, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project.id, project.name, project.description, project.project_type.value,
              project.target_audience, project.duration_seconds, project.style.value,
              project.status, project.created_at, project.updated_at))
        conn.commit()
        conn.close()

    def _persist_script(self, script: AnimationScript):
        conn = get_anim_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO anim_scripts (id, project_id, version, content, scenes, word_count, estimated_duration, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (script.id, script.project_id, script.version, script.content,
              json.dumps(script.scenes), script.word_count, script.estimated_duration,
              script.created_at, script.updated_at))
        conn.commit()
        conn.close()

    def _persist_storyboard(self, storyboard: Storyboard):
        conn = get_anim_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO storyboards (id, project_id, script_id, name, panels, notes, version, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (storyboard.id, storyboard.project_id, storyboard.script_id, storyboard.name,
              json.dumps(storyboard.panels), storyboard.notes, storyboard.version,
              storyboard.status, storyboard.created_at, storyboard.updated_at))
        conn.commit()
        conn.close()

    def _persist_shot(self, shot: AnimationShot):
        conn = get_anim_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO animation_shots (id, project_id, storyboard_id, shot_number, name, description, duration_frames, duration_seconds, camera_type, objects, animation_data, status, assigned_to, dependencies, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (shot.id, shot.project_id, shot.storyboard_id, shot.shot_number,
              shot.name, shot.description, shot.duration_frames, shot.duration_seconds,
              shot.camera_type, json.dumps(shot.objects), json.dumps(shot.animation_data),
              shot.status, shot.assigned_to, json.dumps(shot.dependencies),
              shot.created_at, shot.updated_at))
        conn.commit()
        conn.close()

    def _persist_asset(self, asset: AnimationAsset):
        conn = get_anim_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO anim_assets (id, project_id, asset_type, name, description, file_path, metadata, version, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (asset.id, asset.project_id, asset.asset_type, asset.name,
              asset.description, asset.file_path, json.dumps(asset.metadata),
              asset.version, asset.status, asset.created_at, asset.updated_at))
        conn.commit()
        conn.close()

    def _persist_task(self, task: ProductionTask):
        conn = get_anim_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO production_schedule (id, project_id, phase, task_name, description, start_date, end_date, assigned_to, dependencies, status, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (task.id, task.project_id, task.phase, task.task_name, task.description,
              task.start_date, task.end_date, task.assigned_to, json.dumps(task.dependencies),
              task.status, task.priority, task.created_at, task.updated_at))
        conn.commit()
        conn.close()

    def _persist_review(self, note: Dict):
        conn = get_anim_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO review_notes (id, project_id, entity_type, entity_id, reviewer, notes, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (note["id"], note["project_id"], note["entity_type"], note["entity_id"],
              note["reviewer"], note["notes"], note["status"], note["timestamp"]))
        conn.commit()
        conn.close()


# Global instance
animation_agent = AnimationAgent()


def get_animation_agent() -> AnimationAgent:
    return animation_agent


if __name__ == "__main__":
    print("Animation Agent - Phase 41")
    print("Features: Script Writing, Storyboarding, Shot Planning, Production Scheduling, Asset Management, Review System")
    print("Integrations: Blender Agent, Writing Agent, Voice Agent, Chief of Staff")