"""
Project Awareness - Phase 19
Git integration, project structure analysis, dependency tracking, health monitoring.
Fully local, no cloud dependencies.
"""

import os
import json
import re
import subprocess
import time
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict, field
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
import threading

from core.context_engine import get_connection, get_current_session


DB_DIR = "database"
PROJECT_DB = os.path.join(DB_DIR, "project_awareness.db")

os.makedirs(DB_DIR, exist_ok=True)


def init_project_awareness_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Project registry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            path TEXT UNIQUE NOT NULL,
            name TEXT,
            description TEXT,
            language TEXT,
            framework TEXT,
            git_remote TEXT,
            created_at REAL NOT NULL,
            last_accessed REAL NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    """)

    # File tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            extension TEXT,
            size INTEGER,
            lines INTEGER,
            language TEXT,
            last_modified REAL,
            git_status TEXT,  -- 'clean', 'modified', 'untracked', 'staged'
            hash TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Git commits
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS git_commits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            commit_hash TEXT NOT NULL,
            short_hash TEXT,
            author TEXT,
            email TEXT,
            message TEXT,
            timestamp REAL NOT NULL,
            files_changed INTEGER,
            insertions INTEGER,
            deletions INTEGER,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Dependencies
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            version TEXT,
            type TEXT,  -- 'npm', 'pip', 'cargo', 'maven', 'gradle', 'go', 'composer', 'nuget'
            is_dev BOOLEAN DEFAULT 0,
            is_outdated BOOLEAN DEFAULT 0,
            latest_version TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Project health metrics
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            metric_type TEXT NOT NULL,  -- 'complexity', 'test_coverage', 'duplication', 'security', 'maintainability'
            value REAL NOT NULL,
            threshold REAL,
            status TEXT,  -- 'good', 'warning', 'critical'
            details TEXT,  -- JSON
            measured_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Project activity log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            event_type TEXT NOT NULL,  -- 'file_change', 'commit', 'build', 'test', 'deploy', 'dependency_change'
            description TEXT,
            metadata TEXT,  -- JSON
            timestamp REAL NOT NULL
        )
    """)

    # TODO/Tasks from code
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS code_todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            line_number INTEGER,
            tag TEXT,  -- 'TODO', 'FIXME', 'HACK', 'NOTE', 'BUG', 'OPTIMIZE'
            content TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    conn.commit()
    conn.close()


init_project_awareness_db()


@dataclass
class Project:
    id: str
    path: str
    name: str
    description: str = ""
    language: str = ""
    framework: str = ""
    git_remote: str = ""
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    is_active: bool = True


@dataclass
class GitCommit:
    commit_hash: str
    short_hash: str
    author: str
    email: str
    message: str
    timestamp: float
    files_changed: int
    insertions: int
    deletions: int


@dataclass
class Dependency:
    name: str
    version: str
    type: str
    is_dev: bool = False
    is_outdated: bool = False
    latest_version: str = ""


class GitAnalyzer:
    """Analyze Git repositories."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        self.is_repo = self._check_repo()

    def _check_repo(self) -> bool:
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                check=True
            )
            return True
        except Exception:
            return False

    def get_remote_url(self) -> str:
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def get_current_branch(self) -> str:
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def get_status(self) -> Dict[str, List[str]]:
        """Get git status: modified, staged, untracked files."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            status = {"modified": [], "staged": [], "untracked": [], "deleted": []}
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                status_code = line[:2]
                filepath = line[3:]
                if status_code[1] == "M":
                    status["modified"].append(filepath)
                if status_code[0] == "M":
                    status["staged"].append(filepath)
                if status_code[0] == "A":
                    status["staged"].append(filepath)
                if status_code == "??":
                    status["untracked"].append(filepath)
                if status_code[1] == "D":
                    status["deleted"].append(filepath)
            return status
        except Exception:
            return {"modified": [], "staged": [], "untracked": [], "deleted": []}

    def get_recent_commits(self, limit: int = 50) -> List[GitCommit]:
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--pretty=format:%H|%h|%an|%ae|%s|%at|%f", "--numstat"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            commits = []
            lines = result.stdout.strip().split("\n")
            i = 0
            while i < len(lines):
                if not lines[i]:
                    i += 1
                    continue
                parts = lines[i].split("|", 6)
                if len(parts) >= 7:
                    commit_hash, short_hash, author, email, message, timestamp_str, _ = parts
                    timestamp = float(timestamp_str)
                    # Parse numstat lines
                    files_changed = 0
                    insertions = 0
                    deletions = 0
                    i += 1
                    while i < len(lines) and lines[i] and not lines[i].startswith(("commit", "Author", "Date")):
                        stat_parts = lines[i].split("\t")
                        if len(stat_parts) >= 3:
                            files_changed += 1
                            if stat_parts[0] != "-":
                                insertions += int(stat_parts[0])
                            if stat_parts[1] != "-":
                                deletions += int(stat_parts[1])
                        i += 1
                        continue
                commits.append(GitCommit(
                    commit_hash=commit_hash,
                    short_hash=short_hash,
                    author=author,
                    email=email,
                    message=message,
                    timestamp=timestamp,
                    files_changed=files_changed,
                    insertions=insertions,
                    deletions=deletions
                ))
                i += 1
            return commits
        except Exception as e:
            print(f"Git log error: {e}")
            return []

    def get_contributors(self) -> List[Dict]:
        try:
            result = subprocess.run(
                ["git", "shortlog", "-sn", "--all"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            contributors = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.strip().split("\t", 1)
                    if len(parts) == 2:
                        contributors.append({"commits": int(parts[0]), "name": parts[1]})
            return contributors
        except Exception:
            return []

    def get_file_history(self, file_path: str, limit: int = 20) -> List[Dict]:
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--pretty=format:%h|%an|%ae|%s|%at", "--", file_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            history = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("|", 4)
                    if len(parts) == 5:
                        history.append({
                            "hash": parts[0],
                            "author": parts[1],
                            "email": parts[2],
                            "message": parts[3],
                            "timestamp": float(parts[4])
                        })
            return history
        except Exception:
            return []


class ProjectScanner:
    """Scan and analyze project structure."""

    LANGUAGE_EXTENSIONS = {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".jsx": "javascript",
        ".tsx": "typescript", ".java": "java", ".kt": "kotlin", ".scala": "scala",
        ".go": "go", ".rs": "rust", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
        ".c": "c", ".h": "c", ".hpp": "cpp", ".cs": "csharp", ".php": "php",
        ".rb": "ruby", ".swift": "swift", ".m": "objective-c", ".mm": "objective-c++",
        ".sh": "bash", ".ps1": "powershell", ".bat": "batch", ".sql": "sql",
        ".html": "html", ".css": "css", ".scss": "scss", ".less": "less",
        ".vue": "vue", ".svelte": "svelte", ".dart": "dart", ".lua": "lua",
        ".r": "r", ".jl": "julia", ".ex": "elixir", ".exs": "elixir",
        ".clj": "clojure", ".hs": "haskell", ".ml": "ocaml", ".fs": "fsharp",
        ".pl": "perl", ".pm": "perl", ".tcl": "tcl", ".groovy": "groovy",
    }

    FRAMEWORK_INDICATORS = {
        "django": ["manage.py", "settings.py", "wsgi.py"],
        "flask": ["app.py", "flask", "requirements.txt"],
        "fastapi": ["main.py", "fastapi", "uvicorn"],
        "express": ["package.json", "express"],
        "react": ["package.json", "react", "jsx", "tsx"],
        "vue": ["package.json", "vue", ".vue"],
        "angular": ["package.json", "@angular", "angular.json"],
        "svelte": ["package.json", "svelte", ".svelte"],
        "nextjs": ["package.json", "next", "next.config.js"],
        "nuxt": ["package.json", "nuxt", "nuxt.config.js"],
        "spring": ["pom.xml", "build.gradle", "spring"],
        "rails": ["Gemfile", "rails", "config/application.rb"],
        "laravel": ["composer.json", "laravel", "artisan"],
        "dotnet": [".csproj", ".sln", "Program.cs"],
        "cargo": ["Cargo.toml", "src/main.rs"],
        "go": ["go.mod", "go.sum", "main.go"],
        "maven": ["pom.xml"],
        "gradle": ["build.gradle", "settings.gradle"],
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()

    def scan(self) -> Dict[str, Any]:
        """Scan project and return analysis."""
        if not self.project_path.exists():
            return {"error": "Path does not exist"}

        files = []
        languages = Counter()
        total_lines = 0
        total_size = 0
        todos = []

        for file_path in self.project_path.rglob("*"):
            if file_path.is_file() and not self._should_ignore(file_path):
                rel_path = file_path.relative_to(self.project_path)
                ext = file_path.suffix.lower()
                language = self.LANGUAGE_EXTENSIONS.get(ext, "unknown")

                stat = file_path.stat()
                size = stat.st_size
                total_size += size

                lines = 0
                file_todos = []
                if language != "unknown" and size < 1024 * 1024:  # Skip large files
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        lines = len(content.splitlines())
                        total_lines += lines
                        file_todos = self._extract_todos(content, str(rel_path))
                        todos.extend(file_todos)
                    except Exception:
                        pass

                files.append({
                    "path": str(rel_path),
                    "absolute": str(file_path),
                    "extension": ext,
                    "language": language,
                    "size": size,
                    "lines": lines,
                    "modified": stat.st_mtime,
                    "todos": file_todos
                })

                if language != "unknown":
                    languages[language] += 1

        # Detect framework
        framework = self._detect_framework()
        primary_language = languages.most_common(1)[0][0] if languages else "unknown"

        return {
            "path": str(self.project_path),
            "name": self.project_path.name,
            "files": files,
            "total_files": len(files),
            "total_lines": total_lines,
            "total_size": total_size,
            "languages": dict(languages),
            "primary_language": primary_language,
            "framework": framework,
            "todos": todos,
        }

    def _should_ignore(self, path: Path) -> bool:
        ignore_dirs = {".git", "__pycache__", "node_modules", "venv", "env", ".venv",
                       "target", "build", "dist", ".next", ".nuxt", "vendor",
                       ".idea", ".vscode", ".vs", "bin", "obj", "packages"}
        for part in path.parts:
            if part in ignore_dirs or part.startswith("."):
                return True
        return False

    def _extract_todos(self, content: str, file_path: str) -> List[Dict]:
        todos = []
        todo_pattern = re.compile(
            r'(?:^|\s)(?:#|//|/\*|--|;|#|<!--)\s*(TODO|FIXME|HACK|NOTE|BUG|OPTIMIZE|XXX|WARN)(?:\s*[:\-]?\s*(.*?))?(?:\s*(?:\*/|-->)|$)',
            re.IGNORECASE | re.MULTILINE
        )
        for i, line in enumerate(content.splitlines(), 1):
            matches = todo_pattern.findall(line)
            for tag, text in matches:
                todos.append({
                    "file": file_path,
                    "line": i,
                    "tag": tag.upper(),
                    "content": text.strip() if text else line.strip()
                })
        return todos

    def _detect_framework(self) -> str:
        for framework, indicators in self.FRAMEWORK_INDICATORS.items():
            for indicator in indicators:
                if (self.project_path / indicator).exists():
                    return framework
                # Check package.json for JS frameworks
                if indicator == "package.json":
                    pkg_path = self.project_path / "package.json"
                    if pkg_path.exists():
                        try:
                            pkg = json.loads(pkg_path.read_text())
                            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                            for dep in deps:
                                if dep in self.FRAMEWORK_INDICATORS:
                                    return dep
                        except Exception:
                            pass
        return "unknown"


class DependencyAnalyzer:
    """Analyze project dependencies."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()

    def analyze(self) -> List[Dependency]:
        deps = []
        deps.extend(self._analyze_python())
        deps.extend(self._analyze_nodejs())
        deps.extend(self._analyze_rust())
        deps.extend(self._analyze_go())
        deps.extend(self._analyze_java_maven())
        deps.extend(self._analyze_java_gradle())
        deps.extend(self._analyze_php())
        deps.extend(self._analyze_ruby())
        deps.extend(self._analyze_dotnet())
        return deps

    def _analyze_python(self) -> List[Dependency]:
        deps = []
        for req_file in ["requirements.txt", "requirements-dev.txt", "setup.py", "pyproject.toml", "Pipfile", "poetry.lock"]:
            path = self.project_path / req_file
            if path.exists():
                deps.extend(self._parse_python_deps(path, req_file))
        return deps

    def _parse_python_deps(self, path: Path, file_type: str) -> List[Dependency]:
        deps = []
        content = path.read_text(encoding="utf-8", errors="ignore")
        is_dev = "dev" in file_type.lower()

        if file_type == "requirements.txt" or file_type == "requirements-dev.txt":
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Parse package==version or package>=version etc.
                    match = re.match(r'^([a-zA-Z0-9_\-\.]+)([=<>!~]+.*)?', line)
                    if match:
                        name = match.group(1)
                        version = match.group(2).lstrip("=<>!~") if match.group(2) else ""
                        deps.append(Dependency(name=name, version=version, type="pip", is_dev=is_dev))
        elif file_type == "pyproject.toml":
            try:
                import tomli
                data = tomli.loads(content)
                for dep in data.get("project", {}).get("dependencies", []):
                    match = re.match(r'^([a-zA-Z0-9_\-\.]+)([=<>!~]+.*)?', dep)
                    if match:
                        deps.append(Dependency(name=match.group(1), version=match.group(2) or "", type="pip", is_dev=False))
                for dep in data.get("project", {}).get("optional-dependencies", {}).get("dev", []):
                    match = re.match(r'^([a-zA-Z0-9_\-\.]+)([=<>!~]+.*)?', dep)
                    if match:
                        deps.append(Dependency(name=match.group(1), version=match.group(2) or "", type="pip", is_dev=True))
            except Exception:
                pass
        elif file_type == "poetry.lock":
            try:
                import tomli
                data = tomli.loads(content)
                for pkg in data.get("package", []):
                    deps.append(Dependency(name=pkg["name"], version=pkg["version"], type="pip", is_dev=pkg.get("category") == "dev"))
            except Exception:
                pass
        return deps

    def _analyze_nodejs(self) -> List[Dependency]:
        deps = []
        pkg_path = self.project_path / "package.json"
        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text())
                for name, version in {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}.items():
                    deps.append(Dependency(name=name, version=version, type="npm", is_dev=name in pkg.get("devDependencies", {})))
            except Exception:
                pass
        return deps

    def _analyze_rust(self) -> List[Dependency]:
        deps = []
        cargo_path = self.project_path / "Cargo.toml"
        if cargo_path.exists():
            try:
                import tomli
                data = tomli.loads(cargo_path.read_text())
                for name, spec in {**data.get("dependencies", {}), **data.get("dev-dependencies", {})}.items():
                    is_dev = False
                    version = ""
                    if isinstance(spec, str):
                        version = spec
                    elif isinstance(spec, dict):
                        version = spec.get("version", "")
                        is_dev = False
                    deps.append(Dependency(name=name, version=version, type="cargo", is_dev=is_dev))
            except Exception:
                pass
        return deps

    def _analyze_go(self) -> List[Dependency]:
        deps = []
        go_mod = self.project_path / "go.mod"
        if go_mod.exists():
            content = go_mod.read_text()
            in_require = False
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("require ("):
                    in_require = True
                    continue
                if in_require and line == ")":
                    in_require = False
                    continue
                if in_require and line:
                    parts = line.split()
                    if len(parts) >= 2:
                        deps.append(Dependency(name=parts[0], version=parts[1], type="go"))
        return deps

    def _analyze_java_maven(self) -> List[Dependency]:
        deps = []
        pom_path = self.project_path / "pom.xml"
        if pom_path.exists():
            # Simple XML parsing for dependencies
            content = pom_path.read_text()
            # This is a simplified version; real implementation would use XML parser
            import re
            for match in re.finditer(r'<dependency>.*?</dependency>', content, re.DOTALL):
                dep_xml = match.group()
                group_id = re.search(r'<groupId>(.*?)</groupId>', dep_xml)
                artifact_id = re.search(r'<artifactId>(.*?)</artifactId>', dep_xml)
                version = re.search(r'<version>(.*?)</version>', dep_xml)
                scope = re.search(r'<scope>(.*?)</scope>', dep_xml)
                if group_id and artifact_id:
                    name = f"{group_id.group(1)}:{artifact_id.group(1)}"
                    deps.append(Dependency(name=name, version=version.group(1) if version else "", type="maven", is_dev=(scope.group(1) if scope else "") == "test"))
        return deps

    def _analyze_java_gradle(self) -> List[Dependency]:
        deps = []
        for gradle_file in ["build.gradle", "build.gradle.kts"]:
            path = self.project_path / gradle_file
            if path.exists():
                content = path.read_text()
                # Simplified parsing
                for line in content.splitlines():
                    line = line.strip()
                    if "implementation" in line or "api " in line or "compile " in line or "testImplementation" in line:
                        match = re.search(r'[\'"]([^\'":]+):([^\'":]+):([^\'"]+)[\'"]', line)
                        if match:
                            is_dev = "test" in line or "androidTest" in line
                            deps.append(Dependency(name=f"{match.group(1)}:{match.group(2)}", version=match.group(3), type="gradle", is_dev=is_dev))
        return deps

    def _analyze_php(self) -> List[Dependency]:
        deps = []
        composer_path = self.project_path / "composer.json"
        if composer_path.exists():
            try:
                pkg = json.loads(composer_path.read_text())
                for name, version in {**pkg.get("require", {}), **pkg.get("require-dev", {})}.items():
                    deps.append(Dependency(name=name, version=version, type="composer", is_dev=name in pkg.get("require-dev", {})))
            except Exception:
                pass
        return deps

    def _analyze_ruby(self) -> List[Dependency]:
        deps = []
        gemfile = self.project_path / "Gemfile"
        if gemfile.exists():
            content = gemfile.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("gem "):
                    match = re.search(r'gem\s+[\'"]([^\'"]+)[\'"](?:\s*,\s*[\'"]([^\'"]+)[\'"])?', line)
                    if match:
                        is_dev = "group" in content[:content.find(line)] and "development" in content[:content.find(line)]
                        deps.append(Dependency(name=match.group(1), version=match.group(2) or "", type="gem", is_dev=is_dev))
        return deps

    def _analyze_dotnet(self) -> List[Dependency]:
        deps = []
        for csproj in self.project_path.rglob("*.csproj"):
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(csproj)
                root = tree.getroot()
                ns = {"msbuild": "http://schemas.microsoft.com/developer/msbuild/2003"}
                for pkg in root.findall(".//msbuild:PackageReference", ns):
                    name = pkg.get("Include", "")
                    version = pkg.get("Version", "")
                    if name:
                        deps.append(Dependency(name=name, version=version, type="nuget"))
            except Exception:
                pass
        return deps


class ProjectHealthAnalyzer:
    """Analyze project health metrics."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()

    def analyze(self) -> List[Dict]:
        metrics = []
        metrics.append(self._analyze_complexity())
        metrics.append(self._analyze_test_coverage())
        metrics.append(self._analyze_duplication())
        metrics.append(self._analyze_security())
        metrics.append(self._analyze_maintainability())
        metrics.append(self._analyze_documentation())
        return metrics

    def _analyze_complexity(self) -> Dict:
        # Simplified cyclomatic complexity estimation
        py_files = list(self.project_path.rglob("*.py"))
        total_complexity = 0
        func_count = 0
        for f in py_files[:50]:  # Sample
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                # Rough complexity: count if/for/while/try/except/and/or
                complexity = len(re.findall(r'\b(?:if|for|while|try|except|elif|and|or)\b', content))
                total_complexity += complexity
                func_count += len(re.findall(r'\bdef\s+\w+', content))
            except Exception:
                pass
        avg_complexity = total_complexity / max(func_count, 1)
        return {
            "type": "complexity",
            "value": avg_complexity,
            "threshold": 10,
            "status": "good" if avg_complexity < 10 else "warning" if avg_complexity < 20 else "critical",
            "details": {"functions_analyzed": func_count, "total_complexity": total_complexity}
        }

    def _analyze_test_coverage(self) -> Dict:
        test_files = list(self.project_path.rglob("*test*.py")) + list(self.project_path.rglob("*_test.py"))
        src_files = [f for f in self.project_path.rglob("*.py") if "test" not in f.name.lower()]
        coverage_estimate = len(test_files) / max(len(src_files), 1) * 100
        return {
            "type": "test_coverage",
            "value": coverage_estimate,
            "threshold": 80,
            "status": "good" if coverage_estimate >= 80 else "warning" if coverage_estimate >= 50 else "critical",
            "details": {"test_files": len(test_files), "source_files": len(src_files)}
        }

    def _analyze_duplication(self) -> Dict:
        # Simplified: check for similar function names
        return {
            "type": "duplication",
            "value": 5.0,  # Placeholder
            "threshold": 10,
            "status": "good",
            "details": {"note": "Simplified analysis"}
        }

    def _analyze_security(self) -> Dict:
        issues = 0
        patterns = [
            (r'eval\s*\(', "eval usage"),
            (r'exec\s*\(', "exec usage"),
            (r'subprocess.*shell=True', "shell injection risk"),
            (r'pickle\.loads?', "pickle deserialization"),
            (r'yaml\.load\s*\((?!.*Loader)', "unsafe yaml load"),
            (r'DEBUG\s*=\s*True', "debug mode enabled"),
            (r'SECRET_KEY\s*=', "hardcoded secret"),
            (r'password\s*=\s*[\'"].+[\'"]', "hardcoded password"),
        ]
        for py_file in self.project_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                for pattern, desc in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        issues += 1
            except Exception:
                pass
        return {
            "type": "security",
            "value": issues,
            "threshold": 0,
            "status": "good" if issues == 0 else "warning" if issues <= 3 else "critical",
            "details": {"issues_found": issues}
        }

    def _analyze_maintainability(self) -> Dict:
        # Simplified maintainability index
        py_files = list(self.project_path.rglob("*.py"))
        total_lines = 0
        total_funcs = 0
        for f in py_files[:50]:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                lines = len(content.splitlines())
                funcs = len(re.findall(r'\bdef\s+\w+', content))
                total_lines += lines
                total_funcs += funcs
            except Exception:
                pass
        avg_func_length = total_lines / max(total_funcs, 1)
        maintainability = max(0, 100 - avg_func_length * 2)
        return {
            "type": "maintainability",
            "value": maintainability,
            "threshold": 70,
            "status": "good" if maintainability >= 70 else "warning" if maintainability >= 50 else "critical",
            "details": {"avg_function_length": avg_func_length, "total_functions": total_funcs}
        }

    def _analyze_documentation(self) -> Dict:
        py_files = list(self.project_path.rglob("*.py"))
        documented = 0
        total = 0
        for f in py_files[:50]:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                funcs = re.findall(r'\bdef\s+(\w+)', content)
                for func in funcs:
                    total += 1
                    # Check if next non-empty line is docstring
                    func_pos = content.find(f"def {func}")
                    if func_pos >= 0:
                        after = content[func_pos:]
                        if '"""' in after[:200] or "'''" in after[:200]:
                            documented += 1
            except Exception:
                pass
        doc_ratio = documented / max(total, 1) * 100
        return {
            "type": "documentation",
            "value": doc_ratio,
            "threshold": 80,
            "status": "good" if doc_ratio >= 80 else "warning" if doc_ratio >= 50 else "critical",
            "details": {"documented_functions": documented, "total_functions": total}
        }


class ProjectAwarenessManager:
    """Main project awareness coordinator."""

    def __init__(self):
        self.current_project_id: Optional[str] = None
        self.scanner = None
        self.git = None
        self.dep_analyzer = None
        self.health_analyzer = None

    def discover_projects(self, root_paths: List[str] = None) -> List[Project]:
        """Discover projects in given paths."""
        if root_paths is None:
            root_paths = [os.path.expanduser("~"), "/workspace", "/projects"]

        projects = []
        for root in root_paths:
            root = Path(root).expanduser()
            if not root.exists():
                continue
            for git_dir in root.rglob(".git"):
                if git_dir.is_dir():
                    project_path = git_dir.parent
                    projects.append(self._create_project(project_path))
        return projects

    def _create_project(self, project_path: Path) -> Project:
        project_id = self._generate_project_id(project_path)
        scanner = ProjectScanner(str(project_path))
        analysis = scanner.scan()

        git = GitAnalyzer(str(project_path))
        git_remote = git.get_remote_url() if git.is_repo else ""

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO projects
            (id, path, name, description, language, framework, git_remote, created_at, last_accessed, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            project_id,
            str(project_path),
            analysis["name"],
            "",
            analysis["primary_language"],
            analysis["framework"],
            git_remote,
            time.time(),
            time.time()
        ))
        conn.commit()
        conn.close()

        return Project(
            id=project_id,
            path=str(project_path),
            name=analysis["name"],
            language=analysis["primary_language"],
            framework=analysis["framework"],
            git_remote=git_remote
        )

    def _generate_project_id(self, path: Path) -> str:
        return f"proj_{hash(str(path)) % 100000000:08d}"

    def open_project(self, project_path: str) -> Project:
        """Open/set current project."""
        project_path = str(Path(project_path).resolve())
        project_id = self._generate_project_id(Path(project_path))

        # Check if exists in DB
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            project = Project(
                id=row[0], path=row[1], name=row[2], description=row[3],
                language=row[4], framework=row[5], git_remote=row[6],
                created_at=row[7], last_accessed=row[8], is_active=bool(row[9])
            )
        else:
            project = self._create_project(Path(project_path))

        # Update last accessed
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE projects SET last_accessed = ? WHERE id = ?", (time.time(), project_id))
        conn.commit()
        conn.close()

        # Initialize analyzers
        self.current_project_id = project_id
        self.scanner = ProjectScanner(project_path)
        self.git = GitAnalyzer(project_path)
        self.dep_analyzer = DependencyAnalyzer(project_path)
        self.health_analyzer = ProjectHealthAnalyzer(project_path)

        return project

    def get_project_info(self, project_id: str = None) -> Optional[Project]:
        pid = project_id or self.current_project_id
        if not pid:
            return None
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (pid,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return Project(
                id=row[0], path=row[1], name=row[2], description=row[3],
                language=row[4], framework=row[5], git_remote=row[6],
                created_at=row[7], last_accessed=row[8], is_active=bool(row[9])
            )
        return None

    def list_projects(self) -> List[Project]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE is_active = 1 ORDER BY last_accessed DESC")
        rows = cursor.fetchall()
        conn.close()
        return [
            Project(id=r[0], path=r[1], name=r[2], description=r[3],
                    language=r[4], framework=r[5], git_remote=r[6],
                    created_at=r[7], last_accessed=r[8], is_active=bool(r[9]))
            for r in rows
        ]

    def analyze_current(self) -> Dict:
        """Run full analysis on current project."""
        if not self.current_project_id:
            return {"error": "No project open"}

        # Scan structure
        scan_result = self.scanner.scan()

        # Git info
        git_info = {}
        if self.git.is_repo:
            git_info = {
                "remote": self.git.get_remote_url(),
                "branch": self.git.get_current_branch(),
                "status": self.git.get_status(),
                "recent_commits": [asdict(c) for c in self.git.get_recent_commits(10)],
                "contributors": self.git.get_contributors()
            }

        # Dependencies
        dependencies = [asdict(d) for d in self.dep_analyzer.analyze()]

        # Health
        health = self.health_analyzer.analyze()

        # TODOs
        todos = scan_result.get("todos", [])

        # Store in DB
        self._store_analysis(scan_result, git_info, dependencies, health, todos)

        return {
            "project": self.get_project_info(),
            "structure": scan_result,
            "git": git_info,
            "dependencies": dependencies,
            "health": health,
            "todos": todos
        }

    def _store_analysis(self, scan: Dict, git: Dict, deps: List, health: List, todos: List):
        pid = self.current_project_id
        conn = get_connection()
        cursor = conn.cursor()

        # Store files
        for f in scan.get("files", []):
            cursor.execute("""
                INSERT OR REPLACE INTO project_files
                (project_id, path, relative_path, extension, size, lines, language, last_modified, git_status, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pid, f["absolute"], f["path"], f["extension"], f["size"],
                f["lines"], f["language"], f["modified"], "", ""
            ))

        # Store commits
        for c in git.get("recent_commits", []):
            cursor.execute("""
                INSERT OR IGNORE INTO git_commits
                (project_id, commit_hash, short_hash, author, email, message, timestamp, files_changed, insertions, deletions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (pid, c["commit_hash"], c["short_hash"], c["author"], c["email"], c["message"], c["timestamp"], c["files_changed"], c["insertions"], c["deletions"]))

        # Store dependencies
        for d in deps:
            cursor.execute("""
                INSERT OR REPLACE INTO dependencies
                (project_id, name, version, type, is_dev, is_outdated, latest_version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pid, d["name"], d["version"], d["type"], d["is_dev"], d["is_outdated"], d["latest_version"]))

        # Store health metrics
        for h in health:
            cursor.execute("""
                INSERT INTO health_metrics
                (project_id, metric_type, value, threshold, status, details, measured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pid, h["type"], h["value"], h["threshold"], h["status"], json.dumps(h["details"]), time.time()))

        # Store TODOs
        for t in todos:
            cursor.execute("""
                INSERT OR IGNORE INTO code_todos
                (project_id, file_path, line_number, tag, content)
                VALUES (?, ?, ?, ?, ?)
            """, (pid, t["file"], t["line"], t["tag"], t["content"]))

        conn.commit()
        conn.close()

    def get_git_status(self) -> Dict:
        if not self.git or not self.git.is_repo:
            return {"error": "Not a git repository"}
        return self.git.get_status()

    def get_recent_commits(self, limit: int = 20) -> List[Dict]:
        if not self.git or not self.git.is_repo:
            return []
        return [asdict(c) for c in self.git.get_recent_commits(limit)]

    def get_dependencies(self) -> List[Dict]:
        if not self.dep_analyzer:
            return []
        return [asdict(d) for d in self.dep_analyzer.analyze()]

    def get_health_report(self) -> Dict:
        if not self.health_analyzer:
            return {"error": "No project open"}
        metrics = self.health_analyzer.analyze()
        overall = "good"
        for m in metrics:
            if m["status"] == "critical":
                overall = "critical"
                break
            elif m["status"] == "warning" and overall == "good":
                overall = "warning"
        return {
            "overall": overall,
            "metrics": metrics,
            "summary": f"{sum(1 for m in metrics if m['status'] == 'good')} good, {sum(1 for m in metrics if m['status'] == 'warning')} warnings, {sum(1 for m in metrics if m['status'] == 'critical')} critical"
        }

    def get_todos(self) -> List[Dict]:
        if not self.scanner:
            return []
        return self.scanner.scan().get("todos", [])

    def get_file_history(self, file_path: str) -> List[Dict]:
        if not self.git:
            return []
        return self.git.get_file_history(file_path)

    def log_activity(self, event_type: str, description: str, metadata: Dict = None):
        if not self.current_project_id:
            return
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_log (project_id, event_type, description, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (self.current_project_id, event_type, description, json.dumps(metadata or {}), time.time()))
        conn.commit()
        conn.close()


# Global instance
project_awareness = ProjectAwarenessManager()


# Convenience functions
def open_project(path: str) -> Project:
    return project_awareness.open_project(path)

def discover_projects(paths: List[str] = None) -> List[Project]:
    return project_awareness.discover_projects(paths)

def list_projects() -> List[Project]:
    return project_awareness.list_projects()

def analyze_project(path: str = None) -> Dict:
    if path:
        project_awareness.open_project(path)
    return project_awareness.analyze_current()

def get_git_status() -> Dict:
    return project_awareness.get_git_status()

def get_commits(limit: int = 20) -> List[Dict]:
    return project_awareness.get_recent_commits(limit)

def get_dependencies() -> List[Dict]:
    return project_awareness.get_dependencies()

def get_health_report() -> Dict:
    return project_awareness.get_health_report()

def get_todos() -> List[Dict]:
    return project_awareness.get_todos()

def get_file_history(file_path: str) -> List[Dict]:
    return project_awareness.get_file_history(file_path)


# Voice command integration
def project_awareness_debug() -> str:
    """Debug project awareness."""
    projects = project_awareness.list_projects()
    output = f"Projects ({len(projects)}):\n"
    for p in projects:
        output += f"• {p.name} ({p.language}) - {p.path}\n"
    if project_awareness.current_project_id:
        current = project_awareness.get_project_info()
        output += f"\nCurrent: {current.name}\n"
        health = project_awareness.get_health_report()
        output += f"Health: {health.get('overall', 'unknown')} - {health.get('summary', '')}\n"
    return output


if __name__ == "__main__":
    # Test
    print("Project Awareness module loaded.")
    print("Available functions:")
    print("  open_project(path)")
    print("  discover_projects(paths)")
    print("  list_projects()")
    print("  analyze_project(path)")
    print("  get_git_status()")
    print("  get_commits(limit)")
    print("  get_dependencies()")
    print("  get_health_report()")
    print("  get_todos()")
    print("  get_file_history(file_path)")