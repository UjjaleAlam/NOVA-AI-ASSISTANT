"""
Goal Awareness Agent - Phase 32
Goal tracking, decomposition, progress monitoring, alignment checking.
Fully local, no cloud dependencies.
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

DB_DIR = "database"
GA_DB = os.path.join(DB_DIR, "goal_awareness.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_ga_connection():
    import sqlite3
    conn = sqlite3.connect(GA_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_ga_db():
    conn = get_ga_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            goal_type TEXT,
            category TEXT,
            scope TEXT,
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 3,
            target_date REAL,
            target_value REAL,
            target_unit TEXT,
            current_value REAL DEFAULT 0,
            progress REAL DEFAULT 0,
            progress_updated REAL,
            parent_goal_id TEXT,
            depth INTEGER DEFAULT 0,
            estimated_effort REAL,
            actual_effort REAL DEFAULT 0,
            success_criteria TEXT,
            constraints TEXT,
            assumptions TEXT,
            risks TEXT,
            related_goals TEXT,
            related_habits TEXT,
            related_projects TEXT,
            tags TEXT,
            notes TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            completed_at REAL,
            FOREIGN KEY (parent_goal_id) REFERENCES goals(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS milestones (
            id TEXT PRIMARY KEY,
            goal_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            sequence INTEGER NOT NULL,
            target_date REAL,
            target_value REAL,
            target_unit TEXT,
            status TEXT DEFAULT 'pending',
            progress REAL DEFAULT 0,
            dependencies TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            completed_at REAL,
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goal_progress_history (
            id TEXT PRIMARY KEY,
            goal_id TEXT NOT NULL,
            progress REAL NOT NULL,
            current_value REAL,
            notes TEXT,
            recorded_at REAL NOT NULL,
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goal_reviews (
            id TEXT PRIMARY KEY,
            goal_id TEXT NOT NULL,
            review_type TEXT,
            rating INTEGER,
            what_worked TEXT,
            what_didnt TEXT,
            blockers TEXT,
            adjustments TEXT,
            next_actions TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goal_alignments (
            id TEXT PRIMARY KEY,
            goal_a_id TEXT NOT NULL,
            goal_b_id TEXT NOT NULL,
            alignment_type TEXT,
            strength REAL,
            notes TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (goal_a_id) REFERENCES goals(id),
            FOREIGN KEY (goal_b_id) REFERENCES goals(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goal_dependencies (
            id TEXT PRIMARY KEY,
            depends_on_id TEXT NOT NULL,
            dependent_id TEXT NOT NULL,
            dependency_type TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (depends_on_id) REFERENCES goals(id),
            FOREIGN KEY (dependent_id) REFERENCES goals(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goal_time_allocations (
            id TEXT PRIMARY KEY,
            goal_id TEXT NOT NULL,
            date TEXT NOT NULL,
            planned_hours REAL,
            actual_hours REAL DEFAULT 0,
            focus_quality INTEGER,
            notes TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        )
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_goal_date ON goal_time_allocations(goal_id, date)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goal_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            goal_type TEXT,
            default_scope TEXT,
            suggested_milestones TEXT,
            suggested_habits TEXT,
            estimated_duration_days INTEGER,
            tags TEXT,
            is_public BOOLEAN DEFAULT 0,
            created_at REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_ga_db()


class GoalManager:
    def __init__(self):
        pass

    def create_goal(self, title, goal_type="outcome", category="", scope="monthly",
                    target_date=None, target_value=None, target_unit="", priority=3,
                    description="", parent_goal_id=None,
                    success_criteria=None, constraints=None,
                    estimated_effort=None) -> str:
        goal_id = "goal_{:08d}".format(int(time.time() * 1000) % 100000000)
        depth = 0
        if parent_goal_id:
            parent = self.get_goal(parent_goal_id)
            depth = (parent.get("depth", 0) + 1) if parent else 0

        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO goals (id, title, description, goal_type, category, scope,
                              status, priority, target_date, target_value, target_unit,
                              current_value, progress, progress_updated, parent_goal_id, depth,
                              estimated_effort, actual_effort, success_criteria, constraints,
                              assumptions, risks, related_goals, related_habits, related_projects, tags, notes,
                              created_at, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?)
        """, (goal_id, title, description, goal_type, category, scope,
              "active", priority, target_date, target_value, target_unit,
              0, 0, time.time(), parent_goal_id, depth,
              estimated_effort, 0,
              json.dumps(success_criteria or []), json.dumps(constraints or []),
              json.dumps([]), json.dumps([]),
              json.dumps([]), json.dumps([]), json.dumps([]),
              json.dumps([]), "", time.time(), time.time(), None))
        conn.commit()
        conn.close()
        return goal_id

    def get_goal(self, goal_id):
        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return self._row_to_goal(row)
        return None

    def _row_to_goal(self, row):
        return {
            "id": row[0], "title": row[1], "description": row[2],
            "goal_type": row[3], "category": row[4], "scope": row[5],
            "status": row[6], "priority": row[7], "target_date": row[8],
            "target_value": row[9], "target_unit": row[10],
            "current_value": row[11], "progress": row[12],
            "progress_updated": row[13], "parent_goal_id": row[14],
            "depth": row[15], "estimated_effort": row[16],
            "actual_effort": row[17], "success_criteria": json.loads(row[18]) if row[18] else [],
            "constraints": json.loads(row[19]) if row[19] else [],
            "assumptions": json.loads(row[20]) if row[20] else [],
            "risks": json.loads(row[21]) if row[21] else [],
            "related_goals": json.loads(row[22]) if row[22] else [],
            "related_habits": json.loads(row[23]) if row[23] else [],
            "related_projects": json.loads(row[24]) if row[24] else [],
            "tags": json.loads(row[25]) if row[25] else [],
            "notes": row[26], "created_at": row[27], "updated_at": row[28],
            "completed_at": row[29]
        }

    def update_progress(self, goal_id, current_value, notes="") -> bool:
        goal = self.get_goal(goal_id)
        if not goal:
            return False
        target = goal.get("target_value") or 1
        progress = min(100, (current_value / target) * 100) if target > 0 else 0
        status = "completed" if progress >= 100 else goal["status"]

        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE goals SET current_value = ?, progress = ?, status = ?,
                            progress_updated = ?, updated_at = ?, notes = ?
            WHERE id = ?
        """, (current_value, progress, status, time.time(), time.time(),
              goal.get("notes", "") + "\n" + notes if notes else goal.get("notes", ""),
              goal_id))

        hist_id = "gph_{:08d}".format(int(time.time() * 1000) % 100000000)
        cursor.execute("""
            INSERT INTO goal_progress_history (id, goal_id, progress, current_value, notes, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (hist_id, goal_id, progress, current_value, notes, time.time()))

        conn.commit()
        conn.close()

        if goal.get("parent_goal_id"):
            self._update_parent_progress(goal["parent_goal_id"])
        return True

    def _update_parent_progress(self, parent_id):
        children = self.get_child_goals(parent_id)
        if not children:
            return
        total_progress = sum(c.get("progress", 0) for c in children)
        avg_progress = total_progress / len(children)
        self.update_progress(parent_id, avg_progress)

    def get_child_goals(self, parent_id):
        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals WHERE parent_goal_id = ?", (parent_id,))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_goal(r) for r in rows]

    def add_milestone(self, goal_id, title, sequence,
                      target_date=None, target_value=None,
                      target_unit="", description="",
                      dependencies=None) -> str:
        milestone_id = "ms_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO milestones (id, goal_id, title, description, sequence,
                                   target_date, target_value, target_unit,
                                   status, dependencies, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (milestone_id, goal_id, title, description, sequence,
              target_date, target_value, target_unit,
              json.dumps(dependencies or []), time.time(), time.time()))
        conn.commit()
        conn.close()
        return milestone_id

    def get_milestones(self, goal_id):
        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM milestones WHERE goal_id = ? ORDER BY sequence", (goal_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "goal_id": r[1], "title": r[2], "description": r[3],
             "sequence": r[4], "target_date": r[5], "target_value": r[6],
             "target_unit": r[7], "status": r[8], "progress": r[9],
             "dependencies": json.loads(r[10]) if r[10] else []}
            for r in rows
        ]

    def update_milestone(self, milestone_id, status=None,
                         progress=None, current_value=None) -> bool:
        conn = get_ga_connection()
        cursor = conn.cursor()
        updates = []
        params = []
        if status:
            updates.append("status = ?")
            params.append(status)
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        if current_value is not None:
            updates.append("current_value = ?")
            params.append(current_value)
        if updates:
            updates.append("updated_at = ?")
            params.append(time.time())
            params.append(milestone_id)
            cursor.execute("UPDATE milestones SET {} WHERE id = ?".format(", ".join(updates)), params)
            conn.commit()
        conn.close()
        return True

    def list_goals(self, status=None, category=None,
                   scope=None, parent_id=None):
        conn = get_ga_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM goals WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        if parent_id:
            query += " AND parent_goal_id = ?"
            params.append(parent_id)
        query += " ORDER BY priority, target_date, created_at"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_goal(r) for r in rows]

    def get_goal_tree(self, root_id=None):
        if root_id:
            roots = [self.get_goal(root_id)]
        else:
            roots = [g for g in self.list_goals() if not g.get("parent_goal_id")]

        def build_tree(goal):
            children = self.get_child_goals(goal["id"])
            return {
                **goal,
                "children": [build_tree(c) for c in children],
                "milestones": self.get_milestones(goal["id"])
            }

        return {"roots": [build_tree(r) for r in roots]}

    def add_dependency(self, depends_on_id, dependent_id, dep_type="blocks") -> str:
        dep_id = "gd_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO goal_dependencies (id, depends_on_id, dependent_id,
                                          dependency_type, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (dep_id, depends_on_id, dependent_id, dep_type, time.time()))
        conn.commit()
        conn.close()
        return dep_id

    def check_alignment(self, goal_a_id, goal_b_id):
        a = self.get_goal(goal_a_id)
        b = self.get_goal(goal_b_id)
        if not a or not b:
            return {"error": "Goal not found"}

        alignment = "neutral"
        strength = 0.0

        if a["category"] == b["category"]:
            alignment = "supports"
            strength = 0.5

        if a.get("parent_goal_id") == b.get("parent_goal_id") and a["parent_goal_id"]:
            alignment = "supports"
            strength = 0.7

        if a.get("target_date") and b.get("target_date"):
            if abs(a["target_date"] - b["target_date"]) < 86400 * 7:
                if a["category"] != b["category"]:
                    alignment = "conflicts"
                    strength = -0.3

        align_id = "ga_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO goal_alignments (id, goal_a_id, goal_b_id,
                                        alignment_type, strength, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (align_id, goal_a_id, goal_b_id, alignment, strength, "", time.time()))
        conn.commit()
        conn.close()

        return {"alignment": alignment, "strength": strength, "goal_a": a["title"], "goal_b": b["title"]}

    def allocate_time(self, goal_id, date, planned_hours,
                      actual_hours=0, quality=None) -> str:
        alloc_id = "gta_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO goal_time_allocations (id, goal_id, date, planned_hours,
                                              actual_hours, focus_quality, notes,
                                              created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(goal_id, date) DO UPDATE SET
                planned_hours = excluded.planned_hours,
                actual_hours = excluded.actual_hours,
                focus_quality = excluded.focus_quality,
                updated_at = excluded.updated_at
        """, (alloc_id, goal_id, date, planned_hours, actual_hours,
              quality, "", time.time(), time.time()))
        conn.commit()
        conn.close()
        return alloc_id

    def get_time_allocation(self, goal_id, days=7):
        end = datetime.now()
        start = end - timedelta(days=days)

        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, planned_hours, actual_hours, focus_quality
            FROM goal_time_allocations WHERE goal_id = ? AND date >= ?
        """, (goal_id, start.strftime("%Y-%m-%d")))
        rows = cursor.fetchall()
        conn.close()

        total_planned = sum(r[1] for r in rows)
        total_actual = sum(r[2] for r in rows)
        avg_quality = sum(r[3] for r in rows if r[3]) / max(len([r for r in rows if r[3]]), 1)

        return {
            "goal_id": goal_id, "period_days": days,
            "planned_hours": total_planned, "actual_hours": total_actual,
            "efficiency": round(total_actual / total_planned * 100, 1) if total_planned > 0 else 0,
            "avg_focus_quality": round(avg_quality, 1) if avg_quality else 0,
            "days_with_data": len(rows)
        }

    def review_goal(self, goal_id, review_type="weekly",
                    rating=None, what_worked="", what_didnt="",
                    blockers=None, adjustments=None, next_actions=None) -> str:
        review_id = "gr_{:08d}".format(int(time.time() * 1000) % 100000000)
        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO goal_reviews (id, goal_id, review_type, rating,
                                     what_worked, what_didnt, blockers,
                                     adjustments, next_actions, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (review_id, goal_id, review_type, rating,
              what_worked, what_didnt, json.dumps(blockers or []),
              json.dumps(adjustments or []), json.dumps(next_actions or []),
              time.time()))
        conn.commit()
        conn.close()
        return review_id

    def get_reviews(self, goal_id):
        conn = get_ga_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goal_reviews WHERE goal_id = ? ORDER BY created_at DESC", (goal_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "review_type": r[2], "rating": r[3],
             "what_worked": r[4], "what_didnt": r[5],
             "blockers": json.loads(r[6]) if r[6] else [],
             "adjustments": json.loads(r[7]) if r[7] else [],
             "next_actions": json.loads(r[8]) if r[8] else [],
             "created_at": r[9]}
            for r in rows
        ]


class GoalAwarenessEngine:
    def __init__(self, goal_manager):
        self.gm = goal_manager

    def get_active_goals_summary(self):
        active = self.gm.list_goals(status="active")
        by_category = defaultdict(list)
        by_scope = defaultdict(list)
        for g in active:
            by_category[g["category"]].append(g)
            by_scope[g["scope"]].append(g)

        return {
            "total": len(active),
            "by_category": {k: len(v) for k, v in by_category.items()},
            "by_scope": {k: len(v) for k, v in by_scope.items()},
            "avg_progress": sum(g["progress"] for g in active) / max(len(active), 1),
            "overdue": len([g for g in active if g.get("target_date") and g["target_date"] < time.time()]),
            "goals": active
        }

    def get_goal_health(self, goal_id):
        goal = self.gm.get_goal(goal_id)
        if not goal:
            return {"error": "Goal not found"}

        milestones = self.gm.get_milestones(goal_id)
        time_alloc = self.gm.get_time_allocation(goal_id)
        reviews = self.gm.get_reviews(goal_id)

        health = 50
        health += goal["progress"] * 0.3

        if milestones:
            completed = len([m for m in milestones if m["status"] == "completed"])
            health += (completed / len(milestones)) * 20

        if time_alloc["actual_hours"] > 0:
            health += min(20, time_alloc["efficiency"] * 0.2)

        if goal.get("progress_updated"):
            days_since = (time.time() - goal["progress_updated"]) / 86400
            if days_since < 7:
                health += 10
            elif days_since > 30:
                health -= 15

        if goal.get("target_date") and goal["target_date"] < time.time() and goal["progress"] < 100:
            health -= 20

        health = max(0, min(100, health))

        return {
            "goal_id": goal_id,
            "health_score": round(health, 1),
            "status": "healthy" if health > 70 else "at_risk" if health > 40 else "critical",
            "progress": goal["progress"],
            "milestones_total": len(milestones),
            "milestones_completed": len([m for m in milestones if m["status"] == "completed"]),
            "time_efficiency": time_alloc.get("efficiency", 0),
            "last_progress_update": goal.get("progress_updated"),
            "recommendations": self._get_recommendations(goal, milestones, time_alloc)
        }

    def _get_recommendations(self, goal, milestones, time_alloc):
        recs = []
        if goal["progress"] < 10 and goal.get("target_date"):
            days_left = (goal["target_date"] - time.time()) / 86400
            if days_left > 0 and days_left < 14:
                recs.append("Goal progress low with deadline approaching - increase time allocation")
        if milestones and all(m["status"] == "pending" for m in milestones):
            recs.append("No milestones started - break down first milestone into actionable steps")
        if time_alloc.get("actual_hours", 0) == 0:
            recs.append("No time logged this week - schedule dedicated sessions")
        if goal.get("target_date") and goal["target_date"] < time.time() and goal["progress"] < 100:
            recs.append("Goal overdue - reassess timeline or scope")
        return recs

    def find_conflicts(self):
        active = self.gm.list_goals(status="active")
        conflicts = []

        for i, a in enumerate(active):
            for b in active[i+1:]:
                alignment = self.gm.check_alignment(a["id"], b["id"])
                if alignment.get("alignment") == "conflicts":
                    conflicts.append({
                        "goal_a": a["title"], "goal_b": b["title"],
                        "strength": alignment.get("strength", 0),
                        "categories": [a["category"], b["category"]]
                    })
        return conflicts

    def suggest_next_actions(self, goal_id):
        goal = self.gm.get_goal(goal_id)
        if not goal:
            return []

        milestones = self.gm.get_milestones(goal_id)
        pending = [m for m in milestones if m["status"] == "pending"]

        actions = []
        if pending:
            next_ms = pending[0]
            actions.append("Start milestone: " + next_ms["title"])
            if next_ms.get("target_value"):
                actions.append("Target: " + str(next_ms["target_value"]) + " " + next_ms.get("target_unit", ""))

        if goal["progress"] == 0:
            actions.append("Define first concrete action step")

        if goal.get("target_date"):
            days_left = (goal["target_date"] - time.time()) / 86400
            if days_left < 7:
                actions.append("URGENT: Deadline within a week - prioritize this goal")

        return actions

    def get_weekly_priorities(self):
        active = self.gm.list_goals(status="active")

        scored = []
        for g in active:
            score = g["progress"] * 0.1
            if g.get("target_date"):
                days = (g["target_date"] - time.time()) / 86400
                if days > 0:
                    score += 100 / max(days, 1)
            if g["priority"] == 1:
                score += 50
            elif g["priority"] == 2:
                score += 25
            scored.append(dict(g, priority_score=score))

        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored[:5]


gm = GoalManager()
awareness = GoalAwarenessEngine(gm)


def ga_debug():
    conn = get_ga_connection()
    cursor = conn.cursor()
    tables = ["goals", "milestones", "goal_progress_history", "goal_reviews",
              "goal_alignments", "goal_dependencies", "goal_time_allocations", "goal_templates"]
    output = "Goal Awareness Debug:\n"
    for t in tables:
        cursor.execute("SELECT COUNT(*) FROM {}".format(t))
        count = cursor.fetchone()[0]
        output += "  {}: {} records\n".format(t, count)
    conn.close()
    return output


def create_goal(title, goal_type="outcome", category="", scope="monthly",
                target_date=None, target_value=None, target_unit="",
                priority=3, description="", parent_goal_id=None) -> str:
    return gm.create_goal(title, goal_type, category, scope, target_date,
                           target_value, target_unit, priority, description,
                           parent_goal_id)


def get_goal(goal_id):
    return gm.get_goal(goal_id)


def update_goal_progress(goal_id, value, notes="") -> bool:
    return gm.update_progress(goal_id, value, notes)


def list_goals(status=None, category=None, scope=None):
    return gm.list_goals(status, category, scope)


def get_goal_tree(root_id=None):
    return gm.get_goal_tree(root_id)


def add_milestone(goal_id, title, sequence, **kwargs) -> str:
    return gm.add_milestone(goal_id, title, sequence, **kwargs)


def get_milestones(goal_id):
    return gm.get_milestones(goal_id)


def add_goal_dependency(depends_on, dependent, dep_type="blocks") -> str:
    return gm.add_dependency(depends_on, dependent, dep_type)


def check_goal_alignment(goal_a, goal_b):
    return gm.check_alignment(goal_a, goal_b)


def allocate_goal_time(goal_id, date, planned, actual=0, quality=None) -> str:
    return gm.allocate_time(goal_id, date, planned, actual, quality)


def get_goal_time_allocation(goal_id, days=7):
    return gm.get_time_allocation(goal_id, days)


def review_goal(goal_id, review_type="weekly", **kwargs) -> str:
    return gm.review_goal(goal_id, review_type, **kwargs)


def get_goal_reviews(goal_id):
    return gm.get_reviews(goal_id)


def get_active_goals_summary():
    return awareness.get_active_goals_summary()


def get_goal_health(goal_id):
    return awareness.get_goal_health(goal_id)


def find_goal_conflicts():
    return awareness.find_conflicts()


def suggest_goal_actions(goal_id):
    return awareness.suggest_next_actions(goal_id)


def get_weekly_priorities():
    return awareness.get_weekly_priorities()


if __name__ == "__main__":
    print("Goal Awareness Agent loaded.")
    print("Core: GoalManager, GoalAwarenessEngine")