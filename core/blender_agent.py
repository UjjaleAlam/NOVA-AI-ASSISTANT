"""
Blender Agent - Phase 40
3D modeling, scene creation, editing, rendering, design analysis.
Integrates with Engineering Agent, Coding Agent, Vision Agent.
"""

import json
import time
import os
import subprocess
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path

DB_DIR = "database"
BLENDER_DB = os.path.join(DB_DIR, "blender.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_blender_connection():
    import sqlite3
    conn = sqlite3.connect(BLENDER_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_blender_db():
    conn = get_blender_connection()
    cursor = conn.cursor()

    # Blender projects
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blender_projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            blend_file TEXT,  -- path to .blend file
            status TEXT DEFAULT 'new',  -- new, modeling, rigging, animating, rendering, complete
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Objects in scene
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blender_objects (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            object_type TEXT,  -- mesh, curve, camera, light, empty, armature
            location TEXT,  -- JSON: x, y, z
            rotation TEXT,  -- JSON: x, y, z
            scale TEXT,  -- JSON: x, y, z
            mesh_data TEXT,  -- JSON: vertices, faces, uvs
            material TEXT,  -- JSON
            modifiers TEXT,  -- JSON array
            parent_id TEXT,
            visible BOOLEAN DEFAULT 1,
            selectable BOOLEAN DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES blender_projects(id)
        )
    """)

    # Materials
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blender_materials (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            material_type TEXT,  -- principled, glass, metal, emission, toon
            properties TEXT,  -- JSON: color, roughness, metallic, etc.
            node_tree TEXT,  -- JSON: shader nodes
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES blender_projects(id)
        )
    """)

    # Animations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blender_animations (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            action_type TEXT,  -- object, shape_key, bone, camera
            target_object_id TEXT,
            frame_start INTEGER DEFAULT 1,
            frame_end INTEGER DEFAULT 250,
            fps INTEGER DEFAULT 24,
            keyframes TEXT,  -- JSON
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES blender_projects(id),
            FOREIGN KEY (target_object_id) REFERENCES blender_objects(id)
        )
    """)

    # Render jobs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS render_jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT,
            engine TEXT,  -- cycles, eevee, workbench
            resolution_x INTEGER DEFAULT 1920,
            resolution_y INTEGER DEFAULT 1080,
            samples INTEGER DEFAULT 128,
            frame_start INTEGER DEFAULT 1,
            frame_end INTEGER DEFAULT 250,
            output_path TEXT,
            output_format TEXT,  -- png, jpeg, exr, mp4, gif
            status TEXT DEFAULT 'pending',  -- pending, queued, rendering, completed, failed
            progress REAL DEFAULT 0,
            current_frame INTEGER,
            start_time REAL,
            end_time REAL,
            error TEXT,
            FOREIGN KEY (project_id) REFERENCES blender_projects(id)
        )
    """)

    # Python scripts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blender_scripts (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            script_text TEXT,
            description TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES blender_projects(id)
        )
    """)

    conn.commit()
    conn.close()


init_blender_db()


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class BlenderProject:
    id: str
    name: str
    description: str
    blend_file: Optional[str] = None
    status: str = "new"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class BlenderObject:
    id: str
    project_id: str
    name: str
    object_type: str = "mesh"
    location: Dict = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    rotation: Dict = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    scale: Dict = field(default_factory=lambda: {"x": 1, "y": 1, "z": 1})
    mesh_data: Dict = field(default_factory=dict)
    material: Dict = field(default_factory=dict)
    modifiers: List = field(default_factory=list)
    parent_id: Optional[str] = None
    visible: bool = True
    selectable: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class BlenderMaterial:
    id: str
    project_id: str
    name: str
    material_type: str = "principled"
    properties: Dict = field(default_factory=dict)
    node_tree: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class BlenderAnimation:
    id: str
    project_id: str
    name: str
    action_type: str = "object"
    target_object_id: Optional[str] = None
    frame_start: int = 1
    frame_end: int = 250
    fps: int = 24
    keyframes: List = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class RenderJob:
    id: str
    project_id: str
    name: str
    engine: str = "cycles"
    resolution_x: int = 1920
    resolution_y: int = 1080
    samples: int = 128
    frame_start: int = 1
    frame_end: int = 250
    output_path: str = ""
    output_format: str = "png"
    status: str = "pending"
    progress: float = 0
    current_frame: int = 0
    start_time: float = 0
    end_time: float = 0
    error: str = ""


# ============================================================
# BLENDER AGENT
# ============================================================

class BlenderAgent:
    """Blender 3D modeling, animation, and rendering agent."""

    def __init__(self):
        self.projects: Dict[str, BlenderProject] = {}
        self.objects: Dict[str, BlenderObject] = {}
        self.materials: Dict[str, BlenderMaterial] = {}
        self.animations: Dict[str, BlenderAnimation] = {}
        self.render_jobs: Dict[str, RenderJob] = {}
        self.scripts: Dict[str, Dict] = {}

        # Blender executable path
        self.blender_exe = self._find_blender()

    def _find_blender(self) -> Optional[str]:
        """Find Blender executable."""
        common_paths = [
            r"C:\Program Files\Blender Foundation\Blender\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
            "/usr/bin/blender",
            "/Applications/Blender.app/Contents/MacOS/Blender",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None

    # ==========================================
    # PROJECT MANAGEMENT
    # ==========================================

    def create_project(self, name: str, description: str = "") -> str:
        """Create a new Blender project."""
        project_id = f"blend_{int(time.time() * 1000) % 100000000:08d}"
        project = BlenderProject(
            id=project_id,
            name=name,
            description=description
        )
        self.projects[project_id] = project
        self._persist_project(project)
        return project_id

    def get_project(self, project_id: str) -> Optional[BlenderProject]:
        return self.projects.get(project_id)

    def load_project(self, project_id: str, blend_file: str = None) -> bool:
        """Load an existing .blend file."""
        project = self.projects.get(project_id)
        if not project:
            return False

        if blend_file and os.path.exists(blend_file):
            project.blend_file = blend_file
            project.status = "modeling"
            project.updated_at = time.time()
            self._persist_project(project)

            # Parse .blend file to populate objects
            self._parse_blend_file(project_id, blend_file)
            return True
        return False

    def _parse_blend_file(self, project_id: str, blend_file: str):
        """Parse .blend file using Blender's Python API."""
        script = f"""
import bpy
import json
import sys

data = {{
    "objects": [],
    "materials": []
}}

for obj in bpy.data.objects:
    obj_data = {{
        "name": obj.name,
        "type": obj.type,
        "location": [obj.location.x, obj.location.y, obj.location.z],
        "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
        "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
        "parent": obj.parent.name if obj.parent else None,
        "visible": obj.visible_get(),
        "selectable": not obj.hide_select
    }}
    if obj.type == 'MESH' and obj.data:
        mesh = obj.data
        obj_data["mesh_data"] = {{
            "vertices": len(mesh.vertices),
            "faces": len(mesh.polygons),
            "has_uv": len(mesh.uv_layers) > 0
        }}
    data["objects"].append(obj_data)

for mat in bpy.data.materials:
    mat_data = {{
        "name": mat.name,
        "type": "principled" if mat.use_nodes else "basic"
    }}
    if mat.use_nodes:
        nodes = []
        for node in mat.node_tree.nodes:
            nodes.append({{"type": node.type, "name": node.name}})
        mat_data["nodes"] = nodes
    data["materials"].append(mat_data)

print(json.dumps(data))
"""

        # Save script to temp file and run
        try:
            script_path = f"{project_id}_parse.py"
            with open(script_path, "w") as f:
                f.write(script)

            if self.blender_exe:
                result = subprocess.run([
                    self.blender_exe, "--background", "--python", script_path
                ], capture_output=True, text=True, timeout=60)

                if result.returncode == 0:
                    # Parse output
                    try:
                        data = json.loads(result.stdout.strip().split('\n')[-1])
                        for obj_data in data.get("objects", []):
                            self.add_object(project_id, obj_data)
                        for mat_data in data.get("materials", []):
                            self.add_material(project_id, mat_data)
                    except:
                        pass
        except:
            pass

    # ==========================================
    # OBJECT MANAGEMENT
    # ==========================================

    def add_object(self, project_id: str, obj_data: Dict) -> str:
        """Add object to scene."""
        obj_id = f"obj_{int(time.time() * 1000) % 100000000:08d}"
        obj = BlenderObject(
            id=obj_id,
            project_id=project_id,
            name=obj_data.get("name", "Object"),
            object_type=obj_data.get("type", "mesh"),
            location=obj_data.get("location", {"x": 0, "y": 0, "z": 0}),
            rotation=obj_data.get("rotation", {"x": 0, "y": 0, "z": 0}),
            scale=obj_data.get("scale", {"x": 1, "y": 1, "z": 1}),
            mesh_data=obj_data.get("mesh_data", {}),
            material=obj_data.get("material", {}),
            parent_id=obj_data.get("parent"),
            visible=obj_data.get("visible", True),
            selectable=obj_data.get("selectable", True)
        )
        self.objects[obj_id] = obj
        self._persist_object(obj)
        return obj_id

    def get_object(self, obj_id: str) -> Optional[BlenderObject]:
        return self.objects.get(obj_id)

    def update_object(self, obj_id: str, **kwargs) -> bool:
        obj = self.objects.get(obj_id)
        if not obj:
            return False

        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        obj.updated_at = time.time()
        self._persist_object(obj)
        return True

    def delete_object(self, obj_id: str) -> bool:
        if obj_id in self.objects:
            del self.objects[obj_id]
            conn = get_blender_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM blender_objects WHERE id = ?", (obj_id,))
            conn.commit()
            conn.close()
            return True
        return False

    # ==========================================
    # MATERIALS
    # ==========================================

    def add_material(self, project_id: str, mat_data: Dict) -> str:
        mat_id = f"mat_{int(time.time() * 1000) % 100000000:08d}"
        material = BlenderMaterial(
            id=mat_id,
            project_id=project_id,
            name=mat_data.get("name", "Material"),
            material_type=mat_data.get("type", "principled"),
            properties=mat_data.get("properties", {}),
            node_tree=mat_data.get("node_tree", {})
        )
        self.materials[mat_id] = material
        self._persist_material(material)
        return mat_id

    def create_principled_material(self, project_id: str, name: str,
                                   base_color: List[float] = None,
                                   metallic: float = 0.0,
                                   roughness: float = 0.5,
                                   **kwargs) -> str:
        """Create a principled BSDF material."""
        mat_id = f"mat_{int(time.time() * 1000) % 100000000:08d}"
        props = {
            "base_color": base_color or [0.8, 0.8, 0.8, 1.0],
            "metallic": metallic,
            "roughness": roughness,
            **kwargs
        }

        mat_data = {
            "name": name,
            "type": "principled",
            "properties": props
        }
        return self.add_material(project_id, mat_data)

    def assign_material(self, obj_id: str, mat_id: str) -> bool:
        obj = self.objects.get(obj_id)
        mat = self.materials.get(mat_id)
        if not obj or not mat:
            return False
        obj.material = {"id": mat_id, "name": mat.name}
        obj.updated_at = time.time()
        self._persist_object(obj)
        return True

    # ==========================================
    # ANIMATION
    # ==========================================

    def create_animation(self, project_id: str, name: str,
                         action_type: str = "object",
                         target_object_id: str = None,
                         frame_start: int = 1,
                         frame_end: int = 250,
                         fps: int = 24) -> str:
        """Create a new animation."""
        anim_id = f"anim_{int(time.time() * 1000) % 100000000:08d}"
        animation = BlenderAnimation(
            id=anim_id,
            project_id=project_id,
            name=name,
            action_type=action_type,
            target_object_id=target_object_id,
            frame_start=frame_start,
            frame_end=frame_end,
            fps=fps
        )
        self.animations[anim_id] = animation
        self._persist_animation(animation)
        return anim_id

    def add_keyframe(self, anim_id: str, frame: int, data: Dict) -> bool:
        anim = self.animations.get(anim_id)
        if not anim:
            return False

        keyframe = {"frame": frame, "data": data}
        anim.keyframes.append(keyframe)
        anim.updated_at = time.time()
        self._persist_animation(anim)
        return True

    def add_location_keyframe(self, anim_id: str, obj_id: str,
                              frame: int, location: List[float]) -> bool:
        """Add location keyframe for object."""
        return self.add_keyframe(anim_id, frame, {
            "object_id": obj_id,
            "property": "location",
            "value": location
        })

    def add_rotation_keyframe(self, anim_id: str, obj_id: str,
                              frame: int, rotation: List[float]) -> bool:
        """Add rotation keyframe for object."""
        return self.add_keyframe(anim_id, frame, {
            "object_id": obj_id,
            "property": "rotation_euler",
            "value": rotation
        })

    def add_scale_keyframe(self, anim_id: str, obj_id: str,
                           frame: int, scale: List[float]) -> bool:
        """Add scale keyframe for object."""
        return self.add_keyframe(anim_id, frame, {
            "object_id": obj_id,
            "property": "scale",
            "value": scale
        })

    # ==========================================
    # RENDERING
    # ==========================================

    def create_render_job(self, project_id: str, name: str,
                          engine: str = "cycles",
                          resolution_x: int = 1920,
                          resolution_y: int = 1080,
                          samples: int = 128,
                          frame_start: int = 1,
                          frame_end: int = 250,
                          output_path: str = "",
                          output_format: str = "png") -> str:
        """Create a render job."""
        job_id = f"render_{int(time.time() * 1000) % 100000000:08d}"
        job = RenderJob(
            id=job_id,
            project_id=project_id,
            name=name,
            engine=engine,
            resolution_x=resolution_x,
            resolution_y=resolution_y,
            samples=samples,
            frame_start=frame_start,
            frame_end=frame_end,
            output_path=output_path or f"renders/{project_id}/{name}",
            output_format=output_format
        )
        self.render_jobs[job_id] = job
        self._persist_render_job(job)
        return job_id

    def start_render(self, job_id: str) -> bool:
        """Start a render job."""
        job = self.render_jobs.get(job_id)
        if not job or not self.blender_exe:
            return False

        job.status = "rendering"
        job.start_time = time.time()
        job.progress = 0
        self._persist_render_job(job)

        thread = threading.Thread(target=self._render_async, args=(job_id,))
        thread.start()
        return True

    def _render_async(self, job_id: str):
        """Render in background using Blender."""
        job = self.render_jobs[job_id]
        project = self.projects.get(job.project_id)

        if not project or not project.blend_file:
            job.status = "failed"
            job.error = "No .blend file loaded"
            job.end_time = time.time()
            self._persist_render_job(job)
            return

        # Create render script
        script = f"""
import bpy
import os

scene = bpy.context.scene
scene.render.engine = '{job.engine}'
scene.render.resolution_x = {job.resolution_x}
scene.render.resolution_y = {job.resolution_y}
scene.render.resolution_percentage = 100

if job.engine == 'CYCLES':
    scene.cycles.samples = {job.samples}
    scene.cycles.use_denoising = True

scene.frame_start = {job.frame_start}
scene.frame_end = {job.frame_end}

output_path = '{job.output_path}'
os.makedirs(os.path.dirname(output_path), exist_ok=True)

if job.frame_end > job.frame_start:
    bpy.ops.render.render(animation=True, write_still=True)
else:
    bpy.ops.render.render(write_still=True)

print('RENDER_COMPLETE')
"""

        try:
            script_path = f"render_{job.id}.py"
            with open(script_path, "w") as f:
                f.write(script)

            os.makedirs(os.path.dirname(job.output_path), exist_ok=True)

            result = subprocess.run([
                self.blender_exe, "--background", project.blend_file,
                "--python", script_path
            ], capture_output=True, text=True, timeout=3600)

            if result.returncode == 0:
                job.status = "completed"
                job.progress = 1.0
            else:
                job.status = "failed"
                job.error = result.stderr[:500]

        except subprocess.TimeoutExpired:
            job.status = "failed"
            job.error = "Render timeout"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)

        job.end_time = time.time()
        job.progress = 1.0 if job.status == "completed" else job.progress
        self._persist_render_job(job)

    def get_render_status(self, job_id: str) -> Optional[Dict]:
        job = self.render_jobs.get(job_id)
        if not job:
            return None
        return asdict(job)

    # ==========================================
    # PYTHON SCRIPTING
    # ==========================================

    def add_script(self, project_id: str, name: str, script: str, description: str = "") -> str:
        """Add a Python script for Blender."""
        script_id = f"scr_{int(time.time() * 1000) % 100000000:08d}"
        self.scripts[script_id] = {
            "id": script_id,
            "project_id": project_id,
            "name": name,
            "script": script,
            "description": description,
            "created_at": time.time(),
            "updated_at": time.time()
        }
        self._persist_script(script_id, project_id, name, script, description)
        return script_id

    def run_script(self, project_id: str, script_id: str) -> Dict:
        """Run a Blender Python script."""
        script_data = self.scripts.get(script_id)
        if not script_data:
            return {"error": "Script not found"}

        if not self.blender_exe:
            return {"error": "Blender not found"}

        project = self.projects.get(project_id)
        if not project or not project.blend_file:
            return {"error": "No .blend file loaded"}

        script_path = f"script_{script_id}.py"
        with open(script_path, "w") as f:
            f.write(script_data["script"])

        try:
            result = subprocess.run([
                self.blender_exe, "--background", project.blend_file,
                "--python", script_path
            ], capture_output=True, text=True, timeout=300)

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "Script timeout"}
        except Exception as e:
            return {"error": str(e)}

    # ==========================================
    # SCENE ANALYSIS
    # ============================================

    def analyze_scene(self, project_id: str) -> Dict:
        """Analyze scene for optimization suggestions."""
        objects = [o for o in self.objects.values() if o.project_id == project_id]

        stats = {
            "total_objects": len(objects),
            "by_type": {},
            "total_vertices": 0,
            "total_faces": 0,
            "materials": len([m for m in self.materials.values() if m.project_id == project_id]),
            "animations": len([a for a in self.animations.values() if a.project_id == project_id]),
            "issues": [],
            "suggestions": []
        }

        for obj in objects:
            obj_type = obj.object_type
            stats["by_type"][obj_type] = stats["by_type"].get(obj_type, 0) + 1

            if obj.mesh_data:
                stats["total_vertices"] += obj.mesh_data.get("vertices", 0)
                stats["total_faces"] += obj.mesh_data.get("faces", 0)

            # Check for issues
            if obj.mesh_data and obj.mesh_data.get("faces", 0) > 100000:
                stats["issues"].append(f"High poly count: {obj.name} ({obj.mesh_data.get('faces', 0)} faces)")
                stats["suggestions"].append(f"Consider decimation for {obj.name}")

            if obj.mesh_data and not obj.mesh_data.get("has_uv", False):
                stats["issues"].append(f"Missing UVs: {obj.name}")
                stats["suggestions"].append(f"Add UV unwrapping for {obj.name}")

        return stats

    def generate_scene_report(self, project_id: str) -> str:
        """Generate text report of scene."""
        stats = self.analyze_scene(project_id)
        project = self.projects.get(project_id)

        report = f"Blender Scene Report: {project.name if project else 'Unknown'}\n"
        report += "=" * 50 + "\n\n"
        report += f"Objects: {stats['total_objects']}\n"
        report += f"  Vertices: {stats['total_vertices']:,}\n"
        report += f"  Faces: {stats['total_faces']:,}\n"
        report += f"Materials: {stats['materials']}\n"
        report += f"Animations: {stats['animations']}\n\n"

        report += "By Type:\n"
        for typ, count in stats["by_type"].items():
            report += f"  {typ}: {count}\n"

        if stats["issues"]:
            report += "\nIssues Found:\n"
            for issue in stats["issues"]:
                report += f"  - {issue}\n"

        if stats["suggestions"]:
            report += "\nSuggestions:\n"
            for sug in stats["suggestions"]:
                report += f"  - {sug}\n"

        return report

    # ==========================================
    # PERSISTENCE
    # ============================================

    def _persist_project(self, project: BlenderProject):
        conn = get_blender_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO blender_projects (id, name, description, blend_file, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (project.id, project.name, project.description, project.blend_file,
              project.status, project.created_at, project.updated_at))
        conn.commit()
        conn.close()

    def _persist_object(self, obj: BlenderObject):
        conn = get_blender_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO blender_objects (id, project_id, name, object_type, location, rotation, scale, mesh_data, material, modifiers, parent_id, visible, selectable, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (obj.id, obj.project_id, obj.name, obj.object_type,
              json.dumps(obj.location), json.dumps(obj.rotation), json.dumps(obj.scale),
              json.dumps(obj.mesh_data), json.dumps(obj.material), json.dumps(obj.modifiers),
              obj.parent_id, obj.visible, obj.selectable, obj.created_at, obj.updated_at))
        conn.commit()
        conn.close()

    def _persist_material(self, mat: BlenderMaterial):
        conn = get_blender_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO blender_materials (id, project_id, name, material_type, properties, node_tree, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (mat.id, mat.project_id, mat.name, mat.material_type,
              json.dumps(mat.properties), json.dumps(mat.node_tree),
              mat.created_at, mat.updated_at))
        conn.commit()
        conn.close()

    def _persist_animation(self, anim: BlenderAnimation):
        conn = get_blender_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO blender_animations (id, project_id, name, action_type, target_object_id, frame_start, frame_end, fps, keyframes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (anim.id, anim.project_id, anim.name, anim.action_type,
              anim.target_object_id, anim.frame_start, anim.frame_end, anim.fps,
              json.dumps(anim.keyframes), anim.created_at, anim.updated_at))
        conn.commit()
        conn.close()

    def _persist_render_job(self, job: RenderJob):
        conn = get_blender_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO render_jobs (id, project_id, name, engine, resolution_x, resolution_y, samples, frame_start, frame_end, output_path, output_format, status, progress, current_frame, start_time, end_time, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job.id, job.project_id, job.name, job.engine, job.resolution_x,
              job.resolution_y, job.samples, job.frame_start, job.frame_end,
              job.output_path, job.output_format, job.status, job.progress,
              job.current_frame, job.start_time, job.end_time, job.error))
        conn.commit()
        conn.close()

    def _persist_script(self, script_id: str, project_id: str, name: str, script: str, description: str):
        conn = get_blender_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO blender_scripts (id, project_id, name, script_text, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (script_id, project_id, name, script, description, time.time(), time.time()))
        conn.commit()
        conn.close()


# Global instance
blender_agent = BlenderAgent()


def get_blender_agent() -> BlenderAgent:
    return blender_agent


if __name__ == "__main__":
    print("Blender Agent - Phase 40")
    print("Features: 3D Modeling, Scene Creation, Animation, Rendering (Cycles/Eevee), Python Scripting, Scene Analysis")
    print("Integrations: Engineering Agent, Coding Agent, Vision Agent")